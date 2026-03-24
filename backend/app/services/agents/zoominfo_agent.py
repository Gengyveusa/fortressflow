"""
ZoomInfo Intelligence Agent — Full platform agent extending the existing ZoomInfoService.

Provides person/company enrichment, search, intent signals, scoops, tech stack,
email/phone verification, and bulk enrichment operations.
All methods are async with DB-first API key resolution and rate limiting.
"""

import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.api_key_service import get_api_key
from app.services.zoominfo_service import ZoomInfoService

logger = logging.getLogger(__name__)

_ZOOMINFO_BASE = "https://api.zoominfo.com"
_RATE_LIMIT = AsyncLimiter(max_rate=25, time_period=1)


class ZoomInfoAgent:
    """Full ZoomInfo intelligence agent. Composes ZoomInfoService and adds new capabilities."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._service: ZoomInfoService | None = None
        self._jwt_token: str | None = None

    async def _resolve_api_key(self, user_id: UUID | None) -> str:
        """Resolve ZoomInfo API key: DB first, then env fallback."""
        if user_id:
            async with AsyncSessionLocal() as db:
                key = await get_api_key(db, "zoominfo", user_id)
                if key:
                    return key
        if settings.ZOOMINFO_API_KEY:
            return settings.ZOOMINFO_API_KEY
        raise ValueError(
            "ZoomInfo API key not configured — set via Settings or ZOOMINFO_API_KEY env var"
        )

    async def _authenticate(self, user_id: UUID | None = None) -> str:
        """Authenticate and return JWT token."""
        if self._jwt_token:
            return self._jwt_token

        # Try DB-stored key first
        try:
            key = await self._resolve_api_key(user_id)
            self._jwt_token = key
            return self._jwt_token
        except ValueError:
            pass

        # Fall back to client_id/secret JWT flow
        if not settings.ZOOMINFO_CLIENT_ID or not settings.ZOOMINFO_CLIENT_SECRET:
            raise ValueError("ZoomInfo credentials not configured")

        client = await self._get_client(user_id)
        async with _RATE_LIMIT:
            resp = await client.post(
                "/authenticate",
                json={
                    "username": settings.ZOOMINFO_CLIENT_ID,
                    "password": settings.ZOOMINFO_CLIENT_SECRET,
                },
            )
            resp.raise_for_status()
            self._jwt_token = resp.json().get("jwt", "")
            return self._jwt_token

    async def _get_client(self, user_id: UUID | None = None) -> httpx.AsyncClient:
        """Get or create the httpx client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_ZOOMINFO_BASE,
                timeout=30,
            )
        return self._client

    async def _authed_request(
        self, method: str, path: str, user_id: UUID | None = None, **kwargs
    ) -> httpx.Response:
        """Make an authenticated, rate-limited request."""
        token = await self._authenticate(user_id)
        client = await self._get_client(user_id)
        headers = kwargs.pop("headers", {})
        headers["Authorization"] = f"Bearer {token}"
        async with _RATE_LIMIT:
            resp = await client.request(method, path, headers=headers, **kwargs)
        resp.raise_for_status()
        return resp

    # ── Person ─────────────────────────────────────────────────────────────

    async def enrich_person(
        self,
        email: str | None = None,
        name: str | None = None,
        company: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Enrich a person by email, name, or company. Returns full profile."""
        search_body: dict = {
            "outputFields": [
                "firstName", "lastName", "jobTitle", "companyName",
                "phone", "email", "linkedInUrl", "companyDomain",
                "city", "state", "country", "managementLevel",
            ],
        }
        if email:
            search_body["emailAddress"] = email
        if name:
            search_body["fullName"] = name
        if company:
            search_body["companyName"] = company

        if not (email or name or company):
            return {"error": "At least one of email, name, or company is required"}

        try:
            resp = await self._authed_request(
                "POST", "/search/contact", user_id=user_id, json=search_body,
            )
            results = resp.json().get("result", {}).get("data", [])
            if not results:
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
                    "city": person.get("city"),
                    "state": person.get("state"),
                    "country": person.get("country"),
                    "management_level": person.get("managementLevel"),
                },
                "enriched_at": datetime.now(UTC).isoformat(),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo enrich_person error: %s", exc)
            return {"error": str(exc)}

    async def search_people(
        self, filters: dict, user_id: UUID | None = None
    ) -> list[dict]:
        """Search for people using ZoomInfo filters."""
        try:
            resp = await self._authed_request(
                "POST", "/search/contact", user_id=user_id, json=filters,
            )
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
            logger.error("ZoomInfo search_people error: %s", exc)
            return []

    async def bulk_enrich_people(
        self, identifiers: list[dict], user_id: UUID | None = None
    ) -> list[dict]:
        """Bulk enrich multiple people by their identifiers (email, name+company)."""
        try:
            resp = await self._authed_request(
                "POST", "/enrich/contact",
                user_id=user_id,
                json={"matchPersonInput": identifiers},
            )
            results = resp.json().get("result", {}).get("data", [])
            return [
                {
                    "first_name": p.get("firstName"),
                    "last_name": p.get("lastName"),
                    "email": p.get("email"),
                    "job_title": p.get("jobTitle"),
                    "company_name": p.get("companyName"),
                }
                for p in results
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo bulk_enrich_people error: %s", exc)
            return []

    # ── Company ────────────────────────────────────────────────────────────

    async def enrich_company(
        self,
        domain: str | None = None,
        name: str | None = None,
        company_id: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Enrich a company by domain, name, or ZoomInfo company ID."""
        body: dict = {
            "outputFields": [
                "companyName", "website", "revenue", "employeeCount",
                "industry", "city", "state", "country", "founded",
                "description", "stockTicker",
            ],
        }
        if domain:
            body["companyDomain"] = domain
        if name:
            body["companyName"] = name
        if company_id:
            body["companyId"] = company_id

        if not (domain or name or company_id):
            return {"error": "At least one of domain, name, or company_id is required"}

        try:
            resp = await self._authed_request(
                "POST", "/enrich/company", user_id=user_id, json=body,
            )
            results = resp.json().get("result", {}).get("data", [])
            if not results:
                return {}
            co = results[0]
            return {
                "source": "zoominfo",
                "data": {
                    "name": co.get("companyName"),
                    "website": co.get("website"),
                    "revenue": co.get("revenue"),
                    "employee_count": co.get("employeeCount"),
                    "industry": co.get("industry"),
                    "city": co.get("city"),
                    "state": co.get("state"),
                    "country": co.get("country"),
                    "founded": co.get("founded"),
                    "description": co.get("description"),
                    "stock_ticker": co.get("stockTicker"),
                },
                "enriched_at": datetime.now(UTC).isoformat(),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo enrich_company error: %s", exc)
            return {"error": str(exc)}

    async def search_companies(
        self, filters: dict, user_id: UUID | None = None
    ) -> list[dict]:
        """Search companies using ZoomInfo filters."""
        try:
            resp = await self._authed_request(
                "POST", "/search/company", user_id=user_id, json=filters,
            )
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

    async def get_company_hierarchy(
        self, company_id: str, user_id: UUID | None = None
    ) -> dict:
        """Get a company's organizational hierarchy."""
        try:
            resp = await self._authed_request(
                "POST", "/lookup/companyHierarchy",
                user_id=user_id,
                json={"companyId": company_id},
            )
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_company_hierarchy error: %s", exc)
            return {"error": str(exc)}

    # ── Intent ─────────────────────────────────────────────────────────────

    async def get_intent_signals(
        self,
        company_id: str | None = None,
        topics: list[str] | None = None,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Get buying intent signals for a company or topics."""
        body: dict = {}
        if company_id:
            body["companyId"] = company_id
        if topics:
            body["topics"] = topics

        try:
            resp = await self._authed_request(
                "POST", "/intent", user_id=user_id, json=body,
            )
            results = resp.json().get("result", {}).get("data", [])
            return [
                {
                    "company_id": s.get("companyId"),
                    "company_name": s.get("companyName"),
                    "topic": s.get("topic"),
                    "signal_score": s.get("signalScore"),
                    "audience_strength": s.get("audienceStrength"),
                    "date": s.get("date"),
                }
                for s in results
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_intent_signals error: %s", exc)
            return []

    async def get_surge_scores(
        self, company_ids: list[str], user_id: UUID | None = None
    ) -> list[dict]:
        """Get intent surge scores for a list of companies."""
        try:
            resp = await self._authed_request(
                "POST", "/intent",
                user_id=user_id,
                json={"companyIds": company_ids},
            )
            results = resp.json().get("result", {}).get("data", [])
            return [
                {
                    "company_id": s.get("companyId"),
                    "company_name": s.get("companyName"),
                    "surge_score": s.get("signalScore"),
                    "topics": s.get("topics", []),
                }
                for s in results
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_surge_scores error: %s", exc)
            return []

    # ── Intelligence ───────────────────────────────────────────────────────

    async def get_scoops(
        self,
        company_id: str | None = None,
        scoop_types: list[str] | None = None,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Get actionable intelligence scoops for a company."""
        body: dict = {}
        if company_id:
            body["companyId"] = company_id
        if scoop_types:
            body["scoopTypes"] = scoop_types

        try:
            resp = await self._authed_request(
                "POST", "/scoops", user_id=user_id, json=body,
            )
            results = resp.json().get("result", {}).get("data", [])
            return [
                {
                    "id": s.get("id"),
                    "type": s.get("scoopType"),
                    "description": s.get("description"),
                    "published_date": s.get("publishedDate"),
                    "company_name": s.get("companyName"),
                }
                for s in results
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_scoops error: %s", exc)
            return []

    async def get_news(
        self, company_id: str, user_id: UUID | None = None
    ) -> list[dict]:
        """Get recent news for a company."""
        try:
            resp = await self._authed_request(
                "POST", "/news",
                user_id=user_id,
                json={"companyId": company_id},
            )
            results = resp.json().get("result", {}).get("data", [])
            return [
                {
                    "title": n.get("title"),
                    "url": n.get("url"),
                    "published_date": n.get("publishedDate"),
                    "source": n.get("source"),
                }
                for n in results
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_news error: %s", exc)
            return []

    async def get_tech_stack(
        self, company_id: str, user_id: UUID | None = None
    ) -> dict:
        """Get the technology stack for a company."""
        try:
            resp = await self._authed_request(
                "POST", "/enrich/tech",
                user_id=user_id,
                json={"companyId": company_id},
            )
            data = resp.json().get("result", {}).get("data", [])
            technologies = [
                {
                    "name": t.get("technologyName"),
                    "category": t.get("category"),
                    "subcategory": t.get("subCategory"),
                    "vendor": t.get("vendor"),
                }
                for t in data
            ]
            return {"company_id": company_id, "technologies": technologies}
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_tech_stack error: %s", exc)
            return {"error": str(exc)}

    # ── Verification ───────────────────────────────────────────────────────

    async def verify_email(
        self, email: str, user_id: UUID | None = None
    ) -> dict:
        """Verify an email address."""
        try:
            resp = await self._authed_request(
                "POST", "/lookup/email/validate",
                user_id=user_id,
                json={"emailAddress": email},
            )
            data = resp.json()
            return {
                "email": email,
                "status": data.get("status"),
                "sub_status": data.get("subStatus"),
                "is_valid": data.get("status") == "valid",
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo verify_email error: %s", exc)
            return {"email": email, "error": str(exc)}

    async def verify_phone(
        self, phone: str, user_id: UUID | None = None
    ) -> dict:
        """Verify a phone number."""
        try:
            resp = await self._authed_request(
                "POST", "/lookup/phone/validate",
                user_id=user_id,
                json={"phoneNumber": phone},
            )
            data = resp.json()
            return {
                "phone": phone,
                "status": data.get("status"),
                "phone_type": data.get("phoneType"),
                "is_valid": data.get("status") == "valid",
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo verify_phone error: %s", exc)
            return {"phone": phone, "error": str(exc)}

    # ── Bulk ───────────────────────────────────────────────────────────────

    async def bulk_enrich(
        self, inputs: list[dict], match_type: str = "email", user_id: UUID | None = None
    ) -> dict:
        """Start a bulk enrichment job. Returns job ID for status polling."""
        try:
            resp = await self._authed_request(
                "POST", "/bulk/enrich",
                user_id=user_id,
                json={"inputData": inputs, "matchType": match_type},
            )
            data = resp.json()
            return {
                "job_id": data.get("jobId"),
                "status": data.get("status"),
                "total_records": len(inputs),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo bulk_enrich error: %s", exc)
            return {"error": str(exc)}

    async def get_bulk_status(
        self, job_id: str, user_id: UUID | None = None
    ) -> dict:
        """Check the status of a bulk enrichment job."""
        try:
            resp = await self._authed_request(
                "GET", f"/bulk/{job_id}/status", user_id=user_id,
            )
            data = resp.json()
            return {
                "job_id": job_id,
                "status": data.get("status"),
                "progress": data.get("progress"),
                "total_records": data.get("totalRecords"),
                "completed_records": data.get("completedRecords"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_bulk_status error: %s", exc)
            return {"error": str(exc)}

    async def get_bulk_results(
        self, job_id: str, user_id: UUID | None = None
    ) -> list[dict]:
        """Download results from a completed bulk enrichment job."""
        try:
            resp = await self._authed_request(
                "GET", f"/bulk/{job_id}/results", user_id=user_id,
            )
            return resp.json().get("result", {}).get("data", [])
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_bulk_results error: %s", exc)
            return []

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
