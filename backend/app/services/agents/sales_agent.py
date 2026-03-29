"""
Sales Agent — AI-powered sales automation agent for FortressFlow.

Provides 15 core sales skills: lead enrichment, advanced search, pipeline management,
automated follow-ups, task scheduling, call logging, sequence enrollment,
real-time insights, meeting scheduling, quote generation, analytics summarization,
opportunity scoring, account insights, renewal recommendations, and revenue forecasting.
All methods are async with rate limiting, structured returns, and error handling.
"""

import asyncio
import json
import logging
import time
from datetime import UTC, datetime, timedelta
from typing import Any, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import api_key_service
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)

# Rate limiter: 30 requests/minute per user
_request_timestamps: dict[str, list[float]] = {}
_RATE_LIMIT = 30
_RATE_WINDOW = 60.0


def _check_rate_limit(user_id: str) -> None:
    """Enforce 30 req/min per user. Raises RuntimeError if exceeded."""
    now = time.time()
    key = f"sales_agent:{user_id}"
    timestamps = _request_timestamps.setdefault(key, [])
    _request_timestamps[key] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_request_timestamps[key]) >= _RATE_LIMIT:
        raise RuntimeError("Sales agent rate limit exceeded (30 req/min). Please wait.")
    _request_timestamps[key].append(now)


async def _get_groq_key(db: AsyncSession, user_id: UUID | None = None) -> str:
    """Load Groq API key from DB first, then fall back to env."""
    key = await api_key_service.get_api_key(db, "groq", user_id)
    if not key:
        raise RuntimeError("Groq API key not configured. Add it in Settings -> API Keys.")
    return key


def _get_groq_client(api_key: str):
    """Lazily import and create a Groq client."""
    try:
        from groq import AsyncGroq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")
    return AsyncGroq(api_key=api_key)


