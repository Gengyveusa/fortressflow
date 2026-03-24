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

    async def enrich_person_waterfall(
                self,
        email=None,
        first_name=None,
        last_name=None,
        organization_name=None,
        domain=None,
        linkedin_url=None,
        run_waterfall_email=True,
        run_waterfall_phone=True,
        reveal_personal_emails=True,
        reveal_phone_number=True,
    ) -> dict:
        """Enrich with waterfall enrichment for emails and phone numbers.

        When reveal_phone_number=True, Apollo delivers phone numbers
        asynchronously via webhook. The sync response has demographic data.
        """
        if not settings.APOLLO_API_KEY:
            logger.debug("Apollo API key not configured, skipping waterfall")
            return {}

        webhook_url = getattr(settings, "APOLLO_WEBHOOK_URL", "")
        if reveal_phone_number and not webhook_url:
            logger.error("reveal_phone_number requires APOLLO_WEBHOOK_URL")
            return {"error": "webhook_url required for phone number reveal"}

        payload = {
            "api_key": settings.APOLLO_API_KEY,
            "reveal_personal_emails": reveal_personal_emails,
            "reveal_phone_number": reveal_phone_number,
        }
        if run_waterfall_email:
            payload["run_waterfall_email"] = True
        if run_waterfall_phone:
            payload["run_waterfall_phone"] = True
        if reveal_phone_number and webhook_url:
            payload["webhook_url"] = webhook_url
        if email:
            payload["email"] = email
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if organization_name:
            payload["organization_name"] = organization_name
        if domain:
            payload["domain"] = domain
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url

        try:
            async with self._limiter:
                logger.info(
                    "Apollo waterfall: email=%s, name=%s %s, org=%s",
                    email, first_name, last_name, organization_name,
                )
                resp = await self._client.post(
                    f"{_APOLLO_BASE}/v1/people/match",
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()
                person = data.get("person")
                if not person:
                    logger.info("Apollo waterfall: no results")
                    return {}

                return {
                    "source": "apollo_waterfall",
                    "data": {
                        "id": person.get("id"),
                        "first_name": person.get("first_name"),
                        "last_name": person.get("last_name"),
                        "email": person.get("email"),
                        "email_status": person.get("email_status"),
                        "phone": person.get("phone_number"),
                        "title": person.get("title"),
                        "headline": person.get("headline"),
                        "organization_name": person.get("organization", {}).get("name"),
                        "linkedin_url": person.get("linkedin_url"),
                        "city": person.get("city"),
                        "state": person.get("state"),
                        "country": person.get("country"),
                    },
                    "waterfall_status": {
                        "email_waterfall": data.get("email_waterfall_status"),
                        "phone_waterfall": data.get("phone_waterfall_status"),
                        "phone_reveal_pending": reveal_phone_number,
                    },
                    "enriched_at": datetime.now(UTC).isoformat(),
                }
        except httpx.TimeoutException:
            logger.warning("Apollo waterfall timeout")
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 500, 502, 503):
                logger.warning(
                    "Apollo waterfall transient error %d",
                    exc.response.status_code,
                )
                raise
            logger.error("Apollo waterfall error: %s", exc)
            return {}
