"""
HubSpot CRM Agent — Full platform agent extending the existing HubSpotService.

Provides contact lifecycle management, deal pipeline operations, company management,
list management, activity logging, property management, analytics, and sync.
All methods are async with DB-first API key resolution and rate-limited retries.
"""

import asyncio
import json
import logging
from datetime import UTC, datetime
from uuid import UUID

import httpx
from aiolimiter import AsyncLimiter

from app.config import settings
from app.database import AsyncSessionLocal
from app.services.api_key_service import get_api_key
from app.services.hubspot import HubSpotService

logger = logging.getLogger(__name__)

_HUBSPOT_BASE = "https://api.hubapi.com"
_MAX_RETRIES = 5
_BACKOFF_BASE = 1.0
_HUBSPOT_LIMITER = AsyncLimiter(max_rate=190, time_period=10)


class HubSpotAgent:
    """Full HubSpot CRM agent. Composes HubSpotService and adds new capabilities."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._service: HubSpotService | None = None

    async def _resolve_api_key(self, user_id: UUID | None) -> str:
        """Resolve HubSpot API key: DB first, then env fallback."""
        if user_id:
            async with AsyncSessionLocal() as db:
                key = await get_api_key(db, "hubspot", user_id)
                if key:
                    return key
        if settings.HUBSPOT_API_KEY:
            return settings.HUBSPOT_API_KEY
        raise ValueError("HubSpot API key not configured — set via Settings or HUBSPOT_API_KEY env var")

    async def _get_client(self, user_id: UUID | None) -> httpx.AsyncClient:
        """Get or create an httpx client with the resolved API key."""
        api_key = await self._resolve_api_key(user_id)
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=_HUBSPOT_BASE,
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=30,
            )
        return self._client

    async def _get_service(self, user_id: UUID | None) -> HubSpotService:
        """Get a HubSpotService instance configured with the resolved key."""
        client = await self._get_client(user_id)
        if self._service is None:
            self._service = HubSpotService(http_client=client)
        return self._service

    async def _request_with_backoff(
        self, method: str, url: str, user_id: UUID | None = None, **kwargs
    ) -> httpx.Response:
        """Retry on 429 with exponential backoff, respecting rate limiter."""
        client = await self._get_client(user_id)
        for attempt in range(_MAX_RETRIES):
            async with _HUBSPOT_LIMITER:
                resp = await client.request(method, url, **kwargs)
            if resp.status_code != 429:
                resp.raise_for_status()
                return resp
            retry_after = float(
                resp.headers.get("Retry-After", _BACKOFF_BASE * (2 ** attempt))
            )
            logger.warning(
                "HubSpot rate limit hit; retrying in %.1fs (attempt %d)",
                retry_after,
                attempt + 1,
            )
            await asyncio.sleep(retry_after)
        resp.raise_for_status()
        return resp

    # ── Contacts ───────────────────────────────────────────────────────────

    async def create_contact(self, properties: dict, user_id: UUID | None = None) -> dict:
        """Create a contact in HubSpot."""
        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/contacts",
                user_id=user_id,
                json={"properties": properties},
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_contact error: %s", exc)
            return {"error": str(exc)}

    async def update_contact(
        self, contact_id: str, properties: dict, user_id: UUID | None = None
    ) -> dict:
        """Update a contact's properties."""
        try:
            resp = await self._request_with_backoff(
                "PATCH", f"/crm/v3/objects/contacts/{contact_id}",
                user_id=user_id,
                json={"properties": properties},
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot update_contact error: %s", exc)
            return {"error": str(exc)}

    async def get_contact(self, contact_id: str, user_id: UUID | None = None) -> dict:
        """Get a contact by ID."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/crm/v3/objects/contacts/{contact_id}",
                user_id=user_id,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_contact error: %s", exc)
            return {"error": str(exc)}

    async def search_contacts(
        self,
        filters: list,
        sorts: list | None = None,
        limit: int = 100,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Search contacts using HubSpot CRM search API."""
        payload: dict = {
            "filterGroups": [{"filters": filters}],
            "limit": min(limit, 100),
        }
        if sorts:
            payload["sorts"] = sorts

        results: list[dict] = []
        after: str | None = None

        while True:
            if after:
                payload["after"] = after
            try:
                resp = await self._request_with_backoff(
                    "POST", "/crm/v3/objects/contacts/search",
                    user_id=user_id, json=payload,
                )
                body = resp.json()
                for contact in body.get("results", []):
                    results.append({
                        "id": contact.get("id"),
                        "properties": contact.get("properties", {}),
                    })
                paging = body.get("paging", {}).get("next", {})
                after = paging.get("after")
                if not after or len(results) >= limit:
                    break
            except httpx.HTTPStatusError as exc:
                logger.error("HubSpot search_contacts error: %s", exc)
                break

        return results[:limit]

    async def bulk_create_contacts(
        self, contacts: list[dict], user_id: UUID | None = None
    ) -> dict:
        """Bulk create contacts via batch API."""
        inputs = [{"properties": c} for c in contacts]
        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/contacts/batch/create",
                user_id=user_id,
                json={"inputs": inputs},
            )
            data = resp.json()
            return {
                "status": data.get("status", "COMPLETE"),
                "results": [
                    {"id": r.get("id"), "properties": r.get("properties", {})}
                    for r in data.get("results", [])
                ],
                "errors": data.get("errors", []),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot bulk_create_contacts error: %s", exc)
            return {"error": str(exc)}

    async def merge_contacts(
        self, primary_id: str, secondary_id: str, user_id: UUID | None = None
    ) -> dict:
        """Merge two contacts. The secondary is merged into the primary."""
        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/contacts/merge",
                user_id=user_id,
                json={"primaryObjectId": primary_id, "objectIdToMerge": secondary_id},
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot merge_contacts error: %s", exc)
            return {"error": str(exc)}

    async def delete_contact(self, contact_id: str, user_id: UUID | None = None) -> bool:
        """Archive (soft-delete) a contact."""
        try:
            await self._request_with_backoff(
                "DELETE", f"/crm/v3/objects/contacts/{contact_id}",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot delete_contact error: %s", exc)
            return False

    # ── Deals ──────────────────────────────────────────────────────────────

    async def create_deal(
        self,
        properties: dict,
        associations: list | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a deal with optional associations."""
        payload: dict = {"properties": properties}
        if associations:
            payload["associations"] = associations
        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/deals",
                user_id=user_id, json=payload,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_deal error: %s", exc)
            return {"error": str(exc)}

    async def update_deal(
        self, deal_id: str, properties: dict, user_id: UUID | None = None
    ) -> dict:
        """Update a deal's properties."""
        try:
            resp = await self._request_with_backoff(
                "PATCH", f"/crm/v3/objects/deals/{deal_id}",
                user_id=user_id,
                json={"properties": properties},
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot update_deal error: %s", exc)
            return {"error": str(exc)}

    async def move_deal_stage(
        self, deal_id: str, stage: str, user_id: UUID | None = None
    ) -> dict:
        """Move a deal to a different pipeline stage."""
        return await self.update_deal(deal_id, {"dealstage": stage}, user_id)

    async def get_pipeline(self, pipeline_id: str, user_id: UUID | None = None) -> dict:
        """Get a deal pipeline and its stages."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/crm/v3/pipelines/deals/{pipeline_id}",
                user_id=user_id,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "label": data.get("label"),
                "stages": [
                    {"id": s.get("id"), "label": s.get("label"), "displayOrder": s.get("displayOrder")}
                    for s in data.get("stages", [])
                ],
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_pipeline error: %s", exc)
            return {"error": str(exc)}

    async def get_deals(
        self, filters: list, user_id: UUID | None = None
    ) -> list[dict]:
        """Search deals using filters."""
        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/deals/search",
                user_id=user_id,
                json={"filterGroups": [{"filters": filters}], "limit": 100},
            )
            body = resp.json()
            return [
                {"id": d.get("id"), "properties": d.get("properties", {})}
                for d in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_deals error: %s", exc)
            return []

    # ── Companies ──────────────────────────────────────────────────────────

    async def create_company(
        self, properties: dict, user_id: UUID | None = None
    ) -> dict:
        """Create a company in HubSpot."""
        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/companies",
                user_id=user_id,
                json={"properties": properties},
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_company error: %s", exc)
            return {"error": str(exc)}

    async def update_company(
        self, company_id: str, properties: dict, user_id: UUID | None = None
    ) -> dict:
        """Update a company's properties."""
        try:
            resp = await self._request_with_backoff(
                "PATCH", f"/crm/v3/objects/companies/{company_id}",
                user_id=user_id,
                json={"properties": properties},
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot update_company error: %s", exc)
            return {"error": str(exc)}

    async def associate_contact_to_company(
        self, contact_id: str, company_id: str, user_id: UUID | None = None
    ) -> bool:
        """Associate a contact with a company."""
        try:
            await self._request_with_backoff(
                "PUT",
                f"/crm/v3/objects/contacts/{contact_id}/associations/companies/{company_id}/contact_to_company",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot associate_contact_to_company error: %s", exc)
            return False

    # ── Lists ──────────────────────────────────────────────────────────────

    async def create_list(
        self, name: str, filters: list, user_id: UUID | None = None
    ) -> dict:
        """Create a contact list (ILS v3)."""
        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/lists/",
                user_id=user_id,
                json={
                    "name": name,
                    "objectTypeId": "0-1",  # contacts
                    "processingType": "DYNAMIC" if filters else "MANUAL",
                    "filterBranch": {
                        "filterBranchType": "AND",
                        "filters": filters,
                    } if filters else None,
                },
            )
            data = resp.json()
            return {"listId": data.get("listId"), "name": data.get("name")}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_list error: %s", exc)
            return {"error": str(exc)}

    async def add_to_list(
        self, list_id: str, contact_ids: list[str], user_id: UUID | None = None
    ) -> bool:
        """Add contacts to a static list."""
        try:
            await self._request_with_backoff(
                "PUT", f"/crm/v3/lists/{list_id}/memberships/add",
                user_id=user_id,
                json=contact_ids,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot add_to_list error: %s", exc)
            return False

    async def remove_from_list(
        self, list_id: str, contact_ids: list[str], user_id: UUID | None = None
    ) -> bool:
        """Remove contacts from a static list."""
        try:
            await self._request_with_backoff(
                "PUT", f"/crm/v3/lists/{list_id}/memberships/remove",
                user_id=user_id,
                json=contact_ids,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot remove_from_list error: %s", exc)
            return False

    # ── Activities ─────────────────────────────────────────────────────────

    async def _create_engagement(
        self,
        object_type: str,
        properties: dict,
        contact_id: str,
        association_type_id: int,
        user_id: UUID | None = None,
    ) -> dict:
        """Generic engagement creation with contact association."""
        now_ms = str(int(datetime.now(UTC).timestamp() * 1000))
        properties.setdefault("hs_timestamp", now_ms)
        payload = {
            "properties": properties,
            "associations": [
                {
                    "to": {"id": contact_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": association_type_id,
                        }
                    ],
                }
            ],
        }
        try:
            resp = await self._request_with_backoff(
                "POST", f"/crm/v3/objects/{object_type}",
                user_id=user_id, json=payload,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot _create_engagement (%s) error: %s", object_type, exc)
            return {"error": str(exc)}

    async def log_email(
        self, contact_id: str, subject: str, body: str, user_id: UUID | None = None
    ) -> dict:
        """Log an email engagement against a contact."""
        return await self._create_engagement(
            "emails",
            {"hs_email_subject": subject, "hs_email_text": body, "hs_email_direction": "SENT"},
            contact_id, 198, user_id,  # 198 = email-to-contact
        )

    async def log_call(
        self, contact_id: str, duration_ms: int, notes: str, user_id: UUID | None = None
    ) -> dict:
        """Log a call engagement against a contact."""
        return await self._create_engagement(
            "calls",
            {"hs_call_duration": str(duration_ms), "hs_call_body": notes},
            contact_id, 194, user_id,  # 194 = call-to-contact
        )

    async def log_meeting(
        self,
        contact_id: str,
        title: str,
        start: str,
        end: str,
        notes: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Log a meeting engagement against a contact."""
        return await self._create_engagement(
            "meetings",
            {
                "hs_meeting_title": title,
                "hs_meeting_start_time": start,
                "hs_meeting_end_time": end,
                "hs_meeting_body": notes,
            },
            contact_id, 200, user_id,  # 200 = meeting-to-contact
        )

    async def create_task(
        self, contact_id: str, title: str, due_date: str, user_id: UUID | None = None
    ) -> dict:
        """Create a task associated with a contact."""
        return await self._create_engagement(
            "tasks",
            {
                "hs_task_subject": title,
                "hs_task_status": "NOT_STARTED",
                "hs_timestamp": due_date,
            },
            contact_id, 204, user_id,  # 204 = task-to-contact
        )

    async def log_note(
        self, contact_id: str, body: str, user_id: UUID | None = None
    ) -> dict:
        """Log a note against a contact."""
        return await self._create_engagement(
            "notes",
            {"hs_note_body": body},
            contact_id, 202, user_id,  # 202 = note-to-contact
        )

    # ── Properties ─────────────────────────────────────────────────────────

    async def create_property(
        self,
        object_type: str,
        name: str,
        field_type: str,
        group: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a custom property on an object type."""
        try:
            resp = await self._request_with_backoff(
                "POST", f"/crm/v3/properties/{object_type}",
                user_id=user_id,
                json={
                    "name": name,
                    "label": name.replace("_", " ").title(),
                    "type": "string",
                    "fieldType": field_type,
                    "groupName": group,
                },
            )
            data = resp.json()
            return {"name": data.get("name"), "label": data.get("label"), "type": data.get("type")}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_property error: %s", exc)
            return {"error": str(exc)}

    async def get_properties(
        self, object_type: str, user_id: UUID | None = None
    ) -> list[dict]:
        """Get all properties for an object type."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/crm/v3/properties/{object_type}",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {"name": p.get("name"), "label": p.get("label"), "type": p.get("type"), "fieldType": p.get("fieldType")}
                for p in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_properties error: %s", exc)
            return []

    # ── Analytics ──────────────────────────────────────────────────────────

    async def get_contact_activity(
        self, contact_id: str, user_id: UUID | None = None
    ) -> list[dict]:
        """Get engagement activity history for a contact."""
        activities: list[dict] = []
        for obj_type in ("emails", "calls", "meetings", "notes", "tasks"):
            try:
                resp = await self._request_with_backoff(
                    "GET",
                    f"/crm/v3/objects/contacts/{contact_id}/associations/{obj_type}",
                    user_id=user_id,
                )
                assoc_data = resp.json()
                for item in assoc_data.get("results", []):
                    activities.append({"type": obj_type, "id": item.get("id")})
            except httpx.HTTPStatusError:
                continue
        return activities

    async def get_pipeline_report(
        self, pipeline_id: str, date_range: dict, user_id: UUID | None = None
    ) -> dict:
        """Generate a pipeline report by aggregating deals per stage."""
        pipeline = await self.get_pipeline(pipeline_id, user_id)
        if "error" in pipeline:
            return pipeline

        filters = [{"propertyName": "pipeline", "operator": "EQ", "value": pipeline_id}]
        if date_range.get("start"):
            filters.append({
                "propertyName": "createdate",
                "operator": "GTE",
                "value": date_range["start"],
            })
        if date_range.get("end"):
            filters.append({
                "propertyName": "createdate",
                "operator": "LTE",
                "value": date_range["end"],
            })

        deals = await self.get_deals(filters, user_id)

        stage_counts: dict[str, int] = {}
        stage_amounts: dict[str, float] = {}
        for deal in deals:
            props = deal.get("properties", {})
            stage = props.get("dealstage", "unknown")
            stage_counts[stage] = stage_counts.get(stage, 0) + 1
            try:
                amount = float(props.get("amount", 0) or 0)
            except (ValueError, TypeError):
                amount = 0.0
            stage_amounts[stage] = stage_amounts.get(stage, 0.0) + amount

        return {
            "pipeline": pipeline,
            "total_deals": len(deals),
            "stages": {
                stage: {"count": stage_counts.get(stage, 0), "total_amount": stage_amounts.get(stage, 0.0)}
                for stage in [s["id"] for s in pipeline.get("stages", [])]
            },
        }

    # ── Sync ───────────────────────────────────────────────────────────────

    async def full_sync(self, leads: list, user_id: UUID | None = None) -> dict:
        """Sync a list of FortressFlow leads to HubSpot contacts."""
        service = await self._get_service(user_id)
        created = 0
        updated = 0
        errors = 0

        for lead in leads:
            try:
                hs_id = await service.push_lead_to_hubspot(lead)
                if hs_id:
                    created += 1
                else:
                    errors += 1
            except Exception as exc:
                logger.error("full_sync error for lead %s: %s", getattr(lead, "id", "?"), exc)
                errors += 1

        return {"created": created, "updated": updated, "errors": errors, "total": len(leads)}

    async def pull_updates(
        self, since: str, user_id: UUID | None = None
    ) -> list[dict]:
        """Pull contacts modified since a given ISO timestamp from HubSpot."""
        service = await self._get_service(user_id)
        since_dt = datetime.fromisoformat(since) if isinstance(since, str) else since
        return await service.pull_contacts_from_hubspot(since=since_dt)

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
