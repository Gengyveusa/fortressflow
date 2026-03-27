"""
ZoomInfo Intelligence Agent — Full platform agent extending the existing ZoomInfoService.

Provides person/company enrichment, search, intent signals, scoops, tech stack,
email/phone verification, and bulk enrichment operations.
All methods are async with DB-first API key resolution and rate limiting.
"""

import logging
import time
from datetime import UTC, datetime
from uuid import UUID

import httpx
from aiolimiter import AsyncLimiter
from jose import jwt as jose_jwt

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.api_key_service import get_api_key
from app.services.zoominfo_service import ZoomInfoService

logger = logging.getLogger(__name__)

_ZOOMINFO_BASE = settings.ZOOMINFO_API_BASE_URL or "https://api.zoominfo.com"
_RATE_LIMIT = AsyncLimiter(max_rate=25, time_period=1)


class ZoomInfoAgent:
    """Full ZoomInfo intelligence agent. Composes ZoomInfoService and adds new capabilities."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._service: ZoomInfoService | None = None
        self._access_token: str | None = None
        self._token_expires_at: float = 0

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

    @staticmethod
    def _build_client_jwt() -> str:
        """Build a short-lived JWT signed with the RSA private key."""
        now = int(time.time())
        payload = {
            "iss": settings.ZOOMINFO_CLIENT_ID,
            "aud": "https://api.zoominfo.com",
            "iat": now,
            "exp": now + 300,
        }
        return jose_jwt.encode(payload, settings.ZOOMINFO_PRIVATE_KEY, algorithm="RS256")

    async def _authenticate(self, user_id: UUID | None = None) -> str:
        """Authenticate and return an access token. Uses cached token if still valid."""
        if self._access_token and time.time() < self._token_expires_at:
            return self._access_token

        # 1. Try DB-stored key first
        try:
            key = await self._resolve_api_key(user_id)
            self._access_token = key
            self._token_expires_at = time.time() + 3600
            return self._access_token
        except ValueError:
            pass

        # 2. RSA private-key JWT flow
        if settings.ZOOMINFO_CLIENT_ID and settings.ZOOMINFO_PRIVATE_KEY:
            client_jwt = self._build_client_jwt()
            client = await self._get_client(user_id)
            async with _RATE_LIMIT:
                resp = await client.post(
                    "/authenticate",
                    json={"clientId": settings.ZOOMINFO_CLIENT_ID, "privateKey": client_jwt},
                )
                resp.raise_for_status()
            self._access_token = resp.json().get("jwt", "")
            self._token_expires_at = time.time() + 3300
            return self._access_token

        # 3. Legacy client-id/secret flow
        if settings.ZOOMINFO_CLIENT_ID and settings.ZOOMINFO_CLIENT_SECRET:
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
            self._access_token = resp.json().get("jwt", "")
            self._token_expires_at = time.time() + 3300
            return self._access_token

        raise ValueError("ZoomInfo credentials not configured")

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
        # If token expired (401), refresh and retry once
        if resp.status_code == 401:
            self._access_token = None
            self._token_expires_at = 0
            token = await self._authenticate(user_id)
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

    # ── WebSights ─────────────────────────────────────────────────────────────

    async def get_website_visitors(
        self,
        domain: str,
        date_from: str | None = None,
        date_to: str | None = None,
        page: int = 1,
        page_size: int = 25,
        user_id: UUID | None = None,
    ) -> dict:
        """Get website visitors tracked by ZoomInfo WebSights."""
        body: dict = {
            "domain": domain,
            "page": page,
            "pageSize": min(page_size, 100),
        }
        if date_from:
            body["dateFrom"] = date_from
        if date_to:
            body["dateTo"] = date_to

        try:
            resp = await self._authed_request(
                "POST", "/websights/v1/visitors", user_id=user_id, json=body,
            )
            data = resp.json()
            visitors = data.get("result", {}).get("data", [])
            return {
                "visitors": [
                    {
                        "company_name": v.get("companyName"),
                        "company_id": v.get("companyId"),
                        "domain": v.get("domain"),
                        "visit_count": v.get("visitCount"),
                        "page_views": v.get("pageViews"),
                        "first_visit": v.get("firstVisit"),
                        "last_visit": v.get("lastVisit"),
                        "city": v.get("city"),
                        "state": v.get("state"),
                        "country": v.get("country"),
                    }
                    for v in visitors
                ],
                "total": data.get("result", {}).get("totalResults", 0),
                "page": page,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_website_visitors error: %s", exc)
            return {"error": str(exc)}


    async def get_visitor_companies(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Get companies visiting your website via WebSights."""
        body: dict = {}
        if date_from:
            body["dateFrom"] = date_from
        if date_to:
            body["dateTo"] = date_to

        try:
            resp = await self._authed_request(
                "POST", "/websights/v1/companies", user_id=user_id, json=body,
            )
            data = resp.json()
            companies = data.get("result", {}).get("data", [])
            return [
                {
                    "company_id": c.get("companyId"),
                    "company_name": c.get("companyName"),
                    "domain": c.get("domain"),
                    "industry": c.get("industry"),
                    "employee_count": c.get("employeeCount"),
                    "visit_count": c.get("visitCount"),
                    "first_visit": c.get("firstVisit"),
                    "last_visit": c.get("lastVisit"),
                }
                for c in companies
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_visitor_companies error: %s", exc)
            return []


    # ── Compliance ────────────────────────────────────────────────────────────

    async def check_opt_out(
        self, email: str, user_id: UUID | None = None,
    ) -> dict:
        """Check if an email is opted out."""
        try:
            resp = await self._authed_request(
                "POST", "/compliance/v1/optout/check",
                user_id=user_id,
                json={"emailAddress": email},
            )
            data = resp.json()
            return {
                "email": email,
                "opted_out": data.get("isOptedOut", False),
                "opt_out_date": data.get("optOutDate"),
                "reason": data.get("reason"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo check_opt_out error: %s", exc)
            return {"email": email, "error": str(exc)}


    async def add_opt_out(
        self, email: str, reason: str | None = None, user_id: UUID | None = None,
    ) -> dict:
        """Add an email to the opt-out list."""
        body: dict = {"emailAddress": email}
        if reason:
            body["reason"] = reason

        try:
            resp = await self._authed_request(
                "POST", "/compliance/v1/optout/add",
                user_id=user_id,
                json=body,
            )
            data = resp.json()
            return {
                "email": email,
                "success": True,
                "status": data.get("status", "opted_out"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo add_opt_out error: %s", exc)
            return {"email": email, "success": False, "error": str(exc)}


    async def remove_opt_out(
        self, email: str, user_id: UUID | None = None,
    ) -> dict:
        """Remove an email from the opt-out list."""
        try:
            resp = await self._authed_request(
                "POST", "/compliance/v1/optout/remove",
                user_id=user_id,
                json={"emailAddress": email},
            )
            data = resp.json()
            return {
                "email": email,
                "success": True,
                "status": data.get("status", "removed"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo remove_opt_out error: %s", exc)
            return {"email": email, "success": False, "error": str(exc)}


    async def check_gdpr_status(
        self, email: str, user_id: UUID | None = None,
    ) -> dict:
        """Check GDPR compliance status for an email."""
        try:
            resp = await self._authed_request(
                "POST", "/compliance/v1/gdpr/check",
                user_id=user_id,
                json={"emailAddress": email},
            )
            data = resp.json()
            return {
                "email": email,
                "gdpr_status": data.get("gdprStatus"),
                "consent_given": data.get("consentGiven", False),
                "data_region": data.get("dataRegion"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo check_gdpr_status error: %s", exc)
            return {"email": email, "error": str(exc)}


    # ── Enhanced Search ───────────────────────────────────────────────────────

    async def advanced_search_contacts(
        self, query: str | None = None, filters: dict | None = None, user_id: UUID | None = None,
    ) -> list[dict]:
        """Advanced people search with granular filters.

        filters can include: education, years_experience, certifications,
        management_level, department, revenue_range, etc.
        """
        search_body: dict = {
            "outputFields": [
                "firstName", "lastName", "jobTitle", "companyName",
                "phone", "email", "linkedInUrl", "companyDomain",
                "city", "state", "country", "managementLevel",
                "education", "yearsOfExperience",
            ],
        }
        if query:
            search_body["keyword"] = query
        if filters:
            search_body.update(filters)

        try:
            resp = await self._authed_request(
                "POST", "/search/contact", user_id=user_id, json=search_body,
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
                    "management_level": p.get("managementLevel"),
                    "years_experience": p.get("yearsOfExperience"),
                    "education": p.get("education"),
                }
                for p in results
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo advanced_search_contacts error: %s", exc)
            return []


    async def search_by_technology(
        self,
        technologies: list[str],
        location: str | None = None,
        employee_range: str | None = None,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Find companies using specific technologies."""
        search_body: dict = {
            "technographics": [{"name": t} for t in technologies],
            "outputFields": [
                "companyName", "website", "revenue", "employeeCount",
                "industry", "city", "state", "country",
            ],
        }
        if location:
            search_body["locationCriteria"] = [{"country": location}]
        if employee_range:
            search_body["employeeCount"] = employee_range

        try:
            resp = await self._authed_request(
                "POST", "/search/company", user_id=user_id, json=search_body,
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
            logger.error("ZoomInfo search_by_technology error: %s", exc)
            return []


    # ── Lookup ────────────────────────────────────────────────────────────────

    async def lookup_by_email(
        self, email: str, user_id: UUID | None = None,
    ) -> dict:
        """Lookup a person by email address."""
        try:
            resp = await self._authed_request(
                "POST", "/lookup/v1/email",
                user_id=user_id,
                json={"emailAddress": email},
            )
            data = resp.json()
            person = data.get("result", {}).get("data", [{}])[0] if data.get("result", {}).get("data") else {}
            return {
                "email": email,
                "first_name": person.get("firstName"),
                "last_name": person.get("lastName"),
                "job_title": person.get("jobTitle"),
                "company_name": person.get("companyName"),
                "phone": person.get("phone"),
                "linkedin_url": person.get("linkedInUrl"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo lookup_by_email error: %s", exc)
            return {"email": email, "error": str(exc)}


    async def lookup_by_domain(
        self, domain: str, user_id: UUID | None = None,
    ) -> dict:
        """Lookup a company by domain."""
        try:
            resp = await self._authed_request(
                "POST", "/lookup/v1/domain",
                user_id=user_id,
                json={"companyDomain": domain},
            )
            data = resp.json()
            company = data.get("result", {}).get("data", [{}])[0] if data.get("result", {}).get("data") else {}
            return {
                "domain": domain,
                "name": company.get("companyName"),
                "website": company.get("website"),
                "industry": company.get("industry"),
                "employee_count": company.get("employeeCount"),
                "revenue": company.get("revenue"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo lookup_by_domain error: %s", exc)
            return {"domain": domain, "error": str(exc)}


    async def lookup_by_phone(
        self, phone: str, user_id: UUID | None = None,
    ) -> dict:
        """Lookup a person by phone number."""
        try:
            resp = await self._authed_request(
                "POST", "/lookup/v1/phone",
                user_id=user_id,
                json={"phoneNumber": phone},
            )
            data = resp.json()
            person = data.get("result", {}).get("data", [{}])[0] if data.get("result", {}).get("data") else {}
            return {
                "phone": phone,
                "first_name": person.get("firstName"),
                "last_name": person.get("lastName"),
                "email": person.get("email"),
                "job_title": person.get("jobTitle"),
                "company_name": person.get("companyName"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo lookup_by_phone error: %s", exc)
            return {"phone": phone, "error": str(exc)}


    # ── Scaling / Bulk Jobs ───────────────────────────────────────────────────

    async def submit_bulk_job(
        self,
        job_type: str,
        records: list[dict],
        user_id: UUID | None = None,
    ) -> dict:
        """Submit an enhanced bulk enrichment job with more options.

        job_type: "enrich_contact", "enrich_company", "search"
        """
        try:
            resp = await self._authed_request(
                "POST", "/bulk/enrich",
                user_id=user_id,
                json={
                    "inputData": records,
                    "matchType": job_type,
                    "outputFields": [
                        "firstName", "lastName", "email", "phone",
                        "jobTitle", "companyName", "companyDomain",
                    ],
                },
            )
            data = resp.json()
            return {
                "job_id": data.get("jobId"),
                "status": data.get("status"),
                "total_records": len(records),
                "job_type": job_type,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo submit_bulk_job error: %s", exc)
            return {"error": str(exc)}


    async def get_bulk_job_progress(
        self, job_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Get detailed progress tracking for a bulk job."""
        try:
            resp = await self._authed_request(
                "GET", f"/bulk/{job_id}/status", user_id=user_id,
            )
            data = resp.json()
            return {
                "job_id": job_id,
                "status": data.get("status"),
                "progress_percent": data.get("progress"),
                "total_records": data.get("totalRecords"),
                "completed_records": data.get("completedRecords"),
                "failed_records": data.get("failedRecords", 0),
                "estimated_completion": data.get("estimatedCompletion"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_bulk_job_progress error: %s", exc)
            return {"error": str(exc)}


    async def cancel_bulk_job(
        self, job_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Cancel a running bulk job."""
        try:
            resp = await self._authed_request(
                "POST", f"/bulk/{job_id}/cancel", user_id=user_id,
            )
            data = resp.json()
            return {
                "job_id": job_id,
                "status": data.get("status", "cancelled"),
                "cancelled": True,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo cancel_bulk_job error: %s", exc)
            return {"error": str(exc)}


    # ── Company Intelligence ──────────────────────────────────────────────────

    async def get_funding_info(
        self, company_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Get funding rounds, investors, and amounts for a company."""
        try:
            resp = await self._authed_request(
                "POST", "/enrich/company",
                user_id=user_id,
                json={
                    "companyId": company_id,
                    "outputFields": [
                        "companyName", "funding", "totalFundingAmount",
                        "lastFundingDate", "lastFundingAmount", "lastFundingType",
                        "investors",
                    ],
                },
            )
            data = resp.json()
            results = data.get("result", {}).get("data", [])
            if not results:
                return {"company_id": company_id, "funding": None}
            co = results[0]
            return {
                "company_id": company_id,
                "company_name": co.get("companyName"),
                "total_funding": co.get("totalFundingAmount"),
                "last_funding_date": co.get("lastFundingDate"),
                "last_funding_amount": co.get("lastFundingAmount"),
                "last_funding_type": co.get("lastFundingType"),
                "investors": co.get("investors", []),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_funding_info error: %s", exc)
            return {"error": str(exc)}


    async def get_org_chart(
        self,
        company_id: str,
        department: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Get detailed org chart for a company, optionally filtered by department."""
        search_body: dict = {
            "companyId": company_id,
            "outputFields": [
                "firstName", "lastName", "jobTitle", "managementLevel",
                "department", "email", "phone", "linkedInUrl",
            ],
        }
        if department:
            search_body["department"] = department

        try:
            resp = await self._authed_request(
                "POST", "/search/contact", user_id=user_id, json=search_body,
            )
            results = resp.json().get("result", {}).get("data", [])
            people = [
                {
                    "first_name": p.get("firstName"),
                    "last_name": p.get("lastName"),
                    "job_title": p.get("jobTitle"),
                    "management_level": p.get("managementLevel"),
                    "department": p.get("department"),
                    "email": p.get("email"),
                    "phone": p.get("phone"),
                    "linkedin_url": p.get("linkedInUrl"),
                }
                for p in results
            ]

            # Group by management level for org chart structure
            levels: dict[str, list] = {}
            for person in people:
                level = person.get("management_level", "unknown")
                levels.setdefault(level, []).append(person)

            return {
                "company_id": company_id,
                "department": department,
                "total_people": len(people),
                "by_level": levels,
                "people": people,
            }
        except httpx.HTTPStatusError as exc:
            logger.error("ZoomInfo get_org_chart error: %s", exc)
            return {"error": str(exc)}

