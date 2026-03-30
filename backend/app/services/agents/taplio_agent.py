"""
Taplio LinkedIn Growth Agent — LinkedIn content generation and scheduling via Zapier webhooks.

Taplio has no direct REST API. This agent works by:
1. Using Groq to generate LinkedIn-optimized content (posts, carousels, DMs, hooks)
2. Triggering Zapier webhooks for scheduling, connection requests, and analytics
3. Composing payloads for Taplio's Zapier integrations

All methods are async with DB-first API key resolution.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from sqlalchemy.ext.asyncio import AsyncSession


logger = logging.getLogger(__name__)

_ZAPIER_TIMEOUT = 30

# LinkedIn content system prompts
_LINKEDIN_SYSTEM_PROMPT = (
    "You are an expert LinkedIn content strategist specializing in dental B2B marketing. "
    "You create highly engaging, authentic posts that drive impressions and meaningful engagement. "
    "You understand LinkedIn's algorithm: posts that spark conversation, use hooks, "
    "and provide actionable value perform best. Write in a conversational, authoritative tone. "
    "Avoid corporate jargon. Use short paragraphs and line breaks for readability."
)

_DM_SYSTEM_PROMPT = (
    "You are a LinkedIn outreach specialist for dental B2B sales. "
    "You write personalized, non-salesy DMs that build genuine connections. "
    "Keep messages concise (under 300 characters for connection requests, under 500 for DMs). "
    "Reference specific details about the recipient to show genuine interest."
)


class TaplioAgent:
    """Taplio LinkedIn growth agent. Generates content via Groq, schedules via Zapier."""

    def __init__(self) -> None:
        self._http_client: httpx.AsyncClient | None = None

    async def _get_http_client(self) -> httpx.AsyncClient:
        """Get or create an httpx client for Zapier webhook calls."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=_ZAPIER_TIMEOUT)
        return self._http_client

    async def _call_groq(
        self,
        db: AsyncSession,
        user_id: UUID,
        system_prompt: str,
        user_prompt: str,
        model: str | None = None,
    ) -> str:
        """Call GroqAgent.chat() to generate content."""
        from app.services.agents.groq_agent import GroqAgent

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        result = await GroqAgent.chat(
            db=db,
            messages=messages,
            model=model,
            user_id=user_id,
        )
        return result if isinstance(result, str) else ""

    # ── Content Generation ─────────────────────────────────────────────────

    async def generate_linkedin_post(
        self,
        db: AsyncSession,
        user_id: UUID,
        topic: str,
        tone: str = "professional",
        format: str = "text",
        hook_style: str = "question",
    ) -> dict:
        """Generate an engaging LinkedIn post optimized for the algorithm."""
        user_prompt = (
            f"Write a LinkedIn post about: {topic}\n\n"
            f"Tone: {tone}\n"
            f"Format: {format} (text = plain text post, list = numbered insights, story = narrative)\n"
            f"Hook style: {hook_style} (question, bold statement, statistic, contrarian)\n\n"
            "Requirements:\n"
            "- Start with an attention-grabbing hook (first line is critical)\n"
            "- Use short paragraphs (1-2 sentences each)\n"
            "- Include a clear call-to-action at the end\n"
            "- Add 3-5 relevant hashtags\n"
            "- Keep under 1300 characters for optimal reach\n"
            "- Focus on dental industry B2B value"
        )

        try:
            content = await self._call_groq(db, user_id, _LINKEDIN_SYSTEM_PROMPT, user_prompt)
            return {
                "content": content,
                "topic": topic,
                "tone": tone,
                "format": format,
                "hook_style": hook_style,
                "generated_at": datetime.now(UTC).isoformat(),
                "character_count": len(content),
            }
        except Exception as exc:
            logger.error("Taplio generate_linkedin_post error: %s", exc)
            return {"error": str(exc)}

    async def schedule_post(
        self,
        db: AsyncSession,
        user_id: UUID,
        content: str,
        scheduled_time: str,
        zapier_webhook_url: str,
    ) -> dict:
        """Schedule a LinkedIn post via Zapier webhook to Taplio."""
        payload = {
            "action": "schedule_post",
            "content": content,
            "scheduled_time": scheduled_time,
            "user_id": str(user_id),
            "platform": "linkedin",
        }

        try:
            client = await self._get_http_client()
            resp = await client.post(zapier_webhook_url, json=payload)
            resp.raise_for_status()
            return {
                "success": True,
                "scheduled_time": scheduled_time,
                "content_preview": content[:100] + "..." if len(content) > 100 else content,
                "webhook_status": resp.status_code,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Taplio schedule_post webhook error: %s", exc)
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.error("Taplio schedule_post error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def generate_carousel(
        self,
        db: AsyncSession,
        user_id: UUID,
        topic: str,
        num_slides: int = 8,
        style: str = "educational",
    ) -> dict:
        """Generate LinkedIn carousel content (slide-by-slide text)."""
        user_prompt = (
            f"Create a LinkedIn carousel about: {topic}\n\n"
            f"Number of slides: {num_slides}\n"
            f"Style: {style}\n\n"
            "Requirements:\n"
            "- Slide 1: Hook slide with a compelling title and subtitle\n"
            "- Slides 2-{0}: One key insight per slide, with a headline and 1-2 supporting lines\n"
            "- Last slide: CTA slide (follow, comment, share, save)\n"
            "- Each slide should have: a headline (max 8 words) and body text (max 30 words)\n"
            "- Focus on dental B2B industry insights\n\n"
            "Format each slide as:\n"
            "SLIDE [number]:\n"
            "Headline: [text]\n"
            "Body: [text]"
        ).format(num_slides - 1)

        try:
            content = await self._call_groq(db, user_id, _LINKEDIN_SYSTEM_PROMPT, user_prompt)
            return {
                "slides_content": content,
                "topic": topic,
                "num_slides": num_slides,
                "style": style,
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("Taplio generate_carousel error: %s", exc)
            return {"error": str(exc)}

    async def generate_hook(
        self,
        db: AsyncSession,
        user_id: UUID,
        topic: str,
        num_hooks: int = 5,
    ) -> dict:
        """Generate attention-grabbing LinkedIn hooks."""
        user_prompt = (
            f"Generate {num_hooks} attention-grabbing LinkedIn post hooks about: {topic}\n\n"
            "Requirements:\n"
            "- Each hook should be 1 sentence (max 15 words)\n"
            "- Mix of styles: question, bold statement, statistic, contrarian, personal story\n"
            "- Each should make the reader STOP scrolling\n"
            "- Relevant to dental B2B industry\n\n"
            "Format:\n"
            "1. [hook]\n"
            "2. [hook]\n"
            "etc."
        )

        try:
            content = await self._call_groq(db, user_id, _LINKEDIN_SYSTEM_PROMPT, user_prompt)
            return {
                "hooks": content,
                "topic": topic,
                "num_hooks": num_hooks,
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("Taplio generate_hook error: %s", exc)
            return {"error": str(exc)}

    async def compose_dm(
        self,
        db: AsyncSession,
        user_id: UUID,
        recipient_name: str,
        recipient_title: str,
        recipient_company: str,
        context: str | None = None,
        tone: str = "friendly",
    ) -> dict:
        """Generate a personalized LinkedIn DM."""
        user_prompt = (
            f"Write a personalized LinkedIn DM to:\n"
            f"- Name: {recipient_name}\n"
            f"- Title: {recipient_title}\n"
            f"- Company: {recipient_company}\n"
        )
        if context:
            user_prompt += f"- Context/reason for reaching out: {context}\n"
        user_prompt += (
            f"\nTone: {tone}\n\n"
            "Requirements:\n"
            "- Keep under 500 characters\n"
            "- Reference something specific about them\n"
            "- Don't be salesy — focus on building a connection\n"
            "- End with an easy-to-answer question\n"
            "- Sound human and genuine, not templated"
        )

        try:
            content = await self._call_groq(db, user_id, _DM_SYSTEM_PROMPT, user_prompt)
            return {
                "dm_content": content,
                "recipient": {
                    "name": recipient_name,
                    "title": recipient_title,
                    "company": recipient_company,
                },
                "tone": tone,
                "character_count": len(content),
                "generated_at": datetime.now(UTC).isoformat(),
            }
        except Exception as exc:
            logger.error("Taplio compose_dm error: %s", exc)
            return {"error": str(exc)}

    async def bulk_compose_dms(
        self,
        db: AsyncSession,
        user_id: UUID,
        recipients: list[dict],
        template: str | None = None,
        tone: str = "friendly",
    ) -> dict:
        """Generate personalized DMs for a list of recipients."""
        results: list[dict] = []
        errors: list[dict] = []

        for recipient in recipients:
            name = recipient.get("name", "")
            title = recipient.get("title", "")
            company = recipient.get("company", "")
            context = recipient.get("context", template)

            try:
                dm = await self.compose_dm(
                    db=db,
                    user_id=user_id,
                    recipient_name=name,
                    recipient_title=title,
                    recipient_company=company,
                    context=context,
                    tone=tone,
                )
                if "error" in dm:
                    errors.append({"recipient": name, "error": dm["error"]})
                else:
                    results.append(dm)
            except Exception as exc:
                errors.append({"recipient": name, "error": str(exc)})

        return {
            "dms": results,
            "total_generated": len(results),
            "total_errors": len(errors),
            "errors": errors,
        }

    # ── Zapier Integration ─────────────────────────────────────────────────

    async def trigger_zapier_action(
        self,
        db: AsyncSession,
        user_id: UUID,
        webhook_url: str,
        action: str,
        payload: dict,
    ) -> dict:
        """Generic Zapier webhook trigger for Taplio actions."""
        full_payload = {
            "action": action,
            "user_id": str(user_id),
            "timestamp": datetime.now(UTC).isoformat(),
            **payload,
        }

        try:
            client = await self._get_http_client()
            resp = await client.post(webhook_url, json=full_payload)
            resp.raise_for_status()
            return {
                "success": True,
                "action": action,
                "webhook_status": resp.status_code,
                "response": resp.text[:200] if resp.text else None,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Taplio trigger_zapier_action error: %s", exc)
            return {"success": False, "error": str(exc)}
        except Exception as exc:
            logger.error("Taplio trigger_zapier_action error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def search_leads(
        self,
        db: AsyncSession,
        user_id: UUID,
        location: str | None = None,
        title: str | None = None,
        industry: str | None = None,
        seniority: str | None = None,
        limit: int = 25,
    ) -> dict:
        """Placeholder for Taplio lead database search (requires Taplio Pro + Zapier).

        In practice, this builds a search payload and sends it to Taplio's
        Zapier search webhook. The results come back asynchronously.
        """
        search_criteria = {}
        if location:
            search_criteria["location"] = location
        if title:
            search_criteria["title"] = title
        if industry:
            search_criteria["industry"] = industry
        if seniority:
            search_criteria["seniority"] = seniority
        search_criteria["limit"] = limit

        return {
            "status": "requires_webhook",
            "message": (
                "Taplio lead search requires a Zapier webhook URL configured "
                "for the search_leads trigger. Use trigger_zapier_action() with "
                "action='search_leads' and the search criteria as payload."
            ),
            "search_criteria": search_criteria,
        }

    async def get_post_analytics(
        self,
        db: AsyncSession,
        user_id: UUID,
        zapier_webhook_url: str,
    ) -> dict:
        """Request post analytics via Zapier webhook."""
        return await self.trigger_zapier_action(
            db=db,
            user_id=user_id,
            webhook_url=zapier_webhook_url,
            action="get_analytics",
            payload={"request_type": "post_analytics"},
        )

    async def create_connection_request(
        self,
        db: AsyncSession,
        user_id: UUID,
        linkedin_url: str,
        note: str | None = None,
        zapier_webhook_url: str | None = None,
    ) -> dict:
        """Trigger a LinkedIn connection request via Zapier."""
        if not zapier_webhook_url:
            return {
                "success": False,
                "error": "Zapier webhook URL required for connection requests",
            }

        payload = {
            "linkedin_url": linkedin_url,
        }
        if note:
            payload["note"] = note[:300]  # LinkedIn limits connection notes

        return await self.trigger_zapier_action(
            db=db,
            user_id=user_id,
            webhook_url=zapier_webhook_url,
            action="connection_request",
            payload=payload,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
