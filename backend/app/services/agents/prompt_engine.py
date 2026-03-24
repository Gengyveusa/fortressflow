"""Prompt Template Engine — builds context-rich prompts for every LLM call.

Layers training configs from DB on top of base FortressFlow domain knowledge
to produce system prompts, few-shot messages, guardrails, and field mappings.
"""

import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.agent_training_config import AgentTrainingConfig

logger = logging.getLogger(__name__)


class PromptEngine:
    """Builds context-rich prompts by combining domain knowledge, user configs, and few-shot examples."""

    FORTRESSFLOW_CONTEXT = """
You are an AI agent inside FortressFlow, a B2B lead-generation and multi-channel outreach platform
designed for dental offices and DSOs (Dental Service Organizations).

## Your Domain
- **Target market**: Dental practices, DSOs, dental equipment suppliers, dental labs
- **Common specialties**: General dentistry, periodontics, endodontics, oral surgery, orthodontics,
  prosthodontics, pediatric dentistry, dental hygiene
- **Decision makers**: Practice owners, office managers, DSO regional managers, procurement directors
- **Pain points**: Patient acquisition, practice growth, equipment purchasing, staffing, insurance billing

## Platform Capabilities
- **Lead Management**: Import, enrich (ZoomInfo/Apollo), score, segment leads
- **Multi-Channel Outreach**: Email sequences (SES), SMS (Twilio), LinkedIn automation
- **CRM Sync**: Bi-directional HubSpot integration (contacts, deals, companies)
- **AI Warmup**: Intelligent email deliverability management
- **Compliance**: CAN-SPAM, TCPA, GDPR, CCPA — consent gates on every outreach
- **Analytics**: Open/reply rates, deliverability health, sequence performance

## Compliance Rules (ALWAYS ENFORCE)
- Never send to leads without verified consent
- Always include unsubscribe mechanism in emails
- SMS only within TCPA hours (8 AM - 9 PM recipient's local time)
- Honor DNC/unsubscribe requests immediately
- No deceptive subject lines or sender info

## Tone & Voice
- Professional, consultative, healthcare-appropriate
- Never aggressive or "salesy" — dental professionals respond to expertise and value
- Use dental industry terminology correctly
- Personalize with practice name, specialty, location when available
""".strip()

    # ── Default agent prompts (fallback when no DB config exists) ─────────

    _DEFAULT_PROMPTS: dict[str, dict[str, str]] = {
        "groq": {
            "default": (
                "You are a B2B outreach AI specializing in dental practice growth. "
                "Help users create effective, compliant outreach campaigns."
            ),
            "generate_sequence_content": (
                "You are an expert dental industry email copywriter. "
                "Generate compelling, professional email sequences tailored for dental professionals."
            ),
            "classify_reply": (
                "You classify replies from dental professionals into categories: "
                "positive, negative, ooo, bounce, unsubscribe. Be precise and consider dental industry context."
            ),
            "check_compliance": (
                "You are a compliance officer specializing in dental outreach. "
                "Review content for CAN-SPAM, TCPA, GDPR, and CCPA compliance."
            ),
        },
        "openai": {
            "default": (
                "You are an AI assistant for FortressFlow, a dental B2B outreach platform. "
                "Provide accurate, structured data extraction and analysis."
            ),
        },
        "hubspot": {
            "default": "CRM operations agent for dental practice contacts, deals, and companies.",
        },
        "zoominfo": {
            "default": "Lead intelligence agent specializing in dental industry contact discovery and enrichment.",
        },
        "twilio": {
            "default": "Communications agent for TCPA-compliant SMS and voice outreach to dental professionals.",
        },
    }

    async def build_system_prompt(
        self,
        db: AsyncSession,
        user_id: UUID,
        agent_name: str,
        action: str,
        extra_context: str | None = None,
    ) -> str:
        """Build a complete system prompt for an LLM call.

        Layers:
        1. FORTRESSFLOW_CONTEXT (base domain knowledge)
        2. Agent-specific default prompt (from DB or hardcoded fallback)
        3. Action-specific prompt (from DB or hardcoded fallback)
        4. User guardrails (from DB)
        5. Extra context (passed by caller)
        """
        parts: list[str] = [self.FORTRESSFLOW_CONTEXT]

        # Layer 2: Agent default prompt
        agent_default = await self._load_config_value(
            db, user_id, agent_name, "system_prompt", "default"
        )
        if not agent_default:
            agent_default = self._DEFAULT_PROMPTS.get(agent_name, {}).get("default", "")
        if agent_default:
            parts.append(f"\n## Agent Role\n{agent_default}")

        # Layer 3: Action-specific prompt (only if different from 'default')
        if action != "default":
            action_prompt = await self._load_config_value(
                db, user_id, agent_name, "system_prompt", action
            )
            if not action_prompt:
                action_prompt = self._DEFAULT_PROMPTS.get(agent_name, {}).get(action, "")
            if action_prompt:
                parts.append(f"\n## Task-Specific Instructions\n{action_prompt}")

        # Layer 4: User guardrails
        guardrails = await self.get_guardrails(db, user_id, agent_name)
        if guardrails:
            rules = "\n".join(f"- {g}" for g in guardrails)
            parts.append(f"\n## User Guardrails (MUST follow)\n{rules}")

        # Layer 5: Extra context
        if extra_context:
            parts.append(f"\n## Additional Context\n{extra_context}")

        return "\n".join(parts)

    async def build_few_shot_messages(
        self,
        db: AsyncSession,
        user_id: UUID,
        agent_name: str,
        action: str,
    ) -> list[dict]:
        """Load few-shot examples for this agent+action from DB."""
        value = await self._load_config_value(
            db, user_id, agent_name, "few_shot", action
        )
        if not value:
            # Try the 'default' key as fallback
            value = await self._load_config_value(
                db, user_id, agent_name, "few_shot", "default"
            )
        if not value or not isinstance(value, list):
            return []

        messages: list[dict] = []
        for example in value:
            if isinstance(example, dict) and "input" in example and "output" in example:
                messages.append({"role": "user", "content": example["input"]})
                messages.append({"role": "assistant", "content": example["output"]})
        return messages

    async def get_field_mappings(
        self,
        db: AsyncSession,
        user_id: UUID,
        agent_name: str,
    ) -> dict:
        """Load custom field mappings (e.g., FortressFlow fields -> HubSpot properties)."""
        value = await self._load_config_value(
            db, user_id, agent_name, "field_mappings", "default"
        )
        if isinstance(value, dict):
            return value
        return {}

    async def get_guardrails(
        self,
        db: AsyncSession,
        user_id: UUID,
        agent_name: str,
    ) -> list[str]:
        """Load guardrails/restrictions for this agent."""
        value = await self._load_config_value(
            db, user_id, agent_name, "guardrails", "default"
        )
        if isinstance(value, list):
            return [str(g) for g in value]
        return []

    # ── Internal helpers ─────────────────────────────────────────────────

    async def _load_config_value(
        self,
        db: AsyncSession,
        user_id: UUID,
        agent_name: str,
        config_type: str,
        config_key: str,
    ):
        """Load a single config value from DB. Returns None if not found."""
        try:
            result = await db.execute(
                select(AgentTrainingConfig.config_value)
                .where(
                    AgentTrainingConfig.user_id == user_id,
                    AgentTrainingConfig.agent_name == agent_name,
                    AgentTrainingConfig.config_type == config_type,
                    AgentTrainingConfig.config_key == config_key,
                    AgentTrainingConfig.is_active.is_(True),
                )
                .order_by(AgentTrainingConfig.priority.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
            return row
        except Exception as exc:
            logger.warning(
                "Failed to load training config %s/%s/%s: %s",
                agent_name, config_type, config_key, exc,
            )
            return None
