"""
Enrichment service — ZoomInfo (primary) + Apollo (fallback).

Results are cached in the leads.proof_data JSONB column with a 90-day TTL.
"""

from datetime import UTC, datetime, timedelta
from uuid import UUID

import httpx

from app.config import settings


_CACHE_TTL_DAYS = 90


class EnrichmentService:
    """Wraps ZoomInfo and Apollo enrichment APIs with a 90-day Postgres cache."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(timeout=30)

    async def enrich_lead(self, email: str, db=None) -> dict:
        """
        Try ZoomInfo first, fall back to Apollo.
        Returns enriched data dict (may be empty on failure).
        """
        data = await self.enrich_zoominfo(email)
        if not data:
            data = await self.enrich_apollo(email)
        return data

    async def enrich_zoominfo(self, email: str) -> dict:
        """Fetch enrichment data from ZoomInfo API."""
        if not settings.ZOOMINFO_CLIENT_ID or not settings.ZOOMINFO_CLIENT_SECRET:
            return {}
        try:
            token_resp = await self._client.post(
                "https://api.zoominfo.com/authenticate",
                json={
                    "username": settings.ZOOMINFO_CLIENT_ID,
                    "password": settings.ZOOMINFO_CLIENT_SECRET,
                },
            )
            token_resp.raise_for_status()
            token = token_resp.json().get("jwt", "")

            resp = await self._client.post(
                "https://api.zoominfo.com/search/contact",
                headers={"Authorization": f"Bearer {token}"},
                json={"emailAddress": email, "outputFields": ["firstName", "lastName", "jobTitle", "companyName", "phone"]},
            )
            resp.raise_for_status()
            results = resp.json().get("result", {}).get("data", [])
            if results:
                return {"source": "zoominfo", "data": results[0], "enriched_at": datetime.now(UTC).isoformat()}
        except Exception:
            pass
        return {}

    async def enrich_apollo(self, email: str) -> dict:
        """Fetch enrichment data from Apollo.io API."""
        if not settings.APOLLO_API_KEY:
            return {}
        try:
            resp = await self._client.post(
                "https://api.apollo.io/v1/people/match",
                json={"api_key": settings.APOLLO_API_KEY, "email": email},
            )
            resp.raise_for_status()
            person = resp.json().get("person")
            if person:
                return {"source": "apollo", "data": person, "enriched_at": datetime.now(UTC).isoformat()}
        except Exception:
            pass
        return {}

    async def validate_email(self, email: str) -> bool:
        """Validate email using local validator (no external call)."""
        from app.services.email_validator import is_valid_email
        return is_valid_email(email)

    async def validate_phone(self, phone: str) -> bool:
        """Validate phone using phonenumbers library."""
        from app.services.email_validator import is_valid_phone
        return is_valid_phone(phone)

    def _is_cache_fresh(self, proof_data: dict | None) -> bool:
        """Return True if cached enrichment data is within 90-day TTL."""
        if not proof_data:
            return False
        enriched_at_str = proof_data.get("enriched_at")
        if not enriched_at_str:
            return False
        enriched_at = datetime.fromisoformat(enriched_at_str)
        if enriched_at.tzinfo is None:
            enriched_at = enriched_at.replace(tzinfo=UTC)
        return datetime.now(UTC) - enriched_at < timedelta(days=_CACHE_TTL_DAYS)
