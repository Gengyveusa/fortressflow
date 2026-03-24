"""Groq LLM agent — fast inference for all AI-powered features in FortressFlow."""

import json
import logging
import time
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import api_key_service
from app.utils.sanitize import sanitize_error

logger = logging.getLogger(__name__)

# Rate limiter: 30 requests/minute
_request_timestamps: dict[str, list[float]] = {}
_RATE_LIMIT = 30
_RATE_WINDOW = 60.0

DEFAULT_MODEL = "llama-3.3-70b-versatile"
FAST_MODEL = "llama-3.1-8b-instant"


def _check_rate_limit(user_id: str) -> None:
    """Enforce 30 req/min per user. Raises RuntimeError if exceeded."""
    now = time.time()
    key = f"groq:{user_id}"
    timestamps = _request_timestamps.setdefault(key, [])
    # Prune old entries
    _request_timestamps[key] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_request_timestamps[key]) >= _RATE_LIMIT:
        raise RuntimeError("Groq rate limit exceeded (30 req/min). Please wait.")
    _request_timestamps[key].append(now)


async def _get_api_key(db: AsyncSession, user_id: UUID | None = None) -> str:
    """Load Groq API key from DB first, then fall back to env."""
    key = await api_key_service.get_api_key(db, "groq", user_id)
    if not key:
        raise RuntimeError("Groq API key not configured. Add it in Settings → API Keys.")
    return key


def _get_client(api_key: str):
    """Lazily import and create a Groq client."""
    try:
        from groq import AsyncGroq
    except ImportError:
        raise RuntimeError("groq package not installed. Run: pip install groq")
    return AsyncGroq(api_key=api_key)


