"""
Conversational AI Command Engine — intent classification and routing.

Intercepts chat messages, classifies them into actionable intents using
the LLM (Groq primary / OpenAI fallback), extracts entities, and routes
to the appropriate handler (campaign wizard, business intelligence, etc.).
"""

import json
import logging
from typing import Any
from uuid import UUID

from app.config import settings
from app.services.agents.orchestrator import AgentOrchestrator
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)

# ── Intent Registry ──────────────────────────────────────────────────────────

INTENTS = {
    # Lead Management
    "find_leads": "Find/search/get leads matching criteria",
    "import_leads": "Import leads from CSV or HubSpot",
    "enrich_leads": "Enrich existing leads with ZoomInfo/Apollo",
    # Campaign/Sequence
    "create_campaign": "Create/launch/start a campaign or sequence",
    "pause_campaign": "Pause/stop a running campaign",
    "resume_campaign": "Resume/restart a paused campaign",
    # Analytics/Status
    "check_status": "How are we doing / campaign performance / metrics",
    "check_deliverability": "Email health / bounce rates / warmup status",
    # Configuration
    "configure_integration": "Set up / connect API keys",
    "check_integrations": "What's connected / integration status",
    # Agent operations
    "send_sms": "Send an SMS or text message to a phone number",
    "sync_crm": "Sync leads/contacts with HubSpot CRM",
    "search_company": "Search for company information or intelligence",
    "ai_generate": "Generate AI content, copy, or analysis",
    # Multi-agent planning
    "plan_outreach": "I want to contact/reach/email/call X people in Y area / plan a campaign / what are my options for outreach",
    # Apollo / Taplio / WhatsApp
    "apollo_search": "Search for contacts or companies in Apollo's 210M+ database by title, location, industry, seniority",
    "apollo_sequence": "Add contacts to an Apollo email sequence, manage sequence enrollments, or search for sequences",
    "linkedin_post": "Create, schedule, or manage LinkedIn posts via Taplio — text, carousel, or hook generation",
    "linkedin_dm": "Send personalized LinkedIn direct messages to prospects via Taplio",
    "send_whatsapp": "Send a WhatsApp Business message to a contact via Twilio",
    # Help
    "get_help": "How do I / what can you do / help",
    # ── v2.0 Marketing Agent ──
    "score_lead": "Score a lead / what's their lead score / rate this prospect",
    "segment_customers": "Segment customers / group by behavior / create segments",
    "create_social_post": "Create social media post / write a tweet / LinkedIn content",
    "optimize_send_time": "When should I send / best time to email / optimize timing",
    "generate_landing_page": "Create landing page copy / write a hero section",
    "demand_gen": "Create demand generation sequence / nurture campaign",
    "upsell_crosssell": "Recommend upsell / cross-sell / expansion opportunities",
    "event_promotion": "Promote an event / create event marketing content",
    "multilingual_content": "Translate content / write in Spanish / multilingual",
    "chatbot_response": "Manage chatbot / create bot response / qualify lead via chat",
    # ── v2.0 Sales Agent ──
    "manage_pipeline": "Pipeline status / deal management / move deal stage",
    "schedule_meeting": "Schedule a meeting / book a call / find available times",
    "generate_quote": "Create a quote / proposal / pricing document",
    "score_opportunity": "Score opportunity / MEDDIC analysis / deal health",
    "account_insights": "Account insights / ABM intelligence / buying committee",
    "renewal_recommendation": "Renewal risk / churn prevention / retention strategy",
    "revenue_forecast": "Revenue forecast / pipeline forecast / sales projection",
    "log_call_transcript": "Log a call / summarize call transcript / analyze meeting",
    "automated_followup": "Create follow-up sequence / automated follow-up",
    # ── v2.0 Platform Features ──
    "churn_analysis": "Churn risk / which accounts are at risk / retention",
    "dedup_check": "Find duplicates / dedup health / merge contacts",
    "experiment_status": "Experiment results / A/B test / variant performance",
    "community_stats": "Community stats / member count / waitlist status",
    "call_analytics": "Call analytics / meeting summaries / sentiment analysis",
    "plugin_marketplace": "Available plugins / marketplace / integrations",
    "translate_content": "Translate this / convert to Spanish / multilingual",
    "unknown": "Can't classify",
}

# ── Classification prompt ────────────────────────────────────────────────────

_CLASSIFICATION_PROMPT = """\
You are an intent classifier for FortressFlow, a B2B lead-gen and outreach platform \
for dental offices and DSOs.

Given the user's message, classify it into exactly one intent and extract entities.

Available intents:
{intents_list}

Extract these entities when present:
- specialty: dental specialty (e.g., "periodontist", "oral surgeon", "general dentist", "endodontist")
- location: geographic area (e.g., "Texas", "New York City", "nationwide")
- count: number of leads or items requested (e.g., 50, 100)
- channels: outreach channels (e.g., ["email"], ["email", "linkedin", "sms"])
- campaign_name: name of a specific campaign being referenced
- timeframe: time period (e.g., "7d", "30d", "this week", "last month")
- tone: communication tone (e.g., "professional", "friendly", "urgent")
- sequence_length: number of steps in a sequence (e.g., 5, 7)
- company_size: target company size (e.g., "solo practice", "DSO", "5+ locations")
- integration_name: name of integration (e.g., "hubspot", "zoominfo", "apollo")
- phone_number: phone number for SMS (e.g., "+15551234567")
- sms_body: text message body to send
- company_query: company name or search term
- ai_prompt: content generation prompt or question
- apollo_query: search query for Apollo contacts/companies
- sequence_name: name of an Apollo sequence
- linkedin_topic: topic for LinkedIn post
- linkedin_format: format (text, carousel, article)
- whatsapp_number: WhatsApp phone number
- whatsapp_body: WhatsApp message body

Respond ONLY with valid JSON — no markdown, no explanation:
{{"intent": "<intent_name>", "confidence": <0.0-1.0>, "entities": {{...extracted entities...}}, "missing_required": [...]}}

Rules:
- confidence should reflect how clearly the message maps to the intent
- If the message is ambiguous, use "unknown" with low confidence
- missing_required lists entity keys that are needed but not present in the message
- For "create_campaign", required entities are: target_description (specialty or audience)
- For "find_leads", required entities are: specialty_or_criteria
- For "check_status", nothing is required
- For "pause_campaign" / "resume_campaign", campaign_name is required
- For "send_sms", required entities are: phone_number, sms_body
- For "sync_crm", nothing is required
- For "search_company", required entities are: company_query
- For "ai_generate", required entities are: ai_prompt
- For "apollo_search", required entities are: apollo_query (title, location, or company)
- For "apollo_sequence", required entities are: sequence_name or contact reference
- For "linkedin_post", required entities are: linkedin_topic
- For "linkedin_dm", required entities are: recipient name or profile reference
- For "send_whatsapp", required entities are: whatsapp_number, whatsapp_body
- For "plan_outreach", required entities are: target_description (who to reach). Route here for complex multi-step requests involving lead sourcing + outreach, or when user asks "what are my options" for contacting people

User message: {message}"""


