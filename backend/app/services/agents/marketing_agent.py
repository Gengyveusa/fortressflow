"""Marketing automation agent — 15 core marketing skills powered by Groq LLM."""

import json
import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import api_key_service
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)

# Rate limiter: 30 requests/minute (shared with Groq quotas)
_request_timestamps: dict[str, list[float]] = {}
_RATE_LIMIT = 30
_RATE_WINDOW = 60.0

DEFAULT_MODEL = "llama-3.3-70b-versatile"
FAST_MODEL = "llama-3.1-8b-instant"


def _check_rate_limit(user_id: str) -> None:
    """Enforce 30 req/min per user. Raises RuntimeError if exceeded."""
    now = time.time()
    key = f"marketing:{user_id}"
    timestamps = _request_timestamps.setdefault(key, [])
    _request_timestamps[key] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_request_timestamps[key]) >= _RATE_LIMIT:
        raise RuntimeError("Marketing agent rate limit exceeded (30 req/min). Please wait.")
    _request_timestamps[key].append(now)


async def _get_api_key(db: AsyncSession, user_id: UUID | None = None) -> str:
    """Load Groq API key from DB first, then fall back to env."""
    key = await api_key_service.get_api_key(db, "groq", user_id)
    if not key:
        raise RuntimeError("Groq API key not configured. Add it in Settings -> API Keys.")
    return key


def _get_client(api_key: str):
    """Lazily import and create a Groq client."""
    try:
        from groq import AsyncGroq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")
    return AsyncGroq(api_key=api_key)


