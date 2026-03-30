"""Agentic Testing Agent — self-healing diagnostics, failure analysis, and fix generation.

This agent monitors all FortressFlow agent workflows, detects failures,
diagnoses root causes using LLM, generates code fix suggestions, and
validates repairs. Fixes are NEVER auto-applied — always stored for
human review.
"""

import asyncio
import inspect
import json
import logging
import time
from collections import defaultdict
from datetime import datetime, timedelta, UTC
from typing import Any, Optional
from uuid import UUID, uuid4

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_action_log import AgentActionLog
from app.services.agents.orchestrator import _AGENT_REGISTRY, _ALLOWED_ACTIONS, AgentOrchestrator
from app.services import api_key_service
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)

# ── Rate Limiting ─────────────────────────────────────────────────────────
_request_timestamps: dict[str, list[float]] = {}
_RATE_LIMIT = 10  # requests per minute
_RATE_WINDOW = 60

def _check_rate_limit(key: str) -> None:
    now = time.time()
    timestamps = _request_timestamps.setdefault(key, [])
    timestamps[:] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(timestamps) >= _RATE_LIMIT:
        raise RuntimeError(f"Testing agent rate limit exceeded ({_RATE_LIMIT}/min)")
    timestamps.append(now)

# ── Safe Test Parameters ─────────────────────────────────────────────────
# Read-only params for each agent/action that won't mutate data
_TEST_PARAMS: dict[tuple[str, str], dict] = {
    # Groq
    ("groq", "chat"): {"messages": [{"role": "user", "content": "Say hello in one word"}], "stream": False},
    ("groq", "check_compliance"): {"content": "Check out our dental services at Acme Dental"},
    # OpenAI
    ("openai", "chat"): {"messages": [{"role": "user", "content": "Say hi"}], "stream": False},
    ("openai", "moderate"): {"text": "This is a friendly test message"},
    # Marketing
    ("marketing", "score_leads"): {"leads": [{"name": "Test Lead", "company": "Test Corp", "role": "Dentist"}]},
    ("marketing", "check_compliance"): {"content": "Check out our dental products", "regulations": ["CAN-SPAM"]},
    # Sales
    ("sales", "get_realtime_insights"): {"context": "Q1 pipeline review"},
    ("sales", "schedule_task"): {"task_type": "follow_up", "description": "Test task", "due_date": "2026-04-01"},
}

# Actions that mutate data — skip during diagnostics
_WRITE_ACTIONS = {
    "create_contact", "update_contact", "delete_contact", "bulk_create_contacts", "merge_contacts",
    "create_deal", "update_deal", "create_company", "update_company",
    "create_list", "add_to_list", "remove_from_list",
    "log_email", "log_call", "log_meeting", "create_task", "log_note",
    "send_sms", "bulk_send_sms", "send_mms", "send_whatsapp", "make_call",
    "schedule_message", "send_verification", "buy_phone_number", "release_number",
    "create_contact", "update_contact", "bulk_create_contacts", "delete_contact",
    "create_account", "update_account", "bulk_create_accounts",
    "create_deal", "update_deal", "create_call_record",
    "add_contacts_to_sequence", "schedule_post",
    "create_pipeline", "update_pipeline", "delete_pipeline",
    "create_association", "delete_association", "batch_create_associations",
    "send_transactional_email", "create_campaign_marketing",
    "trigger_workflow", "create_sequence_enrollment",
    "send_message", "create_invoice", "create_payment", "create_subscription",
    "create_webhook_subscription", "delete_webhook_subscription",
    "add_opt_out", "remove_opt_out",
    "submit_bulk_job", "cancel_bulk_job",
    "create_connection_request", "trigger_zapier_action",
    "process_opt_out", "process_opt_in",
    "create_form", "create_property",
    "create_conversation", "add_participant", "send_conversation_message",
    "create_content_template",
    "record_call",
}

# Error category patterns
_ERROR_CATEGORIES = {
    "api_key_missing": ["api key", "api_key", "not configured", "missing key", "no api key", "credentials"],
    "rate_limited": ["rate limit", "too many requests", "429", "throttled"],
    "type_error": ["TypeError", "missing.*argument", "unexpected keyword", "positional argument"],
    "connection_error": ["ConnectionError", "timeout", "connection refused", "unreachable", "ECONNREFUSED"],
    "validation_error": ["ValidationError", "invalid", "required field", "schema"],
    "auth_error": ["401", "403", "unauthorized", "forbidden", "authentication"],
    "not_found": ["404", "not found", "does not exist"],
}


