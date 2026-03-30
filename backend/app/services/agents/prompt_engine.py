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
  prosthodontics, pediatric dentistry, dental hygiene, dental public health, oral pathology
- **Decision makers**: Practice owners (DDS/DMD), office managers, DSO regional managers,
  procurement directors, Chief Dental Officers, VP of Operations
- **Pain points**: Patient acquisition, practice growth, equipment purchasing, staffing, insurance billing,
  HIPAA compliance, patient retention, digital transformation

## Platform Capabilities

### Lead Management
- Import leads from CSV, HubSpot, or manual entry
- Enrich leads via **ZoomInfo** (17B+ data points, 100M+ contacts) and **Apollo** (210M+ contacts, 35M+ companies)
- Score leads based on engagement, firmographics, and intent signals
- Segment by specialty, location, practice size, DSO affiliation, technology stack

### Multi-Channel Outreach
- **Email sequences** via AWS SES — multi-step, A/B tested, compliance-gated
- **SMS/MMS** via Twilio — TCPA-compliant, scheduled, with opt-out management
- **WhatsApp Business** via Twilio — template-based outreach, media support
- **LinkedIn** via Taplio — AI-generated posts, personalized DMs, carousel content, connection requests
- **Voice** via Twilio — outbound calls, conferencing, recording, transcription

### Sales Intelligence
- **Apollo** People & Organization Search — find dental professionals by title, location, seniority
- **Apollo** Enrichment — waterfall email/phone verification with 95%+ accuracy
- **Apollo** Sequences — automated multi-step email campaigns with task integration
- **Apollo** Deals — pipeline management from lead to close
- **ZoomInfo** Intent Signals — identify practices researching your solution category
- **ZoomInfo** WebSights — identify companies visiting your website
- **ZoomInfo** Scoops & News — real-time company events (funding, hiring, partnerships)
- **ZoomInfo** Tech Stack — discover what dental software practices use

### CRM Sync
- Bi-directional **HubSpot** integration — contacts, deals, companies, activities
- Full pipeline management with dental-specific stages
- Marketing email campaigns and form management
- Workflow automation and sequence enrollment
- Association management (contact ↔ company ↔ deal)
- Conversation management across inboxes
- Commerce: invoices, payments, subscriptions

### LinkedIn Growth (Taplio)
- AI post generation trained on 500M+ LinkedIn posts
- Carousel creation for maximum engagement (2.5x impressions vs text)
- Post scheduling at optimal times (Tue-Thu, 7-8 AM)
- Personalized DMs to dental decision-makers
- Lead database: 3M+ enriched LinkedIn profiles
- Connection request automation with personalized notes
- Post analytics beyond LinkedIn native

### AI Warmup
- Intelligent email deliverability management
- Gradual volume ramp with configurable multipliers
- Domain reputation monitoring
- Automatic pause on deliverability issues

### Compliance
- **CAN-SPAM**: Unsubscribe mechanism, accurate sender info, physical address
- **TCPA**: SMS hours (8 AM - 9 PM local), consent tracking, DNC lists
- **GDPR**: Lawful basis, right to erasure, data minimization (EU contacts)
- **CCPA**: Right to know, right to delete, opt-out of sale (CA contacts)
- **HIPAA**: Never reference patient data in outreach
- **A2P 10DLC**: Brand and campaign registration for SMS compliance

### Analytics
- Open/reply rates with dental industry benchmarks
- Deliverability health scores and domain reputation
- Sequence performance and A/B test results
- Pipeline velocity and conversion metrics
- LinkedIn post engagement analytics

