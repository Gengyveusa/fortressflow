"""
Apollo.io enrichment service with async rate limiting.

Rate limit: configurable via APOLLO_RATE_LIMIT (default 50 req/60s).
Uses /v1/people/match endpoint.
"""

import logging
from datetime import UTC, datetime

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings

logger = logging.getLogger(__name__)

_APOLLO_BASE = "https://api.apollo.io"


class ApolloService:
    """Async Apollo.io enrichment client with rate limiting."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30)
        self._limiter = AsyncLimiter(
            max_rate=settings.APOLLO_RATE_LIMIT, time_period=60
        )

    async def enrich_person(self, email: str) -> dict:
        """Enrich a person by email using Apollo /v1/people/match.

        Returns enriched data dict with source/timestamp, or empty dict on failure.
        """
        if not settings.APOLLO_API_KEY:
            logger.debug("Apollo API key not configured, skipping enrichment")
            return {}

        try:
            async with self._limiter:
                logger.info("Apollo enrich_person: %s", email)
                resp = await self._client.post(
                    f"{_APOLLO_BASE}/v1/people/match",
                    json={
                        "api_key": settings.APOLLO_API_KEY,
                        "email": email,
                    },
                )
                resp.raise_for_status()

            person = resp.json().get("person")
            if not person:
                logger.info("Apollo: no results for %s", email)
                return {}

            return {
                "source": "apollo",
                "data": {
                    "first_name": person.get("first_name"),
                    "last_name": person.get("last_name"),
                    "email": person.get("email"),
                    "phone": person.get("phone_number"),
                    "title": person.get("title"),
                    "organization_name": person.get("organization", {}).get("name"),
                    "linkedin_url": person.get("linkedin_url"),
                },
                "enriched_at": datetime.now(UTC).isoformat(),
            }

        except httpx.TimeoutException:
            logger.warning("Apollo timeout for %s", email)
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 500, 502, 503):
                logger.warning(
                    "Apollo transient error %d for %s",
                    exc.response.status_code,
                    email,
                )
                raise
            logger.error("Apollo error for %s: %s", email, exc)
            return {}
