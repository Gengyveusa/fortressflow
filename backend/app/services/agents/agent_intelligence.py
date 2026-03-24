"""Platform Agent Intelligence Layer — context-aware smart operations.

Sits between the orchestrator and raw platform agents. Handles:
- Smart field mapping (FortressFlow -> HubSpot)
- ZoomInfo dental industry search defaults
- Natural language lead search parsing
- Outreach options builder
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.prompt_engine import PromptEngine

logger = logging.getLogger(__name__)


class AgentIntelligence:
    """Context-aware intelligence layer for platform agents."""

    # ── Smart Field Mapping ──────────────────────────────────────────────

    HUBSPOT_FIELD_MAP = {
        "first_name": "firstname",
        "last_name": "lastname",
        "email": "email",
        "phone": "phone",
        "company": "company",
        "title": "jobtitle",
        "specialty": "dental_specialty",
        "practice_size": "numberofemployees",
        "location": "city",
        "state": "state",
        "zip": "zip",
        "npi_number": "npi_number",
        "lead_score": "hs_lead_status",
        "consent_status": "consent_status",
    }

    ZOOMINFO_SEARCH_DEFAULTS = {
        "industry": ["Health Care", "Dental"],
        "sub_industry": ["Dentists' Offices", "Dental Laboratories", "Dental Equipment"],
        "company_type": ["Private", "Subsidiary"],
        "sic_codes": ["8021", "8099", "5047"],
        "naics_codes": ["621210", "621310", "339114"],
    }

    def __init__(self):
        self.prompt_engine = PromptEngine()

    async def smart_search_leads(
        self, db: AsyncSession, user_id: UUID, query_params: dict
    ) -> dict:
        """Parse a natural language lead request into a multi-agent execution plan.

        Example input: {"specialty": "general dentists", "location": "Denver, CO", "count": 100}
        """
        specialty = query_params.get("specialty", "dentists")
        location = query_params.get("location", "")
        count = int(query_params.get("count", 50))

        # Build ZoomInfo search params with dental defaults
        search_params = {
            **self.ZOOMINFO_SEARCH_DEFAULTS,
            "job_title": specialty,
            "limit": count,
        }
        if location:
            search_params["location"] = location

        plan = {
            "target": f"{count} {specialty} in {location}" if location else f"{count} {specialty}",
            "steps": [
                {
                    "step": 1,
                    "agent": "zoominfo",
                    "action": "search_people",
                    "description": f"Search for {specialty} in {location or 'all areas'}",
                    "params": search_params,
                    "depends_on": None,
                },
                {
                    "step": 2,
                    "agent": "zoominfo",
                    "action": "verify_email",
                    "description": "Verify email addresses for found contacts",
                    "params": {},
                    "depends_on": 1,
                },
                {
                    "step": 3,
                    "agent": "hubspot",
                    "action": "bulk_create_contacts",
                    "description": "Import verified contacts into HubSpot CRM",
                    "params": {},
                    "depends_on": 2,
                },
            ],
        }
        return plan

    async def smart_create_campaign(
        self, db: AsyncSession, user_id: UUID, params: dict
    ) -> dict:
        """Build a full campaign plan from natural language parameters."""
        target = params.get("target_description", "dental professionals")
        channels = params.get("channels", ["email"])
        tone = params.get("tone", "professional")

        steps = [
            {
                "step": 1,
                "agent": "groq",
                "action": "generate_sequence_content",
                "description": f"Generate {tone} email sequence for {target}",
                "params": {
                    "sequence_type": "outbound",
                    "target_industry": "dental",
                    "tone": tone,
                    "num_steps": 5,
                },
                "depends_on": None,
            },
            {
                "step": 2,
                "agent": "groq",
                "action": "check_compliance",
                "description": "Check generated content for compliance",
                "params": {"channel": "email"},
                "depends_on": 1,
            },
        ]

        if "sms" in channels:
            steps.append({
                "step": len(steps) + 1,
                "agent": "twilio",
                "action": "send_sms",
                "description": "Set up SMS follow-up for non-responders",
                "params": {},
                "depends_on": 1,
            })

        return {
            "target": target,
            "channels": channels,
            "steps": steps,
        }

    async def map_fields_to_hubspot(
        self, lead_data: dict, user_id: UUID | None = None, db: AsyncSession | None = None
    ) -> dict:
        """Translate FortressFlow lead fields -> HubSpot properties.

        Uses custom mappings from DB if available, falls back to HUBSPOT_FIELD_MAP.
        """
        # Try loading custom mappings from DB
        custom_map = {}
        if db is not None and user_id is not None:
            custom_map = await self.prompt_engine.get_field_mappings(db, user_id, "hubspot")

        # Merge: custom overrides default
        field_map = {**self.HUBSPOT_FIELD_MAP, **custom_map}

        mapped = {}
        for ff_field, value in lead_data.items():
            hs_field = field_map.get(ff_field, ff_field)
            mapped[hs_field] = value

        return mapped

    async def build_outreach_options(
        self, db: AsyncSession, user_id: UUID, params: dict
    ) -> dict:
        """Given a target description, return available outreach options."""
        from app.services.agents.orchestrator import AgentOrchestrator

        target = params.get("target", "dental professionals")
        location = params.get("location", "")
        count = int(params.get("count", 100))

        target_desc = f"{count} {target}"
        if location:
            target_desc += f" in {location}"

        # Check which agents are configured
        agent_statuses = await AgentOrchestrator.get_agent_status(db, user_id)
        configured = {a["agent_name"] for a in agent_statuses if a["configured"]}

        # Count existing leads
        existing_leads = 0
        try:
            from sqlalchemy import func, select as sa_select
            from app.models.lead import Lead
            q = sa_select(func.count(Lead.id))
            if location:
                from sqlalchemy import String
                q = q.where(func.cast(Lead.enriched_data, String).ilike(f"%{location}%"))
            result = await db.execute(q)
            existing_leads = result.scalar_one() or 0
        except Exception:
            pass

        options = []

        # Option 1: Email Sequence (always available if groq is configured)
        email_ready = "groq" in configured
        options.append({
            "name": "Email Sequence",
            "description": "5-step professional email sequence over 14 days",
            "channels": ["email"],
            "estimated_reach": 92,
            "compliance_status": "ready" if email_ready else "needs_groq_setup",
            "estimated_cost": "$0.05/email via SES",
            "requirements": [
                ("SES configured", True),
                ("Email warmup > 30 days", True),
                ("Groq AI configured", "groq" in configured),
            ],
        })

        # Option 2: Multi-Channel Blitz
        twilio_ready = "twilio" in configured
        options.append({
            "name": "Multi-Channel Blitz",
            "description": "Email + LinkedIn + SMS coordinated sequence",
            "channels": ["email", "linkedin", "sms"],
            "estimated_reach": 98,
            "compliance_status": "ready" if twilio_ready else "needs_sms_consent",
            "estimated_cost": "~$2.50/contact (SES + Twilio)",
            "requirements": [
                ("SES configured", True),
                ("Twilio configured", "twilio" in configured),
                ("LinkedIn OAuth", False),
                ("TCPA consent", twilio_ready),
            ],
        })

        # Option 3: LinkedIn First
        options.append({
            "name": "LinkedIn First",
            "description": "LinkedIn connection requests with personalized notes, followed by email",
            "channels": ["linkedin", "email"],
            "estimated_reach": 65,
            "compliance_status": "ready",
            "estimated_cost": "$0.05/email + LinkedIn free",
            "requirements": [
                ("LinkedIn OAuth", False),
                ("SES configured", True),
            ],
        })

        return {
            "target": target_desc,
            "options": options,
            "lead_sourcing": {
                "existing_leads": existing_leads,
                "zoominfo_available": "zoominfo" in configured,
                "action_needed": (
                    f"ZoomInfo search will find ~{count} dentists matching your criteria"
                    if "zoominfo" in configured
                    else "ZoomInfo not configured — add your API key in Settings to search for leads"
                ),
            },
            "next_steps": "Tell me which option you'd like, or say 'go with email' to start immediately.",
        }
