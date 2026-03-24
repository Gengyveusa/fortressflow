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
    # Help
    "get_help": "How do I / what can you do / help",
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

        if intent == "get_help":
            return self._handle_help()

        # Fallback — unknown intent
        return {"type": "text", "content": ""}

    # ── Intent Handlers ──────────────────────────────────────────────────

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
                    action="search_contacts",
                    params={"limit": min(unenriched, 100)},
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
            action="full_sync",
            params={"user_id": str(user_id)},
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
            params={"query": company_query},
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

    def _handle_help(self) -> dict[str, Any]:
        """Return help text with available commands."""
        return {
            "type": "text",
            "content": (
                "**Here's what I can do:**\n\n"
                "**Lead Management**\n"
                "- \"Find periodontists in Texas\" — search your lead database\n"
                "- \"Import leads from CSV\" — guidance on importing\n"
                "- \"Enrich my leads\" — trigger ZoomInfo/Apollo enrichment\n\n"
                "**Campaigns**\n"
                "- \"Launch a campaign targeting oral surgeons in California\" — full campaign wizard\n"
                "- \"Pause the Texas campaign\" — pause an active sequence\n"
                "- \"Resume the Texas campaign\" — restart a paused sequence\n\n"
                "**Analytics**\n"
                "- \"How are we doing?\" — full performance overview\n"
                "- \"How's the Texas campaign?\" — specific campaign metrics\n"
                "- \"Check deliverability\" — email health report\n\n"
                "**Settings**\n"
                "- \"Set up HubSpot\" — integration setup guides\n"
                "- \"What's connected?\" — check integration status\n\n"
                "**AI Agents**\n"
                "- \"Send SMS to +1555... saying Hello\" — send a text message via Twilio\n"
                "- \"Sync my CRM\" — sync contacts/deals with HubSpot\n"
                "- \"Search for Acme Corp\" — company intelligence via ZoomInfo\n"
                "- \"Generate a cold email for dentists\" — AI content generation\n\n"
                "Just type in plain English — I'll figure out what you need!"
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
