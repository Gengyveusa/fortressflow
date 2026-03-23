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

    # ── Deal / Pipeline Tracking ─────────────────────────────────────

    async def create_deal(
        self,
        hs_contact_id: str,
        deal_name: str,
        pipeline: str = "default",
        stage: str = "appointmentscheduled",
        amount: float | None = None,
    ) -> dict:
        """Create a deal in HubSpot and associate it with a contact.

        Returns the created deal properties dict (including 'hs_object_id').
        """
        if not settings.HUBSPOT_API_KEY:
            return {}
        properties: dict[str, str] = {
            "dealname": deal_name,
            "pipeline": pipeline,
            "dealstage": stage,
        }
        if amount is not None:
            properties["amount"] = str(amount)

        payload: dict = {
            "properties": properties,
            "associations": [
                {
                    "to": {"id": hs_contact_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 3,  # deal-to-contact
                        }
                    ],
                }
            ],
        }
        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/deals", json=payload,
            )
            data = resp.json()
            logger.info(
                "Created HubSpot deal '%s' (id=%s) for contact %s",
                deal_name, data.get("id"), hs_contact_id,
            )
            props = data.get("properties", {})
            props["hs_object_id"] = data.get("id")
            return props
        except Exception as exc:
            logger.error("HubSpot create_deal error: %s", exc)
            return {}

    async def update_deal_stage(self, deal_id: str, stage: str) -> dict:
        """Update the pipeline stage of an existing deal.

        Returns the updated deal properties dict.
        """
        if not settings.HUBSPOT_API_KEY:
            return {}
        payload = {"properties": {"dealstage": stage}}
        try:
            resp = await self._request_with_backoff(
                "PATCH", f"/crm/v3/objects/deals/{deal_id}", json=payload,
            )
            data = resp.json()
            logger.info("Updated HubSpot deal %s to stage '%s'", deal_id, stage)
            props = data.get("properties", {})
            props["hs_object_id"] = data.get("id")
            return props
        except Exception as exc:
            logger.error("HubSpot update_deal_stage error: %s", exc)
            return {}

    async def sync_deals(self, hs_contact_id: str) -> list[dict]:
        """Pull deals associated with a contact from HubSpot.

        Returns a list of deal property dicts.
        """
        if not settings.HUBSPOT_API_KEY or not hs_contact_id:
            return []
        try:
            # Get associated deal IDs
            resp = await self._request_with_backoff(
                "GET",
                f"/crm/v3/objects/contacts/{hs_contact_id}/associations/deals",
            )
            assoc_data = resp.json()
            deal_ids = [r["id"] for r in assoc_data.get("results", [])]

            if not deal_ids:
                return []

            deals: list[dict] = []
            for did in deal_ids:
                try:
                    deal_resp = await self._request_with_backoff(
                        "GET",
                        f"/crm/v3/objects/deals/{did}",
                        params={
                            "properties": "dealname,pipeline,dealstage,amount,createdate,hs_lastmodifieddate"
                        },
                    )
                    deal_data = deal_resp.json()
                    props = deal_data.get("properties", {})
                    props["hs_object_id"] = deal_data.get("id")
                    deals.append(props)
                except Exception as exc:
                    logger.warning("Failed to fetch deal %s: %s", did, exc)

            logger.info(
                "Synced %d deals for HubSpot contact %s", len(deals), hs_contact_id,
            )
            return deals
        except Exception as exc:
            logger.error("HubSpot sync_deals error: %s", exc)
            return []

    async def list_pipelines(self) -> list[dict]:
        """Get available deal pipelines and their stages from HubSpot.

        Returns a list of pipeline dicts with nested stages.
        """
        if not settings.HUBSPOT_API_KEY:
            return []
        try:
            resp = await self._request_with_backoff(
                "GET", "/crm/v3/pipelines/deals",
            )
            data = resp.json()
            pipelines: list[dict] = []
            for p in data.get("results", []):
                stages = [
                    {"stage_id": s.get("id", ""), "label": s.get("label", "")}
                    for s in p.get("stages", [])
                ]
                pipelines.append({
                    "pipeline_id": p.get("id", ""),
                    "label": p.get("label", ""),
                    "stages": stages,
                })
            return pipelines
        except Exception as exc:
            logger.error("HubSpot list_pipelines error: %s", exc)
            return []

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
