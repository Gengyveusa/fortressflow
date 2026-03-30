"""Multi-Agent Workflow Planner — converts natural language into structured execution plans.

The brain that parses commands like "I want to contact 100 dentists in Denver"
into multi-agent execution plans, validates them, and runs them step-by-step.

Updated for Phase 10: 7 agents with full platform mastery.
"""

import json
import logging
import uuid as _uuid
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.agent_intelligence import AgentIntelligence
from app.services.agents.prompt_engine import PromptEngine

logger = logging.getLogger(__name__)

# In-memory plan storage (keyed by plan_id)
_plans: dict[str, dict] = {}


class WorkflowPlanner:
    """Converts natural language commands into multi-agent workflow plans."""

    PLANNING_PROMPT = """
You are a workflow planner for FortressFlow. Given a user's natural language request,
create a structured execution plan using the available agents and their capabilities.

Available Agents:

1. **groq** — Primary LLM for content generation, classification, compliance checking
   Actions: chat, generate_sequence_content, classify_reply, check_compliance,
   generate_ab_variants, generate_warmup_email, score_lead_narrative, summarize_analytics

2. **openai** — Fallback LLM for embeddings, moderation, structured extraction, analysis
   Actions: chat, embed, moderate, extract_structured, analyze_template_performance, suggest_improvements

3. **hubspot** — Full CRM operations (contacts, deals, companies, marketing, automation, commerce)
   Actions: create_contact, update_contact, get_contact, search_contacts, bulk_create_contacts,
   merge_contacts, delete_contact, create_deal, update_deal, move_deal_stage, get_pipeline, get_deals,
   create_company, update_company, associate_contact_to_company, create_list, add_to_list,
   remove_from_list, log_email, log_call, log_meeting, create_task, log_note,
   create_property, get_properties, get_contact_activity, get_pipeline_report, full_sync, pull_updates,
   create_pipeline, update_pipeline, delete_pipeline, get_pipeline_stages, create_pipeline_stage,
   update_pipeline_stage, create_association, get_associations, delete_association, batch_create_associations,
   crm_search, import_contacts, get_import_status, export_contacts,
   send_transactional_email, get_marketing_emails, get_email_statistics,
   create_campaign_marketing, get_campaign_report,
   list_forms, get_form_submissions, create_form,
   log_postal_mail, create_task_with_queue,
   get_workflows, trigger_workflow, create_sequence_enrollment,
   list_inboxes, get_threads, send_message,
   create_invoice, create_payment, create_subscription,
   list_hubspot_users, list_teams, list_currencies,
   create_webhook_subscription, list_webhook_subscriptions, delete_webhook_subscription

4. **zoominfo** — Full B2B intelligence (search, enrichment, intent, compliance, WebSights)
   Actions: enrich_person, search_people, bulk_enrich_people, enrich_company, search_companies,
   get_company_hierarchy, get_intent_signals, get_surge_scores, get_scoops, get_news, get_tech_stack,
   verify_email, verify_phone, bulk_enrich, get_bulk_status, get_bulk_results,
   get_website_visitors, get_visitor_companies,
   check_opt_out, add_opt_out, remove_opt_out, check_gdpr_status,
   advanced_search_contacts, search_by_technology,
   lookup_by_email, lookup_by_domain, lookup_by_phone,
   submit_bulk_job, get_bulk_job_progress, cancel_bulk_job,
   get_funding_info, get_org_chart

5. **twilio** — Full communications (SMS, MMS, WhatsApp, voice, conferencing, A2P compliance)
   Actions: send_sms, bulk_send_sms, get_message, list_messages, make_call, get_call, list_calls,
   send_verification, check_verification, lookup_phone, validate_phone,
   list_phone_numbers, buy_phone_number, configure_number, release_number,
   create_messaging_service, add_sender_to_service, get_usage, get_delivery_stats,
   send_mms, send_whatsapp, schedule_message, create_content_template, list_content_templates,
   check_opt_out_status, process_opt_out, process_opt_in,
   create_conference, record_call, get_recording, get_transcription,
   get_line_type, get_sim_swap, get_caller_name,
   create_conversation, add_participant, send_conversation_message,
   get_brand_registration_status, get_campaign_status, get_toll_free_verification_status

6. **apollo** — Sales intelligence & engagement (210M+ contacts, enrichment, sequences, deals)
   Actions: search_people, search_organizations, get_organization_job_postings,
   enrich_person, bulk_enrich_people, enrich_organization,
   create_contact, update_contact, bulk_create_contacts, search_contacts, delete_contact,
   create_account, update_account, bulk_create_accounts,
   create_deal, list_deals, get_deal, update_deal,
   search_sequences, add_contacts_to_sequence, update_contact_sequence_status,
   create_task, bulk_create_tasks, search_tasks,
   create_call_record, search_calls, update_call_record,
   get_usage_stats, list_users, list_email_accounts

7. **taplio** — LinkedIn growth (AI posts, DMs, lead database, analytics via Zapier)
   Actions: generate_linkedin_post, schedule_post, generate_carousel, generate_hook,
   compose_dm, bulk_compose_dms, trigger_zapier_action,
   search_leads, get_post_analytics, create_connection_request

Rules:
- Always check compliance before any outreach
- Always verify emails before sending campaigns
- Use ZoomInfo for B2B intelligence and deep enrichment, Apollo for broad search + sequences
- Use Apollo for finding NEW leads and enrolling in sequences, use HubSpot for EXISTING CRM data
- For campaigns, always generate content BEFORE creating the sequence
- Consider Taplio/LinkedIn for high-value prospects (DSO executives, practice owners)
- Consider Apollo sequences for automated email outreach at scale
- Consider WhatsApp (via Twilio) for DSO contacts who prefer messaging
- Return a plan, don't execute yet — the user confirms first
- When the user asks about "contacting" or "reaching out", consider ALL available channels
- When the user asks to "find" people, prefer Apollo search (broader database) with ZoomInfo enrichment

Output valid JSON:
{
    "understanding": "What the user wants in plain English",
    "plan_type": "search_leads|create_campaign|enrich|analyze|outreach_options|multi_step",
    "steps": [
        {
            "step": 1,
            "agent": "apollo",
            "action": "search_people",
            "description": "Search Apollo for dentists in Denver area",
            "params": {},
            "depends_on": null
        }
    ],
    "options": [],
    "warnings": [],
    "estimated_time": "2-5 minutes",
    "confirmation_needed": true
}
""".strip()

    def __init__(self):
        self.prompt_engine = PromptEngine()
        self.intelligence = AgentIntelligence()

    async def plan(self, db: AsyncSession, user_id: UUID, user_message: str, agent_statuses: list) -> dict:
        """Parse a natural language request into a structured workflow plan.

        Uses the LLM to understand the request, then validates the plan against
        available agents and their configuration status.
        """
        # Build the system prompt with domain context
        system_prompt = await self.prompt_engine.build_system_prompt(
            db,
            user_id,
            "groq",
            "chat",
            extra_context=self.PLANNING_PROMPT,
        )

        # Include agent availability in the user message
        configured = [a["agent_name"] for a in agent_statuses if a["configured"]]
        not_configured = [a["agent_name"] for a in agent_statuses if not a["configured"]]

        augmented_message = (
            f"User request: {user_message}\n\n"
            f"Configured agents: {', '.join(configured) if configured else 'none'}\n"
            f"NOT configured agents: {', '.join(not_configured) if not_configured else 'none'}\n"
            "Create a plan considering which agents are available."
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": augmented_message},
        ]

        # Call LLM (Groq primary, OpenAI fallback)
        raw_plan = await self._call_llm(db, user_id, messages)

        # Parse the plan
        plan = self._parse_plan(raw_plan, user_message)

        # Store the plan for later execution
        plan_id = str(_uuid.uuid4())
        plan["plan_id"] = plan_id
        _plans[plan_id] = plan

        # Also build outreach options if the request seems to be asking for options
        lower_msg = user_message.lower()
        if any(kw in lower_msg for kw in ["option", "what can", "how can", "what are my"]):
            options = await self.present_options(
                db,
                user_id,
                {
                    "target": plan.get("understanding", user_message),
                    "location": self._extract_location(user_message),
                    "count": self._extract_count(user_message),
                },
            )
            plan["outreach_options"] = options

        return plan

    async def execute_plan(
        self, db: AsyncSession, user_id: UUID, plan_id: str, selected_option: int | None = None
    ) -> dict:
        """Execute a confirmed plan step-by-step via the orchestrator."""
        from app.services.agents.orchestrator import AgentOrchestrator

        plan = _plans.get(plan_id)
        if not plan:
            return {"status": "error", "error": f"Plan {plan_id} not found or expired."}

        steps = plan.get("steps", [])
        if not steps:
            return {"status": "error", "error": "Plan has no steps to execute."}

        results = []
        overall_status = "success"

        for step in steps:
            agent_name = step.get("agent", "")
            action = step.get("action", "")
            params = step.get("params", {})
            depends_on = step.get("depends_on")

            # Inject previous result if dependency
            if depends_on is not None and results:
                for prev in results:
                    if prev.get("step") == depends_on and prev.get("status") == "success":
                        params["previous_result"] = prev.get("result")

            dispatch_result = await AgentOrchestrator.dispatch(
                db=db,
                agent_name=agent_name,
                action=action,
                params=params,
                user_id=user_id,
            )

            step_result = {
                "step": step.get("step"),
                "agent": agent_name,
                "action": action,
                "description": step.get("description", ""),
                "status": dispatch_result["status"],
                "result": dispatch_result.get("result"),
                "error": dispatch_result.get("error"),
            }
            results.append(step_result)

            if dispatch_result["status"] != "success":
                overall_status = "partial"

        # Clean up stored plan
        _plans.pop(plan_id, None)

        return {"status": overall_status, "steps": results}

    async def present_options(self, db: AsyncSession, user_id: UUID, params: dict) -> dict:
        """For requests like 'what are my options', build and present available approaches."""
        return await self.intelligence.build_outreach_options(db, user_id, params)

    # ── Internal helpers ─────────────────────────────────────────────────

    async def _call_llm(self, db: AsyncSession, user_id: UUID, messages: list[dict]) -> str:
        """Call LLM with Groq primary / OpenAI fallback."""
        from app.config import settings
        from app.utils.sanitize import sanitize_error

        # Try Groq first
        groq_key = getattr(settings, "GROQ_API_KEY", "")
        if groq_key:
            try:
                from groq import AsyncGroq

                client = AsyncGroq(api_key=groq_key)
                resp = await client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("Groq planning failed: %s", sanitize_error(exc))

        # Try user's DB-stored Groq key
        try:
            from app.services import api_key_service

            user_groq_key = await api_key_service.get_api_key(db, "groq", user_id)
            if user_groq_key:
                from groq import AsyncGroq

                client = AsyncGroq(api_key=user_groq_key)
                resp = await client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content or ""
        except Exception as exc:
            logger.warning("User Groq key planning failed: %s", sanitize_error(exc))

        # OpenAI fallback
        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if openai_key:
            try:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(api_key=openai_key)
                resp = await client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    temperature=0.2,
                    max_tokens=2048,
                    response_format={"type": "json_object"},
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("OpenAI planning failed: %s", sanitize_error(exc))

        # No LLM available — return a basic plan structure
        return json.dumps(
            {
                "understanding": "Unable to parse request — no LLM configured",
                "plan_type": "unknown",
                "steps": [],
                "options": [],
                "warnings": ["No LLM agent (Groq or OpenAI) is configured. Add an API key in Settings."],
                "estimated_time": "N/A",
                "confirmation_needed": False,
            }
        )

    def _parse_plan(self, raw: str, original_message: str) -> dict:
        """Parse LLM JSON response into a plan dict."""
        try:
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            plan = json.loads(cleaned)

            # Validate structure
            if not isinstance(plan, dict):
                plan = {"understanding": original_message, "steps": [], "plan_type": "unknown"}

            plan.setdefault("understanding", original_message)
            plan.setdefault("plan_type", "multi_step")
            plan.setdefault("steps", [])
            plan.setdefault("options", [])
            plan.setdefault("warnings", [])
            plan.setdefault("estimated_time", "2-5 minutes")
            plan.setdefault("confirmation_needed", True)

            return plan

        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("Failed to parse plan: %s — raw: %s", exc, raw[:200])
            return {
                "understanding": original_message,
                "plan_type": "unknown",
                "steps": [],
                "options": [],
                "warnings": [f"Failed to parse plan: {exc}"],
                "estimated_time": "N/A",
                "confirmation_needed": True,
            }

    def _extract_location(self, message: str) -> str:
        """Simple location extraction from natural language."""
        lower = message.lower()
        # Look for "in <location>" pattern
        if " in " in lower:
            parts = lower.split(" in ", 1)
            if len(parts) > 1:
                loc = parts[1].strip()
                # Take until a common stop word
                for stop in [" today", " this", " and", " what", " how", ",", "."]:
                    if stop in loc:
                        loc = loc[: loc.index(stop)]
                return loc.strip().title()
        return ""

    def _extract_count(self, message: str) -> int:
        """Simple count extraction from natural language."""
        import re

        match = re.search(r"(\d+)\s*(?:dentist|doctor|lead|contact|people|person)", message.lower())
        if match:
            return int(match.group(1))
        return 100  # default