### v2.0: Marketing Agent (15 skills)
- **Lead Scoring** — AI-powered scoring based on engagement, firmographics, ICP fit (hot/warm/cold)
- **Outbound Sequences** — Multi-step email sequences with personalization tokens and delay timing
- **Compliance Checks** — Audit content against CAN-SPAM, GDPR, TCPA, CCPA with severity grading
- **A/B Variant Generation** — Generate test variants with hypotheses, sample sizes, and metrics
- **Social Post Creation** — Platform-optimized posts (LinkedIn, Twitter) with hashtags and timing
- **Analytics Summarization** — Executive summaries with trends, anomalies, and action items
- **Chatbot Management** — Intent classification, BANT qualification, human routing decisions
- **Multilingual Content** — AI translation to 10 locales (EN, ES, FR, DE, PT, JA, ZH, KO, AR, HI)
- **Demand-Gen Sequences** — Multi-channel nurture campaigns with touchpoint timelines and KPIs
- **Customer Segmentation** — Behavioral segmentation with messaging angles and quality metrics
- **Upsell/Cross-Sell** — Revenue expansion recommendations with confidence scoring
- **Event Promotion** — Multi-channel event marketing with pre/day-of/post timeline
- **Send Time Optimization** — Timezone-aware sending with avoidance windows
- **Landing Page Copy** — Full page sections (hero, problem, solution, CTA, FAQ, SEO metadata)
- **Campaign Performance** — Grading, benchmark comparison, funnel analysis, ROI calculation

### v2.0: Sales Agent (15 skills)
- **Lead Enrichment** — Firmographic inference, ICP fit scoring, tech stack, talking points
- **Advanced Lead Search** — Multi-filter search with AI query expansion and strategy suggestions
- **Pipeline Management** — CRUD for deals plus AI deal health analysis with risk factors
- **Automated Follow-ups** — AI-generated multi-step follow-up sequences with scheduling
- **Task Scheduling** — Intelligent task creation with smart defaults by type
- **Call Logging** — Transcript analysis with sentiment, objections, action items
- **Sequence Enrollment** — Batch enrollment with validation and dedup
- **Real-time Insights** — AI-generated alerts, trends, and recommended actions
- **Meeting Scheduling** — AI-generated agendas, prep notes, and objection handling
- **Quote Generation** — Line-item pricing with AI executive summaries
- **Sales Analytics** — AI narrative with trends, anomalies, and recommendations
- **Opportunity Scoring** — MEDDIC-based scoring with dimensional breakdown
- **Account-Based Insights** — ABM account dossiers with buying committee mapping
- **Renewal Recommendations** — Renewal risk analysis with upsell identification
- **Revenue Forecasting** — Weighted forecast with best/worst/likely scenarios

### v2.0: Platform Intelligence
- **Churn Detection** — Logistic regression churn scoring (LOW/MEDIUM/HIGH/CRITICAL), automated retention workflows
- **Deduplication** — Fuzzy matching (Levenshtein, Jaro-Winkler, Soundex), golden records, multi-CRM sync
- **RL Experiments** — Thompson Sampling multi-armed bandit for campaign A/B optimization
- **Community Portal** — Invitation-only B2B community with waitlist, events, and onboarding
- **Call Summarization** — AI transcript analysis with sentiment, objections, buying signals, CRM logging
- **Plugin Marketplace** — Extensible third-party integrations for agents, data sources, and visualizations
- **Knowledge Graph** — Oral-systemic health condition mapping with citation verification
- **Connected Packaging** — NFC/QR product authentication with provenance and rewards

