"""
ZoomInfo enrichment service with async rate limiting.

Rate limit: configurable via ZOOMINFO_RATE_LIMIT (default 25 req/s).
Auth via ZOOMINFO_API_KEY or client_id/secret JWT flow.
"""

import logging
from datetime import UTC, datetime

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings

logger = logging.getLogger(__name__)

_ZOOMINFO_BASE = "https://api.zoominfo.com"


class ZoomInfoService:
    """Async ZoomInfo enrichment client with rate limiting."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30)
        self._limiter = AsyncLimiter(
            max_rate=settings.ZOOMINFO_RATE_LIMIT, time_period=1
        )
        self._jwt_token: str | None = None

    async def _authenticate(self) -> str:
        """Authenticate with ZoomInfo and return JWT token."""
        if self._jwt_token:
            return self._jwt_token

        if settings.ZOOMINFO_API_KEY:
            self._jwt_token = settings.ZOOMINFO_API_KEY
            return self._jwt_token

        if not settings.ZOOMINFO_CLIENT_ID or not settings.ZOOMINFO_CLIENT_SECRET:
            raise ValueError("ZoomInfo credentials not configured")

        async with self._limiter:
            resp = await self._client.post(
                f"{_ZOOMINFO_BASE}/authenticate",
                json={
                    "username": settings.ZOOMINFO_CLIENT_ID,
                    "password": settings.ZOOMINFO_CLIENT_SECRET,
                },
            )
            resp.raise_for_status()
            self._jwt_token = resp.json().get("jwt", "")
            return self._jwt_token

    async def enrich_person(
        self, email: str, company: str | None = None
    ) -> dict:
        """Enrich a person by email (and optional company).

        Returns enriched data dict with source/timestamp, or empty dict on failure.
        """
        if not (
            settings.ZOOMINFO_API_KEY
            or (settings.ZOOMINFO_CLIENT_ID and settings.ZOOMINFO_CLIENT_SECRET)
        ):
            logger.debug("ZoomInfo not configured, skipping enrichment")
            return {}

        try:
            token = await self._authenticate()
            search_body: dict = {
                "emailAddress": email,
                "outputFields": [
                    "firstName",
                    "lastName",
                    "jobTitle",
                    "companyName",
                    "phone",
                    "email",
                    "linkedInUrl",
                    "companyDomain",
                ],
            }
            if company:
                search_body["companyName"] = company

            async with self._limiter:
                logger.info("ZoomInfo enrich_person: %s", email)
                resp = await self._client.post(
                    f"{_ZOOMINFO_BASE}/search/contact",
                    headers={"Authorization": f"Bearer {token}"},
                    json=search_body,
                )
                resp.raise_for_status()

            results = resp.json().get("result", {}).get("data", [])
            if not results:
                logger.info("ZoomInfo: no results for %s", email)
                return {}

            person = results[0]
            return {
                "source": "zoominfo",
                "data": {
                    "first_name": person.get("firstName"),
                    "last_name": person.get("lastName"),
                    "email": person.get("email"),
                    "phone": person.get("phone"),
                    "job_title": person.get("jobTitle"),
                    "company_name": person.get("companyName"),
                    "company_domain": person.get("companyDomain"),
                    "linkedin_url": person.get("linkedInUrl"),
                },
                "enriched_at": datetime.now(UTC).isoformat(),
            }

        except httpx.TimeoutException:
            logger.warning("ZoomInfo timeout for %s", email)
            raise
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code in (429, 500, 502, 503):
                logger.warning(
                    "ZoomInfo transient error %d for %s",
                    exc.response.status_code,
                    email,
                )
                raise
            logger.error("ZoomInfo error for %s: %s", email, exc)
            return {}
        except ValueError:
            logger.warning("ZoomInfo credentials not configured")
            return {}
