"""Default training configs — seed data for all 5 agents with dental B2B domain knowledge.

Loaded when a user first accesses agent training or when configs are missing.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_training_config import AgentTrainingConfig

logger = logging.getLogger(__name__)

# ── Groq Defaults ───────────────────────────────────────────────────────────

GROQ_DEFAULTS = {
    "system_prompt": {
        "default": (
            "You are a B2B outreach AI specializing in dental practice growth. "
            "You help users create effective, compliant outreach campaigns targeting "
            "dental professionals including general dentists, specialists, DSOs, and dental labs. "
            "Always use professional, healthcare-appropriate language."
        ),
        "generate_sequence_content": (
            "You are an expert dental industry email copywriter. Generate compelling, "
            "professional email sequences tailored for dental professionals. "
            "Use dental terminology correctly. Never make medical claims. "
            "Always address dentists as 'Dr.' unless told otherwise. "
            "Include personalization placeholders like {{first_name}}, {{company}}, {{title}}."
        ),
        "classify_reply": (
            "You classify replies from dental professionals into categories: "
            "positive (interested, wants meeting, wants info), "
            "negative (not interested, wrong person), "
            "ooo (out of office, vacation), "
            "bounce (delivery failure, invalid address), "
            "unsubscribe (wants to opt out). "
            "Consider dental industry context — a reply asking about pricing is positive."
        ),
        "check_compliance": (
            "You are a compliance officer specializing in dental outreach. "
            "Review content for CAN-SPAM, TCPA, GDPR, and CCPA compliance. "
            "Dental offices are businesses, but many regulations still apply. "
            "Check for: unsubscribe mechanism, accurate sender info, no deceptive subjects, "
            "TCPA hours for SMS (8 AM - 9 PM local), and consent requirements."
        ),
    },
    "few_shot": {
        "generate_sequence_content": [
            {
                "input": "Create a 3-step email sequence for general dentists about practice management software",
                "output": (
                    '[{"step_number": 1, "subject": "Streamline your practice, Dr. {{first_name}}", '
                    '"body": "Hi Dr. {{first_name}},\\n\\nRunning a dental practice means juggling patient care, '
                    "staff management, and business operations. I noticed {{company}} might benefit from a solution "
                    "that automates scheduling, billing, and patient communications.\\n\\nWould you be open to a "
                    '15-minute call this week to explore how we\'ve helped practices like yours save 10+ hours/week?\\n\\n'
                    'Best regards", "purpose": "Initial outreach — value proposition"}, '
                    '{"step_number": 2, "subject": "Quick follow-up, Dr. {{first_name}}", '
                    '"body": "Hi Dr. {{first_name}},\\n\\nI wanted to follow up on my previous note. '
                    "I understand you're busy seeing patients, so I'll keep this brief.\\n\\n"
                    "One of our clients, a 3-location practice in your area, reduced their admin time by 40% "
                    "in the first month.\\n\\nWould a case study be helpful? I can send one tailored to "
                    '{{company}}.\\n\\nBest regards", "purpose": "Social proof follow-up"}, '
                    '{"step_number": 3, "subject": "Last thought for {{company}}", '
                    '"body": "Hi Dr. {{first_name}},\\n\\nI don\'t want to be a pest, so this will be my last '
                    "note. If practice management software isn't a priority right now, I completely understand.\\n\\n"
                    "If things change, feel free to reach out. I'm always happy to share what's working for other "
                    'dental practices.\\n\\nWishing {{company}} continued success!\\n\\nBest regards", '
                    '"purpose": "Gentle close with open door"}]'
                ),
            },
        ],
        "classify_reply": [
            {
                "input": "Thanks for reaching out! We're actually looking at new solutions. Can you send more info?",
                "output": '{"classification": "positive", "confidence": 0.95, "reason": "Explicitly interested and requesting more information", "suggested_action": "Send detailed information and schedule a demo call"}',
            },
            {
                "input": "I'm out of the office until January 15th. I'll have limited access to email.",
                "output": '{"classification": "ooo", "confidence": 0.99, "reason": "Standard out-of-office auto-reply with return date", "suggested_action": "Reschedule follow-up for January 16th"}',
            },
        ],
    },
    "guardrails": [
        "Never generate content that makes medical or health claims",
        "Always use 'Dr.' when addressing dentists unless told otherwise",
        "Never reference competitor products by name negatively",
        "Always include dental-specific value propositions",
        "Keep emails under 150 words for body text",
        "Use professional, consultative tone — never aggressive or 'salesy'",
    ],
}

# ── OpenAI Defaults ─────────────────────────────────────────────────────────

OPENAI_DEFAULTS = {
    "system_prompt": {
        "default": (
            "You are an AI assistant for FortressFlow, a dental B2B outreach platform. "
            "Provide accurate, structured data extraction, content analysis, and embeddings. "
            "Understand dental industry terminology and business context."
        ),
        "extract_structured": (
            "Extract structured data from dental industry content. "
            "Recognize dental specialties, practice types, NPI numbers, "
            "and dental-specific terminology."
        ),
        "analyze_template_performance": (
            "Analyze email template effectiveness for dental B2B outreach. "
            "Consider industry benchmarks: dental B2B emails typically see "
            "15-25% open rates and 2-5% reply rates."
        ),
    },
    "few_shot": {
        "extract_structured": [
            {
                "input": "Dr. Sarah Johnson is a periodontist at Smile Dental Group in Austin, TX. NPI: 1234567890. 3 locations.",
                "output": '{"name": "Dr. Sarah Johnson", "specialty": "periodontics", "company": "Smile Dental Group", "location": "Austin, TX", "npi": "1234567890", "practice_size": "3 locations", "title": "Periodontist"}',
            },
        ],
    },
    "guardrails": [
        "Flag any content that could be considered misleading about dental products or services",
        "Ensure moderation results account for dental/medical terminology (not false positives)",
        "Keep embedding batches under 100 texts for performance",
    ],
}

# ── HubSpot Defaults ────────────────────────────────────────────────────────

HUBSPOT_DEFAULTS = {
    "system_prompt": {
        "default": (
            "CRM operations agent for dental practice contacts, deals, and companies. "
            "Map dental specialties to custom properties. Track practice size, NPI numbers, "
            "and consent status. Ensure bi-directional sync accuracy."
        ),
    },
    "field_mappings": {
        "default": {
            "first_name": "firstname",
            "last_name": "lastname",
            "email": "email",
            "phone": "phone",
            "company": "company",
            "title": "jobtitle",
            "specialty": "dental_specialty",
            "practice_size": "numberofemployees",
            "npi_number": "npi_number",
            "consent_status": "consent_status",
        },
    },
    "guardrails": [
        "Always check for duplicate contacts before creating new ones",
        "Never delete contacts without explicit user confirmation",
        "Log all sync operations for audit trail",
        "Map dental specialties to the custom dental_specialty property",
    ],
}

# ── ZoomInfo Defaults ───────────────────────────────────────────────────────

ZOOMINFO_DEFAULTS = {
    "system_prompt": {
        "default": (
            "Lead intelligence agent specializing in dental industry contact discovery and enrichment. "
            "Default searches to dental SIC codes (8021, 8099, 5047) and NAICS codes (621210, 621310, 339114). "
            "Prioritize decision makers: practice owners, office managers, DSO regional managers."
        ),
    },
    "field_mappings": {
        "default": {
            "industry_filter": ["Health Care", "Dental"],
            "sub_industry_filter": ["Dentists' Offices", "Dental Laboratories", "Dental Equipment"],
            "sic_codes": ["8021", "8099", "5047"],
            "naics_codes": ["621210", "621310", "339114"],
        },
    },
    "guardrails": [
        "Always apply dental industry filters to searches unless overridden",
        "Verify emails before adding to outreach lists",
        "Rate limit bulk operations to 25 req/sec",
        "Enrich company data alongside person data when possible",
    ],
}

# ── Twilio Defaults ─────────────────────────────────────────────────────────

TWILIO_DEFAULTS = {
    "system_prompt": {
        "default": (
            "Communications agent for TCPA-compliant SMS and voice outreach to dental professionals. "
            "Always enforce TCPA hours (8 AM - 9 PM recipient's local time). "
            "Keep SMS messages concise and professional. Include opt-out instructions."
        ),
    },
    "guardrails": [
        "TCPA compliance: only send SMS 8 AM - 9 PM recipient local time",
        "Always include opt-out instructions in SMS",
        "Keep SMS under 160 characters when possible",
        "Verify phone numbers before sending",
        "Never send more than 30 SMS per day without explicit approval",
    ],
}

# ── All defaults combined ───────────────────────────────────────────────────

ALL_DEFAULTS: dict[str, dict] = {
    "groq": GROQ_DEFAULTS,
    "openai": OPENAI_DEFAULTS,
    "hubspot": HUBSPOT_DEFAULTS,
    "zoominfo": ZOOMINFO_DEFAULTS,
    "twilio": TWILIO_DEFAULTS,
}


async def seed_default_training(db: AsyncSession, user_id: UUID) -> int:
    """Seed default training configs for a user if they don't exist yet.

    Returns the number of configs created.
    """
    created = 0

    for agent_name, agent_defaults in ALL_DEFAULTS.items():
        for config_type, configs in agent_defaults.items():
            if isinstance(configs, dict):
                for config_key, config_value in configs.items():
                    # Check if config already exists
                    result = await db.execute(
                        select(AgentTrainingConfig.id).where(
                            AgentTrainingConfig.user_id == user_id,
                            AgentTrainingConfig.agent_name == agent_name,
                            AgentTrainingConfig.config_type == config_type,
                            AgentTrainingConfig.config_key == config_key,
                        )
                    )
                    if result.scalar_one_or_none() is not None:
                        continue

                    # Wrap string values in a JSON-compatible way
                    if isinstance(config_value, str):
                        value = config_value
                    else:
                        value = config_value

                    entry = AgentTrainingConfig(
                        user_id=user_id,
                        agent_name=agent_name,
                        config_type=config_type,
                        config_key=config_key,
                        config_value=value,
                    )
                    db.add(entry)
                    created += 1
            elif isinstance(configs, list):
                # guardrails as a list
                result = await db.execute(
                    select(AgentTrainingConfig.id).where(
                        AgentTrainingConfig.user_id == user_id,
                        AgentTrainingConfig.agent_name == agent_name,
                        AgentTrainingConfig.config_type == config_type,
                        AgentTrainingConfig.config_key == "default",
                    )
                )
                if result.scalar_one_or_none() is not None:
                    continue

                entry = AgentTrainingConfig(
                    user_id=user_id,
                    agent_name=agent_name,
                    config_type=config_type,
                    config_key="default",
                    config_value=configs,
                )
                db.add(entry)
                created += 1

    if created > 0:
        await db.flush()
        logger.info("Seeded %d default training configs for user %s", created, user_id)

    return created