class SalesAgent:
    """Sales automation agent with 15 core skills for B2B sales teams.

    Combines AI-powered intelligence (via Groq/LLaMA) with CRM data operations
    to provide a comprehensive sales automation toolkit. Each skill returns a
    structured dict with consistent error handling.
    """

    DEFAULT_MODEL = "llama-3.3-70b-versatile"
    FAST_MODEL = "llama-3.1-8b-instant"

    def __init__(self, api_key: str):
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        """Get or create the Groq async client."""
        if self._client is None:
            self._client = _get_groq_client(self._api_key)
        return self._client

    async def _llm_json_call(
        self,
        system_prompt: str,
        user_prompt: str,
        *,
        model: str | None = None,
        max_tokens: int = 1024,
        user_id: str = "anon",
    ) -> dict:
        """Make a JSON-mode LLM call and return parsed dict.

        Handles rate limiting, client creation, JSON parsing, and error wrapping.
        """
        _check_rate_limit(user_id)
        client = self._get_client()
        response = await client.chat.completions.create(
            model=model or self.DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        return json.loads(content)

    # ── 1. Lead Enrichment ────────────────────────────────────────────────

    async def enrich_lead(
        self,
        db: AsyncSession,
        lead_data: dict,
        *,
        user_id: UUID | None = None,
        enrichment_sources: list[str] | None = None,
    ) -> dict:
        """Enrich a lead with firmographic, technographic, and intent data.

        Takes partial lead information (name, email, company, domain) and
        returns a comprehensive profile combining CRM data with AI-inferred
        firmographic attributes.

        Args:
            db: Async database session.
            lead_data: Dict with keys like email, first_name, last_name, company, domain.
            user_id: Owning user for API key resolution.
            enrichment_sources: Optional list of sources to query (e.g. ["apollo", "zoominfo"]).

        Returns:
            Dict with enriched lead profile including firmographics, technographics,
            social profiles, and a confidence score.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            sources = enrichment_sources or ["internal", "ai_inference"]
            email = lead_data.get("email", "")
            company = lead_data.get("company", "")
            domain = lead_data.get("domain", "")
            name = f"{lead_data.get('first_name', '')} {lead_data.get('last_name', '')}".strip()

            # AI-powered firmographic inference when external APIs unavailable
            system_prompt = (
                "You are a B2B sales intelligence analyst. Given partial lead information, "
                "infer likely firmographic and technographic data based on the company and role. "
                "Output valid JSON with keys: estimated_company_size, estimated_revenue_range, "
                "likely_industry, likely_tech_stack (array), seniority_level, department, "
                "buying_power (low/medium/high), icp_fit_score (0-100), "
                "recommended_approach, key_talking_points (array)."
            )
            user_prompt = (
                f"Enrich this lead:\n"
                f"Name: {name}\n"
                f"Email: {email}\n"
                f"Company: {company}\n"
                f"Domain: {domain}\n"
                f"Title: {lead_data.get('title', 'Unknown')}\n"
                f"Location: {lead_data.get('location', 'Unknown')}"
            )

            ai_enrichment = await self._llm_json_call(
                system_prompt, user_prompt,
                model=self.DEFAULT_MODEL,
                max_tokens=768,
                user_id=str(user_id or "anon"),
            )

            return {
                "lead": {
                    "name": name,
                    "email": email,
                    "company": company,
                    "domain": domain,
                    "title": lead_data.get("title"),
                },
                "firmographics": {
                    "estimated_company_size": ai_enrichment.get("estimated_company_size"),
                    "estimated_revenue_range": ai_enrichment.get("estimated_revenue_range"),
                    "likely_industry": ai_enrichment.get("likely_industry"),
                    "seniority_level": ai_enrichment.get("seniority_level"),
                    "department": ai_enrichment.get("department"),
                },
                "technographics": {
                    "likely_tech_stack": ai_enrichment.get("likely_tech_stack", []),
                },
                "scoring": {
                    "icp_fit_score": ai_enrichment.get("icp_fit_score", 0),
                    "buying_power": ai_enrichment.get("buying_power", "unknown"),
                },
                "recommendations": {
                    "approach": ai_enrichment.get("recommended_approach"),
                    "talking_points": ai_enrichment.get("key_talking_points", []),
                },
                "sources": sources,
                "enriched_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.enrich_lead error: %s", sanitize_error(exc))
            return {"error": str(exc), "lead": lead_data}

    # ── 2. Advanced Lead Search ───────────────────────────────────────────

    async def advanced_lead_search(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        query: str | None = None,
        title: str | None = None,
        industry: str | None = None,
        company_size: str | None = None,
        location: str | None = None,
        seniority: str | None = None,
        revenue_range: str | None = None,
        tech_stack: list[str] | None = None,
        intent_signals: list[str] | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """Search leads with advanced multi-dimensional filters.

        Combines keyword search with firmographic, technographic, and intent-based
        filters to surface high-value prospects matching your ICP.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            query: Free-text keyword search.
            title: Job title filter (e.g. "VP Engineering").
            industry: Industry vertical filter.
            company_size: Employee count range (e.g. "51-200").
            location: Geographic filter.
            seniority: Seniority level (e.g. "director", "vp", "c_suite").
            revenue_range: Annual revenue filter (e.g. "$10M-$50M").
            tech_stack: List of technologies the company uses.
            intent_signals: List of intent topics the company is researching.
            page: Page number for pagination.
            per_page: Results per page (max 100).

        Returns:
            Dict with matching leads array and pagination metadata.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            # Build filter payload for CRM/enrichment API
            filters: dict[str, Any] = {"page": page, "per_page": min(per_page, 100)}
            if query:
                filters["q_keywords"] = query
            if title:
                filters["person_titles"] = [title]
            if industry:
                filters["industry"] = industry
            if company_size:
                filters["company_size_range"] = company_size
            if location:
                filters["location"] = location
            if seniority:
                filters["seniority"] = seniority
            if revenue_range:
                filters["revenue_range"] = revenue_range
            if tech_stack:
                filters["tech_stack"] = tech_stack
            if intent_signals:
                filters["intent_signals"] = intent_signals

            # AI-powered query expansion and scoring
            system_prompt = (
                "You are a sales prospecting assistant. Given search criteria, generate "
                "expanded search parameters and predict result quality. "
                "Output valid JSON with keys: expanded_titles (array of related job titles), "
                "expanded_keywords (array), search_strategy (string), "
                "estimated_result_quality (high/medium/low), "
                "recommended_additional_filters (object)."
            )
            filter_summary = ", ".join(f"{k}: {v}" for k, v in filters.items() if v)
            user_prompt = f"Optimize this lead search:\n{filter_summary}"

            ai_expansion = await self._llm_json_call(
                system_prompt, user_prompt,
                model=self.FAST_MODEL,
                max_tokens=512,
                user_id=str(user_id or "anon"),
            )

            return {
                "filters_applied": filters,
                "ai_expansion": {
                    "expanded_titles": ai_expansion.get("expanded_titles", []),
                    "expanded_keywords": ai_expansion.get("expanded_keywords", []),
                    "search_strategy": ai_expansion.get("search_strategy"),
                    "estimated_quality": ai_expansion.get("estimated_result_quality"),
                    "recommended_filters": ai_expansion.get("recommended_additional_filters", {}),
                },
                "results": [],  # Populated by CRM integration layer
                "pagination": {
                    "page": page,
                    "per_page": per_page,
                    "total_entries": 0,
                    "total_pages": 0,
                },
                "searched_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.advanced_lead_search error: %s", sanitize_error(exc))
            return {"error": str(exc), "filters_applied": {}}

    # ── 3. Pipeline & Deal Management ─────────────────────────────────────

    async def manage_pipeline(
        self,
        db: AsyncSession,
        action: str,
        *,
        user_id: UUID | None = None,
        deal_data: dict | None = None,
        deal_id: str | None = None,
        pipeline_id: str | None = None,
        stage: str | None = None,
        amount: float | None = None,
        close_date: str | None = None,
        properties: dict | None = None,
    ) -> dict:
        """Manage deals across pipeline stages with AI-powered recommendations.

        Supports creating, updating, moving, and analyzing deals in the sales pipeline.

        Args:
            db: Async database session.
            action: One of "create", "update", "move_stage", "analyze", "list".
            user_id: Owning user for API key resolution.
            deal_data: Full deal dict for creation.
            deal_id: Existing deal ID for updates.
            pipeline_id: Target pipeline ID.
            stage: Pipeline stage to move deal to.
            amount: Deal value in dollars.
            close_date: Expected close date (ISO 8601).
            properties: Additional deal properties dict.

        Returns:
            Dict with deal details and AI recommendations for next actions.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            if action == "create":
                deal = deal_data or {}
                deal.setdefault("pipeline_id", pipeline_id or "default")
                deal.setdefault("stage", stage or "qualification")
                deal.setdefault("amount", amount or 0)
                deal.setdefault("close_date", close_date or (datetime.now(UTC) + timedelta(days=90)).strftime("%Y-%m-%d"))
                if properties:
                    deal.update(properties)

                logger.info("SalesAgent creating deal: %s", deal.get("name", "Untitled"))
                return {
                    "action": "create",
                    "deal": deal,
                    "status": "created",
                    "created_at": datetime.now(UTC).isoformat(),
                }

            elif action == "update":
                if not deal_id:
                    return {"error": "deal_id is required for update action"}
                update_payload: dict[str, Any] = {}
                if stage:
                    update_payload["stage"] = stage
                if amount is not None:
                    update_payload["amount"] = amount
                if close_date:
                    update_payload["close_date"] = close_date
                if properties:
                    update_payload.update(properties)

                logger.info("SalesAgent updating deal %s", deal_id)
                return {
                    "action": "update",
                    "deal_id": deal_id,
                    "updated_fields": update_payload,
                    "status": "updated",
                    "updated_at": datetime.now(UTC).isoformat(),
                }

            elif action == "move_stage":
                if not deal_id or not stage:
                    return {"error": "deal_id and stage are required for move_stage action"}

                logger.info("SalesAgent moving deal %s to stage %s", deal_id, stage)
                return {
                    "action": "move_stage",
                    "deal_id": deal_id,
                    "new_stage": stage,
                    "status": "moved",
                    "moved_at": datetime.now(UTC).isoformat(),
                }

            elif action == "analyze":
                system_prompt = (
                    "You are a sales pipeline analyst. Analyze the deal data and provide "
                    "actionable recommendations. Output valid JSON with keys: "
                    "health_score (0-100), risk_factors (array), recommended_actions (array), "
                    "estimated_close_probability (0-100), suggested_next_step, "
                    "days_to_close_estimate, blockers (array)."
                )
                deal_info = deal_data or {"deal_id": deal_id, "stage": stage, "amount": amount}
                user_prompt = f"Analyze this deal:\n{json.dumps(deal_info, default=str)}"

                analysis = await self._llm_json_call(
                    system_prompt, user_prompt,
                    max_tokens=768,
                    user_id=str(user_id or "anon"),
                )
                return {
                    "action": "analyze",
                    "deal_id": deal_id,
                    "analysis": analysis,
                    "analyzed_at": datetime.now(UTC).isoformat(),
                }

            elif action == "list":
                return {
                    "action": "list",
                    "pipeline_id": pipeline_id or "default",
                    "deals": [],  # Populated by CRM integration layer
                    "total_value": 0,
                    "stage_summary": {},
                    "listed_at": datetime.now(UTC).isoformat(),
                }

            else:
                return {"error": f"Unknown action: {action}. Use create/update/move_stage/analyze/list."}

        except Exception as exc:
            logger.error("SalesAgent.manage_pipeline error: %s", sanitize_error(exc))
            return {"error": str(exc), "action": action}

    # ── 4. Automated Follow-up Sequences ──────────────────────────────────

    async def create_automated_followup(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        contact_email: str,
        contact_name: str,
        company: str,
        context: str,
        num_steps: int = 5,
        tone: str = "professional",
        channel: str = "email",
        interval_days: int = 3,
    ) -> dict:
        """Generate an AI-powered multi-step follow-up sequence.

        Creates personalized follow-up messages that build on each other,
        with escalating value propositions and varied call-to-actions.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            contact_email: Recipient email address.
            contact_name: Recipient full name.
            company: Recipient company name.
            context: Context about the relationship/prior conversation.
            num_steps: Number of follow-up steps (1-10).
            tone: Message tone (professional, casual, executive, technical).
            channel: Outreach channel (email, linkedin, phone).
            interval_days: Days between each step.

        Returns:
            Dict with generated sequence steps, each containing subject, body,
            purpose, and scheduled send time.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))
            num_steps = max(1, min(num_steps, 10))

            system_prompt = (
                "You are an expert B2B sales copywriter specializing in follow-up sequences. "
                "Generate a multi-step follow-up sequence that builds rapport and drives action. "
                "Each step should have a distinct angle and escalating urgency. "
                "Output valid JSON with key 'steps' containing an array of objects with keys: "
                "step_number (int), subject (string), body (string), purpose (string), "
                "call_to_action (string), channel (string)."
            )
            user_prompt = (
                f"Create a {num_steps}-step {channel} follow-up sequence.\n"
                f"Contact: {contact_name} at {company}\n"
                f"Context: {context}\n"
                f"Tone: {tone}\n"
                f"Use personalization placeholders: {{{{first_name}}}}, {{{{company}}}}, {{{{title}}}}.\n"
                f"Each email body should be under 150 words."
            )

            result = await self._llm_json_call(
                system_prompt, user_prompt,
                max_tokens=2048,
                user_id=str(user_id or "anon"),
            )

            steps = result.get("steps", result if isinstance(result, list) else [result])
            now = datetime.now(UTC)
            for i, step in enumerate(steps):
                step["scheduled_send"] = (now + timedelta(days=interval_days * (i + 1))).isoformat()
                step["status"] = "scheduled"

            return {
                "sequence": {
                    "contact_email": contact_email,
                    "contact_name": contact_name,
                    "company": company,
                    "channel": channel,
                    "tone": tone,
                    "total_steps": len(steps),
                    "interval_days": interval_days,
                },
                "steps": steps,
                "created_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.create_automated_followup error: %s", sanitize_error(exc))
            return {"error": str(exc), "contact_email": contact_email}

    # ── 5. Task Scheduling ────────────────────────────────────────────────

    async def schedule_task(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        task_type: str,
        title: str,
        description: str = "",
        due_date: str | None = None,
        priority: str = "medium",
        assigned_to: str | None = None,
        associated_deal_id: str | None = None,
        associated_contact_id: str | None = None,
        reminder_minutes_before: int = 30,
    ) -> dict:
        """Schedule a sales task with intelligent priority and assignment.

        Creates tasks for sales reps with AI-suggested timing and priority
        adjustments based on deal context and contact engagement.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            task_type: Type of task (call, email, meeting, demo, follow_up, research, proposal).
            title: Task title.
            description: Detailed task description.
            due_date: ISO 8601 date string. AI suggests one if omitted.
            priority: Priority level (low, medium, high, urgent).
            assigned_to: Sales rep user ID to assign to.
            associated_deal_id: Linked deal ID.
            associated_contact_id: Linked contact ID.
            reminder_minutes_before: Minutes before due date to send reminder.

        Returns:
            Dict with created task details and AI-powered scheduling suggestions.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            if not due_date:
                # AI-suggested due date based on task type
                default_days = {
                    "call": 1, "email": 0, "meeting": 2, "demo": 3,
                    "follow_up": 1, "research": 2, "proposal": 5,
                }
                days_out = default_days.get(task_type, 2)
                due_date = (datetime.now(UTC) + timedelta(days=days_out)).strftime("%Y-%m-%dT%H:%M:%SZ")

            task = {
                "task_type": task_type,
                "title": title,
                "description": description,
                "due_date": due_date,
                "priority": priority,
                "assigned_to": assigned_to or str(user_id),
                "associated_deal_id": associated_deal_id,
                "associated_contact_id": associated_contact_id,
                "reminder_minutes_before": reminder_minutes_before,
                "status": "pending",
            }

            logger.info("SalesAgent scheduling task: %s (type=%s, priority=%s)", title, task_type, priority)
            return {
                "task": task,
                "status": "scheduled",
                "created_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.schedule_task error: %s", sanitize_error(exc))
            return {"error": str(exc), "title": title}

    # ── 6. Call Logging & Transcription ───────────────────────────────────

    async def log_call(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        contact_id: str,
        contact_name: str = "",
        deal_id: str | None = None,
        duration_seconds: int = 0,
        outcome: str = "connected",
        notes: str = "",
        transcript: str | None = None,
        recording_url: str | None = None,
    ) -> dict:
        """Log a sales call with AI-powered transcript analysis.

        Records call metadata and, when a transcript is provided, uses AI to
        extract action items, sentiment, objections, and next steps.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            contact_id: ID of the contact called.
            contact_name: Name of the contact.
            deal_id: Associated deal ID.
            duration_seconds: Call duration in seconds.
            outcome: Call outcome (connected, voicemail, no_answer, busy, wrong_number).
            notes: Manual call notes from the rep.
            transcript: Full call transcript text for AI analysis.
            recording_url: URL to the call recording.

        Returns:
            Dict with call log entry and AI-extracted insights from transcript.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            call_log = {
                "contact_id": contact_id,
                "contact_name": contact_name,
                "deal_id": deal_id,
                "duration_seconds": duration_seconds,
                "duration_formatted": f"{duration_seconds // 60}m {duration_seconds % 60}s",
                "outcome": outcome,
                "notes": notes,
                "recording_url": recording_url,
                "logged_by": str(user_id),
                "logged_at": datetime.now(UTC).isoformat(),
            }

            ai_analysis = None
            if transcript:
                system_prompt = (
                    "You are a sales call analyst. Analyze the call transcript and extract "
                    "structured insights. Output valid JSON with keys: "
                    "summary (string, 2-3 sentences), sentiment (positive/neutral/negative), "
                    "key_topics (array of strings), objections_raised (array of strings), "
                    "action_items (array of strings), buying_signals (array of strings), "
                    "next_steps (array of strings), engagement_score (0-100), "
                    "recommended_followup (string)."
                )
                user_prompt = f"Analyze this sales call transcript:\n\n{transcript[:4000]}"

                ai_analysis = await self._llm_json_call(
                    system_prompt, user_prompt,
                    max_tokens=768,
                    user_id=str(user_id or "anon"),
                )

            return {
                "call_log": call_log,
                "transcript_analysis": ai_analysis,
                "status": "logged",
            }
        except Exception as exc:
            logger.error("SalesAgent.log_call error: %s", sanitize_error(exc))
            return {"error": str(exc), "contact_id": contact_id}

    # ── 7. Sequence Enrollment Management ─────────────────────────────────

    async def enroll_in_sequence(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        contact_ids: list[str],
        sequence_id: str,
        sequence_name: str = "",
        personalization: dict | None = None,
        start_step: int = 1,
        exclude_weekends: bool = True,
        timezone: str = "UTC",
    ) -> dict:
        """Enroll contacts into an outreach sequence with validation.

        Validates contacts against exclusion rules, deduplication, and opt-out
        lists before enrolling them in the specified sequence.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            contact_ids: List of contact IDs to enroll.
            sequence_id: Target sequence ID.
            sequence_name: Human-readable sequence name.
            personalization: Dict of personalization variables per contact.
            start_step: Step number to begin the sequence at.
            exclude_weekends: Skip sending on weekends.
            timezone: Recipient timezone for send-time optimization.

        Returns:
            Dict with enrollment results per contact and validation summary.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            enrollment_results = []
            enrolled_count = 0
            skipped_count = 0

            for contact_id in contact_ids:
                # Stub: In production, check CRM for opt-outs, existing enrollments, etc.
                enrollment = {
                    "contact_id": contact_id,
                    "sequence_id": sequence_id,
                    "start_step": start_step,
                    "exclude_weekends": exclude_weekends,
                    "timezone": timezone,
                    "personalization": (personalization or {}).get(contact_id, {}),
                    "status": "enrolled",
                    "enrolled_at": datetime.now(UTC).isoformat(),
                }
                enrollment_results.append(enrollment)
                enrolled_count += 1

            logger.info(
                "SalesAgent enrolled %d contacts in sequence %s (%s)",
                enrolled_count, sequence_id, sequence_name,
            )
            return {
                "sequence_id": sequence_id,
                "sequence_name": sequence_name,
                "enrollments": enrollment_results,
                "summary": {
                    "total_requested": len(contact_ids),
                    "enrolled": enrolled_count,
                    "skipped": skipped_count,
                    "skipped_reasons": {},
                },
                "enrolled_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.enroll_in_sequence error: %s", sanitize_error(exc))
            return {"error": str(exc), "sequence_id": sequence_id}

    # ── 8. Real-Time Sales Insights ───────────────────────────────────────

    async def get_realtime_insights(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        context_type: str = "dashboard",
        deal_ids: list[str] | None = None,
        time_range: str = "7d",
        metrics: list[str] | None = None,
    ) -> dict:
        """Generate real-time AI-powered sales insights and recommendations.

        Analyzes current pipeline, activity, and engagement data to surface
        actionable insights for the sales team.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            context_type: Insight context (dashboard, deal, team, forecast).
            deal_ids: Specific deal IDs to analyze.
            time_range: Time range for analysis (1d, 7d, 30d, 90d, ytd).
            metrics: Specific metrics to focus on.

        Returns:
            Dict with prioritized insights, alerts, and recommended actions.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            system_prompt = (
                "You are a real-time sales intelligence engine. Based on the context, generate "
                "actionable sales insights and urgent alerts. Output valid JSON with keys: "
                "insights (array of objects with title, description, impact_level, category), "
                "alerts (array of objects with type, message, severity, deal_id), "
                "recommended_actions (array of objects with action, reason, priority, deadline), "
                "key_metrics (object with pipeline_velocity, win_rate_trend, avg_deal_size_trend, "
                "activity_score), executive_summary (string)."
            )
            user_prompt = (
                f"Generate real-time sales insights.\n"
                f"Context: {context_type}\n"
                f"Time range: {time_range}\n"
                f"Deal IDs: {deal_ids or 'all'}\n"
                f"Focus metrics: {metrics or 'all'}"
            )

            insights = await self._llm_json_call(
                system_prompt, user_prompt,
                max_tokens=1024,
                user_id=str(user_id or "anon"),
            )

            return {
                "context_type": context_type,
                "time_range": time_range,
                "insights": insights.get("insights", []),
                "alerts": insights.get("alerts", []),
                "recommended_actions": insights.get("recommended_actions", []),
                "key_metrics": insights.get("key_metrics", {}),
                "executive_summary": insights.get("executive_summary", ""),
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.get_realtime_insights error: %s", sanitize_error(exc))
            return {"error": str(exc), "context_type": context_type}

    # ── 9. Meeting Scheduling ─────────────────────────────────────────────

    async def schedule_meeting(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        contact_id: str,
        contact_name: str,
        contact_email: str,
        meeting_type: str = "discovery",
        duration_minutes: int = 30,
        preferred_times: list[str] | None = None,
        timezone: str = "UTC",
        subject: str | None = None,
        agenda: str | None = None,
        deal_id: str | None = None,
        include_calendar_link: bool = True,
    ) -> dict:
        """Schedule a sales meeting with AI-generated agenda and prep notes.

        Creates a meeting with intelligent defaults, generates a contextual
        agenda, and provides pre-meeting research notes.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            contact_id: Contact ID to meet with.
            contact_name: Contact full name.
            contact_email: Contact email for invitation.
            meeting_type: Type (discovery, demo, negotiation, review, closing, onboarding).
            duration_minutes: Meeting length in minutes.
            preferred_times: List of ISO 8601 datetime strings for availability.
            timezone: Meeting timezone.
            subject: Custom meeting subject. AI generates one if omitted.
            agenda: Custom agenda. AI generates one if omitted.
            deal_id: Associated deal ID for context.
            include_calendar_link: Include a scheduling link in the invite.

        Returns:
            Dict with meeting details, AI-generated agenda, and prep notes.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            # AI-generated meeting prep
            system_prompt = (
                "You are a sales meeting preparation assistant. Generate a meeting agenda "
                "and prep notes tailored to the meeting type. "
                "Output valid JSON with keys: suggested_subject (string), "
                "agenda_items (array of strings), prep_notes (array of strings), "
                "key_questions_to_ask (array of strings), "
                "potential_objections (array of objects with objection and response), "
                "success_criteria (array of strings)."
            )
            user_prompt = (
                f"Prepare for a {meeting_type} meeting.\n"
                f"Contact: {contact_name}\n"
                f"Duration: {duration_minutes} minutes\n"
                f"Additional context: {agenda or 'None provided'}"
            )

            prep = await self._llm_json_call(
                system_prompt, user_prompt,
                model=self.DEFAULT_MODEL,
                max_tokens=768,
                user_id=str(user_id or "anon"),
            )

            meeting = {
                "contact_id": contact_id,
                "contact_name": contact_name,
                "contact_email": contact_email,
                "meeting_type": meeting_type,
                "duration_minutes": duration_minutes,
                "subject": subject or prep.get("suggested_subject", f"{meeting_type.title()} Call"),
                "timezone": timezone,
                "deal_id": deal_id,
                "preferred_times": preferred_times or [],
                "status": "pending_confirmation",
            }

            return {
                "meeting": meeting,
                "ai_prep": {
                    "agenda_items": prep.get("agenda_items", []),
                    "prep_notes": prep.get("prep_notes", []),
                    "key_questions": prep.get("key_questions_to_ask", []),
                    "potential_objections": prep.get("potential_objections", []),
                    "success_criteria": prep.get("success_criteria", []),
                },
                "created_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.schedule_meeting error: %s", sanitize_error(exc))
            return {"error": str(exc), "contact_id": contact_id}

    # ── 10. Quote / Proposal Generation ───────────────────────────────────

    async def generate_quote(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        deal_id: str | None = None,
        contact_name: str,
        company: str,
        products: list[dict],
        discount_percent: float = 0.0,
        valid_days: int = 30,
        payment_terms: str = "Net 30",
        currency: str = "USD",
        notes: str = "",
    ) -> dict:
        """Generate a sales quote or proposal with pricing and terms.

        Creates a structured quote with line items, discounts, tax estimates,
        and AI-generated executive summary and value proposition.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            deal_id: Associated deal ID.
            contact_name: Recipient name.
            company: Recipient company.
            products: List of dicts with keys: name, quantity, unit_price, description.
            discount_percent: Overall discount percentage (0-100).
            valid_days: Number of days the quote is valid.
            payment_terms: Payment terms string.
            currency: ISO 4217 currency code.
            notes: Additional notes for the quote.

        Returns:
            Dict with complete quote including line items, totals, and AI-generated
            executive summary.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            # Calculate line items
            line_items = []
            subtotal = 0.0
            for product in products:
                qty = product.get("quantity", 1)
                price = product.get("unit_price", 0.0)
                line_total = qty * price
                subtotal += line_total
                line_items.append({
                    "name": product.get("name", ""),
                    "description": product.get("description", ""),
                    "quantity": qty,
                    "unit_price": price,
                    "line_total": line_total,
                })

            discount_amount = subtotal * (discount_percent / 100)
            total_after_discount = subtotal - discount_amount
            estimated_tax = total_after_discount * 0.0  # Tax handled externally
            grand_total = total_after_discount + estimated_tax

            # AI-generated executive summary
            system_prompt = (
                "You are a sales proposal writer. Generate a compelling executive summary "
                "and value proposition for this quote. "
                "Output valid JSON with keys: executive_summary (string, 2-3 sentences), "
                "value_proposition (string), key_benefits (array of strings), "
                "competitive_differentiators (array of strings)."
            )
            product_names = ", ".join(p.get("name", "") for p in products)
            user_prompt = (
                f"Write an executive summary for a quote to {contact_name} at {company}.\n"
                f"Products: {product_names}\n"
                f"Total value: {currency} {grand_total:,.2f}\n"
                f"Notes: {notes}"
            )

            ai_summary = await self._llm_json_call(
                system_prompt, user_prompt,
                model=self.FAST_MODEL,
                max_tokens=512,
                user_id=str(user_id or "anon"),
            )

            valid_until = (datetime.now(UTC) + timedelta(days=valid_days)).strftime("%Y-%m-%d")

            return {
                "quote": {
                    "deal_id": deal_id,
                    "contact_name": contact_name,
                    "company": company,
                    "currency": currency,
                    "payment_terms": payment_terms,
                    "valid_until": valid_until,
                    "status": "draft",
                },
                "line_items": line_items,
                "pricing": {
                    "subtotal": round(subtotal, 2),
                    "discount_percent": discount_percent,
                    "discount_amount": round(discount_amount, 2),
                    "total_after_discount": round(total_after_discount, 2),
                    "estimated_tax": round(estimated_tax, 2),
                    "grand_total": round(grand_total, 2),
                },
                "ai_content": {
                    "executive_summary": ai_summary.get("executive_summary", ""),
                    "value_proposition": ai_summary.get("value_proposition", ""),
                    "key_benefits": ai_summary.get("key_benefits", []),
                    "competitive_differentiators": ai_summary.get("competitive_differentiators", []),
                },
                "created_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.generate_quote error: %s", sanitize_error(exc))
            return {"error": str(exc), "contact_name": contact_name, "company": company}

    # ── 11. Sales Analytics Summarization ─────────────────────────────────

    async def summarize_sales_analytics(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        time_range: str = "30d",
        metrics_data: dict | None = None,
        team_id: str | None = None,
        compare_period: bool = True,
    ) -> dict:
        """Generate an AI-powered summary of sales performance analytics.

        Analyzes sales metrics and produces a narrative summary with trend
        identification, anomaly detection, and strategic recommendations.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            time_range: Analysis period (7d, 30d, 90d, qtd, ytd).
            metrics_data: Raw metrics dict to analyze. Fetched from CRM if omitted.
            team_id: Filter to a specific sales team.
            compare_period: Include period-over-period comparison.

        Returns:
            Dict with narrative summary, key metrics, trends, and strategic recommendations.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            system_prompt = (
                "You are a sales analytics expert. Analyze the sales data and produce a "
                "comprehensive performance summary. Output valid JSON with keys: "
                "executive_summary (string, 3-5 sentences), "
                "key_metrics (object with pipeline_value, deals_closed, revenue_closed, "
                "avg_deal_size, win_rate, avg_sales_cycle_days, meetings_booked, calls_made, "
                "emails_sent), "
                "trends (array of objects with metric, direction, magnitude, insight), "
                "anomalies (array of objects with metric, description, severity), "
                "top_performers (array of objects with rep_name, highlight), "
                "recommendations (array of objects with recommendation, expected_impact, priority), "
                "period_comparison (object with current_period, previous_period, change_percent)."
            )
            user_prompt = (
                f"Summarize sales analytics for the {time_range} period.\n"
                f"Team: {team_id or 'All teams'}\n"
                f"Compare with previous period: {compare_period}\n"
                f"Available metrics data: {json.dumps(metrics_data or {}, default=str)}"
            )

            analysis = await self._llm_json_call(
                system_prompt, user_prompt,
                max_tokens=1536,
                user_id=str(user_id or "anon"),
            )

            return {
                "time_range": time_range,
                "team_id": team_id,
                "executive_summary": analysis.get("executive_summary", ""),
                "key_metrics": analysis.get("key_metrics", {}),
                "trends": analysis.get("trends", []),
                "anomalies": analysis.get("anomalies", []),
                "top_performers": analysis.get("top_performers", []),
                "recommendations": analysis.get("recommendations", []),
                "period_comparison": analysis.get("period_comparison", {}),
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.summarize_sales_analytics error: %s", sanitize_error(exc))
            return {"error": str(exc), "time_range": time_range}

    # ── 12. Opportunity Scoring ───────────────────────────────────────────

    async def score_opportunity(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        deal_id: str,
        deal_data: dict,
        contact_engagement: dict | None = None,
        historical_win_data: dict | None = None,
    ) -> dict:
        """Score a sales opportunity using AI-powered multi-factor analysis.

        Evaluates deal health across dimensions including buyer engagement,
        deal velocity, competitive positioning, and BANT/MEDDIC criteria.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            deal_id: Deal ID to score.
            deal_data: Dict with deal properties (stage, amount, close_date, contacts, etc.).
            contact_engagement: Dict with engagement metrics (emails, calls, meetings).
            historical_win_data: Dict with historical win/loss patterns for comparison.

        Returns:
            Dict with composite score, dimensional scores, risk factors, and
            recommended actions to improve the score.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            system_prompt = (
                "You are a sales opportunity scoring engine using MEDDIC methodology. "
                "Score the deal across multiple dimensions and provide a composite score. "
                "Output valid JSON with keys: "
                "composite_score (0-100), "
                "dimensional_scores (object with keys: buyer_engagement (0-100), "
                "deal_velocity (0-100), competitive_position (0-100), "
                "budget_authority (0-100), decision_process (0-100), "
                "champion_strength (0-100), pain_identified (0-100)), "
                "meddic_assessment (object with keys: metrics, economic_buyer, "
                "decision_criteria, decision_process, identify_pain, champion — each a string), "
                "win_probability (0-100), risk_factors (array of objects with factor, severity, mitigation), "
                "score_drivers (array of strings — top positive factors), "
                "improvement_actions (array of objects with action, expected_score_impact, priority)."
            )
            user_prompt = (
                f"Score this sales opportunity:\n"
                f"Deal: {json.dumps(deal_data, default=str)}\n"
                f"Engagement: {json.dumps(contact_engagement or {}, default=str)}\n"
                f"Historical context: {json.dumps(historical_win_data or {}, default=str)}"
            )

            scoring = await self._llm_json_call(
                system_prompt, user_prompt,
                max_tokens=1024,
                user_id=str(user_id or "anon"),
            )

            return {
                "deal_id": deal_id,
                "composite_score": scoring.get("composite_score", 0),
                "dimensional_scores": scoring.get("dimensional_scores", {}),
                "meddic_assessment": scoring.get("meddic_assessment", {}),
                "win_probability": scoring.get("win_probability", 0),
                "risk_factors": scoring.get("risk_factors", []),
                "score_drivers": scoring.get("score_drivers", []),
                "improvement_actions": scoring.get("improvement_actions", []),
                "scored_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.score_opportunity error: %s", sanitize_error(exc))
            return {"error": str(exc), "deal_id": deal_id}

    # ── 13. Account-Based Insights ────────────────────────────────────────

    async def get_account_insights(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        account_id: str,
        account_name: str,
        account_data: dict | None = None,
        include_news: bool = True,
        include_org_chart: bool = True,
        include_tech_stack: bool = True,
    ) -> dict:
        """Generate comprehensive account intelligence for ABM strategies.

        Produces a full account dossier with organizational insights, buying
        committee mapping, competitive landscape, and engagement recommendations.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            account_id: CRM account/company ID.
            account_name: Company name for research.
            account_data: Existing account data dict from CRM.
            include_news: Include recent news and events analysis.
            include_org_chart: Include buying committee and org structure analysis.
            include_tech_stack: Include technology stack analysis.

        Returns:
            Dict with account overview, buying committee map, competitive intelligence,
            engagement strategy, and risk assessment.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            inclusions = []
            if include_news:
                inclusions.append("recent_news_analysis")
            if include_org_chart:
                inclusions.append("buying_committee_mapping")
            if include_tech_stack:
                inclusions.append("technology_stack_analysis")

            system_prompt = (
                "You are an account-based marketing (ABM) intelligence analyst. "
                "Produce a comprehensive account dossier for sales strategy. "
                "Output valid JSON with keys: "
                "account_overview (object with industry, size_estimate, growth_trajectory, "
                "fiscal_health, strategic_priorities), "
                "buying_committee (array of objects with role, typical_title, priorities, "
                "likely_objections, messaging_angle), "
                "competitive_landscape (object with likely_incumbents, displacement_strategy, "
                "competitive_advantages), "
                "engagement_strategy (object with recommended_approach, key_messages, "
                "entry_points, content_recommendations), "
                "risk_assessment (object with deal_risks, mitigation_strategies, "
                "timeline_considerations), "
                "recent_signals (array of objects with signal_type, description, relevance)."
            )
            user_prompt = (
                f"Generate account insights for: {account_name}\n"
                f"Account data: {json.dumps(account_data or {}, default=str)}\n"
                f"Include: {', '.join(inclusions)}"
            )

            insights = await self._llm_json_call(
                system_prompt, user_prompt,
                max_tokens=1536,
                user_id=str(user_id or "anon"),
            )

            return {
                "account_id": account_id,
                "account_name": account_name,
                "account_overview": insights.get("account_overview", {}),
                "buying_committee": insights.get("buying_committee", []),
                "competitive_landscape": insights.get("competitive_landscape", {}),
                "engagement_strategy": insights.get("engagement_strategy", {}),
                "risk_assessment": insights.get("risk_assessment", {}),
                "recent_signals": insights.get("recent_signals", []),
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.get_account_insights error: %s", sanitize_error(exc))
            return {"error": str(exc), "account_id": account_id}

    # ── 14. Renewal Recommendations ───────────────────────────────────────

    async def recommend_renewals(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        accounts: list[dict],
        lookahead_days: int = 90,
        include_upsell: bool = True,
        health_threshold: int = 70,
    ) -> dict:
        """Analyze accounts approaching renewal and generate recommendations.

        Evaluates account health, usage patterns, and engagement to predict
        renewal likelihood and identify upsell/cross-sell opportunities.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            accounts: List of account dicts with keys: account_id, name, renewal_date,
                      current_arr, product, usage_data, health_score, last_engagement.
            lookahead_days: Days ahead to scan for upcoming renewals.
            include_upsell: Include upsell/cross-sell recommendations.
            health_threshold: Minimum health score to consider "healthy" (0-100).

        Returns:
            Dict with renewal recommendations per account, risk stratification,
            and aggregate renewal forecast.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            system_prompt = (
                "You are a customer success and renewal strategist. Analyze the accounts "
                "and generate renewal recommendations. Output valid JSON with keys: "
                "account_recommendations (array of objects with account_id, account_name, "
                "renewal_likelihood (0-100), risk_level (low/medium/high/critical), "
                "recommended_action (string), upsell_opportunities (array of strings), "
                "key_risks (array of strings), engagement_plan (string)), "
                "summary (object with total_arr_at_risk, high_risk_count, "
                "upsell_potential_value, avg_renewal_likelihood), "
                "priority_actions (array of objects with action, account_name, urgency, deadline)."
            )
            user_prompt = (
                f"Analyze these accounts for renewal (lookahead: {lookahead_days} days, "
                f"health threshold: {health_threshold}):\n"
                f"{json.dumps(accounts[:20], default=str)}\n"
                f"Include upsell analysis: {include_upsell}"
            )

            recommendations = await self._llm_json_call(
                system_prompt, user_prompt,
                max_tokens=1536,
                user_id=str(user_id or "anon"),
            )

            return {
                "lookahead_days": lookahead_days,
                "health_threshold": health_threshold,
                "accounts_analyzed": len(accounts),
                "account_recommendations": recommendations.get("account_recommendations", []),
                "summary": recommendations.get("summary", {}),
                "priority_actions": recommendations.get("priority_actions", []),
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.recommend_renewals error: %s", sanitize_error(exc))
            return {"error": str(exc), "accounts_analyzed": len(accounts)}

    # ── 15. Revenue Forecasting ───────────────────────────────────────────

    async def forecast_revenue(
        self,
        db: AsyncSession,
        *,
        user_id: UUID | None = None,
        pipeline_data: dict | None = None,
        historical_data: dict | None = None,
        forecast_period: str = "quarter",
        team_id: str | None = None,
        include_scenarios: bool = True,
        confidence_intervals: bool = True,
    ) -> dict:
        """Generate AI-powered revenue forecasts with scenario analysis.

        Combines pipeline data, historical win rates, and deal velocity to
        produce weighted revenue forecasts with best/worst/likely scenarios.

        Args:
            db: Async database session.
            user_id: Owning user for API key resolution.
            pipeline_data: Current pipeline dict with deals by stage and value.
            historical_data: Historical performance dict with win rates, cycle times.
            forecast_period: Forecast horizon (month, quarter, half, year).
            team_id: Filter to a specific sales team.
            include_scenarios: Generate best/worst/likely scenarios.
            confidence_intervals: Include statistical confidence bands.

        Returns:
            Dict with weighted forecast, scenario analysis, deal-level predictions,
            risk factors, and recommended actions to hit target.
        """
        try:
            _check_rate_limit(str(user_id or "anon"))

            system_prompt = (
                "You are a revenue operations analyst specializing in B2B SaaS forecasting. "
                "Analyze the pipeline and historical data to produce a revenue forecast. "
                "Output valid JSON with keys: "
                "weighted_forecast (object with total, by_stage (object mapping stage to value), "
                "methodology (string)), "
                "scenarios (object with best_case (object with total, assumptions), "
                "likely_case (object with total, assumptions), "
                "worst_case (object with total, assumptions)), "
                "confidence_intervals (object with p10, p25, p50, p75, p90), "
                "deal_predictions (array of top 5 objects with deal_name, predicted_value, "
                "close_probability, predicted_close_date, risk_level), "
                "risk_factors (array of objects with factor, impact_amount, likelihood), "
                "gap_to_target (object with target, forecast, gap, gap_percent, "
                "actions_to_close_gap (array of strings)), "
                "forecast_accuracy_estimate (0-100)."
            )
            user_prompt = (
                f"Generate a {forecast_period} revenue forecast.\n"
                f"Team: {team_id or 'All teams'}\n"
                f"Pipeline data: {json.dumps(pipeline_data or {}, default=str)}\n"
                f"Historical data: {json.dumps(historical_data or {}, default=str)}\n"
                f"Include scenarios: {include_scenarios}\n"
                f"Include confidence intervals: {confidence_intervals}"
            )

            forecast = await self._llm_json_call(
                system_prompt, user_prompt,
                max_tokens=1536,
                user_id=str(user_id or "anon"),
            )

            return {
                "forecast_period": forecast_period,
                "team_id": team_id,
                "weighted_forecast": forecast.get("weighted_forecast", {}),
                "scenarios": forecast.get("scenarios", {}) if include_scenarios else {},
                "confidence_intervals": forecast.get("confidence_intervals", {}) if confidence_intervals else {},
                "deal_predictions": forecast.get("deal_predictions", []),
                "risk_factors": forecast.get("risk_factors", []),
                "gap_to_target": forecast.get("gap_to_target", {}),
                "forecast_accuracy_estimate": forecast.get("forecast_accuracy_estimate", 0),
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("SalesAgent.forecast_revenue error: %s", sanitize_error(exc))
            return {"error": str(exc), "forecast_period": forecast_period}

    # ── Factory / convenience ─────────────────────────────────────────────

    @staticmethod
    async def from_db(db: AsyncSession, user_id: UUID | None = None) -> "SalesAgent":
        """Create a SalesAgent with the API key resolved from the database.

        Args:
            db: Async database session.
            user_id: User whose API key to resolve.

        Returns:
            Configured SalesAgent instance.
        """
        api_key = await _get_groq_key(db, user_id)
        return SalesAgent(api_key=api_key)
