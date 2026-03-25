"""Platform Agent Intelligence Layer — context-aware smart operations.

Sits between the orchestrator and raw platform agents. Handles:
- Smart field mapping (FortressFlow -> HubSpot, Apollo, ZoomInfo)
- Industry search defaults for dental B2B
- Natural language lead search parsing
- Outreach options builder (now with Apollo sequences + Taplio LinkedIn)
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.agents.prompt_engine import PromptEngine

logger = logging.getLogger(__name__)


class AgentIntelligence:
    """Context-aware intelligence layer for platform agents."""

    # ── Smart Field Mapping: FortressFlow → HubSpot ──────────────────────

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
        "website": "website",
        "linkedin_url": "linkedin_company_page",
        "annual_revenue": "annualrevenue",
        "dso_affiliation": "dso_affiliation",
        "lead_source": "hs_lead_source",
        "lifecycle_stage": "lifecyclestage",
    }

    # ── Smart Field Mapping: FortressFlow → Apollo ───────────────────────

    APOLLO_FIELD_MAP = {
        "first_name": "first_name",
        "last_name": "last_name",
        "email": "email",
        "phone": "phone_numbers[0].sanitized_number",
        "company": "organization.name",
        "company_domain": "organization.primary_domain",
        "title": "title",
        "linkedin_url": "linkedin_url",
        "city": "city",
        "state": "state",
        "country": "country",
        "seniority": "seniority",
        "department": "departments[0]",
        "employee_count": "organization.estimated_num_employees",
        "industry": "organization.industry",
        "company_revenue": "organization.annual_revenue_printed",
        "specialty": "title",  # Apollo uses title for dental specialty context
        "practice_size": "organization.estimated_num_employees",
    }

    # ── Taplio LinkedIn Content Defaults ─────────────────────────────────

    TAPLIO_CONTENT_DEFAULTS = {
        "post_formats": {
            "thought_leadership": {
                "structure": "Hook → Insight → Data Point → Takeaway → CTA",
                "length": 1300,
                "example_hooks": [
                    "Most dental practices are leaving $200K+ on the table annually.",
                    "I analyzed 500 dental practices. Here's what the top 10% do differently.",
                    "The #1 reason dental patients don't return has nothing to do with clinical care.",
                ],
            },
            "listicle": {
                "structure": "Hook → Numbered list (5-10 items) → Summary → CTA",
                "length": 1500,
                "example_hooks": [
                    "7 things I wish I knew before opening my dental practice:",
                    "5 dental technology trends that will define 2026:",
                ],
            },
            "story": {
                "structure": "Situation → Challenge → Action → Result → Lesson",
                "length": 1200,
                "example_hooks": [
                    "3 years ago, a solo dental practice was on the verge of closing.",
                    "I made a $50K mistake in my dental practice. Here's what I learned.",
                ],
            },
            "data_insight": {
                "structure": "Surprising stat → Context → Analysis → Implications → Question",
                "length": 1000,
                "example_hooks": [
                    "65% of dental practices don't track their patient retention rate.",
                    "The average dental practice spends $47K/year on marketing. Most can't measure ROI.",
                ],
            },
        },
        "dental_topics": [
            "Practice growth and patient acquisition",
            "DSO trends and consolidation",
            "Dental technology adoption",
            "Team management and staffing",
            "Patient experience and retention",
            "Insurance and billing optimization",
            "Digital dentistry workflows",
            "Dental practice valuation and exit planning",
            "HIPAA compliance and cybersecurity",
            "Dental marketing and branding",
        ],
        "optimal_schedule": {
            "best_days": ["Tuesday", "Wednesday", "Thursday"],
            "best_times": ["07:00", "07:30", "08:00", "12:00", "12:30"],
            "avoid_days": ["Saturday", "Sunday"],
            "avoid_times": ["Before 06:00", "After 20:00"],
        },
        "dm_templates": {
            "dentist_owner": (
                "Hi Dr. {{first_name}} — I noticed {{company}} is growing in the {{location}} area. "
                "We've been helping dental practices like yours {{value_prop}}. "
                "Would love to share some insights. Open to a quick chat?"
            ),
            "office_manager": (
                "Hi {{first_name}} — managing a dental office is no small feat. "
                "I wanted to share something that's been helping offices like {{company}} "
                "{{value_prop}}. Worth a 5-min look?"
            ),
            "dso_executive": (
                "Hi {{first_name}} — {{company}}'s growth has been impressive. "
                "We work with several DSOs on {{value_prop}} at scale. "
                "Would be great to compare notes. Open to connecting?"
            ),
        },
    }

    # ── ZoomInfo Search Defaults ─────────────────────────────────────────

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

        Now considers Apollo as a primary search source alongside ZoomInfo,
        and includes Taplio LinkedIn as a follow-up engagement channel.

        Example input: {"specialty": "general dentists", "location": "Denver, CO", "count": 100}
        """
        specialty = query_params.get("specialty", "dentists")
        location = query_params.get("location", "")
        count = int(query_params.get("count", 50))
        source = query_params.get("source", "auto")  # auto, zoominfo, apollo

        # Build search params with dental defaults
        zoominfo_params = {
            **self.ZOOMINFO_SEARCH_DEFAULTS,
            "job_title": specialty,
            "limit": count,
        }
        if location:
            zoominfo_params["location"] = location

        apollo_params = {
            "q_person_title": f"{specialty} OR DDS OR DMD",
            "per_page": min(count, 100),
            "page": 1,
        }
        if location:
            apollo_params["person_locations"] = [location]

        target_desc = f"{count} {specialty} in {location}" if location else f"{count} {specialty}"

        steps = []
        step_num = 1

        # Step 1: Search for leads (ZoomInfo or Apollo based on preference/availability)
        if source in ("auto", "zoominfo"):
            steps.append({
                "step": step_num,
                "agent": "zoominfo",
                "action": "search_people",
                "description": f"Search ZoomInfo for {specialty} in {location or 'all areas'}",
                "params": zoominfo_params,
                "depends_on": None,
            })
            step_num += 1

        if source in ("auto", "apollo"):
            steps.append({
                "step": step_num,
                "agent": "apollo",
                "action": "search_people",
                "description": f"Search Apollo for {specialty} in {location or 'all areas'}",
                "params": apollo_params,
                "depends_on": None,
            })
            step_num += 1

        # Step 2: Verify emails
        steps.append({
            "step": step_num,
            "agent": "zoominfo",
            "action": "verify_email",
            "description": "Verify email addresses for found contacts",
            "params": {},
            "depends_on": 1,
        })
        step_num += 1

        # Step 3: Import to HubSpot CRM
        steps.append({
            "step": step_num,
            "agent": "hubspot",
            "action": "bulk_create_contacts",
            "description": "Import verified contacts into HubSpot CRM",
            "params": {},
            "depends_on": step_num - 1,
        })

        plan = {
            "target": target_desc,
            "steps": steps,
        }
        return plan

    async def smart_create_campaign(
        self, db: AsyncSession, user_id: UUID, params: dict
    ) -> dict:
        """Build a full campaign plan from natural language parameters.

        Now includes Apollo sequences and LinkedIn via Taplio as channel options.
        """
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

        step_num = 3

        if "sms" in channels:
            steps.append({
                "step": step_num,
                "agent": "twilio",
                "action": "send_sms",
                "description": "Set up SMS follow-up for non-responders",
                "params": {},
                "depends_on": 1,
            })
            step_num += 1

        if "whatsapp" in channels:
            steps.append({
                "step": step_num,
                "agent": "twilio",
                "action": "send_whatsapp",
                "description": "Set up WhatsApp follow-up for high-priority leads",
                "params": {},
                "depends_on": 1,
            })
            step_num += 1

        if "apollo_sequence" in channels:
            steps.append({
                "step": step_num,
                "agent": "apollo",
                "action": "add_contacts_to_sequence",
                "description": "Enroll contacts in Apollo email sequence for automated follow-up",
                "params": {},
                "depends_on": 1,
            })
            step_num += 1

        if "linkedin" in channels:
            steps.append({
                "step": step_num,
                "agent": "taplio",
                "action": "compose_dm",
                "description": "Compose personalized LinkedIn DMs for target contacts",
                "params": {"tone": tone},
                "depends_on": 1,
            })
            step_num += 1

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

    async def map_fields_to_apollo(
        self, lead_data: dict, user_id: UUID | None = None, db: AsyncSession | None = None
    ) -> dict:
        """Translate FortressFlow lead fields -> Apollo contact fields.

        Uses custom mappings from DB if available, falls back to APOLLO_FIELD_MAP.
        """
        # Try loading custom mappings from DB
        custom_map = {}
        if db is not None and user_id is not None:
            custom_map = await self.prompt_engine.get_field_mappings(db, user_id, "apollo")

        # Merge: custom overrides default
        field_map = {**self.APOLLO_FIELD_MAP, **custom_map}

        mapped = {}
        for ff_field, value in lead_data.items():
            apollo_field = field_map.get(ff_field)
            if apollo_field:
                # Handle nested field paths (e.g., "organization.name")
                if "." in apollo_field or "[" in apollo_field:
                    # For nested paths, store under the top-level key for API submission
                    top_key = apollo_field.split(".")[0].split("[")[0]
                    if top_key not in mapped:
                        mapped[top_key] = {}
                    # For simple cases, just use the FF field name
                    mapped[ff_field] = value
                else:
                    mapped[apollo_field] = value
            else:
                mapped[ff_field] = value

        return mapped

    async def build_outreach_options(
        self, db: AsyncSession, user_id: UUID, params: dict
    ) -> dict:
        """Given a target description, return available outreach options.

        Now includes Apollo sequences and LinkedIn via Taplio as options.
        """
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
            "description": "5-step professional email sequence over 14 days via AWS SES",
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

        # Option 2: Apollo Email Sequence
        apollo_ready = "apollo" in configured
        if apollo_ready:
            options.append({
                "name": "Apollo Email Sequence",
                "description": "Automated multi-step sequence via Apollo with built-in deliverability",
                "channels": ["email"],
                "estimated_reach": 90,
                "compliance_status": "ready",
                "estimated_cost": "Included in Apollo plan",
                "requirements": [
                    ("Apollo configured", True),
                    ("Apollo email account connected", True),
                    ("Sequence created in Apollo", True),
                ],
            })

        # Option 3: Multi-Channel Blitz
        twilio_ready = "twilio" in configured
        options.append({
            "name": "Multi-Channel Blitz",
            "description": "Email + SMS + LinkedIn coordinated sequence",
            "channels": ["email", "sms", "linkedin"],
            "estimated_reach": 98,
            "compliance_status": "ready" if twilio_ready else "needs_sms_consent",
            "estimated_cost": "~$2.50/contact (SES + Twilio + Taplio)",
            "requirements": [
                ("SES configured", True),
                ("Twilio configured", "twilio" in configured),
                ("Taplio configured", "taplio" in configured),
                ("TCPA consent", twilio_ready),
            ],
        })

        # Option 4: LinkedIn First (via Taplio)
        taplio_ready = "taplio" in configured
        options.append({
            "name": "LinkedIn First",
            "description": "LinkedIn connection requests + DMs, followed by email for non-responders",
            "channels": ["linkedin", "email"],
            "estimated_reach": 65,
            "compliance_status": "ready" if taplio_ready else "needs_taplio_setup",
            "estimated_cost": "$0.05/email + Taplio subscription",
            "requirements": [
                ("Taplio configured", "taplio" in configured),
                ("SES configured", True),
            ],
        })

        # Option 5: WhatsApp Outreach
        if twilio_ready:
            options.append({
                "name": "WhatsApp Business Outreach",
                "description": "WhatsApp messages with approved templates, ideal for DSO contacts",
                "channels": ["whatsapp"],
                "estimated_reach": 75,
                "compliance_status": "ready",
                "estimated_cost": "~$0.05/message (Twilio WhatsApp)",
                "requirements": [
                    ("Twilio configured", True),
                    ("WhatsApp Business approved", True),
                    ("Content templates approved", True),
                ],
            })

        # Build lead sourcing info
        lead_sources = []
        if "zoominfo" in configured:
            lead_sources.append(
                f"ZoomInfo: search ~{count} dental contacts matching criteria"
            )
        if "apollo" in configured:
            lead_sources.append(
                f"Apollo: search 210M+ contacts for {target}"
            )
        if not lead_sources:
            lead_sources.append(
                "No lead source configured — add ZoomInfo or Apollo API key in Settings"
            )

        return {
            "target": target_desc,
            "options": options,
            "lead_sourcing": {
                "existing_leads": existing_leads,
                "zoominfo_available": "zoominfo" in configured,
                "apollo_available": "apollo" in configured,
                "taplio_available": "taplio" in configured,
                "sources": lead_sources,
                "action_needed": (
                    " | ".join(lead_sources)
                ),
            },
            "next_steps": "Tell me which option you'd like, or say 'go with email' to start immediately.",
        }