class TestingAgent:
    """Self-healing testing agent for FortressFlow platform diagnostics."""

    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    FAST_MODEL = "llama-3.1-8b-instant"

    def __init__(self):
        self._client = None
        self._api_key = None

    async def _ensure_client(self, db: AsyncSession = None, user_id: UUID = None):
        """Resolve Groq API key and create client."""
        if self._client:
            return
        key = None
        if db and user_id:
            try:
                key = await api_key_service.get_api_key(db, "groq", user_id)
            except Exception:
                pass
        if not key:
            from app.config import settings
            key = getattr(settings, "GROQ_API_KEY", "")
        if not key:
            raise RuntimeError("No Groq API key configured for testing agent")
        self._api_key = key
        from groq import AsyncGroq
        self._client = AsyncGroq(api_key=key)

    async def _llm_call(self, system_prompt: str, user_message: str, db=None, user_id=None, model=None) -> dict:
        """Make an LLM call and return parsed JSON."""
        await self._ensure_client(db, user_id)
        try:
            response = await self._client.chat.completions.create(
                model=model or self.FAST_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                max_tokens=2048,
            )
            return json.loads(response.choices[0].message.content)
        except Exception as e:
            logger.error("TestingAgent LLM call failed: %s", e)
            return {"error": str(e)}

    # ── Skill 1: Health Check ─────────────────────────────────────────────

    async def health_check(self, db: AsyncSession, user_id: UUID) -> dict:
        """Quick status check of all agents — keys configured, action counts."""
        _check_rate_limit(str(user_id))

        agent_statuses = await AgentOrchestrator.get_agent_status(db, user_id)

        results = []
        for status in agent_statuses:
            name = status["agent_name"]
            actions = _ALLOWED_ACTIONS.get(name, set())
            results.append({
                "agent_name": name,
                "configured": status["configured"],
                "has_db_key": status["has_db_key"],
                "has_env_key": status["has_env_key"],
                "total_actions": len(actions),
                "status": "healthy" if status["configured"] else "unconfigured",
            })

        healthy = sum(1 for r in results if r["status"] == "healthy")
        return {
            "total_agents": len(results),
            "healthy": healthy,
            "unconfigured": len(results) - healthy,
            "agents": results,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Skill 2: Run Diagnostic ───────────────────────────────────────────

    async def run_diagnostic(self, db: AsyncSession, user_id: UUID, agent_filter: str = None) -> dict:
        """Scan all agents, try each action with test params, report health."""
        _check_rate_limit(str(user_id))

        from app.models.diagnostic_run import DiagnosticRun

        run = DiagnosticRun(
            user_id=user_id,
            run_type="full_diagnostic",
            status="running",
        )
        db.add(run)
        await db.flush()

        results = []
        passed = 0
        failed = 0
        skipped = 0

        agents_to_test = {agent_filter: _ALLOWED_ACTIONS.get(agent_filter, set())} if agent_filter else _ALLOWED_ACTIONS

        semaphore = asyncio.Semaphore(3)

        async def test_action(agent_name: str, action: str):
            nonlocal passed, failed, skipped

            if action in _WRITE_ACTIONS:
                results.append({"agent": agent_name, "action": action, "status": "skipped", "reason": "write action"})
                skipped += 1
                return

            async with semaphore:
                test_params = _TEST_PARAMS.get((agent_name, action), {})
                try:
                    result = await AgentOrchestrator.dispatch(db, agent_name, action, test_params, user_id)
                    if result["status"] == "success":
                        passed += 1
                        results.append({"agent": agent_name, "action": action, "status": "passed", "latency_ms": result.get("latency_ms")})
                    else:
                        failed += 1
                        results.append({"agent": agent_name, "action": action, "status": "failed", "error": result.get("error", "")[:200]})
                except Exception as e:
                    failed += 1
                    results.append({"agent": agent_name, "action": action, "status": "error", "error": str(e)[:200]})

        tasks = []
        for agent_name, actions in agents_to_test.items():
            for action in sorted(actions):
                tasks.append(test_action(agent_name, action))

        await asyncio.gather(*tasks)

        run.status = "completed"
        run.completed_at = datetime.now(UTC)
        run.summary = {"total": len(results), "passed": passed, "failed": failed, "skipped": skipped}
        run.details = results
        await db.flush()

        return {
            "run_id": str(run.id),
            "status": "completed",
            "summary": run.summary,
            "details": sorted(results, key=lambda r: (r["status"] != "failed", r["agent"], r["action"])),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Skill 3: Analyze Failures ─────────────────────────────────────────

    async def analyze_failures(self, db: AsyncSession, user_id: UUID, hours: int = 24, limit: int = 100) -> dict:
        """Query recent failures from AgentActionLog, group and categorize."""
        _check_rate_limit(str(user_id))

        cutoff = datetime.now(UTC) - timedelta(hours=hours)
        query = (
            select(AgentActionLog)
            .where(
                AgentActionLog.user_id == user_id,
                AgentActionLog.status.in_(["error", "rate_limited"]),
                AgentActionLog.created_at >= cutoff,
            )
            .order_by(AgentActionLog.created_at.desc())
            .limit(limit)
        )
        result = await db.execute(query)
        logs = result.scalars().all()

        # Group by agent/action
        by_agent: dict[str, list] = defaultdict(list)
        by_category: dict[str, int] = defaultdict(int)

        for log in logs:
            key = f"{log.agent_name}.{log.action}"
            error_msg = (log.error_message or "").lower()

            # Categorize error
            category = "unknown"
            for cat, patterns in _ERROR_CATEGORIES.items():
                if any(p in error_msg for p in patterns):
                    category = cat
                    break

            by_agent[key].append({
                "id": str(log.id),
                "error": log.error_message[:200] if log.error_message else "",
                "category": category,
                "latency_ms": log.latency_ms,
                "created_at": log.created_at.isoformat() if log.created_at else "",
            })
            by_category[category] += 1

        # Build summary
        top_failures = sorted(by_agent.items(), key=lambda x: -len(x[1]))[:10]

        return {
            "time_window_hours": hours,
            "total_failures": len(logs),
            "by_category": dict(by_category),
            "top_failing_actions": [
                {"action": k, "count": len(v), "latest_error": v[0]["error"], "category": v[0]["category"]}
                for k, v in top_failures
            ],
            "all_failures": [
                {"action": k, "failures": v}
                for k, v in by_agent.items()
            ],
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Skill 4: Diagnose Issue ───────────────────────────────────────────

    async def diagnose_issue(self, db: AsyncSession, user_id: UUID, agent_name: str, action: str, error_message: str = None) -> dict:
        """Use LLM to diagnose the root cause of a specific failure."""
        _check_rate_limit(str(user_id))

        # Get recent error if not provided
        if not error_message:
            query = (
                select(AgentActionLog)
                .where(
                    AgentActionLog.user_id == user_id,
                    AgentActionLog.agent_name == agent_name,
                    AgentActionLog.action == action,
                    AgentActionLog.status.in_(["error", "rate_limited"]),
                )
                .order_by(AgentActionLog.created_at.desc())
                .limit(1)
            )
            result = await db.execute(query)
            log = result.scalar_one_or_none()
            if log:
                error_message = log.error_message

        if not error_message:
            return {"diagnosis": "No failures found for this agent/action", "severity": "none"}

        # Get method signature for context
        try:
            from app.services.agents.orchestrator import _get_agent_class
            cls = _get_agent_class(agent_name)
            method = getattr(cls, action, None)
            sig = str(inspect.signature(method)) if method else "unknown"
        except Exception:
            sig = "unknown"

        diagnosis = await self._llm_call(
            system_prompt=(
                "You are a senior software engineer diagnosing a Python/FastAPI application failure. "
                "Analyze the error and provide a root cause diagnosis. Return JSON:\n"
                '{"root_cause": "description", "severity": "critical|high|medium|low", '
                '"category": "api_key|type_error|param_mismatch|connection|validation|config|code_bug", '
                '"explanation": "detailed explanation", '
                '"suggested_fix": "what to change", '
                '"fix_type": "config|code_patch|param_fix|api_key|dependency"}'
            ),
            user_message=(
                f"Agent: {agent_name}\n"
                f"Action: {action}\n"
                f"Method signature: {sig}\n"
                f"Error: {error_message}\n"
            ),
            db=db, user_id=user_id,
        )

        # Store as fix suggestion
        from app.models.fix_suggestion import FixSuggestion
        suggestion = FixSuggestion(
            user_id=user_id,
            agent_name=agent_name,
            action=action,
            error_message=error_message,
            diagnosis=diagnosis.get("explanation", diagnosis.get("root_cause", "")),
            suggested_fix=diagnosis.get("suggested_fix", ""),
            fix_type=diagnosis.get("fix_type", "unknown"),
            severity=diagnosis.get("severity", "medium"),
            status="pending",
        )
        db.add(suggestion)
        await db.flush()

        return {
            "suggestion_id": str(suggestion.id),
            "agent_name": agent_name,
            "action": action,
            "diagnosis": diagnosis,
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Skill 5: Generate Fix ─────────────────────────────────────────────

    async def generate_fix(self, db: AsyncSession, user_id: UUID, agent_name: str = None, action: str = None, error_message: str = None) -> dict:
        """Generate a code patch for a diagnosed issue. NEVER auto-applied."""
        _check_rate_limit(str(user_id))

        # Get method source for context
        source_code = ""
        try:
            from app.services.agents.orchestrator import _get_agent_class
            cls = _get_agent_class(agent_name)
            method = getattr(cls, action, None)
            if method:
                source_code = inspect.getsource(method)[:3000]
        except Exception:
            pass

        fix = await self._llm_call(
            system_prompt=(
                "You are a senior Python developer. Generate a fix for the given code issue. "
                "Return JSON with:\n"
                '{"fix_description": "what the fix does", '
                '"code_patch": "the fixed code or unified diff", '
                '"fix_type": "code_patch|config|param_fix", '
                '"confidence": 0.0-1.0, '
                '"side_effects": "potential risks", '
                '"test_command": "how to verify the fix"}'
            ),
            user_message=(
                f"Agent: {agent_name}\nAction: {action}\n"
                f"Error: {error_message}\n\n"
                f"Current source code:\n```python\n{source_code}\n```"
            ),
            db=db, user_id=user_id, model=self.DEFAULT_MODEL,
        )

        return {
            "agent_name": agent_name,
            "action": action,
            "fix": fix,
            "status": "suggestion_only",
            "note": "This fix has NOT been applied. Review and apply manually.",
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Skill 6: Validate Fix ─────────────────────────────────────────────

    async def validate_fix(self, db: AsyncSession, user_id: UUID, agent_name: str, action: str) -> dict:
        """Re-run a previously failed workflow to check if the fix worked."""
        _check_rate_limit(str(user_id))

        test_params = _TEST_PARAMS.get((agent_name, action), {})
        result = await AgentOrchestrator.dispatch(db, agent_name, action, test_params, user_id)

        validated = result["status"] == "success"

        return {
            "agent_name": agent_name,
            "action": action,
            "validated": validated,
            "result_status": result["status"],
            "error": result.get("error"),
            "latency_ms": result.get("latency_ms"),
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Skill 7: Integration Test ─────────────────────────────────────────

    async def run_integration_test(self, db: AsyncSession, user_id: UUID, workflow_name: str = "intelligence") -> dict:
        """Run a predefined multi-agent workflow end-to-end."""
        _check_rate_limit(str(user_id))

        workflows = {
            "intelligence": [
                {"agent_name": "groq", "action": "chat", "params": {"messages": [{"role": "user", "content": "Summarize dental industry trends in 2 sentences"}], "stream": False}},
            ],
            "content_pipeline": [
                {"agent_name": "marketing", "action": "create_social_post", "params": {"topic": "AI in dental practice management", "platform": "linkedin"}},
            ],
            "sales_analysis": [
                {"agent_name": "sales", "action": "get_realtime_insights", "params": {"context": "Q1 pipeline"}},
            ],
        }

        steps = workflows.get(workflow_name, workflows["intelligence"])

        # Add depends_on for chained steps
        for i, step in enumerate(steps):
            step["depends_on"] = i - 1 if i > 0 else None

        result = await AgentOrchestrator.run_workflow(db, steps, user_id)

        return {
            "workflow_name": workflow_name,
            "status": result["status"],
            "steps": result["steps"],
            "timestamp": datetime.now(UTC).isoformat(),
        }

    # ── Skill 8: Generate Test Cases ──────────────────────────────────────

    async def generate_test_cases(self, db: AsyncSession, user_id: UUID, agent_name: str, action: str) -> dict:
        """Use LLM to generate pytest test cases for an agent action."""
        _check_rate_limit(str(user_id))

        # Get method signature
        sig = "unknown"
        docstring = ""
        try:
            from app.services.agents.orchestrator import _get_agent_class
            cls = _get_agent_class(agent_name)
            method = getattr(cls, action, None)
            if method:
                sig = str(inspect.signature(method))
                docstring = inspect.getdoc(method) or ""
        except Exception:
            pass

        result = await self._llm_call(
            system_prompt=(
                "You are a senior Python test engineer. Generate pytest test cases. "
                "Use AsyncMock for db, create realistic test data. Follow this pattern:\n\n"
                "```python\nimport pytest\nfrom unittest.mock import AsyncMock, MagicMock, patch\n\n"
                "class TestAgentAction:\n"
                "    @pytest.mark.asyncio\n"
                "    async def test_success_case(self):\n"
                "        # Arrange, Act, Assert\n"
                "        pass\n```\n\n"
                "Return JSON: {\"test_code\": \"full pytest code\", \"test_count\": N, \"coverage_notes\": \"what's covered\"}"
            ),
            user_message=(
                f"Agent: {agent_name}\nAction: {action}\n"
                f"Method signature: {sig}\n"
                f"Docstring: {docstring}\n"
            ),
            db=db, user_id=user_id, model=self.DEFAULT_MODEL,
        )

        return {
            "agent_name": agent_name,
            "action": action,
            "test_cases": result,
            "timestamp": datetime.now(UTC).isoformat(),
        }
