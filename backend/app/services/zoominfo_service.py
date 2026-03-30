"""
ZoomInfo enrichment service with async rate limiting.

Rate limit: configurable via ZOOMINFO_RATE_LIMIT (default 25 req/s).
Auth priority:
  1. ZOOMINFO_API_KEY (direct Bearer token)
  2. RSA private-key JWT flow (ZOOMINFO_CLIENT_ID + ZOOMINFO_PRIVATE_KEY)
  3. Client-id/secret legacy flow (ZOOMINFO_CLIENT_ID + ZOOMINFO_CLIENT_SECRET)
"""

import logging
import time
from datetime import UTC, datetime

import httpx
from aiolimiter import AsyncLimiter
from jose import jwt as jose_jwt

from app.config import settings

logger = logging.getLogger(__name__)


class ZoomInfoService:
    """Async ZoomInfo enrichment client with rate limiting."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._base_url = settings.ZOOMINFO_API_BASE_URL or "https://api.zoominfo.com"
        self._client = http_client or httpx.AsyncClient(timeout=30)
        self._limiter = AsyncLimiter(max_rate=settings.ZOOMINFO_RATE_LIMIT, time_period=1)
        self._access_token: str | None = None
        self._token_expires_at: float = 0

    def _is_configured(self) -> bool:
        """Return True if any ZoomInfo auth method is configured."""
        return bool(
            settings.ZOOMINFO_API_KEY
            or (settings.ZOOMINFO_CLIENT_ID and settings.ZOOMINFO_PRIVATE_KEY)
            or (settings.ZOOMINFO_CLIENT_ID and settings.ZOOMINFO_CLIENT_SECRET)
        )

    def _build_client_jwt(self) -> str:
        """Build a short-lived JWT signed with the RSA private key."""
        now = int(time.time())
        payload = {
            "iss": settings.ZOOMINFO_CLIENT_ID,
            "aud": "https://api.zoominfo.com",
            "iat": now,
            "exp": now + 300,
        }
        return jose_jwt.encode(
            payload,
            settings.ZOOMINFO_PRIVATE_KEY,
            algorithm="RS256",
        )

    async def _authenticate(self) -> str:
        """Authenticate with ZoomInfo and return an access token.

        Uses cached token if still valid (tokens last ~1 hour).
        """
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        # 1. Direct API key — use as-is
        if settings.ZOOMINFO_API_KEY:
            self._access_token = settings.ZOOMINFO_API_KEY
            self._token_expires_at = time.time() + 3600
            return self._access_token

        # 2. RSA private-key JWT flow
        if settings.ZOOMINFO_CLIENT_ID and settings.ZOOMINFO_PRIVATE_KEY:
            client_jwt = self._build_client_jwt()
            async with self._limiter:
                resp = await self._client.post(
                    f"{self._base_url}/authenticate",
                    headers={"Content-Type": "application/json"},
                    json={"clientId": settings.ZOOMINFO_CLIENT_ID, "privateKey": client_jwt},
                )
                resp.raise_for_status()
            self._access_token = resp.json().get("jwt", "")
            # Cache for 55 minutes (tokens last ~1h, refresh early)
            self._token_expires_at = time.time() + 3300
            return self._access_token

        # 3. Legacy client-id/secret flow
        if settings.ZOOMINFO_CLIENT_ID and settings.ZOOMINFO_CLIENT_SECRET:
            async with self._limiter:
                resp = await self._client.post(
                    f"{self._base_url}/authenticate",
                    json={
                        "username": settings.ZOOMINFO_CLIENT_ID,
                        "password": settings.ZOOMINFO_CLIENT_SECRET,
                    },
                )
                resp.raise_for_status()
            self._access_token = resp.json().get("jwt", "")
            self._token_expires_at = time.time() + 3300
            return self._access_token

        raise ValueError("ZoomInfo credentials not configured")

    async def _authed_request(self, method: str, path: str, **kwargs) -> httpx.Response:
        """Make an authenticated, rate-limited request to ZoomInfo."""
        token = await self._authenticate()
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        url = f"{self._base_url}{path}"
        async with self._limiter:
            resp = await self._client.request(method, url, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp

    # ── Contact / Lead operations ──────────────────────────────

    async def enrich_person(self, email: str, company: str | None = None) -> dict:
        """Enrich a person by email (and optional company).

        Returns enriched data dict with source/timestamp, or empty dict on failure.
        """
        if not self._is_configured():
            logger.debug("ZoomInfo not configured, skipping enrichment")
            return {}

        try:
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

            logger.info("ZoomInfo enrich_person: %s", email)
            resp = await self._authed_request("POST", "/search/contact", json=search_body)

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

    async def search_contacts(self, query: dict) -> list[dict]:
        """Search for contacts/leads.

        `query` is passed directly as the ZoomInfo search body.
        At minimum include filters like jobTitle, companyName, etc.
        """
        if not self._is_configured():
            return []

        try:
            query.setdefault(
                "outputFields",
                [
                    "firstName",
                    "lastName",
                    "jobTitle",
                    "companyName",
                    "phone",
                    "email",
                    "linkedInUrl",
                    "companyDomain",
                ],
            )
            resp = await self._authed_request("POST", "/search/contact", json=query)
            results = resp.json().get("result", {}).get("data", [])
            return [
                {
                    "id": p.get("id"),
                    "first_name": p.get("firstName"),
                    "last_name": p.get("lastName"),
                    "email": p.get("email"),
                    "phone": p.get("phone"),
                    "job_title": p.get("jobTitle"),
                    "company_name": p.get("companyName"),
                    "linkedin_url": p.get("linkedInUrl"),
                }
                for p in results
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo search_contacts error: %s", exc)
            return []

    async def enrich_contact(self, email: str) -> dict:
        """Enrich a single lead by email address.

        Convenience wrapper around enrich_person for the task spec.
        """
        return await self.enrich_person(email)

    async def search_companies(self, query: dict) -> list[dict]:
        """Search for companies using ZoomInfo filters.

        `query` is passed directly as the ZoomInfo search body.
        """
        if not self._is_configured():
            return []

        try:
            query.setdefault(
                "outputFields",
                [
                    "companyName",
                    "website",
                    "revenue",
                    "employeeCount",
                    "industry",
                    "city",
                    "state",
                    "country",
                ],
            )
            resp = await self._authed_request("POST", "/search/company", json=query)
            results = resp.json().get("result", {}).get("data", [])
            return [
                {
                    "id": c.get("id"),
                    "name": c.get("companyName"),
                    "website": c.get("website"),
                    "revenue": c.get("revenue"),
                    "employee_count": c.get("employeeCount"),
                    "industry": c.get("industry"),
                }
                for c in results
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo search_companies error: %s", exc)
            return []
