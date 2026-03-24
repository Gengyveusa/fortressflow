"""Agent orchestrator — central coordinator for dispatching to agents and logging actions."""

import logging
import time
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.database import AsyncSessionLocal
from app.models.agent_action_log import AgentActionLog
from app.services import api_key_service
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)

# Mapping of agent_name -> (module_path, class_name)
_AGENT_REGISTRY: dict[str, tuple[str, str]] = {
    "groq": ("app.services.agents.groq_agent", "GroqAgent"),
    "openai": ("app.services.agents.openai_agent", "OpenAIAgent"),
    "hubspot": ("app.services.agents.hubspot_agent", "HubSpotAgent"),
    "zoominfo": ("app.services.agents.zoominfo_agent", "ZoomInfoAgent"),
    "twilio": ("app.services.agents.twilio_agent", "TwilioAgent"),
}

# Allowed actions per agent (whitelist)
_ALLOWED_ACTIONS: dict[str, set[str]] = {
    "groq": {
        "chat",
        "generate_sequence_content",
        "classify_reply",
        "check_compliance",
        "generate_ab_variants",
        "generate_warmup_email",
        "score_lead_narrative",
        "summarize_analytics",
    },
    "openai": {
        "chat",
        "embed",
        "moderate",
        "extract_structured",
        "analyze_template_performance",
        "suggest_improvements",
    },
    "hubspot": {
        "create_contact", "update_contact", "get_contact", "search_contacts",
        "bulk_create_contacts", "merge_contacts", "delete_contact",
        "create_deal", "update_deal", "move_deal_stage", "get_pipeline", "get_deals",
        "create_company", "update_company", "associate_contact_to_company",
        "create_list", "add_to_list", "remove_from_list",
        "log_email", "log_call", "log_meeting", "create_task", "log_note",
        "create_property", "get_properties",
        "get_contact_activity", "get_pipeline_report",
        "full_sync", "pull_updates",
    },
    "zoominfo": {
        "enrich_person", "search_people", "bulk_enrich_people",
        "enrich_company", "search_companies", "get_company_hierarchy",
        "get_intent_signals", "get_surge_scores",
        "get_scoops", "get_news", "get_tech_stack",
        "verify_email", "verify_phone",
        "bulk_enrich", "get_bulk_status", "get_bulk_results",
    },
    "twilio": {
        "send_sms", "bulk_send_sms", "get_message", "list_messages",
        "make_call", "get_call", "list_calls",
        "send_verification", "check_verification",
        "lookup_phone", "validate_phone",
        "list_phone_numbers", "buy_phone_number", "configure_number", "release_number",
        "create_messaging_service", "add_sender_to_service",
        "get_usage", "get_delivery_stats",
    },
}


def _get_agent_class(agent_name: str):
    """Dynamically import and return the agent class."""
    if agent_name not in _AGENT_REGISTRY:
        raise ValueError(f"Unknown agent: {agent_name}. Available: {', '.join(_AGENT_REGISTRY)}")

    module_path, class_name = _AGENT_REGISTRY[agent_name]
    import importlib
    module = importlib.import_module(module_path)
    return getattr(module, class_name)


def _sanitize_params(params: dict) -> dict:
    """Remove sensitive fields from params before logging."""
    sensitive_keys = {"api_key", "password", "secret", "token", "credentials"}
    return {
        k: "[REDACTED]" if k.lower() in sensitive_keys else v
        for k, v in params.items()
    }


async def _log_action(
    db: AsyncSession,
    user_id: UUID,
    agent_name: str,
    action: str,
    params: dict | None,
    result_summary: dict | None,
    status: str,
    latency_ms: int | None,
    error_message: str | None,
) -> None:
    """Persist an agent action log entry."""
    log_entry = AgentActionLog(
        user_id=user_id,
        agent_name=agent_name,
        action=action,
        params=_sanitize_params(params) if params else None,
        result_summary=result_summary,
        status=status,
        latency_ms=latency_ms,
        error_message=error_message,
    )
    db.add(log_entry)
    await db.flush()


