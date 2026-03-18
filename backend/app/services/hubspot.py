"""
HubSpot CRM integration with exponential backoff for rate limits.
"""

import asyncio
import logging
from uuid import UUID

import httpx

from app.config import settings
from app.models.lead import Lead

logger = logging.getLogger(__name__)

_HUBSPOT_BASE = "https://api.hubapi.com"
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0


class HubSpotService:
    """Wraps HubSpot v3 Contacts + Engagements APIs."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(
            base_url=_HUBSPOT_BASE,
            headers={"Authorization": f"Bearer {settings.HUBSPOT_API_KEY}"},
            timeout=30,
        )

    async def _request_with_backoff(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Retry on 429 with exponential backoff."""
        for attempt in range(_MAX_RETRIES):
            resp = await self._client.request(method, url, **kwargs)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = float(resp.headers.get("Retry-After", _BACKOFF_BASE * (2 ** attempt)))
            logger.warning("HubSpot rate limit hit; retrying in %.1fs (attempt %d)", retry_after, attempt + 1)
            await asyncio.sleep(retry_after)
        resp.raise_for_status()
        return resp

    async def sync_lead(self, lead: Lead) -> str:
        """
        Upsert a lead into HubSpot Contacts.
        Returns the HubSpot contact ID (vid / hs_object_id).
        """
        if not settings.HUBSPOT_API_KEY:
            return ""
        payload = {
            "properties": {
                "email": lead.email,
                "firstname": lead.first_name,
                "lastname": lead.last_name,
                "company": lead.company,
                "jobtitle": lead.title,
                "phone": lead.phone or "",
            }
        }
        try:
            resp = await self._request_with_backoff(
                "POST",
                "/crm/v3/objects/contacts",
                json=payload,
            )
            return str(resp.json().get("id", ""))
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                # Already exists — fetch by email
                resp = await self._request_with_backoff(
                    "GET",
                    f"/crm/v3/objects/contacts/{lead.email}",
                    params={"idProperty": "email"},
                )
                return str(resp.json().get("id", ""))
            logger.error("HubSpot sync_lead error: %s", exc)
            return ""

    async def log_activity(
        self,
        lead_id: UUID,
        activity_type: str,
        description: str,
        hs_contact_id: str = "",
    ) -> None:
        """
        Log an engagement activity against a HubSpot contact.

        Pass hs_contact_id (returned by sync_lead) to associate the engagement
        with the correct contact timeline. Without it the engagement is created
        but will not appear on any contact record.
        """
        if not settings.HUBSPOT_API_KEY:
            return
        contact_ids = [int(hs_contact_id)] if hs_contact_id else []
        payload = {
            "engagement": {"active": True, "type": activity_type.upper()},
            "associations": {"contactIds": contact_ids},
            "metadata": {"body": description},
        }
        try:
            await self._request_with_backoff("POST", "/engagements/v1/engagements", json=payload)
        except Exception as exc:
            logger.error("HubSpot log_activity error: %s", exc)

    async def create_note(
        self, lead_id: UUID, content: str, hs_contact_id: str = ""
    ) -> None:
        """Create a note engagement in HubSpot."""
        await self.log_activity(lead_id, "NOTE", content, hs_contact_id=hs_contact_id)
