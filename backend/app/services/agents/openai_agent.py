"""OpenAI agent — fallback LLM, embeddings, moderation, structured extraction."""

import json
import logging
import time
from collections.abc import AsyncGenerator
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.services import api_key_service

logger = logging.getLogger(__name__)

# Rate limiter: 60 requests/minute
_request_timestamps: dict[str, list[float]] = {}
_RATE_LIMIT = 60
_RATE_WINDOW = 60.0

DEFAULT_CHAT_MODEL = "gpt-4o-mini"
EMBEDDING_MODEL = "text-embedding-3-small"


def _check_rate_limit(user_id: str) -> None:
    """Enforce 60 req/min per user. Raises RuntimeError if exceeded."""
    now = time.time()
    key = f"openai:{user_id}"
    timestamps = _request_timestamps.setdefault(key, [])
    _request_timestamps[key] = [t for t in timestamps if now - t < _RATE_WINDOW]
    if len(_request_timestamps[key]) >= _RATE_LIMIT:
        raise RuntimeError("OpenAI rate limit exceeded (60 req/min). Please wait.")
    _request_timestamps[key].append(now)


async def _get_api_key(db: AsyncSession, user_id: UUID | None = None) -> str:
    """Load OpenAI API key from DB first, then fall back to env."""
    key = await api_key_service.get_api_key(db, "openai", user_id)
    if not key:
        raise RuntimeError("OpenAI API key not configured. Add it in Settings → API Keys.")
    return key


def _get_client(api_key: str):
    """Lazily import and create an OpenAI async client."""
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise RuntimeError("openai package not installed. Run: pip install openai")
    return AsyncOpenAI(api_key=api_key)


class OpenAIAgent:
    """OpenAI API agent — fallback LLM + embeddings + moderation + structured outputs."""

    # ── Chat completions ─────────────────────────────────────────────────

    @staticmethod
    async def chat(
        db: AsyncSession,
        messages: list[dict],
        stream: bool = False,
        json_mode: bool = False,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> str | AsyncGenerator[str, None]:
        """GPT-4o-mini chat completions — streaming and non-streaming."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        # Inject PromptEngine system prompt if no system message exists
        if prompt_engine_context and user_id:
            has_system = any(m.get("role") == "system" for m in messages)
            if not has_system:
                try:
                    pe = prompt_engine_context.get("prompt_engine")
                    if pe:
                        action = prompt_engine_context.get("action", "chat")
                        sys_prompt = await pe.build_system_prompt(db, user_id, "openai", action)
                        messages = [{"role": "system", "content": sys_prompt}] + messages
                except Exception as exc:
                    logger.debug("PromptEngine fallback for openai.chat: %s", exc)

        kwargs: dict = {
            "model": DEFAULT_CHAT_MODEL,
            "messages": messages,
            "max_tokens": settings.CHAT_MAX_TOKENS,
        }
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        if stream:
            return OpenAIAgent._stream_chat(client, kwargs)

        response = await client.chat.completions.create(**kwargs)
        return response.choices[0].message.content

    @staticmethod
    async def _stream_chat(client, kwargs: dict) -> AsyncGenerator[str, None]:
        """Internal streaming generator."""
        kwargs["stream"] = True
        response = await client.chat.completions.create(**kwargs)
        async for chunk in response:
            delta = chunk.choices[0].delta
            if delta.content:
                yield delta.content

    # ── Embeddings ───────────────────────────────────────────────────────

    @staticmethod
    async def embed(
        db: AsyncSession,
        texts: list[str],
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> list[list[float]]:
        """Generate embeddings using text-embedding-3-small."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        response = await client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=texts,
        )
        return [item.embedding for item in response.data]

    # ── Content moderation ───────────────────────────────────────────────

    @staticmethod
    async def moderate(
        db: AsyncSession,
        content: str,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Run content through OpenAI's moderation endpoint."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        response = await client.moderations.create(input=content)
        result = response.results[0]
        return {
            "flagged": result.flagged,
            "categories": {k: v for k, v in result.categories.model_dump().items() if v},
            "category_scores": {
                k: round(v, 4)
                for k, v in result.category_scores.model_dump().items()
                if v > 0.01
            },
        }

    # ── Structured extraction ────────────────────────────────────────────

    @staticmethod
    async def extract_structured(
        db: AsyncSession,
        text: str,
        schema_description: str,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Extract structured JSON from unstructured text using json_mode."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are a data extraction specialist. Extract structured information from the "
            "provided text according to the schema description. Output valid JSON only."
        )

        response = await client.chat.completions.create(
            model=DEFAULT_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": f"Schema: {schema_description}\n\nText to extract from:\n{text}",
                },
            ],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    # ── Template performance analysis ────────────────────────────────────

    @staticmethod
    async def analyze_template_performance(
        db: AsyncSession,
        template_content: str,
        metrics: dict,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> dict:
        """Analyze email template effectiveness based on performance metrics."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            "You are an email marketing performance analyst. Analyze the template and its "
            "performance metrics. Provide actionable insights. "
            "Output valid JSON: "
            '{"score": <0-100>, "strengths": ["..."], "weaknesses": ["..."], '
            '"recommendations": ["..."], "predicted_improvement": "..."}.'
        )

        response = await client.chat.completions.create(
            model=DEFAULT_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Template:\n{template_content}\n\n"
                        f"Metrics:\n{json.dumps(metrics, default=str)}"
                    ),
                },
            ],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        return json.loads(response.choices[0].message.content)

    # ── Content improvement suggestions ──────────────────────────────────

    @staticmethod
    async def suggest_improvements(
        db: AsyncSession,
        content: str,
        channel: str,
        metrics: dict,
        user_id: UUID | None = None,
        prompt_engine_context: dict | None = None,
    ) -> list[dict]:
        """Suggest content improvements based on channel and performance data."""
        _check_rate_limit(str(user_id or "anon"))
        api_key = await _get_api_key(db, user_id)
        client = _get_client(api_key)

        system_prompt = (
            f"You are a {channel} content optimization expert for B2B outreach. "
            "Suggest specific, actionable improvements for the provided content. "
            "Output valid JSON: "
            '{"suggestions": [{"area": "...", "current": "...", "suggested": "...", '
            '"expected_impact": "...", "priority": "high|medium|low"}]}.'
        )

        response = await client.chat.completions.create(
            model=DEFAULT_CHAT_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        f"Channel: {channel}\n"
                        f"Content:\n{content}\n\n"
                        f"Current metrics:\n{json.dumps(metrics, default=str)}"
                    ),
                },
            ],
            max_tokens=1024,
            response_format={"type": "json_object"},
        )
        parsed = json.loads(response.choices[0].message.content)
        return parsed.get("suggestions", [])
