"""
HubSpot CRM integration with exponential backoff for rate limits.

Supports bidirectional sync (push/pull contacts), note logging after enrichment,
and webhook ingestion.
"""

import asyncio
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings
from app.models.lead import Lead

logger = logging.getLogger(__name__)

_HUBSPOT_BASE = "https://api.hubapi.com"
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0

# HubSpot Professional+ rate limit: 190 req/10s burst
_HUBSPOT_LIMITER = AsyncLimiter(max_rate=190, time_period=10)


class HubSpotService:
    """Wraps HubSpot v3 Contacts + Engagements APIs with bidirectional sync."""

    def __init__(self, http_client: httpx.AsyncClient | None = None) -> None:
        self._client = http_client or httpx.AsyncClient(
            base_url=_HUBSPOT_BASE,
            headers={"Authorization": f"Bearer {settings.HUBSPOT_API_KEY}"},
            timeout=30,
        )

    async def _request_with_backoff(self, method: str, url: str, **kwargs) -> httpx.Response:
        """Retry on 429 with exponential backoff, respecting rate limiter."""
        for attempt in range(_MAX_RETRIES):
            async with _HUBSPOT_LIMITER:
                resp = await self._client.request(method, url, **kwargs)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = float(resp.headers.get("Retry-After", _BACKOFF_BASE * (2 ** attempt)))
            logger.warning("HubSpot rate limit hit; retrying in %.1fs (attempt %d)", retry_after, attempt + 1)
            await asyncio.sleep(retry_after)
        resp.raise_for_status()
        return resp

    # ── Push: Local → HubSpot ──────────────────────────────────────────

    async def push_lead_to_hubspot(self, lead: Lead) -> str:
        """Create or update a contact in HubSpot CRM.

        Returns the HubSpot contact ID (hs_object_id).
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
            hs_id = str(resp.json().get("id", ""))
            logger.info("Pushed lead %s to HubSpot as contact %s", lead.id, hs_id)
            return hs_id
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 409:
                # Already exists — fetch by email
                resp = await self._request_with_backoff(
                    "GET",
                    f"/crm/v3/objects/contacts/{lead.email}",
                    params={"idProperty": "email"},
                )
                return str(resp.json().get("id", ""))
            logger.error("HubSpot push_lead error: %s", exc)
            return ""

    # Keep legacy alias
    async def sync_lead(self, lead: Lead) -> str:
        """Alias for push_lead_to_hubspot for backward compatibility."""
        return await self.push_lead_to_hubspot(lead)

    # ── Pull: HubSpot → Local ──────────────────────────────────────────

    async def pull_contacts_from_hubspot(
        self, since: datetime | None = None
    ) -> list[dict]:
        """Search HubSpot for contacts modified since a given datetime.

        Uses the CRM search API with filterGroups on hs_lastmodifieddate.
        Returns a list of contact property dicts.
        """
        if not settings.HUBSPOT_API_KEY:
            return []

        filter_groups: list[dict] = []
        if since:
            ts_ms = int(since.timestamp() * 1000)
            filter_groups = [
                {
                    "filters": [
                        {
                            "propertyName": "hs_lastmodifieddate",
                            "operator": "GTE",
                            "value": str(ts_ms),
                        }
                    ]
                }
            ]

        payload: dict = {
            "filterGroups": filter_groups,
            "properties": [
                "email",
                "firstname",
                "lastname",
                "company",
                "jobtitle",
                "phone",
            ],
            "limit": 100,
        }

        all_contacts: list[dict] = []
        after: str | None = None

        while True:
            if after:
                payload["after"] = after

            try:
                resp = await self._request_with_backoff(
                    "POST",
                    "/crm/v3/objects/contacts/search",
                    json=payload,
                )
                body = resp.json()
                results = body.get("results", [])
                for contact in results:
                    props = contact.get("properties", {})
                    props["hs_object_id"] = contact.get("id")
                    all_contacts.append(props)

                paging = body.get("paging", {}).get("next", {})
                after = paging.get("after")
                if not after:
                    break
            except Exception as exc:
                logger.error("HubSpot pull_contacts error: %s", exc)
                break

        logger.info("Pulled %d contacts from HubSpot", len(all_contacts))
        return all_contacts

    # ── Note Logging ───────────────────────────────────────────────────

    async def create_enrichment_note(
        self,
        hs_contact_id: str,
        enrichment_details: str,
    ) -> None:
        """Create a Note in HubSpot after enrichment.

        Associates the note with the given contact using associationTypeId=2.
        """
        if not settings.HUBSPOT_API_KEY or not hs_contact_id:
            return

        now_ms = int(datetime.now(UTC).timestamp() * 1000)
        payload = {
            "properties": {
                "hs_note_subject": "FortressFlow: Enriched Lead",
                "hs_note_body": enrichment_details,
                "hs_timestamp": str(now_ms),
            },
            "associations": [
                {
                    "to": {"id": hs_contact_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 2,
                        }
                    ],
                }
            ],
        }
        try:
            await self._request_with_backoff(
                "POST",
                "/crm/v3/objects/notes",
                json=payload,
            )
            logger.info("Created enrichment note for HubSpot contact %s", hs_contact_id)
        except Exception as exc:
            logger.error("HubSpot create_enrichment_note error: %s", exc)

    # ── Legacy methods (kept for backward compatibility) ───────────────

    async def log_activity(
        self,
        lead_id: UUID,
        activity_type: str,
        description: str,
        hs_contact_id: str = "",
    ) -> None:
        """Log an engagement activity against a HubSpot contact."""
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