class GroqAgent:
    """Full-featured Groq LLM agent for FortressFlow AI capabilities."""

    # ── Chat completions ─────────────────────────────────────────────────

    @staticmethod
    async def chat(
        db: AsyncSession,
        messages: list[dict],
        stream: bool = False,
        model: str | None = None,
        user_id: UUID | None = None,
    ) -> str | AsyncGenerator[str, None]:
        """Chat completions — streaming and non-streaming.

        Default model: llama-3.3-70b-versatile.
        """
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)
        model = model or DEFAULT_MODEL

        if stream:
            return GroqAgent._stream_chat(client, messages, model)

        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=settings.CHAT_MAX_TOKENS,
        )
        return response.choices[0].message.content

    @staticmethod
    async def _stream_chat(client, messages: list[dict], model: str) -> AsyncGenerator[str, None]:
        """Internal streaming generator."""
        response = await client.chat.completions.create(
            model=model,
            messages=messages,
            max_tokens=settings.CHAT_MAX_TOKENS,
            stream=True,
        )
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    # ── Sequence content generation ──────────────────────────────────────

    @staticmethod
    async def generate_sequence_content(
        db: AsyncSession,
        sequence_type: str,
        target_industry: str,
        tone: str,
        num_steps: int,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Generate email subjects + bodies for sequence steps."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are an expert B2B email copywriter specializing in outbound sales sequences. "
            "Generate email sequence steps with compelling subject lines and body copy. "
            "Each step should build on the previous one, creating a natural progression. "
            "Output valid JSON only — an array of objects with keys: "
            '"step_number", "subject", "body", "purpose".'
        )
        user_prompt = (
            f"Create a {num_steps}-step {sequence_type} email sequence for the {target_industry} industry. "
            f"Tone: {tone}. Each email should be concise (under 150 words for body). "
            f"Include personalization placeholders like {{{{first_name}}}}, {{{{company}}}}, {{{{title}}}}."
        )

        response = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        content = response.choices[0].message.content
        parsed = json.loads(content)
        # Handle both {"steps": [...]} and [...] formats
        if isinstance(parsed, dict) and "steps" in parsed:
            return parsed["steps"]
        if isinstance(parsed, list):
            return parsed
        return [parsed]

    # ── Reply classification ─────────────────────────────────────────────

    @staticmethod
    async def classify_reply(
        db: AsyncSession,
        email_text: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Classify inbound reply as positive/negative/ooo/bounce/unsubscribe."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are an email reply classifier for a B2B sales platform. "
            "Classify the reply into exactly one category: positive, negative, ooo, bounce, unsubscribe. "
            'Output valid JSON: {"classification": "<category>", "confidence": <0.0-1.0>, '
            '"reason": "<brief explanation>", "suggested_action": "<what to do next>"}.'
        )

        response = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Classify this reply:\n\n{email_text}"},
            ],
            max_tokens=256,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    # ── Compliance check ─────────────────────────────────────────────────

    @staticmethod
    async def check_compliance(
        db: AsyncSession,
        content: str,
        channel: str,
        regulations: list[str] | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Check outreach content against CAN-SPAM/GDPR/TCPA regulations."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        regs = regulations or ["CAN-SPAM", "GDPR", "TCPA"]
        regs_str = ", ".join(regs)

        system_prompt = (
            f"You are a compliance expert for B2B outreach. Review the {channel} content "
            f"for compliance with {regs_str}. "
            "Output valid JSON: "
            '{"compliant": <true/false>, "issues": [{"regulation": "...", "issue": "...", '
            '"severity": "high|medium|low", "fix": "..."}], "score": <0-100>}.'
        )

        response = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Review this {channel} content:\n\n{content}"},
            ],
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    # ── A/B variant generation ───────────────────────────────────────────

    @staticmethod
    async def generate_ab_variants(
        db: AsyncSession,
        original_content: str,
        num_variants: int,
        user_id: UUID | None = None,
    ) -> list[str]:
        """Create A/B test variants of email or message content."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are an A/B testing specialist for B2B email marketing. "
            f"Generate {num_variants} alternative versions of the provided content. "
            "Each variant should test a different angle (tone, CTA, structure, personalization). "
            'Output valid JSON: {"variants": ["variant 1 text", "variant 2 text", ...]}.'
        )

        response = await client.chat.completions.create(
            model=DEFAULT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Create {num_variants} variants of:\n\n{original_content}"},
            ],
            max_tokens=2048,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        return parsed.get("variants", [])

    # ── Warmup email generation ──────────────────────────────────────────

    @staticmethod
    async def generate_warmup_email(
        db: AsyncSession,
        sender_context: str,
        seed_context: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Generate a natural-sounding warmup email."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are an email warmup specialist. Generate a natural, conversational email "
            "that looks like genuine correspondence between business contacts. "
            "The email must NOT look like marketing or sales outreach. "
            "It should be the kind of email that triggers positive engagement (replies, not-spam). "
            'Output valid JSON: {"subject": "...", "body": "...", "tone": "..."}.'
        )
        user_prompt = (
            f"Sender context: {sender_context}\n"
            f"Seed/recipient context: {seed_context}\n"
            "Generate a warmup email that would naturally prompt a reply."
        )

        response = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=512,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    # ── Lead score narrative ─────────────────────────────────────────────

    @staticmethod
    async def score_lead_narrative(
        db: AsyncSession,
        lead_data: dict,
        signals: list[str],
        user_id: UUID | None = None,
    ) -> str:
        """Generate human-readable lead score explanation."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are a sales intelligence analyst. Given lead data and buying signals, "
            "write a concise 2-3 sentence narrative explaining why this lead is scored "
            "the way it is, what signals matter most, and what action the sales rep should take."
        )
        user_prompt = (
            f"Lead data: {json.dumps(lead_data, default=str)}\n"
            f"Buying signals: {', '.join(signals)}\n"
            "Write a brief scoring narrative."
        )

        response = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            max_tokens=256,
        )
        return response.choices[0].message.content

    # ── Analytics summarization ──────────────────────────────────────────

    @staticmethod
    async def summarize_analytics(
        db: AsyncSession,
        metrics_data: dict,
        user_id: UUID | None = None,
    ) -> str:
        """Summarize analytics/metrics in natural language."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are a B2B marketing analytics expert. Summarize the provided metrics "
            "in 3-5 sentences. Highlight key trends, anomalies, and actionable insights. "
            "Use specific numbers from the data. Be direct and useful."
        )

        response = await client.chat.completions.create(
            model=FAST_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Summarize these metrics:\n\n{json.dumps(metrics_data, default=str)}"},
            ],
            max_tokens=512,
        )
        return response.choices[0].message.content