class MarketingAgent:
    """Marketing automation agent with 15 core skills.

    All methods are async static methods that accept a database session,
    relevant parameters, and an optional user_id for rate limiting and
    API key resolution. Each returns structured dicts or lists suitable
    for API responses.
    """

    # ── 1. Lead Scoring ─────────────────────────────────────────────────

    @staticmethod
    async def score_leads(
        db: AsyncSession,
        leads: list[dict],
        scoring_criteria: dict | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Score leads based on engagement signals and firmographic fit.

        Args:
            db: Async database session.
            leads: List of lead dicts with keys like name, company, title,
                   engagement_events, industry, company_size, etc.
            scoring_criteria: Optional custom weights, e.g.
                {"engagement_weight": 0.6, "fit_weight": 0.4, "ideal_profile": {...}}.
            user_id: Current user UUID for rate limiting / key lookup.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with "scored_leads" list (each with score, tier, reasoning)
            and "summary" statistics.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        criteria_str = json.dumps(scoring_criteria or {
            "engagement_weight": 0.6,
            "fit_weight": 0.4,
            "ideal_profile": {
                "company_size": "50-500",
                "industries": ["SaaS", "Technology", "Financial Services"],
            },
        }, default=str)

        system_prompt = (
            "You are a B2B lead scoring specialist. Score each lead on a 0-100 scale "
            "based on engagement signals (email opens, clicks, site visits, content downloads) "
            "and firmographic fit (industry, company size, title seniority, tech stack). "
            "Assign tiers: hot (80-100), warm (50-79), cold (0-49). "
            "Output valid JSON: "
            '{"scored_leads": [{"name": "...", "score": <int>, "tier": "hot|warm|cold", '
            '"engagement_score": <int>, "fit_score": <int>, '
            '"reasoning": "...", "next_action": "..."}], '
            '"summary": {"total": <int>, "hot": <int>, "warm": <int>, "cold": <int>, '
            '"avg_score": <float>}}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Scoring criteria:\n{criteria_str}\n\n"
                            f"Leads to score:\n{json.dumps(leads, default=str)}"
                        ),
                    },
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("Scored %d leads for user %s", len(leads), user_id)
            return result
        except Exception as exc:
            logger.error("score_leads failed: %s", sanitize_error(exc))
            raise

    # ── 2. Outbound Email Sequence ──────────────────────────────────────

    @staticmethod
    async def create_outbound_sequence(
        db: AsyncSession,
        target_persona: str,
        industry: str,
        value_proposition: str,
        num_steps: int = 5,
        tone: str = "professional",
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Create a multi-step outbound email sequence.

        Args:
            db: Async database session.
            target_persona: e.g. "VP of Engineering at mid-market SaaS".
            industry: Target industry vertical.
            value_proposition: Core value prop to weave into emails.
            num_steps: Number of sequence steps (default 5).
            tone: Writing tone (professional, casual, consultative, bold).
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with "sequence_name", "steps" list, and "metadata".
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are an elite B2B outbound sales copywriter. Create a multi-step "
            "email sequence that builds rapport, delivers value, and drives meetings. "
            "Each step should have a distinct purpose (intro, value, social proof, "
            "breakup, etc.) with compelling subject lines and concise bodies (<150 words). "
            "Include personalization tokens: {{first_name}}, {{company}}, {{title}}, {{pain_point}}. "
            "Output valid JSON: "
            '{"sequence_name": "...", "steps": [{"step_number": <int>, '
            '"delay_days": <int>, "subject": "...", "body": "...", '
            '"purpose": "...", "cta": "..."}], '
            '"metadata": {"total_steps": <int>, "total_duration_days": <int>, '
            '"target_persona": "...", "tone": "..."}}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Create a {num_steps}-step outbound sequence.\n"
                            f"Target persona: {target_persona}\n"
                            f"Industry: {industry}\n"
                            f"Value proposition: {value_proposition}\n"
                            f"Tone: {tone}"
                        ),
                    },
                ],
                max_tokens=3072,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Created %d-step outbound sequence for user %s",
                num_steps, user_id,
            )
            return result
        except Exception as exc:
            logger.error("create_outbound_sequence failed: %s", sanitize_error(exc))
            raise

    # ── 3. Compliance Check ─────────────────────────────────────────────

    @staticmethod
    async def check_compliance(
        db: AsyncSession,
        content: str,
        channel: str,
        regulations: list[str] | None = None,
        sender_info: dict | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Check marketing content against CAN-SPAM, GDPR, TCPA, CCPA.

        Args:
            db: Async database session.
            content: The marketing content to audit.
            channel: Distribution channel (email, sms, social, web).
            regulations: Specific regulations to check against.
            sender_info: Optional dict with sender name, address, etc.
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with compliance status, issues found, score, and fixes.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        regs = regulations or ["CAN-SPAM", "GDPR", "TCPA", "CCPA"]
        regs_str = ", ".join(regs)
        sender_str = json.dumps(sender_info or {}, default=str)

        system_prompt = (
            f"You are a marketing compliance expert specializing in {regs_str}. "
            f"Review the {channel} content for regulatory compliance. "
            "Check for: unsubscribe mechanism, physical address, sender identification, "
            "consent requirements, data handling disclosures, deceptive subject lines, "
            "opt-out honoring timeline, and jurisdiction-specific rules. "
            "Output valid JSON: "
            '{"compliant": <true/false>, "overall_score": <0-100>, '
            '"issues": [{"regulation": "...", "issue": "...", '
            '"severity": "critical|high|medium|low", "fix": "...", '
            '"section_reference": "..."}], '
            '"recommendations": ["..."], '
            '"missing_elements": ["..."]}'
        )

        try:
            response = await client.chat.completions.create(
                model=FAST_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Channel: {channel}\n"
                            f"Regulations: {regs_str}\n"
                            f"Sender info: {sender_str}\n\n"
                            f"Content to review:\n{content}"
                        ),
                    },
                ],
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Compliance check completed for user %s: compliant=%s",
                user_id, result.get("compliant"),
            )
            return result
        except Exception as exc:
            logger.error("check_compliance failed: %s", sanitize_error(exc))
            raise

    # ── 4. A/B Test Variant Generation ──────────────────────────────────

    @staticmethod
    async def generate_ab_variants(
        db: AsyncSession,
        original_content: str,
        content_type: str = "email",
        num_variants: int = 3,
        test_variables: list[str] | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Generate A/B test variants with specific hypothesis per variant.

        Args:
            db: Async database session.
            original_content: The control content to create variants from.
            content_type: Type of content (email, subject_line, cta, landing_page, ad).
            num_variants: Number of variants to generate (default 3).
            test_variables: Specific elements to vary (tone, cta, length, personalization).
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with "control", "variants" list, and "test_plan".
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        variables = test_variables or ["tone", "cta", "length", "structure"]
        variables_str = ", ".join(variables)

        system_prompt = (
            f"You are an A/B testing specialist for {content_type} marketing. "
            f"Generate {num_variants} distinct variants, each testing a different variable: "
            f"{variables_str}. Each variant must have a clear hypothesis. "
            "Output valid JSON: "
            '{"control": {"content": "...", "label": "Control"}, '
            '"variants": [{"variant_id": "B|C|D", "content": "...", '
            '"variable_tested": "...", "hypothesis": "...", '
            '"expected_impact": "..."}], '
            '"test_plan": {"recommended_sample_size": <int>, '
            '"recommended_duration_days": <int>, '
            '"primary_metric": "...", "secondary_metrics": ["..."]}}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Content type: {content_type}\n"
                            f"Variables to test: {variables_str}\n\n"
                            f"Original (control):\n{original_content}"
                        ),
                    },
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Generated %d A/B variants for user %s",
                num_variants, user_id,
            )
            return result
        except Exception as exc:
            logger.error("generate_ab_variants failed: %s", sanitize_error(exc))
            raise

    # ── 5. Social Media Post Creation ───────────────────────────────────

    @staticmethod
    async def create_social_post(
        db: AsyncSession,
        topic: str,
        platform: str,
        brand_voice: str = "professional",
        include_hashtags: bool = True,
        include_cta: bool = True,
        content_goal: str = "engagement",
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Create platform-optimized social media posts.

        Args:
            db: Async database session.
            topic: Subject or theme of the post.
            platform: Target platform (linkedin, twitter, facebook, instagram).
            brand_voice: Voice/tone (professional, casual, thought_leader, bold).
            include_hashtags: Whether to include relevant hashtags.
            include_cta: Whether to include a call-to-action.
            content_goal: Goal (engagement, traffic, leads, awareness, education).
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with post content, hashtags, CTA, and platform metadata.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        platform_limits = {
            "linkedin": 3000,
            "twitter": 280,
            "facebook": 500,
            "instagram": 2200,
        }
        char_limit = platform_limits.get(platform.lower(), 500)

        system_prompt = (
            f"You are a B2B social media strategist specializing in {platform}. "
            f"Create a {brand_voice} post optimized for {content_goal}. "
            f"Character limit: {char_limit}. "
            "Output valid JSON: "
            '{"post_text": "...", "hashtags": ["..."], '
            '"cta": "...", "suggested_media": "...", '
            '"best_posting_time": "...", '
            '"engagement_hooks": ["..."], '
            '"platform": "...", "character_count": <int>}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Platform: {platform}\n"
                            f"Topic: {topic}\n"
                            f"Brand voice: {brand_voice}\n"
                            f"Goal: {content_goal}\n"
                            f"Include hashtags: {include_hashtags}\n"
                            f"Include CTA: {include_cta}"
                        ),
                    },
                ],
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("Created %s post for user %s", platform, user_id)
            return result
        except Exception as exc:
            logger.error("create_social_post failed: %s", sanitize_error(exc))
            raise

    # ── 6. Analytics Summarization ──────────────────────────────────────

    @staticmethod
    async def summarize_analytics(
        db: AsyncSession,
        metrics_data: dict,
        time_period: str = "last_30_days",
        comparison_period: str | None = None,
        focus_areas: list[str] | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Summarize marketing analytics with trends and recommendations.

        Args:
            db: Async database session.
            metrics_data: Dict of marketing metrics (open rates, CTR, conversions, etc.).
            time_period: Period being analyzed.
            comparison_period: Optional prior period for comparison.
            focus_areas: Specific areas to focus on (email, social, paid, seo).
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with narrative summary, key metrics, trends, and action items.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        areas_str = ", ".join(focus_areas) if focus_areas else "all channels"

        system_prompt = (
            "You are a senior marketing analytics expert. Analyze the provided metrics "
            f"for {time_period}, focusing on {areas_str}. "
            "Identify trends, anomalies, and opportunities. Use specific numbers. "
            "Output valid JSON: "
            '{"executive_summary": "...", '
            '"key_metrics": [{"metric": "...", "value": "...", '
            '"trend": "up|down|flat", "change_pct": <float>, '
            '"assessment": "good|warning|critical"}], '
            '"insights": ["..."], '
            '"action_items": [{"priority": "high|medium|low", '
            '"action": "...", "expected_impact": "..."}], '
            '"overall_health_score": <0-100>}'
        )

        user_content = f"Time period: {time_period}\n"
        if comparison_period:
            user_content += f"Comparison period: {comparison_period}\n"
        user_content += f"\nMetrics data:\n{json.dumps(metrics_data, default=str)}"

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_content},
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("Summarized analytics for user %s", user_id)
            return result
        except Exception as exc:
            logger.error("summarize_analytics failed: %s", sanitize_error(exc))
            raise

    # ── 7. Chatbot Response Management ──────────────────────────────────

    @staticmethod
    async def manage_chatbot(
        db: AsyncSession,
        visitor_message: str,
        conversation_history: list[dict] | None = None,
        company_context: dict | None = None,
        routing_rules: dict | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Generate chatbot responses and route conversations intelligently.

        Args:
            db: Async database session.
            visitor_message: The latest message from the website visitor.
            conversation_history: Prior messages in the conversation.
            company_context: Company info, products, FAQs for grounding.
            routing_rules: Rules for when to escalate to human agents.
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with bot response, intent classification, routing decision,
            and suggested follow-ups.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        history_str = json.dumps(conversation_history or [], default=str)
        context_str = json.dumps(company_context or {}, default=str)
        rules_str = json.dumps(routing_rules or {
            "escalate_on": ["pricing request", "demo request", "complaint", "technical issue"],
            "qualify_on": ["budget", "timeline", "authority", "need"],
        }, default=str)

        system_prompt = (
            "You are an intelligent B2B marketing chatbot. Respond helpfully and "
            "naturally to website visitors. Qualify leads using BANT criteria. "
            "Determine if the conversation should be routed to a human agent. "
            "Output valid JSON: "
            '{"response": "...", '
            '"intent": "...", '
            '"sentiment": "positive|neutral|negative", '
            '"qualification_signals": {"budget": <bool>, "authority": <bool>, '
            '"need": <bool>, "timeline": <bool>}, '
            '"route_to_human": <true/false>, '
            '"routing_reason": "...", '
            '"suggested_followups": ["..."], '
            '"lead_score_delta": <int>}'
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    f"Company context: {context_str}\n"
                    f"Routing rules: {rules_str}\n"
                    f"Conversation history: {history_str}\n\n"
                    f"Visitor message: {visitor_message}"
                ),
            },
        ]

        try:
            response = await client.chat.completions.create(
                model=FAST_MODEL,
                messages=messages,
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Chatbot response for user %s, intent=%s, route=%s",
                user_id, result.get("intent"), result.get("route_to_human"),
            )
            return result
        except Exception as exc:
            logger.error("manage_chatbot failed: %s", sanitize_error(exc))
            raise

    # ── 8. Multilingual Content Generation ──────────────────────────────

    @staticmethod
    async def generate_multilingual_content(
        db: AsyncSession,
        source_content: str,
        source_language: str = "en",
        target_languages: list[str] | None = None,
        content_type: str = "email",
        preserve_tone: bool = True,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Generate culturally adapted multilingual marketing content.

        Args:
            db: Async database session.
            source_content: Original content in source language.
            source_language: ISO 639-1 code of source (default "en").
            target_languages: List of ISO 639-1 codes (default: es, fr, de, pt).
            content_type: Type of content (email, social, ad, landing_page).
            preserve_tone: Whether to maintain brand voice across languages.
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with translations, cultural notes, and quality indicators.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        targets = target_languages or ["es", "fr", "de", "pt"]
        targets_str = ", ".join(targets)

        system_prompt = (
            "You are a multilingual marketing content specialist. "
            f"Translate and culturally adapt the {content_type} content from "
            f"{source_language} to: {targets_str}. "
            "Do NOT do literal translation. Adapt idioms, CTAs, and cultural references. "
            f"{'Preserve the original brand voice and tone.' if preserve_tone else 'Adapt tone for each locale.'} "
            "Output valid JSON: "
            '{"source": {"language": "...", "content": "..."}, '
            '"translations": [{"language": "...", "content": "...", '
            '"cultural_notes": "...", "adaptations_made": ["..."], '
            '"confidence": <0.0-1.0>}], '
            '"quality_summary": "..."}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Source language: {source_language}\n"
                            f"Target languages: {targets_str}\n"
                            f"Content type: {content_type}\n\n"
                            f"Content to translate:\n{source_content}"
                        ),
                    },
                ],
                max_tokens=3072,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Generated multilingual content in %d languages for user %s",
                len(targets), user_id,
            )
            return result
        except Exception as exc:
            logger.error("generate_multilingual_content failed: %s", sanitize_error(exc))
            raise

    # ── 9. Demand Generation Sequence ───────────────────────────────────

    @staticmethod
    async def create_demand_gen_sequence(
        db: AsyncSession,
        campaign_goal: str,
        target_audience: str,
        channels: list[str] | None = None,
        num_touchpoints: int = 7,
        budget_tier: str = "medium",
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Create a multi-channel demand generation sequence.

        Args:
            db: Async database session.
            campaign_goal: e.g. "Drive demo requests for new product launch".
            target_audience: Description of the target audience/ICP.
            channels: Marketing channels to use (email, social, webinar, content, paid).
            num_touchpoints: Total touchpoints across all channels (default 7).
            budget_tier: Budget level (low, medium, high).
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with campaign plan, touchpoints timeline, content briefs, and KPIs.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        channel_list = channels or ["email", "linkedin", "content", "webinar", "retargeting"]
        channels_str = ", ".join(channel_list)

        system_prompt = (
            "You are a demand generation strategist for B2B companies. "
            f"Create a {num_touchpoints}-touchpoint demand gen sequence across: {channels_str}. "
            f"Budget tier: {budget_tier}. "
            "Design a journey that moves prospects from awareness to consideration to decision. "
            "Output valid JSON: "
            '{"campaign_name": "...", "objective": "...", '
            '"touchpoints": [{"day": <int>, "channel": "...", '
            '"action": "...", "content_brief": "...", '
            '"cta": "...", "goal": "..."}], '
            '"content_assets_needed": ["..."], '
            '"kpis": [{"metric": "...", "target": "...", "measurement": "..."}], '
            '"estimated_timeline_weeks": <int>, '
            '"funnel_stage_mapping": {"awareness": [<ints>], '
            '"consideration": [<ints>], "decision": [<ints>]}}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Campaign goal: {campaign_goal}\n"
                            f"Target audience: {target_audience}\n"
                            f"Channels: {channels_str}\n"
                            f"Touchpoints: {num_touchpoints}\n"
                            f"Budget tier: {budget_tier}"
                        ),
                    },
                ],
                max_tokens=3072,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Created demand gen sequence with %d touchpoints for user %s",
                num_touchpoints, user_id,
            )
            return result
        except Exception as exc:
            logger.error("create_demand_gen_sequence failed: %s", sanitize_error(exc))
            raise

    # ── 10. Customer Segmentation ───────────────────────────────────────

    @staticmethod
    async def segment_customers(
        db: AsyncSession,
        customers: list[dict],
        segmentation_criteria: list[str] | None = None,
        num_segments: int = 4,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Segment customers into actionable groups based on behavior and attributes.

        Args:
            db: Async database session.
            customers: List of customer dicts with attributes like industry,
                       company_size, deal_value, engagement_level, lifecycle_stage, etc.
            segmentation_criteria: Criteria to segment by (behavior, firmographic,
                                   engagement, value).
            num_segments: Target number of segments (default 4).
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with segments, assignments, and targeting recommendations.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        criteria = segmentation_criteria or [
            "engagement_level", "company_size", "industry", "deal_value",
        ]
        criteria_str = ", ".join(criteria)

        system_prompt = (
            "You are a customer segmentation analyst for B2B marketing. "
            f"Analyze the customer data and create {num_segments} distinct, "
            f"actionable segments based on: {criteria_str}. "
            "Each segment should have a clear profile, targeting strategy, and messaging angle. "
            "Output valid JSON: "
            '{"segments": [{"segment_id": <int>, "name": "...", '
            '"description": "...", "size": <int>, "size_pct": <float>, '
            '"key_characteristics": ["..."], '
            '"recommended_channels": ["..."], '
            '"messaging_angle": "...", '
            '"priority": "high|medium|low"}], '
            '"customer_assignments": [{"customer_index": <int>, '
            '"segment_id": <int>, "confidence": <float>}], '
            '"segmentation_quality": {"distinctiveness": <float>, '
            '"actionability": <float>, "coverage": <float>}}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Segmentation criteria: {criteria_str}\n"
                            f"Target segments: {num_segments}\n\n"
                            f"Customer data:\n{json.dumps(customers[:50], default=str)}"
                        ),
                    },
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Segmented %d customers into %d segments for user %s",
                len(customers), num_segments, user_id,
            )
            return result
        except Exception as exc:
            logger.error("segment_customers failed: %s", sanitize_error(exc))
            raise

    # ── 11. Upsell / Cross-sell Recommendations ─────────────────────────

    @staticmethod
    async def recommend_upsell_crosssell(
        db: AsyncSession,
        customer_profile: dict,
        current_products: list[str],
        available_products: list[dict],
        purchase_history: list[dict] | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Generate personalized upsell and cross-sell recommendations.

        Args:
            db: Async database session.
            customer_profile: Dict with company info, industry, size, etc.
            current_products: Products the customer currently owns.
            available_products: Products available for recommendation.
            purchase_history: Historical purchases and usage data.
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with upsell and cross-sell recommendations, messaging, and timing.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are a B2B revenue expansion strategist. Analyze the customer profile, "
            "current product usage, and available catalog to recommend upsell and "
            "cross-sell opportunities. Prioritize recommendations by revenue potential "
            "and likelihood of acceptance. "
            "Output valid JSON: "
            '{"upsell_recommendations": [{"product": "...", '
            '"rationale": "...", "messaging": "...", '
            '"confidence": <float>, "estimated_revenue": "...", '
            '"trigger_event": "...", "best_approach": "..."}], '
            '"crosssell_recommendations": [{"product": "...", '
            '"rationale": "...", "messaging": "...", '
            '"confidence": <float>, "estimated_revenue": "...", '
            '"synergy_with": "..."}], '
            '"overall_expansion_potential": "high|medium|low", '
            '"recommended_timing": "...", '
            '"talk_track": "..."}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Customer profile: {json.dumps(customer_profile, default=str)}\n"
                            f"Current products: {json.dumps(current_products, default=str)}\n"
                            f"Available products: {json.dumps(available_products, default=str)}\n"
                            f"Purchase history: {json.dumps(purchase_history or [], default=str)}"
                        ),
                    },
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Generated upsell/cross-sell recommendations for user %s",
                user_id,
            )
            return result
        except Exception as exc:
            logger.error("recommend_upsell_crosssell failed: %s", sanitize_error(exc))
            raise

    # ── 12. Event Promotion Content ─────────────────────────────────────

    @staticmethod
    async def create_event_promotion(
        db: AsyncSession,
        event_name: str,
        event_type: str,
        event_date: str,
        event_details: dict | None = None,
        channels: list[str] | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Create multi-channel event promotion content.

        Args:
            db: Async database session.
            event_name: Name of the event.
            event_type: Type (webinar, conference, workshop, product_launch, meetup).
            event_date: Date string for the event.
            event_details: Additional details (speakers, agenda, location, url).
            channels: Channels to create content for (email, social, landing_page, ad).
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with promotion content for each channel and a timeline.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        promo_channels = channels or ["email", "linkedin", "twitter", "landing_page"]
        channels_str = ", ".join(promo_channels)
        details_str = json.dumps(event_details or {}, default=str)

        system_prompt = (
            "You are an event marketing specialist for B2B companies. "
            f"Create promotion content for a {event_type} across: {channels_str}. "
            "Include pre-event, day-of, and post-event content. "
            "Output valid JSON: "
            '{"event_name": "...", "event_type": "...", '
            '"promotions": [{"channel": "...", "phase": "pre|day_of|post", '
            '"timing": "...", "subject_or_headline": "...", '
            '"body": "...", "cta": "...", "visual_suggestion": "..."}], '
            '"promotion_timeline": [{"days_before": <int>, '
            '"action": "...", "channel": "..."}], '
            '"registration_page_copy": {"headline": "...", '
            '"subheadline": "...", "bullet_points": ["..."], '
            '"urgency_element": "..."}, '
            '"follow_up_sequence": [{"timing": "...", "content": "..."}]}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Event: {event_name}\n"
                            f"Type: {event_type}\n"
                            f"Date: {event_date}\n"
                            f"Details: {details_str}\n"
                            f"Channels: {channels_str}"
                        ),
                    },
                ],
                max_tokens=3072,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Created event promotion for '%s' for user %s",
                event_name, user_id,
            )
            return result
        except Exception as exc:
            logger.error("create_event_promotion failed: %s", sanitize_error(exc))
            raise

    # ── 13. Send Time Optimization ──────────────────────────────────────

    @staticmethod
    async def optimize_send_time(
        db: AsyncSession,
        audience_data: dict,
        campaign_type: str = "email",
        timezone_distribution: dict | None = None,
        historical_performance: list[dict] | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Determine optimal send times based on audience behavior.

        Args:
            db: Async database session.
            audience_data: Audience characteristics (roles, industries, regions).
            campaign_type: Channel type (email, social, sms, push).
            timezone_distribution: Dict mapping timezones to audience percentages.
            historical_performance: Past send-time performance data.
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with recommended send times, rationale, and timezone windows.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        tz_str = json.dumps(timezone_distribution or {
            "US/Eastern": 40, "US/Pacific": 25, "Europe/London": 15,
            "US/Central": 10, "Other": 10,
        }, default=str)
        history_str = json.dumps(historical_performance or [], default=str)

        system_prompt = (
            f"You are a {campaign_type} deliverability and engagement optimization expert. "
            "Analyze the audience data, timezone distribution, and historical performance "
            "to recommend optimal send times. Consider industry norms, role-based behavior "
            "patterns, and day-of-week effects. "
            "Output valid JSON: "
            '{"primary_recommendation": {"day": "...", "time_utc": "...", '
            '"rationale": "..."}, '
            '"alternative_windows": [{"day": "...", "time_utc": "...", '
            '"expected_performance": "..."}], '
            '"timezone_strategy": {"approach": "single_blast|staggered|timezone_optimized", '
            '"windows": [{"timezone": "...", "local_time": "...", '
            '"audience_pct": <float>}]}, '
            '"avoid_times": [{"day": "...", "time": "...", "reason": "..."}], '
            '"confidence": <float>, '
            '"factors_considered": ["..."]}'
        )

        try:
            response = await client.chat.completions.create(
                model=FAST_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Campaign type: {campaign_type}\n"
                            f"Audience data: {json.dumps(audience_data, default=str)}\n"
                            f"Timezone distribution: {tz_str}\n"
                            f"Historical performance: {history_str}"
                        ),
                    },
                ],
                max_tokens=1024,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("Optimized send time for user %s", user_id)
            return result
        except Exception as exc:
            logger.error("optimize_send_time failed: %s", sanitize_error(exc))
            raise

    # ── 14. Landing Page Copy Generation ────────────────────────────────

    @staticmethod
    async def generate_landing_page_copy(
        db: AsyncSession,
        product_or_offer: str,
        target_audience: str,
        page_goal: str = "lead_capture",
        tone: str = "professional",
        key_benefits: list[str] | None = None,
        social_proof: list[str] | None = None,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Generate conversion-optimized landing page copy.

        Args:
            db: Async database session.
            product_or_offer: What the page is promoting.
            target_audience: Who the page is targeting.
            page_goal: Conversion goal (lead_capture, demo_request, free_trial, download).
            tone: Writing tone (professional, bold, friendly, urgent).
            key_benefits: Product/offer benefits to highlight.
            social_proof: Testimonials, stats, logos to incorporate.
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with all landing page copy sections and SEO metadata.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        benefits_str = json.dumps(key_benefits or [], default=str)
        proof_str = json.dumps(social_proof or [], default=str)

        system_prompt = (
            "You are a conversion copywriter specializing in B2B landing pages. "
            f"Create high-converting landing page copy for a {page_goal} page. "
            "Follow proven frameworks: PAS (Problem-Agitate-Solution) or AIDA. "
            "Output valid JSON: "
            '{"hero_section": {"headline": "...", "subheadline": "...", '
            '"cta_button_text": "...", "supporting_text": "..."}, '
            '"problem_section": {"headline": "...", "body": "..."}, '
            '"solution_section": {"headline": "...", "body": "...", '
            '"features": [{"title": "...", "description": "..."}]}, '
            '"social_proof_section": {"headline": "...", '
            '"testimonial": "...", "stats": ["..."]}, '
            '"cta_section": {"headline": "...", "body": "...", '
            '"button_text": "...", "urgency_element": "..."}, '
            '"faq": [{"question": "...", "answer": "..."}], '
            '"seo": {"meta_title": "...", "meta_description": "...", '
            '"h1": "...", "keywords": ["..."]}}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Product/Offer: {product_or_offer}\n"
                            f"Target audience: {target_audience}\n"
                            f"Page goal: {page_goal}\n"
                            f"Tone: {tone}\n"
                            f"Key benefits: {benefits_str}\n"
                            f"Social proof: {proof_str}"
                        ),
                    },
                ],
                max_tokens=3072,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info("Generated landing page copy for user %s", user_id)
            return result
        except Exception as exc:
            logger.error("generate_landing_page_copy failed: %s", sanitize_error(exc))
            raise

    # ── 15. Campaign Performance Analysis ───────────────────────────────

    @staticmethod
    async def analyze_campaign_performance(
        db: AsyncSession,
        campaign_data: dict,
        benchmarks: dict | None = None,
        campaign_type: str = "email",
        include_recommendations: bool = True,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Analyze campaign performance with benchmarking and recommendations.

        Args:
            db: Async database session.
            campaign_data: Dict with campaign metrics (sends, opens, clicks,
                           conversions, revenue, costs, etc.).
            benchmarks: Industry benchmark data for comparison.
            campaign_type: Type of campaign (email, social, paid, content, event).
            include_recommendations: Whether to include improvement suggestions.
            user_id: Current user UUID.
            prompt_engine_context: Optional PromptEngine context.

        Returns:
            Dict with performance grades, benchmark comparisons, funnel analysis,
            and optimization recommendations.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        benchmarks_str = json.dumps(benchmarks or {
            "email": {"open_rate": 21.5, "click_rate": 2.3, "conversion_rate": 1.5},
            "social": {"engagement_rate": 3.5, "click_rate": 1.2},
            "paid": {"ctr": 2.0, "conversion_rate": 3.5, "cpc": 2.50},
        }, default=str)

        system_prompt = (
            f"You are a {campaign_type} campaign performance analyst for B2B marketing. "
            "Analyze the campaign data against industry benchmarks. Grade each metric, "
            "identify the biggest opportunities, and calculate ROI. "
            "Output valid JSON: "
            '{"campaign_grade": "A|B|C|D|F", '
            '"overall_score": <0-100>, '
            '"metric_analysis": [{"metric": "...", "value": <float>, '
            '"benchmark": <float>, "grade": "A|B|C|D|F", '
            '"vs_benchmark": "above|at|below", "delta_pct": <float>}], '
            '"funnel_analysis": {"top_of_funnel": <int>, '
            '"middle_of_funnel": <int>, "bottom_of_funnel": <int>, '
            '"conversion_rate": <float>, "drop_off_points": ["..."]}, '
            '"roi_analysis": {"total_cost": <float>, "total_revenue": <float>, '
            '"roi_pct": <float>, "cost_per_lead": <float>, '
            '"cost_per_acquisition": <float>}, '
            '"top_performers": ["..."], '
            '"underperformers": ["..."], '
            '"recommendations": [{"priority": "high|medium|low", '
            '"area": "...", "action": "...", "expected_impact": "..."}]}'
        )

        try:
            response = await client.chat.completions.create(
                model=DEFAULT_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": (
                            f"Campaign type: {campaign_type}\n"
                            f"Include recommendations: {include_recommendations}\n\n"
                            f"Campaign data:\n{json.dumps(campaign_data, default=str)}\n\n"
                            f"Industry benchmarks:\n{benchmarks_str}"
                        ),
                    },
                ],
                max_tokens=2048,
                response_format={"type": "json_object"},
            )
            result = json.loads(response.choices[0].message.content)
            logger.info(
                "Analyzed campaign performance for user %s: grade=%s",
                user_id, result.get("campaign_grade"),
            )
            return result
        except Exception as exc:
            logger.error("analyze_campaign_performance failed: %s", sanitize_error(exc))
            raise