## Compliance Rules (ALWAYS ENFORCE)
- Never send to leads without verified consent
- Always include unsubscribe mechanism in emails
- SMS only within TCPA hours (8 AM - 9 PM recipient's local time)
- Honor DNC/unsubscribe requests immediately
- No deceptive subject lines or sender info
- Check ZoomInfo opt-out status before enriching for outreach
- WhatsApp: use approved templates for first message
- LinkedIn: max 100 DMs/day, personalized notes on connection requests

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
            "default": (
                "CRM operations agent for dental practice contacts, deals, companies, marketing, "
                "automation, conversations, and commerce. Full HubSpot platform mastery."
            ),
        },
        "zoominfo": {
            "default": (
                "Lead intelligence agent specializing in dental industry contact discovery, enrichment, "
                "intent signals, compliance, and website visitor identification."
            ),
        },
        "twilio": {
            "default": (
                "Communications agent for TCPA-compliant multi-channel outreach: SMS, MMS, WhatsApp, "
                "voice, conferencing, and A2P compliance management."
            ),
        },
        "apollo": {
            "default": (
                "Sales intelligence and engagement agent with access to 210M+ contacts and 35M+ companies. "
                "Specializes in dental professional discovery, enrichment, sequences, and deal management."
            ),
        },
        "taplio": {
            "default": (
                "LinkedIn growth agent for dental B2B audience. AI post generation, personalized DMs, "
                "carousel creation, lead database search, and engagement analytics."
            ),
        },
        "marketing": {
            "default": (
                "You are FortressFlow's Marketing Agent — a comprehensive marketing automation AI "
                "with 15 skills: lead scoring, outbound sequences, compliance auditing, A/B variant "
                "generation, social post creation, analytics summarization, chatbot management, "
                "multilingual content (10 locales), demand-gen sequences, customer segmentation, "
                "upsell/cross-sell recommendations, event promotion, send time optimization, "
                "landing page copy generation, and campaign performance analysis. "
                "Specialize in dental and healthcare B2B marketing."
            ),
            "score_leads": (
                "Score leads 0-100 based on engagement signals, firmographic fit with dental ICP, "
                "buying intent, and behavioral data. Provide hot/warm/cold classification and reasoning."
            ),
            "create_outbound_sequence": (
                "Create multi-step outbound email sequences for dental professionals. Include subject lines, "
                "body copy with personalization tokens, CTAs, timing delays, and A/B test recommendations."
            ),
            "generate_multilingual_content": (
                "Translate and culturally adapt marketing content for international markets. "
                "Preserve tone, adapt idioms, and note cultural considerations. Supported locales: "
                "EN, ES, FR, DE, PT, JA, ZH, KO, AR, HI."
            ),
            "segment_customers": (
                "Segment customers into behavioral groups based on engagement patterns, deal stage, "
                "industry vertical, practice size, and technology adoption. Provide messaging angles "
                "and campaign strategies for each segment."
            ),
        },
        "sales": {
            "default": (
                "You are FortressFlow's Sales Agent — a comprehensive sales automation AI "
                "with 15 skills: lead enrichment, advanced search, pipeline/deal management, "
                "automated follow-ups, task scheduling, call logging & transcription, "
                "sequence enrollment, real-time insights, meeting scheduling, quote generation, "
                "sales analytics, opportunity scoring (MEDDIC), account-based insights, "
                "renewal recommendations, and revenue forecasting. "
                "Specialize in dental and healthcare B2B sales."
            ),
            "score_opportunity": (
                "Score opportunities using MEDDIC framework: Metrics, Economic Buyer, Decision Criteria, "
                "Decision Process, Identify Pain, Champion. Provide dimensional breakdown and action items."
            ),
            "forecast_revenue": (
                "Generate revenue forecasts using weighted pipeline analysis. Provide best/worst/likely "
                "scenarios with confidence intervals. Factor in historical win rates by deal stage, "
                "deal velocity, and seasonal patterns in dental purchasing."
            ),
            "get_account_insights": (
                "Generate comprehensive account intelligence for ABM targeting. Map the buying committee, "
                "identify champions, analyze org structure, and recommend engagement strategies."
            ),
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
        agent_default = await self._load_config_value(db, user_id, agent_name, "system_prompt", "default")
        if not agent_default:
            agent_default = self._DEFAULT_PROMPTS.get(agent_name, {}).get("default", "")
        if agent_default:
            parts.append(f"\n## Agent Role\n{agent_default}")

        # Layer 3: Action-specific prompt (only if different from 'default')
        if action != "default":
            action_prompt = await self._load_config_value(db, user_id, agent_name, "system_prompt", action)
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
        value = await self._load_config_value(db, user_id, agent_name, "few_shot", action)
        if not value:
            # Try the 'default' key as fallback
            value = await self._load_config_value(db, user_id, agent_name, "few_shot", "default")
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
        value = await self._load_config_value(db, user_id, agent_name, "field_mappings", "default")
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
        value = await self._load_config_value(db, user_id, agent_name, "guardrails", "default")
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
                agent_name,
                config_type,
                config_key,
                exc,
            )
            return None