class IntentResult:
    """Result of intent classification."""

    __slots__ = ("intent", "confidence", "entities", "missing_required", "raw_response")

    def __init__(
        self,
        intent: str = "unknown",
        confidence: float = 0.0,
        entities: dict[str, Any] | None = None,
        missing_required: list[str] | None = None,
        raw_response: str = "",
    ) -> None:
        self.intent = intent
        self.confidence = confidence
        self.entities = entities or {}
        self.missing_required = missing_required or []
        self.raw_response = raw_response

    def is_actionable(self) -> bool:
        return self.intent != "unknown" and self.confidence >= 0.7

    def needs_clarification(self) -> bool:
        return (
            (self.intent != "unknown" and self.confidence < 0.7)
            or bool(self.missing_required)
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "intent": self.intent,
            "confidence": self.confidence,
            "entities": self.entities,
            "missing_required": self.missing_required,
        }


class CommandEngine:
    """
    Core command engine — classifies user messages into intents and routes
    them to the appropriate handler.
    """

    async def classify_intent(self, message: str) -> IntentResult:
        """
        Classify a user message into an actionable intent using LLM.

        Uses the same Groq → OpenAI fallback cascade as the chat service.
        """
        intents_list = "\n".join(
            f"- {name}: {desc}" for name, desc in INTENTS.items()
        )
        prompt = _CLASSIFICATION_PROMPT.format(
            intents_list=intents_list,
            message=message,
        )

        messages = [
            {"role": "system", "content": "You are an intent classification engine. Respond only with valid JSON."},
            {"role": "user", "content": prompt},
        ]

        raw = await self._call_llm(messages, temperature=0.1, max_tokens=512)

        return self._parse_classification(raw)

    async def route_intent(
        self,
        result: IntentResult,
        message: str,
        user_id: str,
        session_id: str,
        session_state: dict[str, Any] | None = None,
        db=None,
    ) -> dict[str, Any]:
        """
        Route a classified intent to the appropriate handler.

        Returns a structured response dict with type and content.
        """
        intent = result.intent

        # If missing required fields, delegate to smart questioner
        if result.needs_clarification():
            from app.services.smart_questioner import SmartQuestioner

            questioner = SmartQuestioner()
            return await questioner.ask_clarification(
                result, message, session_state or {}
            )

        # Route to handlers
        if intent == "create_campaign":
            from app.services.campaign_wizard import CampaignWizard

            wizard = CampaignWizard()
            return await wizard.start_campaign(
                params=result.entities,
                user_id=user_id,
                session_id=session_id,
            )

        if intent in ("check_status", "check_deliverability"):
            from app.services.business_intelligence import BusinessIntelligence

            bi = BusinessIntelligence()
            return await bi.handle_query(
                intent=intent,
                entities=result.entities,
                user_id=user_id,
            )

        if intent == "find_leads":
            return await self._handle_find_leads(result.entities, user_id)

        if intent == "import_leads":
            return {
                "type": "text",
                "content": (
                    "To import leads, you have two options:\n\n"
                    "1. **CSV Upload**: Go to **Leads → Import CSV** or use "
                    "`POST /api/v1/leads/import/csv`\n"
                    "2. **HubSpot Sync**: Connect HubSpot in **Settings → Integrations** "
                    "to auto-sync contacts\n\n"
                    "After import, leads are automatically enriched via ZoomInfo/Apollo. "
                    "Want me to walk you through either option?"
                ),
            }

        if intent == "enrich_leads":
            return await self._handle_enrich_leads(result.entities, user_id, db)

        if intent == "pause_campaign":
            return await self._handle_pause_campaign(result.entities, user_id)

        if intent == "resume_campaign":
            return await self._handle_resume_campaign(result.entities, user_id)

        if intent == "configure_integration":
            return self._handle_configure_integration(result.entities)

        if intent == "check_integrations":
            return await self._handle_check_integrations(user_id, db)

        if intent == "send_sms":
            return await self._handle_send_sms(result.entities, user_id, db)

        if intent == "sync_crm":
            return await self._handle_sync_crm(result.entities, user_id, db)

        if intent == "search_company":
            return await self._handle_search_company(result.entities, user_id, db)

        if intent == "ai_generate":
            return await self._handle_ai_generate(result.entities, user_id, db)

        if intent == "plan_outreach":
            return await self._handle_plan_outreach(
                result.entities, message, user_id, db
            )


        if intent == "apollo_search":
            return await self._handle_apollo_search(result.entities, user_id, db)

        if intent == "apollo_sequence":
            return await self._handle_apollo_sequence(result.entities, user_id, db)

        if intent == "linkedin_post":
            return await self._handle_linkedin_post(result.entities, user_id, db)

        if intent == "linkedin_dm":
            return await self._handle_linkedin_dm(result.entities, user_id, db)

        if intent == "send_whatsapp":
            return await self._handle_send_whatsapp(result.entities, user_id, db)

        if intent == "get_help":
            return self._handle_help()

        # ── v2.0 Marketing Agent intents ──
        if intent == "score_lead":
            return await self._handle_agent_dispatch("marketing", "score_leads", result.entities, user_id, db)
        if intent == "segment_customers":
            return await self._handle_agent_dispatch("marketing", "segment_customers", result.entities, user_id, db)
        if intent == "create_social_post":
            return await self._handle_agent_dispatch("marketing", "create_social_post", result.entities, user_id, db)
        if intent == "optimize_send_time":
            return await self._handle_agent_dispatch("marketing", "optimize_send_time", result.entities, user_id, db)
        if intent == "generate_landing_page":
            return await self._handle_agent_dispatch("marketing", "generate_landing_page_copy", result.entities, user_id, db)
        if intent == "demand_gen":
            return await self._handle_agent_dispatch("marketing", "create_demand_gen_sequence", result.entities, user_id, db)
        if intent == "upsell_crosssell":
            return await self._handle_agent_dispatch("marketing", "recommend_upsell_crosssell", result.entities, user_id, db)
        if intent == "event_promotion":
            return await self._handle_agent_dispatch("marketing", "create_event_promotion", result.entities, user_id, db)
        if intent == "multilingual_content" or intent == "translate_content":
            return await self._handle_agent_dispatch("marketing", "generate_multilingual_content", result.entities, user_id, db)
        if intent == "chatbot_response":
            return await self._handle_agent_dispatch("marketing", "manage_chatbot", result.entities, user_id, db)

        # ── v2.0 Sales Agent intents ──
        if intent == "manage_pipeline":
            return await self._handle_agent_dispatch("sales", "manage_pipeline", result.entities, user_id, db)
        if intent == "schedule_meeting":
            return await self._handle_agent_dispatch("sales", "schedule_meeting", result.entities, user_id, db)
        if intent == "generate_quote":
            return await self._handle_agent_dispatch("sales", "generate_quote", result.entities, user_id, db)
        if intent == "score_opportunity":
            return await self._handle_agent_dispatch("sales", "score_opportunity", result.entities, user_id, db)
        if intent == "account_insights":
            return await self._handle_agent_dispatch("sales", "get_account_insights", result.entities, user_id, db)
        if intent == "renewal_recommendation":
            return await self._handle_agent_dispatch("sales", "recommend_renewals", result.entities, user_id, db)
        if intent == "revenue_forecast":
            return await self._handle_agent_dispatch("sales", "forecast_revenue", result.entities, user_id, db)
        if intent == "log_call_transcript":
            return await self._handle_agent_dispatch("sales", "log_call", result.entities, user_id, db)
        if intent == "automated_followup":
            return await self._handle_agent_dispatch("sales", "create_automated_followup", result.entities, user_id, db)

        # ── v2.0 Platform Feature intents ──
        if intent == "churn_analysis":
            return await self._handle_insights_fetch("/insights/churn/predictions", "Churn Detection")
        if intent == "dedup_check":
            return await self._handle_insights_fetch("/insights/deduplication/health", "Deduplication Health")
        if intent == "experiment_status":
            return await self._handle_insights_fetch("/insights/experiments/summary", "Experiment Results")
        if intent == "community_stats":
            return await self._handle_insights_fetch("/insights/community/stats", "Community Stats")
        if intent == "call_analytics":
            return await self._handle_insights_fetch("/insights/calls/analytics", "Call Analytics")
        if intent == "plugin_marketplace":
            return await self._handle_insights_fetch("/insights/plugins/marketplace", "Plugin Marketplace")

        # Fallback — unknown intent
        return {"type": "text", "content": ""}

    # ── v2.0 Generic Handlers ────────────────────────────────────────────

    async def _handle_agent_dispatch(
        self, agent_name: str, action: str, entities: dict[str, Any], user_id: str, db
    ) -> dict[str, Any]:
        """Dispatch to any agent via the orchestrator and return formatted results."""
        try:
            from uuid import UUID as _UUID
            uid = _UUID(user_id) if isinstance(user_id, str) else user_id
            result = await AgentOrchestrator.dispatch(db, agent_name, action, entities, uid)
            if result.get("status") == "success":
                content = result.get("result", {})
                if isinstance(content, dict):
                    # Format key-value pairs nicely
                    formatted = f"**{agent_name.title()} → {action.replace('_', ' ').title()}**\n\n"
                    for k, v in content.items():
                        if isinstance(v, (list, dict)):
                            formatted += f"**{k.replace('_', ' ').title()}:** {json.dumps(v, indent=2, default=str)[:500]}\n\n"
                        else:
                            formatted += f"**{k.replace('_', ' ').title()}:** {v}\n"
                    return {"type": "text", "content": formatted}
                return {"type": "text", "content": str(content)}
            else:
                error = result.get("error", "Unknown error")
                return {"type": "text", "content": f"⚠️ {agent_name}.{action} failed: {error}"}
        except Exception as exc:
            logger.error("Agent dispatch %s.%s failed: %s", agent_name, action, exc)
            return {"type": "text", "content": f"⚠️ Could not execute {agent_name}.{action}: {sanitize_error(exc)}"}

    async def _handle_insights_fetch(self, endpoint: str, label: str) -> dict[str, Any]:
        """Fetch data from an insights endpoint and format for chat."""
        try:
            import httpx
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(f"http://127.0.0.1:8000/api/v1{endpoint}")
                if resp.status_code == 200:
                    data = resp.json()
                    formatted = f"**{label}**\n\n"
                    if isinstance(data, dict):
                        for k, v in list(data.items())[:15]:
                            if isinstance(v, (list, dict)):
                                formatted += f"**{k.replace('_', ' ').title()}:** {json.dumps(v, default=str)[:300]}\n\n"
                            else:
                                formatted += f"**{k.replace('_', ' ').title()}:** {v}\n"
                    elif isinstance(data, list):
                        for item in data[:5]:
                            if isinstance(item, dict):
                                title = item.get("title", item.get("name", ""))
                                desc = item.get("description", "")
                                formatted += f"• **{title}**: {desc}\n"
                    return {"type": "text", "content": formatted}
                return {"type": "text", "content": f"⚠️ Could not fetch {label} (HTTP {resp.status_code})"}
        except Exception as exc:
            logger.error("Insights fetch %s failed: %s", endpoint, exc)
            return {"type": "text", "content": f"⚠️ Could not fetch {label}: {sanitize_error(exc)}"}

    # ── Original Intent Handlers ───────────────────────────────────────────

    async def _handle_find_leads(
        self, entities: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        """Search for leads matching the given criteria."""
        from sqlalchemy import func, select

        from app.database import AsyncSessionLocal
        from app.models.lead import Lead

        specialty = entities.get("specialty_or_criteria") or entities.get("specialty", "")
        location = entities.get("location", "")
        count = int(entities.get("count", 25))

        async with AsyncSessionLocal() as db:
            query = select(Lead)

            if specialty:
                query = query.where(
                    func.lower(Lead.title).contains(specialty.lower())
                    | func.lower(Lead.company).contains(specialty.lower())
                    | func.cast(Lead.enriched_data, String).ilike(f"%{specialty}%")
                )
            if location:
                query = query.where(
                    func.cast(Lead.enriched_data, String).ilike(f"%{location}%")
                )

            from sqlalchemy import String

            query = query.limit(min(count, 100))
            result = await db.execute(query)
            leads = result.scalars().all()

        if not leads:
            search_desc = specialty or "your criteria"
            return {
                "type": "text",
                "content": (
                    f"No leads found matching **{search_desc}**"
                    f"{f' in {location}' if location else ''}. "
                    "Would you like me to:\n"
                    "1. Search with broader criteria?\n"
                    "2. Enrich new leads via ZoomInfo/Apollo?\n"
                    "3. Import leads from CSV?"
                ),
            }

        lead_lines = []
        for lead in leads[:10]:
            lead_lines.append(
                f"- **{lead.first_name} {lead.last_name}** — {lead.title} at {lead.company} ({lead.email})"
            )

        more_text = ""
        if len(leads) > 10:
            more_text = f"\n\n... and {len(leads) - 10} more. "
        elif len(leads) == count:
            more_text = "\n\nReached the limit. "

        return {
            "type": "text",
            "content": (
                f"Found **{len(leads)}** leads"
                f"{f' matching {specialty}' if specialty else ''}"
                f"{f' in {location}' if location else ''}:\n\n"
                + "\n".join(lead_lines)
                + more_text
                + "Want me to create a campaign targeting these leads?"
            ),
        }

    async def _handle_enrich_leads(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Trigger lead enrichment — counts un-enriched leads and dispatches to ZoomInfo."""
        from sqlalchemy import func, select

        from app.database import AsyncSessionLocal
        from app.models.lead import Lead

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(func.count(Lead.id)).where(Lead.last_enriched_at.is_(None))
            )
            unenriched = result.scalar_one() or 0

        if unenriched == 0:
            return {
                "type": "text",
                "content": "All leads are already enriched! No action needed.",
            }

        # If we have a db session, dispatch enrichment to ZoomInfo agent
        if db is not None:
            try:
                uid = UUID(user_id) if isinstance(user_id, str) else user_id
                agent_result = await AgentOrchestrator.dispatch(
                    db=db,
                    agent_name="zoominfo",
                    action="search_people",
                    params={"filters": {"pageSize": min(unenriched, 100)}},
                    user_id=uid,
                )
                if agent_result.get("status") == "success":
                    return {
                        "type": "text",
                        "content": (
                            f"**{unenriched}** leads need enrichment.\n\n"
                            "ZoomInfo enrichment has been initiated. Results will be applied "
                            "to your leads as they come in.\n\n"
                            f"Enrichment latency: {agent_result.get('latency_ms', 'N/A')}ms"
                        ),
                    }
                else:
                    error = agent_result.get("error", "Unknown error")
                    logger.warning("ZoomInfo enrichment dispatch failed: %s", error)
            except Exception as exc:
                logger.warning("Failed to dispatch to ZoomInfo: %s", sanitize_error(exc))

        return {
            "type": "text",
            "content": (
                f"**{unenriched}** leads have not been enriched yet.\n\n"
                "To enrich leads:\n"
                "1. **ZoomInfo**: Provides company data, technographics, and intent signals\n"
                "2. **Apollo**: Adds email verification, org charts, and AI scoring\n\n"
                "Both run automatically on new imports if API keys are configured. "
                "Go to **Settings → Integrations** to check your connections."
            ),
        }

    async def _handle_pause_campaign(
        self, entities: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        """Pause a campaign/sequence."""
        from sqlalchemy import select, update

        from app.database import AsyncSessionLocal
        from app.models.sequence import Sequence, SequenceStatus

        campaign_name = entities.get("campaign_name", "")

        async with AsyncSessionLocal() as db:
            if campaign_name:
                result = await db.execute(
                    select(Sequence).where(
                        Sequence.name.ilike(f"%{campaign_name}%"),
                        Sequence.status == SequenceStatus.active,
                    )
                )
                seq = result.scalars().first()
                if seq:
                    seq.status = SequenceStatus.paused
                    await db.commit()
                    return {
                        "type": "text",
                        "content": f"Paused campaign **{seq.name}**. Use \"resume {seq.name}\" to restart it.",
                    }
                return {
                    "type": "text",
                    "content": f"No active campaign found matching \"{campaign_name}\". Check `/sequences` for active campaigns.",
                }

            # List active campaigns to choose from
            result = await db.execute(
                select(Sequence).where(Sequence.status == SequenceStatus.active).limit(10)
            )
            active = result.scalars().all()
            if not active:
                return {"type": "text", "content": "No active campaigns to pause."}

            lines = ["Which campaign would you like to pause?\n"]
            for s in active:
                lines.append(f"- **{s.name}**")
            return {
                "type": "question",
                "content": "\n".join(lines),
                "options": [s.name for s in active],
            }

    async def _handle_resume_campaign(
        self, entities: dict[str, Any], user_id: str
    ) -> dict[str, Any]:
        """Resume a paused campaign/sequence."""
        from sqlalchemy import select

        from app.database import AsyncSessionLocal
        from app.models.sequence import Sequence, SequenceStatus

        campaign_name = entities.get("campaign_name", "")

        async with AsyncSessionLocal() as db:
            if campaign_name:
                result = await db.execute(
                    select(Sequence).where(
                        Sequence.name.ilike(f"%{campaign_name}%"),
                        Sequence.status == SequenceStatus.paused,
                    )
                )
                seq = result.scalars().first()
                if seq:
                    seq.status = SequenceStatus.active
                    await db.commit()
                    return {
                        "type": "text",
                        "content": f"Resumed campaign **{seq.name}**. It's now active and sending.",
                    }
                return {
                    "type": "text",
                    "content": f"No paused campaign found matching \"{campaign_name}\".",
                }

            result = await db.execute(
                select(Sequence).where(Sequence.status == SequenceStatus.paused).limit(10)
            )
            paused = result.scalars().all()
            if not paused:
                return {"type": "text", "content": "No paused campaigns to resume."}

            lines = ["Which campaign would you like to resume?\n"]
            for s in paused:
                lines.append(f"- **{s.name}**")
            return {
                "type": "question",
                "content": "\n".join(lines),
                "options": [s.name for s in paused],
            }

    def _handle_configure_integration(self, entities: dict[str, Any]) -> dict[str, Any]:
        """Guide user through integration setup."""
        integration = entities.get("integration_name", "").lower()

        guides = {
            "hubspot": (
                "**Setting up HubSpot:**\n"
                "1. Go to **Settings → Integrations → HubSpot**\n"
                "2. Enter your HubSpot API key (found in HubSpot → Settings → Integrations → API key)\n"
                "3. Enable **Breeze AI** for smart content and prospecting\n"
                "4. Save and test the connection"
            ),
            "zoominfo": (
                "**Setting up ZoomInfo:**\n"
                "1. Go to **Settings → Integrations → ZoomInfo**\n"
                "2. Enter your Client ID and Client Secret\n"
                "3. Enable **Copilot** for GTM intelligence\n"
                "4. Save and test the connection"
            ),
            "apollo": (
                "**Setting up Apollo:**\n"
                "1. Go to **Settings → Integrations → Apollo**\n"
                "2. Enter your Apollo API key\n"
                "3. Enable **AI Scoring** for lead prioritization\n"
                "4. Save and test the connection"
            ),
        }

        if integration in guides:
            return {"type": "text", "content": guides[integration]}

        return {
            "type": "text",
            "content": (
                "Which integration would you like to set up?\n\n"
                "- **HubSpot** — CRM sync + Breeze AI\n"
                "- **ZoomInfo** — Lead intelligence + Copilot\n"
                "- **Apollo** — Enrichment + AI scoring\n"
                "- **AWS SES** — Email sending\n"
                "- **Twilio** — SMS channel\n"
                "- **LinkedIn** — Social outreach\n\n"
                "Just tell me which one!"
            ),
        }

    async def _handle_check_integrations(
        self, user_id: str = "", db=None
    ) -> dict[str, Any]:
        """Show current integration status including AI agent status."""
        integrations = []

        def _status(enabled: bool, has_key: bool) -> str:
            if enabled and has_key:
                return "Connected"
            if has_key:
                return "Key set, not enabled"
            return "Not configured"

        integrations.append(
            f"- **HubSpot Breeze**: {_status(settings.HUBSPOT_BREEZE_ENABLED, bool(settings.HUBSPOT_API_KEY))}"
        )
        integrations.append(
            f"- **ZoomInfo Copilot**: {_status(settings.ZOOMINFO_COPILOT_ENABLED, bool(settings.ZOOMINFO_API_KEY))}"
        )
        integrations.append(
            f"- **Apollo AI**: {_status(settings.APOLLO_AI_ENABLED, bool(settings.APOLLO_API_KEY))}"
        )
        integrations.append(
            f"- **AWS SES**: {'Configured' if settings.AWS_ACCESS_KEY_ID else 'Not configured'}"
        )
        integrations.append(
            f"- **Twilio SMS**: {'Configured' if settings.TWILIO_ACCOUNT_SID else 'Not configured'}"
        )
        integrations.append(
            f"- **LinkedIn**: {'Configured' if settings.LINKEDIN_OAUTH_CLIENT_ID else 'Not configured'}"
        )

        # Add AI agent status if db session is available
        agent_section = ""
        if db is not None and user_id:
            try:
                uid = UUID(user_id) if isinstance(user_id, str) else user_id
                agent_statuses = await AgentOrchestrator.get_agent_status(db, uid)
                agent_lines = []
                for agent in agent_statuses:
                    name = agent["agent_name"].capitalize()
                    status = "Configured" if agent["configured"] else "Not configured"
                    source = ""
                    if agent["configured"]:
                        source = " (DB key)" if agent["has_db_key"] else " (env key)"
                    agent_lines.append(f"- **{name} Agent**: {status}{source}")
                agent_section = "\n\n**AI Agent Status**\n\n" + "\n".join(agent_lines)
            except Exception as exc:
                logger.warning("Failed to fetch agent status: %s", sanitize_error(exc))

        return {
            "type": "text",
            "content": "**Integration Status**\n\n" + "\n".join(integrations) + agent_section,
        }

    async def _handle_send_sms(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Dispatch SMS sending to Twilio agent."""
        phone_number = entities.get("phone_number", "")
        sms_body = entities.get("sms_body", "")

        if not phone_number or not sms_body:
            return {
                "type": "text",
                "content": (
                    "To send an SMS, I need:\n"
                    "- **Phone number** (e.g., +15551234567)\n"
                    "- **Message body**\n\n"
                    "Example: \"Send SMS to +15551234567: Hello from FortressFlow!\""
                ),
            }

        if db is None:
            return {"type": "text", "content": "Unable to send SMS — no database session available."}

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        result = await AgentOrchestrator.dispatch(
            db=db,
            agent_name="twilio",
            action="send_sms",
            params={"to": phone_number, "body": sms_body},
            user_id=uid,
        )

        if result.get("status") == "success":
            return {
                "type": "text",
                "content": f"SMS sent to **{phone_number}** successfully! (latency: {result.get('latency_ms', 'N/A')}ms)",
            }
        return {
            "type": "text",
            "content": f"Failed to send SMS: {result.get('error', 'Unknown error')}. Check your Twilio configuration in **Settings → Integrations**.",
        }

    async def _handle_sync_crm(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Dispatch CRM sync to HubSpot agent."""
        if db is None:
            return {"type": "text", "content": "Unable to sync CRM — no database session available."}

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        result = await AgentOrchestrator.dispatch(
            db=db,
            agent_name="hubspot",
            action="pull_updates",
            params={"since": "2020-01-01T00:00:00Z"},
            user_id=uid,
        )

        if result.get("status") == "success":
            return {
                "type": "text",
                "content": (
                    "HubSpot CRM sync initiated successfully!\n\n"
                    f"Latency: {result.get('latency_ms', 'N/A')}ms\n\n"
                    "Contacts, deals, and companies will be synced. "
                    "Check the **Leads** page for updated data."
                ),
            }
        return {
            "type": "text",
            "content": f"CRM sync failed: {result.get('error', 'Unknown error')}. Check your HubSpot API key in **Settings → Integrations**.",
        }

    async def _handle_search_company(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Dispatch company search to ZoomInfo agent."""
        company_query = entities.get("company_query", "")

        if not company_query:
            return {
                "type": "text",
                "content": "What company would you like to search for? Provide a company name or search term.",
            }

        if db is None:
            return {"type": "text", "content": "Unable to search — no database session available."}

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        result = await AgentOrchestrator.dispatch(
            db=db,
            agent_name="zoominfo",
            action="search_companies",
            params={"filters": {"companyName": company_query}},
            user_id=uid,
        )

        if result.get("status") == "success":
            data = result.get("result", {})
            return {
                "type": "text",
                "content": (
                    f"Company search results for **{company_query}**:\n\n"
                    f"{json.dumps(data, indent=2, default=str)[:2000]}\n\n"
                    f"Latency: {result.get('latency_ms', 'N/A')}ms"
                ),
            }
        return {
            "type": "text",
            "content": f"Company search failed: {result.get('error', 'Unknown error')}. Check your ZoomInfo API key in **Settings → Integrations**.",
        }

    async def _handle_ai_generate(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Dispatch AI content generation to Groq agent."""
        ai_prompt = entities.get("ai_prompt", "")

        if not ai_prompt:
            return {
                "type": "text",
                "content": "What would you like me to generate? Provide a prompt or topic.",
            }

        if db is None:
            return {"type": "text", "content": "Unable to generate content — no database session available."}

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        result = await AgentOrchestrator.dispatch(
            db=db,
            agent_name="groq",
            action="chat",
            params={"messages": [{"role": "user", "content": ai_prompt}]},
            user_id=uid,
        )

        if result.get("status") == "success":
            content = result.get("result", "")
            return {
                "type": "text",
                "content": f"**AI Generated Content:**\n\n{content}",
            }
        return {
            "type": "text",
            "content": f"Content generation failed: {result.get('error', 'Unknown error')}. Check your Groq/OpenAI API key in **Settings → Integrations**.",
        }

    async def _handle_plan_outreach(
        self, entities: dict[str, Any], message: str, user_id: str, db=None
    ) -> dict[str, Any]:
        """Handle complex multi-step outreach planning requests."""
        if db is None:
            return {"type": "text", "content": "Unable to plan outreach — no database session available."}

        try:
            from app.services.agents.orchestrator import AgentOrchestrator
            from app.services.agents.workflow_planner import WorkflowPlanner

            uid = UUID(user_id) if isinstance(user_id, str) else user_id
            planner = WorkflowPlanner()

            # Get agent statuses
            agent_statuses = await AgentOrchestrator.get_agent_status(db, uid)

            # Create the plan
            plan = await planner.plan(db, uid, message, agent_statuses)

            # Format the response
            parts = []
            understanding = plan.get("understanding", message)
            parts.append(f"I understand you want to: **{understanding}**\n")

            # Show outreach options if available
            outreach_options = plan.get("outreach_options")
            if outreach_options:
                target = outreach_options.get("target", "")
                parts.append(f"**Target:** {target}\n")

                sourcing = outreach_options.get("lead_sourcing", {})
                existing = sourcing.get("existing_leads", 0)
                parts.append(f"**Lead Sourcing**")
                parts.append(f"- Currently {existing} matching leads in your database")
                parts.append(f"- {sourcing.get('action_needed', '')}\n")

                parts.append("**Outreach Options**\n")
                for i, opt in enumerate(outreach_options.get("options", []), 1):
                    name = opt.get("name", "")
                    desc = opt.get("description", "")
                    channels = ", ".join(opt.get("channels", []))
                    reach = opt.get("estimated_reach", "N/A")
                    cost = opt.get("estimated_cost", "N/A")
                    reqs = opt.get("requirements", [])

                    parts.append(f"**Option {i}: {name}**")
                    parts.append(f"- {desc}")
                    parts.append(f"- Channels: {channels}")
                    parts.append(f"- Estimated reach: ~{reach}%")
                    parts.append(f"- Cost: {cost}")
                    req_lines = []
                    for req in reqs:
                        if isinstance(req, (list, tuple)) and len(req) == 2:
                            check = "+" if req[1] else "x"
                            req_lines.append(f"  - [{check}] {req[0]}")
                        else:
                            req_lines.append(f"  - {req}")
                    parts.extend(req_lines)
                    parts.append("")

                parts.append(outreach_options.get("next_steps", ""))
            else:
                # Show plan steps
                steps = plan.get("steps", [])
                if steps:
                    parts.append("**Execution Plan:**\n")
                    for step in steps:
                        sn = step.get("step", "?")
                        agent = step.get("agent", "?")
                        desc = step.get("description", "")
                        parts.append(f"{sn}. **{agent}** — {desc}")
                    parts.append("")

                warnings = plan.get("warnings", [])
                if warnings:
                    parts.append("**Warnings:**")
                    for w in warnings:
                        parts.append(f"- {w}")
                    parts.append("")

                est = plan.get("estimated_time", "")
                if est:
                    parts.append(f"Estimated time: {est}")

                plan_id = plan.get("plan_id", "")
                if plan_id:
                    parts.append(f"\nSay **\"go\"** or **\"execute\"** to run this plan. (Plan ID: {plan_id})")

            return {
                "type": "text",
                "content": "\n".join(parts),
            }

        except Exception as exc:
            logger.exception("Plan outreach failed: %s", exc)
            return {
                "type": "text",
                "content": f"Failed to create outreach plan: {sanitize_error(exc)}",
            }


    async def _handle_apollo_search(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Search Apollo for contacts or companies."""
        if db is None:
            return {"type": "text", "content": "Unable to search — no database session available."}

        query = entities.get("apollo_query", "") or entities.get("specialty", "") or entities.get("company_query", "")
        location = entities.get("location", "")
        count = int(entities.get("count", 25))

        if not query and not location:
            return {
                "type": "text",
                "content": (
                    "What would you like to search for in Apollo? I can search for:\n"
                    "- **People**: dentists, office managers, DSO executives\n"
                    "- **Companies**: dental practices, DSOs, dental labs\n\n"
                    "Example: \"Find periodontists in Denver\" or \"Search for DSOs in Texas\""
                ),
            }

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        # Determine if searching people or organizations
        is_org_search = any(kw in query.lower() for kw in ["company", "companies", "organization", "practice", "dso", "lab"])

        if is_org_search:
            result = await AgentOrchestrator.dispatch(
                db=db, agent_name="apollo", action="search_organizations",
                params={"query": query, "locations": [location] if location else None, "per_page": min(count, 100)},
                user_id=uid,
            )
        else:
            result = await AgentOrchestrator.dispatch(
                db=db, agent_name="apollo", action="search_people",
                params={"query": query, "location": location, "per_page": min(count, 100)},
                user_id=uid,
            )

        if result.get("status") == "success":
            data = result.get("result", {})
            return {
                "type": "text",
                "content": (
                    f"**Apollo Search Results** for \"{query}\"{f' in {location}' if location else ''}:\n\n"
                    f"{json.dumps(data, indent=2, default=str)[:3000]}\n\n"
                    f"Latency: {result.get('latency_ms', 'N/A')}ms"
                ),
            }
        return {"type": "text", "content": f"Apollo search failed: {result.get('error', 'Unknown error')}. Check your Apollo API key in Settings."}

    async def _handle_apollo_sequence(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Manage Apollo email sequences."""
        if db is None:
            return {"type": "text", "content": "Unable to manage sequences — no database session available."}

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        result = await AgentOrchestrator.dispatch(
            db=db, agent_name="apollo", action="search_sequences",
            params={"query": entities.get("sequence_name", "")},
            user_id=uid,
        )

        if result.get("status") == "success":
            data = result.get("result", {})
            return {"type": "text", "content": f"**Apollo Sequences:**\n\n{json.dumps(data, indent=2, default=str)[:3000]}"}
        return {"type": "text", "content": f"Failed to fetch sequences: {result.get('error', 'Unknown error')}"}

    async def _handle_linkedin_post(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Generate LinkedIn content via Taplio agent."""
        if db is None:
            return {"type": "text", "content": "Unable to generate content — no database session available."}

        topic = entities.get("linkedin_topic", "") or entities.get("ai_prompt", "")
        if not topic:
            return {"type": "text", "content": "What topic would you like the LinkedIn post to be about?"}

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        result = await AgentOrchestrator.dispatch(
            db=db, agent_name="taplio", action="generate_linkedin_post",
            params={"topic": topic, "tone": entities.get("tone", "professional"), "format": entities.get("linkedin_format", "text")},
            user_id=uid,
        )

        if result.get("status") == "success":
            content = result.get("result", "")
            return {"type": "text", "content": f"**Generated LinkedIn Post:**\n\n{content}\n\nWant me to schedule this or make changes?"}
        return {"type": "text", "content": f"Post generation failed: {result.get('error', 'Unknown error')}"}

    async def _handle_linkedin_dm(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Compose personalized LinkedIn DM via Taplio agent."""
        if db is None:
            return {"type": "text", "content": "Unable to compose DM — no database session available."}

        recipient = entities.get("recipient_name", "") or entities.get("name", "")
        if not recipient:
            return {"type": "text", "content": "Who would you like to send a LinkedIn message to? Provide their name or profile details."}

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        result = await AgentOrchestrator.dispatch(
            db=db, agent_name="taplio", action="compose_dm",
            params={
                "recipient_name": recipient,
                "recipient_title": entities.get("title", ""),
                "recipient_company": entities.get("company", ""),
                "context": entities.get("context", "dental outreach"),
                "tone": entities.get("tone", "professional"),
            },
            user_id=uid,
        )

        if result.get("status") == "success":
            dm = result.get("result", "")
            return {"type": "text", "content": f"**Draft LinkedIn DM for {recipient}:**\n\n{dm}\n\nWant me to send this or make changes?"}
        return {"type": "text", "content": f"DM generation failed: {result.get('error', 'Unknown error')}"}

    async def _handle_send_whatsapp(
        self, entities: dict[str, Any], user_id: str, db=None
    ) -> dict[str, Any]:
        """Send WhatsApp message via Twilio agent."""
        phone = entities.get("whatsapp_number", "") or entities.get("phone_number", "")
        body = entities.get("whatsapp_body", "") or entities.get("sms_body", "")

        if not phone or not body:
            return {
                "type": "text",
                "content": (
                    "To send a WhatsApp message, I need:\n"
                    "- **Phone number** (with country code, e.g., +15551234567)\n"
                    "- **Message body**\n\n"
                    "Example: \"Send WhatsApp to +15551234567: Hello from FortressFlow!\""
                ),
            }

        if db is None:
            return {"type": "text", "content": "Unable to send — no database session available."}

        uid = UUID(user_id) if isinstance(user_id, str) else user_id
        result = await AgentOrchestrator.dispatch(
            db=db, agent_name="twilio", action="send_whatsapp",
            params={"to": f"whatsapp:{phone}" if not phone.startswith("whatsapp:") else phone, "body": body},
            user_id=uid,
        )

        if result.get("status") == "success":
            return {"type": "text", "content": f"WhatsApp message sent to **{phone}** successfully!"}
        return {"type": "text", "content": f"Failed to send WhatsApp: {result.get('error', 'Unknown error')}. Check your Twilio configuration."}


    def _handle_help(self) -> dict[str, Any]:
        """Return help text with all v2.0 capabilities."""
        return {
            "type": "text",
            "content": (
                "**🚀 FortressFlow AI Assistant — Full Capabilities**\n\n"
                "**🎯 Marketing Agent** (15 skills)\n"
                "- \"Score this lead\" — AI lead scoring\n"
                "- \"Create an outbound sequence for dentists\" — multi-step sequences\n"
                "- \"Write a LinkedIn post about dental AI\" — social content\n"
                "- \"Translate this email to Spanish\" — 10 languages supported\n"
                "- \"Segment my customers\" — behavioral segmentation\n"
                "- \"Create event promotion for our webinar\" — event marketing\n"
                "- \"Generate landing page copy\" — conversion-optimized copy\n"
                "- \"Best time to send emails?\" — send time optimization\n"
                "- \"A/B test variants\" — variant generation\n\n"
                "**💼 Sales Agent** (15 skills)\n"
                "- \"Enrich this company\" — firmographic data\n"
                "- \"Pipeline status\" — deal management\n"
                "- \"Schedule a meeting\" — meeting booking\n"
                "- \"Generate a quote\" — proposals & pricing\n"
                "- \"Score this opportunity\" — MEDDIC analysis\n"
                "- \"Revenue forecast\" — pipeline projections\n"
                "- \"Account insights for Acme Corp\" — ABM intelligence\n"
                "- \"Renewal recommendations\" — churn prevention\n\n"
                "**📊 Analytics & Intelligence**\n"
                "- \"Churn risk\" — predictive churn detection\n"
                "- \"Dedup health\" — duplicate contact status\n"
                "- \"Experiment results\" — A/B test outcomes\n"
                "- \"Community stats\" — member & waitlist data\n"
                "- \"Call analytics\" — meeting sentiment & action items\n\n"
                "**🔌 Integrations**\n"
                "- **HubSpot** — full CRM (contacts, deals, pipelines, workflows)\n"
                "- **ZoomInfo** — company/person enrichment, intent signals\n"
                "- **Apollo** — 210M+ contact search, sequences\n"
                "- **Twilio** — SMS, voice, WhatsApp\n"
                "- **Taplio** — LinkedIn automation via Zapier\n\n"
                "**⚡ Slash Commands:** /agents /churn /dedup /experiments /community "
                "/calls /plugins /score /enrich /forecast /translate\n\n"
                "Just type in plain English — I'll route to the right agent!"
            ),
        }

    # ── LLM Call ─────────────────────────────────────────────────────────

    async def _call_llm(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 512,
    ) -> str:
        """Call LLM with Groq primary / OpenAI fallback. Returns raw text."""
        # Try Groq first
        groq_key = getattr(settings, "GROQ_API_KEY", "")
        if groq_key:
            try:
                from groq import AsyncGroq

                client = AsyncGroq(api_key=groq_key)
                resp = await client.chat.completions.create(
                    model=settings.GROQ_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("Groq classification failed: %s", sanitize_error(exc))

        # OpenAI fallback
        openai_key = getattr(settings, "OPENAI_API_KEY", "")
        if openai_key:
            try:
                from openai import AsyncOpenAI

                client = AsyncOpenAI(api_key=openai_key)
                resp = await client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                return resp.choices[0].message.content or ""
            except Exception as exc:
                logger.warning("OpenAI classification failed: %s", sanitize_error(exc))

        # No LLM available — return empty
        return ""

    def _parse_classification(self, raw: str) -> IntentResult:
        """Parse LLM JSON response into an IntentResult."""
        if not raw:
            return IntentResult(intent="unknown", confidence=0.0)

        try:
            # Strip markdown code fences if present
            cleaned = raw.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1] if "\n" in cleaned else cleaned[3:]
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()

            data = json.loads(cleaned)
            intent = data.get("intent", "unknown")
            if intent not in INTENTS:
                intent = "unknown"

            return IntentResult(
                intent=intent,
                confidence=float(data.get("confidence", 0.0)),
                entities=data.get("entities", {}),
                missing_required=data.get("missing_required", []),
                raw_response=raw,
            )
        except (json.JSONDecodeError, ValueError, TypeError) as exc:
            logger.warning("Failed to parse classification response: %s — raw: %s", exc, raw[:200])
            return IntentResult(intent="unknown", confidence=0.0, raw_response=raw)