class AgentOrchestrator:
    """Central coordinator — route to agents, load keys, execute, log."""

    @staticmethod
    async def dispatch(
        db: AsyncSession,
        agent_name: str,
        action: str,
        params: dict,
        user_id: UUID,
    ) -> dict:
        """Route to the correct agent, execute the action, and log the result.

        Returns: {"status": "success"|"error", "result": ..., "latency_ms": ...}
        """
        # Validate agent and action
        if agent_name not in _AGENT_REGISTRY:
            return {"status": "error", "result": None, "error": f"Unknown agent: {agent_name}"}

        allowed = _ALLOWED_ACTIONS.get(agent_name, set())
        if action not in allowed:
            return {
                "status": "error",
                "result": None,
                "error": f"Action '{action}' not available for {agent_name}. Available: {', '.join(sorted(allowed))}",
            }

        start = time.time()
        try:
            agent_cls = _get_agent_class(agent_name)
            method = getattr(agent_cls, action, None)
            if method is None:
                raise AttributeError(f"{agent_name} has no method '{action}'")

            # Inject db and user_id into params
            call_params = {**params, "db": db, "user_id": user_id}

            # Inject prompt engine context for LLM agents
            if agent_name in ("groq", "openai") and "prompt_engine_context" not in call_params:
                try:
                    from app.services.agents.prompt_engine import PromptEngine
                    pe = PromptEngine()
                    call_params["prompt_engine_context"] = {
                        "agent_name": agent_name,
                        "action": action,
                        "prompt_engine": pe,
                    }
                except Exception:
                    pass  # Non-critical — agents fall back to hardcoded prompts

            result = await method(**call_params)

            latency_ms = int((time.time() - start) * 1000)

            # Build a summary for logging (truncate large results)
            if isinstance(result, str):
                summary = {"type": "text", "length": len(result), "preview": result[:200]}
            elif isinstance(result, (dict, list)):
                summary = {"type": type(result).__name__, "preview": str(result)[:500]}
            else:
                summary = {"type": type(result).__name__}

            await _log_action(db, user_id, agent_name, action, params, summary, "success", latency_ms, None)

            return {"status": "success", "result": result, "latency_ms": latency_ms}

        except RuntimeError as exc:
            latency_ms = int((time.time() - start) * 1000)
            error_msg = sanitize_error(exc)
            status = "rate_limited" if "rate limit" in str(exc).lower() else "error"
            await _log_action(db, user_id, agent_name, action, params, None, status, latency_ms, error_msg)
            return {"status": status, "result": None, "error": error_msg, "latency_ms": latency_ms}

        except Exception as exc:
            latency_ms = int((time.time() - start) * 1000)
            error_msg = sanitize_error(exc)
            logger.exception("Agent %s.%s failed: %s", agent_name, action, error_msg)
            await _log_action(db, user_id, agent_name, action, params, None, "error", latency_ms, error_msg)
            return {"status": "error", "result": None, "error": error_msg, "latency_ms": latency_ms}

    @staticmethod
    async def run_workflow(
        db: AsyncSession,
        steps: list[dict],
        user_id: UUID,
    ) -> dict:
        """Execute a multi-step workflow across agents.

        Each step: {"agent_name": str, "action": str, "params": dict, "depends_on": int|None}
        If depends_on is set, the result of that step index is injected as "previous_result".
        """
        results: list[dict] = []
        overall_status = "success"

        for i, step in enumerate(steps):
            agent_name = step["agent_name"]
            action = step["action"]
            params = dict(step.get("params", {}))

            # Inject dependency result if specified
            depends_on = step.get("depends_on")
            if depends_on is not None and 0 <= depends_on < len(results):
                prev = results[depends_on]
                if prev["status"] == "success":
                    params["previous_result"] = prev["result"]
                else:
                    results.append({
                        "step_index": i,
                        "agent_name": agent_name,
                        "action": action,
                        "status": "skipped",
                        "result": None,
                        "error": f"Dependency step {depends_on} failed",
                    })
                    overall_status = "partial"
                    continue

            dispatch_result = await AgentOrchestrator.dispatch(db, agent_name, action, params, user_id)
            results.append({
                "step_index": i,
                "agent_name": agent_name,
                "action": action,
                "status": dispatch_result["status"],
                "result": dispatch_result.get("result"),
                "error": dispatch_result.get("error"),
            })

            if dispatch_result["status"] != "success":
                overall_status = "partial"

        return {"status": overall_status, "steps": results}

    @staticmethod
    async def get_agent_status(
        db: AsyncSession,
        user_id: UUID,
    ) -> list[dict]:
        """Return which agents have valid API keys configured for this user."""
        all_agents = {
            "groq": "groq",
            "openai": "openai",
            "hubspot": "hubspot",
            "zoominfo": "zoominfo",
            "twilio": "twilio",
        }

        statuses = []
        for agent_name, service_name in all_agents.items():
            # Check DB key
            from app.models.api_configuration import ApiConfiguration
            from sqlalchemy import select
            result = await db.execute(
                select(ApiConfiguration).where(
                    ApiConfiguration.user_id == user_id,
                    ApiConfiguration.service_name == service_name,
                )
            )
            has_db_key = result.scalar_one_or_none() is not None

            # Check env key
            env_key = await api_key_service.get_api_key(db, service_name)
            has_env_key = bool(env_key) if not has_db_key else False  # Only check env if no DB key

            statuses.append({
                "agent_name": agent_name,
                "configured": has_db_key or bool(env_key),
                "has_db_key": has_db_key,
                "has_env_key": bool(env_key),
            })

        return statuses
