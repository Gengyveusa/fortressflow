"""
Apollo.io Sales Intelligence Agent — Full platform agent for FortressFlow.

Provides people/org search, enrichment, contact management, account management,
deal tracking, sequence automation, task management, call logging, and usage analytics.
All methods are async with DB-first API key resolution and rate-limited retries.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.api_key_service import get_api_key

logger = logging.getLogger(__name__)

_APOLLO_BASE = "https://api.apollo.io/api/v1"
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0
_APOLLO_LIMITER = AsyncLimiter(
    max_rate=settings.APOLLO_RATE_LIMIT if hasattr(settings, "APOLLO_RATE_LIMIT") else 50,
    time_period=60,
)


class ApolloAgent:
    """Full Apollo.io sales intelligence agent for search, enrichment, and engagement."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._api_key: str | None = None

    async def _resolve_api_key(self, user_id: UUID | None) -> str:
        """Resolve Apollo API key: DB first, then env fallback."""
        if user_id:
            async with AsyncSessionLocal() as db:
                key = await get_api_key(db, "apollo", user_id)
                if key:
                    return key
        if settings.APOLLO_API_KEY:
            return settings.APOLLO_API_KEY
        raise ValueError("Apollo API key not configured — set via Settings or APOLLO_API_KEY env var")

    async def _get_client(self, user_id: UUID | None = None) -> httpx.AsyncClient:
        """Get or create an httpx client with the resolved API key."""
        self._api_key = await self._resolve_api_key(user_id)
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_APOLLO_BASE,
                headers={"x-api-key": self._api_key},
                timeout=30,
            )
        return self._client

    async def _request_with_backoff(
        self, method: str, url: str, user_id: UUID | None = None, **kwargs
    ) -> httpx.Response:
        """Retry on 429 with exponential backoff, respecting rate limiter."""
        client = await self._get_client(user_id)
        for attempt in range(_MAX_RETRIES):
            async with _APOLLO_LIMITER:
                resp = await client.request(method, url, **kwargs)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = float(resp.headers.get("Retry-After", _BACKOFF_BASE * (2**attempt)))
            logger.warning(
                "Apollo rate limit hit; retrying in %.1fs (attempt %d)",
                retry_after,
                attempt + 1,
            )
            await asyncio.sleep(retry_after)
        resp.raise_for_status()
        return resp

    # ── Search ─────────────────────────────────────────────────────────────

    async def search_people(
        self,
        db,
        user_id: UUID,
        query: str | None = None,
        title: str | None = None,
        location: str | None = None,
        industry: str | None = None,
        company_size: str | None = None,
        seniority: str | None = None,
        department: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """Search Apollo's 210M+ person database with granular filters."""
        payload: dict = {"page": page, "per_page": min(per_page, 100)}
        if query:
            payload["q_keywords"] = query
        if title:
            payload["person_titles"] = [title]
        if location:
            payload["person_locations"] = [location]
        if industry:
            payload["organization_industry_tag_ids"] = [industry]
        if company_size:
            payload["organization_num_employees_ranges"] = [company_size]
        if seniority:
            payload["person_seniorities"] = [seniority]
        if department:
            payload["contact_email_status"] = [department]

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/people/search",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            people = data.get("people", [])
            return {
                "people": [
                    {
                        "id": p.get("id"),
                        "first_name": p.get("first_name"),
                        "last_name": p.get("last_name"),
                        "name": p.get("name"),
                        "email": p.get("email"),
                        "title": p.get("title"),
                        "organization_name": p.get("organization", {}).get("name"),
                        "linkedin_url": p.get("linkedin_url"),
                        "city": p.get("city"),
                        "state": p.get("state"),
                        "country": p.get("country"),
                        "seniority": p.get("seniority"),
                        "departments": p.get("departments"),
                    }
                    for p in people
                ],
                "pagination": {
                    "page": data.get("pagination", {}).get("page", page),
                    "per_page": data.get("pagination", {}).get("per_page", per_page),
                    "total_entries": data.get("pagination", {}).get("total_entries", 0),
                    "total_pages": data.get("pagination", {}).get("total_pages", 0),
                },
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo search_people error: %s", exc)
            return {"error": str(exc)}

    async def search_organizations(
        self,
        db,
        user_id: UUID,
        query: str | None = None,
        locations: list[str] | None = None,
        industries: list[str] | None = None,
        employee_ranges: list[str] | None = None,
        revenue_ranges: list[str] | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """Search Apollo's 35M+ organization database."""
        payload: dict = {"page": page, "per_page": min(per_page, 100)}
        if query:
            payload["q_organization_keyword_tags"] = [query]
        if locations:
            payload["organization_locations"] = locations
        if industries:
            payload["organization_industry_tag_ids"] = industries
        if employee_ranges:
            payload["organization_num_employees_ranges"] = employee_ranges
        if revenue_ranges:
            payload["organization_revenue_ranges"] = revenue_ranges

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/organizations/search",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            orgs = data.get("organizations", [])
            return {
                "organizations": [
                    {
                        "id": o.get("id"),
                        "name": o.get("name"),
                        "website_url": o.get("website_url"),
                        "industry": o.get("industry"),
                        "estimated_num_employees": o.get("estimated_num_employees"),
                        "annual_revenue": o.get("annual_revenue"),
                        "city": o.get("city"),
                        "state": o.get("state"),
                        "country": o.get("country"),
                        "linkedin_url": o.get("linkedin_url"),
                        "founded_year": o.get("founded_year"),
                    }
                    for o in orgs
                ],
                "pagination": {
                    "page": data.get("pagination", {}).get("page", page),
                    "total_entries": data.get("pagination", {}).get("total_entries", 0),
                },
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo search_organizations error: %s", exc)
            return {"error": str(exc)}

    async def get_organization_job_postings(
        self,
        db,
        user_id: UUID,
        organization_id: str,
    ) -> dict:
        """Get open job postings at a target organization."""
        try:
            resp = await self._request_with_backoff(
                "GET",
                f"/organizations/{organization_id}/job_postings",
                user_id=user_id,
            )
            data = resp.json()
            postings = data.get("job_postings", [])
            return {
                "organization_id": organization_id,
                "job_postings": [
                    {
                        "id": jp.get("id"),
                        "title": jp.get("title"),
                        "url": jp.get("url"),
                        "city": jp.get("city"),
                        "state": jp.get("state"),
                        "country": jp.get("country"),
                        "posted_at": jp.get("posted_at"),
                    }
                    for jp in postings
                ],
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo get_organization_job_postings error: %s", exc)
            return {"error": str(exc)}

    # ── Enrichment ─────────────────────────────────────────────────────────

    async def enrich_person(
        self,
        db,
        user_id: UUID,
        email: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        domain: str | None = None,
        linkedin_url: str | None = None,
        reveal_phone: bool = False,
        reveal_email: bool = True,
        webhook_url: str | None = None,
    ) -> dict:
        """Enrich a person with email/phone waterfall. POST /people/match."""
        payload: dict = {
            "reveal_personal_emails": reveal_email,
            "reveal_phone_number": reveal_phone,
        }
        if email:
            payload["email"] = email
        if first_name:
            payload["first_name"] = first_name
        if last_name:
            payload["last_name"] = last_name
        if domain:
            payload["domain"] = domain
        if linkedin_url:
            payload["linkedin_url"] = linkedin_url
        if webhook_url:
            payload["webhook_url"] = webhook_url

        if not any([email, first_name, linkedin_url]):
            return {"error": "At least one of email, first_name, or linkedin_url is required"}

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/people/match",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            person = data.get("person", {})
            return {
                "source": "apollo",
                "match": {
                    "id": person.get("id"),
                    "first_name": person.get("first_name"),
                    "last_name": person.get("last_name"),
                    "name": person.get("name"),
                    "email": person.get("email"),
                    "phone": person.get("phone_numbers", [{}])[0].get("sanitized_number")
                    if person.get("phone_numbers")
                    else None,
                    "title": person.get("title"),
                    "organization_name": person.get("organization", {}).get("name"),
                    "linkedin_url": person.get("linkedin_url"),
                    "city": person.get("city"),
                    "state": person.get("state"),
                    "country": person.get("country"),
                    "seniority": person.get("seniority"),
                },
                "enriched_at": datetime.now(UTC).isoformat(),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo enrich_person error: %s", exc)
            return {"error": str(exc)}

    async def bulk_enrich_people(
        self,
        db,
        user_id: UUID,
        details: list[dict],
    ) -> dict:
        """Bulk enrich up to 10 people per call. POST /people/bulk_match."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                "/people/bulk_match",
                user_id=user_id,
                json={"details": details[:10]},
            )
            data = resp.json()
            matches = data.get("matches", [])
            return {
                "matches": [
                    {
                        "id": m.get("id"),
                        "first_name": m.get("first_name"),
                        "last_name": m.get("last_name"),
                        "email": m.get("email"),
                        "title": m.get("title"),
                        "organization_name": m.get("organization", {}).get("name"),
                    }
                    for m in matches
                ],
                "total": len(matches),
                "enriched_at": datetime.now(UTC).isoformat(),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo bulk_enrich_people error: %s", exc)
            return {"error": str(exc)}

    async def enrich_organization(
        self,
        db,
        user_id: UUID,
        domain: str,
    ) -> dict:
        """Enrich an organization by domain. GET /organizations/enrich."""
        try:
            resp = await self._request_with_backoff(
                "GET",
                "/organizations/enrich",
                user_id=user_id,
                params={"domain": domain},
            )
            data = resp.json()
            org = data.get("organization", {})
            return {
                "source": "apollo",
                "data": {
                    "id": org.get("id"),
                    "name": org.get("name"),
                    "website_url": org.get("website_url"),
                    "industry": org.get("industry"),
                    "estimated_num_employees": org.get("estimated_num_employees"),
                    "annual_revenue": org.get("annual_revenue"),
                    "city": org.get("city"),
                    "state": org.get("state"),
                    "country": org.get("country"),
                    "linkedin_url": org.get("linkedin_url"),
                    "founded_year": org.get("founded_year"),
                    "description": org.get("short_description"),
                },
                "enriched_at": datetime.now(UTC).isoformat(),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo enrich_organization error: %s", exc)
            return {"error": str(exc)}

    # ── Contacts ───────────────────────────────────────────────────────────

    async def create_contact(
        self,
        db,
        user_id: UUID,
        first_name: str,
        last_name: str,
        email: str | None = None,
        title: str | None = None,
        organization_name: str | None = None,
        **kwargs,
    ) -> dict:
        """Create a contact in Apollo CRM. POST /contacts."""
        payload: dict = {
            "first_name": first_name,
            "last_name": last_name,
        }
        if email:
            payload["email"] = email
        if title:
            payload["title"] = title
        if organization_name:
            payload["organization_name"] = organization_name
        payload.update(kwargs)

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/contacts",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            contact = data.get("contact", {})
            return {
                "id": contact.get("id"),
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "email": contact.get("email"),
                "title": contact.get("title"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo create_contact error: %s", exc)
            return {"error": str(exc)}

    async def update_contact(
        self,
        db,
        user_id: UUID,
        contact_id: str,
        **properties,
    ) -> dict:
        """Update a contact's properties. PATCH /contacts/{id}."""
        try:
            resp = await self._request_with_backoff(
                "PATCH",
                f"/contacts/{contact_id}",
                user_id=user_id,
                json=properties,
            )
            data = resp.json()
            contact = data.get("contact", {})
            return {
                "id": contact.get("id"),
                "first_name": contact.get("first_name"),
                "last_name": contact.get("last_name"),
                "email": contact.get("email"),
                "title": contact.get("title"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo update_contact error: %s", exc)
            return {"error": str(exc)}

    async def bulk_create_contacts(
        self,
        db,
        user_id: UUID,
        contacts: list[dict],
    ) -> dict:
        """Bulk create contacts. POST /contacts/bulk."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                "/contacts/bulk",
                user_id=user_id,
                json={"contacts": contacts},
            )
            data = resp.json()
            return {
                "contacts": data.get("contacts", []),
                "total": len(data.get("contacts", [])),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo bulk_create_contacts error: %s", exc)
            return {"error": str(exc)}

    async def search_contacts(
        self,
        db,
        user_id: UUID,
        query: str | None = None,
        sort_by: str | None = None,
        sort_order: str = "asc",
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """Search contacts in your Apollo account. POST /contacts/search."""
        payload: dict = {"page": page, "per_page": min(per_page, 100)}
        if query:
            payload["q_keywords"] = query
        if sort_by:
            payload["sort_by_field"] = sort_by
            payload["sort_ascending"] = sort_order == "asc"

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/contacts/search",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            contacts = data.get("contacts", [])
            return {
                "contacts": [
                    {
                        "id": c.get("id"),
                        "first_name": c.get("first_name"),
                        "last_name": c.get("last_name"),
                        "email": c.get("email"),
                        "title": c.get("title"),
                        "organization_name": c.get("organization_name"),
                    }
                    for c in contacts
                ],
                "pagination": {
                    "page": data.get("pagination", {}).get("page", page),
                    "total_entries": data.get("pagination", {}).get("total_entries", 0),
                },
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo search_contacts error: %s", exc)
            return {"error": str(exc)}

    async def delete_contact(
        self,
        db,
        user_id: UUID,
        contact_id: str,
    ) -> bool:
        """Delete a contact from Apollo. DELETE /contacts/{id}."""
        try:
            await self._request_with_backoff(
                "DELETE",
                f"/contacts/{contact_id}",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo delete_contact error: %s", exc)
            return False

    # ── Accounts ───────────────────────────────────────────────────────────

    async def create_account(
        self,
        db,
        user_id: UUID,
        name: str,
        domain: str | None = None,
        **kwargs,
    ) -> dict:
        """Create an account in Apollo CRM. POST /accounts."""
        payload: dict = {"name": name}
        if domain:
            payload["domain"] = domain
        payload.update(kwargs)

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/accounts",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            account = data.get("account", {})
            return {
                "id": account.get("id"),
                "name": account.get("name"),
                "domain": account.get("domain"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo create_account error: %s", exc)
            return {"error": str(exc)}

    async def update_account(
        self,
        db,
        user_id: UUID,
        account_id: str,
        **properties,
    ) -> dict:
        """Update an account's properties. PATCH /accounts/{id}."""
        try:
            resp = await self._request_with_backoff(
                "PATCH",
                f"/accounts/{account_id}",
                user_id=user_id,
                json=properties,
            )
            data = resp.json()
            account = data.get("account", {})
            return {
                "id": account.get("id"),
                "name": account.get("name"),
                "domain": account.get("domain"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo update_account error: %s", exc)
            return {"error": str(exc)}

    async def bulk_create_accounts(
        self,
        db,
        user_id: UUID,
        accounts: list[dict],
    ) -> dict:
        """Bulk create accounts. POST /accounts/bulk."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                "/accounts/bulk",
                user_id=user_id,
                json={"accounts": accounts},
            )
            data = resp.json()
            return {
                "accounts": data.get("accounts", []),
                "total": len(data.get("accounts", [])),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo bulk_create_accounts error: %s", exc)
            return {"error": str(exc)}

    # ── Deals ──────────────────────────────────────────────────────────────

    async def create_deal(
        self,
        db,
        user_id: UUID,
        name: str,
        amount: float | None = None,
        stage: str | None = None,
        owner_id: str | None = None,
        **kwargs,
    ) -> dict:
        """Create a deal in Apollo. POST /deals."""
        payload: dict = {"name": name}
        if amount is not None:
            payload["amount"] = amount
        if stage:
            payload["stage"] = stage
        if owner_id:
            payload["owner_id"] = owner_id
        payload.update(kwargs)

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/deals",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            deal = data.get("deal", data)
            return {
                "id": deal.get("id"),
                "name": deal.get("name"),
                "amount": deal.get("amount"),
                "stage": deal.get("stage"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo create_deal error: %s", exc)
            return {"error": str(exc)}

    async def list_deals(
        self,
        db,
        user_id: UUID,
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """List deals. GET /deals."""
        try:
            resp = await self._request_with_backoff(
                "GET",
                "/deals",
                user_id=user_id,
                params={"page": page, "per_page": min(per_page, 100)},
            )
            data = resp.json()
            deals = data.get("deals", [])
            return {
                "deals": [
                    {
                        "id": d.get("id"),
                        "name": d.get("name"),
                        "amount": d.get("amount"),
                        "stage": d.get("stage"),
                    }
                    for d in deals
                ],
                "pagination": {
                    "page": data.get("pagination", {}).get("page", page),
                    "total_entries": data.get("pagination", {}).get("total_entries", 0),
                },
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo list_deals error: %s", exc)
            return {"error": str(exc)}

    async def get_deal(
        self,
        db,
        user_id: UUID,
        deal_id: str,
    ) -> dict:
        """Get a deal by ID. GET /deals/{id}."""
        try:
            resp = await self._request_with_backoff(
                "GET",
                f"/deals/{deal_id}",
                user_id=user_id,
            )
            data = resp.json()
            deal = data.get("deal", data)
            return {
                "id": deal.get("id"),
                "name": deal.get("name"),
                "amount": deal.get("amount"),
                "stage": deal.get("stage"),
                "owner_id": deal.get("owner_id"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo get_deal error: %s", exc)
            return {"error": str(exc)}

    async def update_deal(
        self,
        db,
        user_id: UUID,
        deal_id: str,
        **properties,
    ) -> dict:
        """Update a deal. PATCH /deals/{id}."""
        try:
            resp = await self._request_with_backoff(
                "PATCH",
                f"/deals/{deal_id}",
                user_id=user_id,
                json=properties,
            )
            data = resp.json()
            deal = data.get("deal", data)
            return {
                "id": deal.get("id"),
                "name": deal.get("name"),
                "amount": deal.get("amount"),
                "stage": deal.get("stage"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo update_deal error: %s", exc)
            return {"error": str(exc)}

    # ── Sequences ──────────────────────────────────────────────────────────

    async def search_sequences(
        self,
        db,
        user_id: UUID,
        query: str | None = None,
    ) -> dict:
        """Search email sequences. POST /sequences/search."""
        payload: dict = {}
        if query:
            payload["q_keywords"] = query

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/sequences/search",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            sequences = data.get("sequences", [])
            return {
                "sequences": [
                    {
                        "id": s.get("id"),
                        "name": s.get("name"),
                        "active": s.get("active"),
                        "num_steps": s.get("num_steps"),
                        "created_at": s.get("created_at"),
                    }
                    for s in sequences
                ],
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo search_sequences error: %s", exc)
            return {"error": str(exc)}

    async def add_contacts_to_sequence(
        self,
        db,
        user_id: UUID,
        sequence_id: str,
        contact_ids: list[str],
        email_account_id: str | None = None,
    ) -> dict:
        """Add contacts to an outreach sequence. POST /sequences/{id}/contacts."""
        payload: dict = {"contact_ids": contact_ids}
        if email_account_id:
            payload["emailer_campaign_id"] = email_account_id

        try:
            resp = await self._request_with_backoff(
                "POST",
                f"/sequences/{sequence_id}/contacts",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "sequence_id": sequence_id,
                "contacts_added": len(contact_ids),
                "status": data.get("status", "success"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo add_contacts_to_sequence error: %s", exc)
            return {"error": str(exc)}

    async def update_contact_sequence_status(
        self,
        db,
        user_id: UUID,
        sequence_id: str,
        contact_id: str,
        status: str,
    ) -> dict:
        """Update a contact's enrollment status in a sequence."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                f"/sequences/{sequence_id}/contacts/{contact_id}/status",
                user_id=user_id,
                json={"status": status},
            )
            data = resp.json()
            return {
                "sequence_id": sequence_id,
                "contact_id": contact_id,
                "status": data.get("status", status),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo update_contact_sequence_status error: %s", exc)
            return {"error": str(exc)}

    # ── Tasks ──────────────────────────────────────────────────────────────

    async def create_task(
        self,
        db,
        user_id: UUID,
        contact_id: str,
        type: str = "action_item",
        priority: str = "medium",
        due_date: str | None = None,
        note: str | None = None,
    ) -> dict:
        """Create a task in Apollo. POST /tasks."""
        payload: dict = {
            "contact_id": contact_id,
            "type": type,
            "priority": priority,
        }
        if due_date:
            payload["due_date"] = due_date
        if note:
            payload["note"] = note

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/tasks",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            task = data.get("task", data)
            return {
                "id": task.get("id"),
                "contact_id": task.get("contact_id"),
                "type": task.get("type"),
                "priority": task.get("priority"),
                "due_date": task.get("due_date"),
                "status": task.get("status"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo create_task error: %s", exc)
            return {"error": str(exc)}

    async def bulk_create_tasks(
        self,
        db,
        user_id: UUID,
        tasks: list[dict],
    ) -> dict:
        """Bulk create tasks. POST /tasks/bulk."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                "/tasks/bulk",
                user_id=user_id,
                json={"tasks": tasks},
            )
            data = resp.json()
            return {
                "tasks": data.get("tasks", []),
                "total": len(data.get("tasks", [])),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo bulk_create_tasks error: %s", exc)
            return {"error": str(exc)}

    async def search_tasks(
        self,
        db,
        user_id: UUID,
        status: str | None = None,
        type: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """Search tasks. POST /tasks/search."""
        payload: dict = {"page": page, "per_page": min(per_page, 100)}
        if status:
            payload["status"] = status
        if type:
            payload["type"] = type

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/tasks/search",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            found_tasks = data.get("tasks", [])
            return {
                "tasks": [
                    {
                        "id": t.get("id"),
                        "contact_id": t.get("contact_id"),
                        "type": t.get("type"),
                        "priority": t.get("priority"),
                        "due_date": t.get("due_date"),
                        "status": t.get("status"),
                        "note": t.get("note"),
                    }
                    for t in found_tasks
                ],
                "pagination": {
                    "page": data.get("pagination", {}).get("page", page),
                    "total_entries": data.get("pagination", {}).get("total_entries", 0),
                },
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo search_tasks error: %s", exc)
            return {"error": str(exc)}

    # ── Calls ──────────────────────────────────────────────────────────────

    async def create_call_record(
        self,
        db,
        user_id: UUID,
        contact_id: str,
        direction: str = "outbound",
        duration: int | None = None,
        disposition: str | None = None,
        notes: str | None = None,
    ) -> dict:
        """Log a call record. POST /calls."""
        payload: dict = {
            "contact_id": contact_id,
            "direction": direction,
        }
        if duration is not None:
            payload["duration"] = duration
        if disposition:
            payload["disposition"] = disposition
        if notes:
            payload["note"] = notes

        try:
            resp = await self._request_with_backoff(
                "POST",
                "/calls",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            call = data.get("call", data)
            return {
                "id": call.get("id"),
                "contact_id": call.get("contact_id"),
                "direction": call.get("direction"),
                "duration": call.get("duration"),
                "disposition": call.get("disposition"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo create_call_record error: %s", exc)
            return {"error": str(exc)}

    async def search_calls(
        self,
        db,
        user_id: UUID,
        contact_id: str | None = None,
        page: int = 1,
        per_page: int = 25,
    ) -> dict:
        """Search call records. GET /calls."""
        params: dict = {"page": page, "per_page": min(per_page, 100)}
        if contact_id:
            params["contact_id"] = contact_id

        try:
            resp = await self._request_with_backoff(
                "GET",
                "/calls",
                user_id=user_id,
                params=params,
            )
            data = resp.json()
            calls = data.get("calls", [])
            return {
                "calls": [
                    {
                        "id": c.get("id"),
                        "contact_id": c.get("contact_id"),
                        "direction": c.get("direction"),
                        "duration": c.get("duration"),
                        "disposition": c.get("disposition"),
                        "created_at": c.get("created_at"),
                    }
                    for c in calls
                ],
                "pagination": {
                    "page": data.get("pagination", {}).get("page", page),
                    "total_entries": data.get("pagination", {}).get("total_entries", 0),
                },
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo search_calls error: %s", exc)
            return {"error": str(exc)}

    async def update_call_record(
        self,
        db,
        user_id: UUID,
        call_id: str,
        **properties,
    ) -> dict:
        """Update a call record. PUT /calls/{id}."""
        try:
            resp = await self._request_with_backoff(
                "PUT",
                f"/calls/{call_id}",
                user_id=user_id,
                json=properties,
            )
            data = resp.json()
            call = data.get("call", data)
            return {
                "id": call.get("id"),
                "contact_id": call.get("contact_id"),
                "direction": call.get("direction"),
                "duration": call.get("duration"),
                "disposition": call.get("disposition"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo update_call_record error: %s", exc)
            return {"error": str(exc)}

    # ── Misc ───────────────────────────────────────────────────────────────

    async def get_usage_stats(
        self,
        db,
        user_id: UUID,
    ) -> dict:
        """Get Apollo account usage statistics. POST /usage."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                "/usage",
                user_id=user_id,
                json={},
            )
            data = resp.json()
            usage = data.get("usage", data)
            return {
                "credits_used": usage.get("credits_used"),
                "credits_limit": usage.get("credits_limit"),
                "credits_remaining": usage.get("credits_remaining"),
                "emails_sent": usage.get("emails_sent"),
                "emails_limit": usage.get("emails_limit"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo get_usage_stats error: %s", exc)
            return {"error": str(exc)}

    async def list_users(
        self,
        db,
        user_id: UUID,
    ) -> dict:
        """List Apollo users in the team. GET /users."""
        try:
            resp = await self._request_with_backoff(
                "GET",
                "/users",
                user_id=user_id,
            )
            data = resp.json()
            users = data.get("users", [])
            return {
                "users": [
                    {
                        "id": u.get("id"),
                        "email": u.get("email"),
                        "first_name": u.get("first_name"),
                        "last_name": u.get("last_name"),
                        "role": u.get("role"),
                    }
                    for u in users
                ],
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo list_users error: %s", exc)
            return {"error": str(exc)}

    async def list_email_accounts(
        self,
        db,
        user_id: UUID,
    ) -> dict:
        """List connected email accounts. GET /email_accounts."""
        try:
            resp = await self._request_with_backoff(
                "GET",
                "/email_accounts",
                user_id=user_id,
            )
            data = resp.json()
            accounts = data.get("email_accounts", [])
            return {
                "email_accounts": [
                    {
                        "id": a.get("id"),
                        "email": a.get("email"),
                        "type": a.get("type"),
                        "active": a.get("active"),
                    }
                    for a in accounts
                ],
            }
        except httpx.HTTPStatusError as exc:
            logger.error("Apollo list_email_accounts error: %s", exc)
            return {"error": str(exc)}

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
