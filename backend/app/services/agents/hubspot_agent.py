"""
HubSpot CRM Agent — Full platform agent extending the existing HubSpotService.

Provides contact lifecycle management, deal pipeline operations, company management,
list management, activity logging, property management, analytics, and sync.
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

    # ── Pipelines ─────────────────────────────────────────────────────────────

    async def create_pipeline(
        self,
        object_type: str,
        label: str,
        stages: list[dict],
        user_id: UUID | None = None,
    ) -> dict:
        """Create a pipeline for an object type (deals, tickets, etc.).

        stages: [{"label": "New", "displayOrder": 0}, ...]
        """
        try:
            resp = await self._request_with_backoff(
                "POST", f"/crm/v3/pipelines/{object_type}",
                user_id=user_id,
                json={"label": label, "stages": stages},
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
            logger.error("HubSpot create_pipeline error: %s", exc)
            return {"error": str(exc)}

    async def update_pipeline(
        self,
        object_type: str,
        pipeline_id: str,
        label: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Update a pipeline's label."""
        try:
            resp = await self._request_with_backoff(
                "PATCH", f"/crm/v3/pipelines/{object_type}/{pipeline_id}",
                user_id=user_id,
                json={"label": label},
            )
            data = resp.json()
            return {"id": data.get("id"), "label": data.get("label")}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot update_pipeline error: %s", exc)
            return {"error": str(exc)}

    async def delete_pipeline(
        self, object_type: str, pipeline_id: str, user_id: UUID | None = None,
    ) -> bool:
        """Delete a pipeline."""
        try:
            await self._request_with_backoff(
                "DELETE", f"/crm/v3/pipelines/{object_type}/{pipeline_id}",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot delete_pipeline error: %s", exc)
            return False

    async def get_pipeline_stages(
        self, object_type: str, pipeline_id: str, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get all stages for a pipeline."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/crm/v3/pipelines/{object_type}/{pipeline_id}/stages",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {"id": s.get("id"), "label": s.get("label"), "displayOrder": s.get("displayOrder")}
                for s in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_pipeline_stages error: %s", exc)
            return []

    async def create_pipeline_stage(
        self,
        object_type: str,
        pipeline_id: str,
        label: str,
        display_order: int,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a stage in a pipeline."""
        try:
            resp = await self._request_with_backoff(
                "POST", f"/crm/v3/pipelines/{object_type}/{pipeline_id}/stages",
                user_id=user_id,
                json={"label": label, "displayOrder": display_order},
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "label": data.get("label"),
                "displayOrder": data.get("displayOrder"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_pipeline_stage error: %s", exc)
            return {"error": str(exc)}

    async def update_pipeline_stage(
        self,
        object_type: str,
        pipeline_id: str,
        stage_id: str,
        label: str,
        display_order: int | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Update a pipeline stage."""
        payload: dict = {"label": label}
        if display_order is not None:
            payload["displayOrder"] = display_order
        try:
            resp = await self._request_with_backoff(
                "PATCH",
                f"/crm/v3/pipelines/{object_type}/{pipeline_id}/stages/{stage_id}",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "label": data.get("label"),
                "displayOrder": data.get("displayOrder"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot update_pipeline_stage error: %s", exc)
            return {"error": str(exc)}

    # ── Associations v4 ───────────────────────────────────────────────────────

    async def create_association(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        association_type: str,
        user_id: UUID | None = None,
    ) -> bool:
        """Create an association between two CRM objects (v4 API)."""
        try:
            await self._request_with_backoff(
                "PUT",
                f"/crm/v4/objects/{from_type}/{from_id}/associations/{to_type}/{to_id}",
                user_id=user_id,
                json=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": association_type}],
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_association error: %s", exc)
            return False

    async def get_associations(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Get associations from one object to another type."""
        try:
            resp = await self._request_with_backoff(
                "GET",
                f"/crm/v4/objects/{from_type}/{from_id}/associations/{to_type}",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "to_id": a.get("toObjectId"),
                    "association_types": [
                        {"category": t.get("category"), "type_id": t.get("typeId"), "label": t.get("label")}
                        for t in a.get("associationTypes", [])
                    ],
                }
                for a in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_associations error: %s", exc)
            return []

    async def delete_association(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        user_id: UUID | None = None,
    ) -> bool:
        """Delete an association between two CRM objects."""
        try:
            await self._request_with_backoff(
                "DELETE",
                f"/crm/v4/objects/{from_type}/{from_id}/associations/{to_type}/{to_id}",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot delete_association error: %s", exc)
            return False

    async def batch_create_associations(
        self,
        from_type: str,
        to_type: str,
        inputs: list[dict],
        user_id: UUID | None = None,
    ) -> dict:
        """Batch create associations between objects."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                f"/crm/v4/associations/{from_type}/{to_type}/batch/create",
                user_id=user_id,
                json={"inputs": inputs},
            )
            data = resp.json()
            return {
                "status": data.get("status", "COMPLETE"),
                "results": data.get("results", []),
                "errors": data.get("errors", []),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot batch_create_associations error: %s", exc)
            return {"error": str(exc)}

    # ── CRM Search ────────────────────────────────────────────────────────────

    async def crm_search(
        self,
        object_type: str,
        filters: list | None = None,
        sorts: list | None = None,
        properties: list[str] | None = None,
        limit: int = 100,
        after: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Generic CRM search across any object type."""
        payload: dict = {"limit": min(limit, 100)}
        if filters:
            payload["filterGroups"] = [{"filters": filters}]
        if sorts:
            payload["sorts"] = sorts
        if properties:
            payload["properties"] = properties
        if after:
            payload["after"] = after

        try:
            resp = await self._request_with_backoff(
                "POST", f"/crm/v3/objects/{object_type}/search",
                user_id=user_id,
                json=payload,
            )
            body = resp.json()
            return {
                "results": [
                    {"id": r.get("id"), "properties": r.get("properties", {})}
                    for r in body.get("results", [])
                ],
                "total": body.get("total", 0),
                "paging": body.get("paging"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot crm_search error: %s", exc)
            return {"error": str(exc)}

    # ── Imports / Exports ─────────────────────────────────────────────────────

    async def import_contacts(
        self, file_url: str, mapping: dict, user_id: UUID | None = None,
    ) -> dict:
        """Start a contact import job."""
        import_request = {
            "name": f"import_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
            "importOperations": {"0-1": "CREATE"},
            "dateFormat": "YEAR_MONTH_DAY",
            "files": [
                {
                    "fileName": "contacts.csv",
                    "fileImportPage": {
                        "hasHeader": True,
                        "columnMappings": [
                            {
                                "columnObjectTypeId": "0-1",
                                "columnName": col,
                                "propertyName": prop,
                            }
                            for col, prop in mapping.items()
                        ],
                    },
                }
            ],
        }

        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/imports",
                user_id=user_id,
                json=import_request,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "state": data.get("state"),
                "created_at": data.get("createdAt"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot import_contacts error: %s", exc)
            return {"error": str(exc)}

    async def get_import_status(
        self, import_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Check the status of an import job."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/crm/v3/imports/{import_id}",
                user_id=user_id,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "state": data.get("state"),
                "opt_out_import": data.get("optOutImport"),
                "metadata": data.get("metadata"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_import_status error: %s", exc)
            return {"error": str(exc)}

    async def export_contacts(
        self,
        filters: list | None = None,
        properties: list[str] | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Export contacts by searching and building a result set."""
        props = properties or ["email", "firstname", "lastname", "phone", "company"]
        search_result = await self.crm_search(
            object_type="contacts",
            filters=filters,
            properties=props,
            limit=100,
            user_id=user_id,
        )
        if "error" in search_result:
            return search_result

        return {
            "contacts": search_result.get("results", []),
            "total": search_result.get("total", 0),
            "properties_exported": props,
            "exported_at": datetime.now(UTC).isoformat(),
        }

    # ── Marketing ─────────────────────────────────────────────────────────────

    async def send_transactional_email(
        self,
        email_id: str,
        to_email: str,
        contact_properties: dict | None = None,
        custom_properties: dict | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Send a transactional email."""
        payload: dict = {
            "emailId": int(email_id),
            "message": {"to": to_email},
        }
        if contact_properties:
            payload["contactProperties"] = contact_properties
        if custom_properties:
            payload["customProperties"] = custom_properties

        try:
            resp = await self._request_with_backoff(
                "POST", "/marketing/v3/transactional/single-email/send",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "status": data.get("status"),
                "send_result": data.get("sendResult"),
                "requested_at": data.get("requestedAt"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot send_transactional_email error: %s", exc)
            return {"error": str(exc)}

    async def get_marketing_emails(
        self, limit: int = 50, offset: int = 0, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get marketing emails."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/marketing/v3/emails",
                user_id=user_id,
                params={"limit": min(limit, 100), "offset": offset},
            )
            body = resp.json()
            return [
                {
                    "id": e.get("id"),
                    "name": e.get("name"),
                    "subject": e.get("subject"),
                    "state": e.get("state"),
                    "type": e.get("type"),
                }
                for e in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_marketing_emails error: %s", exc)
            return []

    async def get_email_statistics(
        self, email_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Get statistics for a marketing email."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/marketing/v3/emails/{email_id}/statistics",
                user_id=user_id,
            )
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_email_statistics error: %s", exc)
            return {"error": str(exc)}

    async def create_campaign(
        self,
        name: str,
        budget: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a marketing campaign."""
        payload: dict = {"name": name}
        if budget is not None:
            payload["budget"] = budget
        if start_date:
            payload["startDate"] = start_date
        if end_date:
            payload["endDate"] = end_date

        try:
            resp = await self._request_with_backoff(
                "POST", "/marketing/v3/campaigns",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "budget": data.get("budget"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_campaign error: %s", exc)
            return {"error": str(exc)}

    async def get_campaign_report(
        self, campaign_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Get a campaign's performance report."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/marketing/v3/campaigns/{campaign_id}/reports",
                user_id=user_id,
            )
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_campaign_report error: %s", exc)
            return {"error": str(exc)}

    # ── Forms ─────────────────────────────────────────────────────────────────

    async def list_forms(self, user_id: UUID | None = None) -> list[dict]:
        """List all marketing forms."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/marketing/v3/forms", user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "formType": f.get("formType"),
                    "createdAt": f.get("createdAt"),
                }
                for f in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_forms error: %s", exc)
            return []

    async def get_form_submissions(
        self, form_id: str, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get form submissions."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/marketing/v3/forms/{form_id}/submissions",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "submittedAt": s.get("submittedAt"),
                    "values": s.get("values", []),
                }
                for s in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_form_submissions error: %s", exc)
            return []

    async def create_form(
        self,
        name: str,
        form_type: str = "hubspot",
        fields: list[dict] | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a marketing form."""
        payload: dict = {"name": name, "formType": form_type}
        if fields:
            payload["fieldGroups"] = [{"fields": fields}]

        try:
            resp = await self._request_with_backoff(
                "POST", "/marketing/v3/forms",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "formType": data.get("formType"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_form error: %s", exc)
            return {"error": str(exc)}

    # ── Engagements (expand) ──────────────────────────────────────────────────

    async def log_postal_mail(
        self,
        contact_id: str,
        body: str,
        associations: list | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Log a postal mail engagement against a contact."""
        return await self._create_engagement(
            "postal_mail",
            {"hs_postal_mail_body": body},
            contact_id, 453, user_id,  # 453 = postal_mail-to-contact
        )

    async def create_task_with_queue(
        self,
        contact_id: str,
        subject: str,
        body: str | None = None,
        due_date: str | None = None,
        priority: str = "MEDIUM",
        queue_id: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a task with optional queue assignment and priority."""
        properties: dict = {
            "hs_task_subject": subject,
            "hs_task_status": "NOT_STARTED",
            "hs_task_priority": priority,
        }
        if body:
            properties["hs_task_body"] = body
        if due_date:
            properties["hs_timestamp"] = due_date
        if queue_id:
            properties["hs_queue_membership_ids"] = queue_id

        return await self._create_engagement(
            "tasks", properties, contact_id, 204, user_id,
        )

    # ── Automation ────────────────────────────────────────────────────────────

    async def get_workflows(
        self, limit: int = 50, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get automation workflows."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/automation/v4/flows",
                user_id=user_id,
                params={"limit": min(limit, 100)},
            )
            body = resp.json()
            return [
                {
                    "id": w.get("id"),
                    "name": w.get("name"),
                    "type": w.get("type"),
                    "enabled": w.get("enabled"),
                }
                for w in body.get("results", body.get("flows", []))
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_workflows error: %s", exc)
            return []

    async def trigger_workflow(
        self,
        workflow_id: str,
        contact_email: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Trigger (enroll a contact in) a workflow."""
        try:
            await self._request_with_backoff(
                "POST",
                f"/automation/v2/workflows/{workflow_id}/enrollments/contacts/{contact_email}",
                user_id=user_id,
            )
            return {"success": True, "workflow_id": workflow_id, "contact": contact_email}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot trigger_workflow error: %s", exc)
            return {"error": str(exc)}

    async def create_sequence_enrollment(
        self,
        sequence_id: str,
        contact_id: str,
        sender_email: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Enroll a contact in a sequence."""
        try:
            resp = await self._request_with_backoff(
                "POST", "/automation/v1/sequences/enroll",
                user_id=user_id,
                json={
                    "sequenceId": sequence_id,
                    "contactId": contact_id,
                    "senderEmail": sender_email,
                },
            )
            data = resp.json()
            return {
                "enrollment_id": data.get("id"),
                "sequence_id": sequence_id,
                "contact_id": contact_id,
                "status": data.get("status"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_sequence_enrollment error: %s", exc)
            return {"error": str(exc)}

    # ── Conversations ─────────────────────────────────────────────────────────

    async def list_inboxes(self, user_id: UUID | None = None) -> list[dict]:
        """List conversation inboxes."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/conversations/v3/conversations/inboxes",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": i.get("id"),
                    "name": i.get("name"),
                    "type": i.get("type"),
                }
                for i in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_inboxes error: %s", exc)
            return []

    async def get_threads(
        self, inbox_id: str, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get conversation threads for an inbox."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/conversations/v3/conversations/threads",
                user_id=user_id,
                params={"inboxId": inbox_id},
            )
            body = resp.json()
            return [
                {
                    "id": t.get("id"),
                    "status": t.get("status"),
                    "created_at": t.get("createdAt"),
                    "latest_message_timestamp": t.get("latestMessageTimestamp"),
                }
                for t in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_threads error: %s", exc)
            return []

    async def send_message(
        self,
        thread_id: str,
        text: str,
        channel_type: str = "EMAIL",
        user_id: UUID | None = None,
    ) -> dict:
        """Send a message in a conversation thread."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                f"/conversations/v3/conversations/threads/{thread_id}/messages",
                user_id=user_id,
                json={"type": "MESSAGE", "text": text, "channelAccountId": channel_type},
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "thread_id": thread_id,
                "text": text,
                "created_at": data.get("createdAt"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot send_message error: %s", exc)
            return {"error": str(exc)}

    # ── Commerce ──────────────────────────────────────────────────────────────

    async def create_invoice(
        self,
        contact_id: str,
        line_items: list[dict],
        due_date: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create an invoice linked to a contact."""
        properties: dict = {}
        if due_date:
            properties["hs_due_date"] = due_date

        payload: dict = {"properties": properties}
        associations = [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 87}],
            }
        ]
        payload["associations"] = associations

        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/invoices",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_invoice error: %s", exc)
            return {"error": str(exc)}

    async def create_payment(
        self, amount: float, contact_id: str | None = None, user_id: UUID | None = None,
    ) -> dict:
        """Create a payment record."""
        properties: dict = {"hs_payment_amount": str(amount)}
        payload: dict = {"properties": properties}

        if contact_id:
            payload["associations"] = [
                {
                    "to": {"id": contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 89}],
                }
            ]

        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/payments",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_payment error: %s", exc)
            return {"error": str(exc)}

    async def create_subscription(
        self,
        name: str,
        contact_id: str | None = None,
        line_items: list[dict] | None = None,
        billing_frequency: str = "monthly",
        user_id: UUID | None = None,
    ) -> dict:
        """Create a subscription record."""
        properties: dict = {
            "hs_subscription_name": name,
            "hs_billing_frequency": billing_frequency,
        }
        payload: dict = {"properties": properties}

        if contact_id:
            payload["associations"] = [
                {
                    "to": {"id": contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 91}],
                }
            ]

        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/subscriptions",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_subscription error: %s", exc)
            return {"error": str(exc)}

    # ── Settings ──────────────────────────────────────────────────────────────

    async def list_users(self, user_id: UUID | None = None) -> list[dict]:
        """List users in the HubSpot account."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/settings/v3/users", user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": u.get("id"),
                    "email": u.get("email"),
                    "role_id": u.get("roleId"),
                    "primary_team_id": u.get("primaryTeamId"),
                }
                for u in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_users error: %s", exc)
            return []

    async def list_teams(self, user_id: UUID | None = None) -> list[dict]:
        """List teams in the HubSpot account."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/settings/v3/users/teams", user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                }
                for t in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_teams error: %s", exc)
            return []

    async def list_currencies(self, user_id: UUID | None = None) -> list[dict]:
        """List currencies configured in the account."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/settings/v3/account-info/currencies", user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "code": c.get("code"),
                    "name": c.get("name"),
                    "exchange_rate": c.get("exchangeRate"),
                }
                for c in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_currencies error: %s", exc)
            return []

    # ── Webhooks ──────────────────────────────────────────────────────────────

    async def create_webhook_subscription(
        self,
        event_type: str,
        webhook_url: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a webhook subscription for CRM events."""
        app_id = getattr(settings, "HUBSPOT_APP_ID", None)
        if not app_id:
            return {"error": "HUBSPOT_APP_ID not configured"}

        try:
            resp = await self._request_with_backoff(
                "POST", f"/webhooks/v3/{app_id}/subscriptions",
                user_id=user_id,
                json={
                    "eventType": event_type,
                    "propertyName": None,
                    "active": True,
                },
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "event_type": data.get("eventType"),
                "active": data.get("active"),
                "created_at": data.get("createdAt"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_webhook_subscription error: %s", exc)
            return {"error": str(exc)}

    async def list_webhook_subscriptions(
        self, user_id: UUID | None = None,
    ) -> list[dict]:
        """List webhook subscriptions."""
        app_id = getattr(settings, "HUBSPOT_APP_ID", None)
        if not app_id:
            return []

        try:
            resp = await self._request_with_backoff(
                "GET", f"/webhooks/v3/{app_id}/subscriptions",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": s.get("id"),
                    "event_type": s.get("eventType"),
                    "active": s.get("active"),
                }
                for s in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_webhook_subscriptions error: %s", exc)
            return []

    async def delete_webhook_subscription(
        self, subscription_id: str, user_id: UUID | None = None,
    ) -> bool:
        """Delete a webhook subscription."""
        app_id = getattr(settings, "HUBSPOT_APP_ID", None)
        if not app_id:
            return False

        try:
            await self._request_with_backoff(
                "DELETE", f"/webhooks/v3/{app_id}/subscriptions/{subscription_id}",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot delete_webhook_subscription error: %s", exc)
            return False

    async def close(self) -> None:
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()

    # ── Pipelines ─────────────────────────────────────────────────────────────

    async def create_pipeline(
        self,
        object_type: str,
        label: str,
        stages: list[dict],
        user_id: UUID | None = None,
    ) -> dict:
        """Create a pipeline for an object type (deals, tickets, etc.).

        stages: [{"label": "New", "displayOrder": 0}, ...]
        """
        try:
            resp = await self._request_with_backoff(
                "POST", f"/crm/v3/pipelines/{object_type}",
                user_id=user_id,
                json={"label": label, "stages": stages},
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
            logger.error("HubSpot create_pipeline error: %s", exc)
            return {"error": str(exc)}


    async def update_pipeline(
        self,
        object_type: str,
        pipeline_id: str,
        label: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Update a pipeline's label."""
        try:
            resp = await self._request_with_backoff(
                "PATCH", f"/crm/v3/pipelines/{object_type}/{pipeline_id}",
                user_id=user_id,
                json={"label": label},
            )
            data = resp.json()
            return {"id": data.get("id"), "label": data.get("label")}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot update_pipeline error: %s", exc)
            return {"error": str(exc)}


    async def delete_pipeline(
        self, object_type: str, pipeline_id: str, user_id: UUID | None = None,
    ) -> bool:
        """Delete a pipeline."""
        try:
            await self._request_with_backoff(
                "DELETE", f"/crm/v3/pipelines/{object_type}/{pipeline_id}",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot delete_pipeline error: %s", exc)
            return False


    async def get_pipeline_stages(
        self, object_type: str, pipeline_id: str, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get all stages for a pipeline."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/crm/v3/pipelines/{object_type}/{pipeline_id}/stages",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {"id": s.get("id"), "label": s.get("label"), "displayOrder": s.get("displayOrder")}
                for s in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_pipeline_stages error: %s", exc)
            return []


    async def create_pipeline_stage(
        self,
        object_type: str,
        pipeline_id: str,
        label: str,
        display_order: int,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a stage in a pipeline."""
        try:
            resp = await self._request_with_backoff(
                "POST", f"/crm/v3/pipelines/{object_type}/{pipeline_id}/stages",
                user_id=user_id,
                json={"label": label, "displayOrder": display_order},
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "label": data.get("label"),
                "displayOrder": data.get("displayOrder"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_pipeline_stage error: %s", exc)
            return {"error": str(exc)}


    async def update_pipeline_stage(
        self,
        object_type: str,
        pipeline_id: str,
        stage_id: str,
        label: str,
        display_order: int | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Update a pipeline stage."""
        payload: dict = {"label": label}
        if display_order is not None:
            payload["displayOrder"] = display_order
        try:
            resp = await self._request_with_backoff(
                "PATCH",
                f"/crm/v3/pipelines/{object_type}/{pipeline_id}/stages/{stage_id}",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "label": data.get("label"),
                "displayOrder": data.get("displayOrder"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot update_pipeline_stage error: %s", exc)
            return {"error": str(exc)}


    # ── Associations v4 ───────────────────────────────────────────────────────

    async def create_association(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        association_type: str,
        user_id: UUID | None = None,
    ) -> bool:
        """Create an association between two CRM objects (v4 API)."""
        try:
            await self._request_with_backoff(
                "PUT",
                f"/crm/v4/objects/{from_type}/{from_id}/associations/{to_type}/{to_id}",
                user_id=user_id,
                json=[{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": association_type}],
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_association error: %s", exc)
            return False


    async def get_associations(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        user_id: UUID | None = None,
    ) -> list[dict]:
        """Get associations from one object to another type."""
        try:
            resp = await self._request_with_backoff(
                "GET",
                f"/crm/v4/objects/{from_type}/{from_id}/associations/{to_type}",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "to_id": a.get("toObjectId"),
                    "association_types": [
                        {"category": t.get("category"), "type_id": t.get("typeId"), "label": t.get("label")}
                        for t in a.get("associationTypes", [])
                    ],
                }
                for a in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_associations error: %s", exc)
            return []


    async def delete_association(
        self,
        from_type: str,
        from_id: str,
        to_type: str,
        to_id: str,
        user_id: UUID | None = None,
    ) -> bool:
        """Delete an association between two CRM objects."""
        try:
            await self._request_with_backoff(
                "DELETE",
                f"/crm/v4/objects/{from_type}/{from_id}/associations/{to_type}/{to_id}",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot delete_association error: %s", exc)
            return False


    async def batch_create_associations(
        self,
        from_type: str,
        to_type: str,
        inputs: list[dict],
        user_id: UUID | None = None,
    ) -> dict:
        """Batch create associations between objects.

        inputs: [{"from": {"id": "..."}, "to": {"id": "..."}, "types": [{"associationCategory": "...", "associationTypeId": ...}]}]
        """
        try:
            resp = await self._request_with_backoff(
                "POST",
                f"/crm/v4/associations/{from_type}/{to_type}/batch/create",
                user_id=user_id,
                json={"inputs": inputs},
            )
            data = resp.json()
            return {
                "status": data.get("status", "COMPLETE"),
                "results": data.get("results", []),
                "errors": data.get("errors", []),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot batch_create_associations error: %s", exc)
            return {"error": str(exc)}


    # ── CRM Search ────────────────────────────────────────────────────────────

    async def crm_search(
        self,
        object_type: str,
        filters: list | None = None,
        sorts: list | None = None,
        properties: list[str] | None = None,
        limit: int = 100,
        after: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Generic CRM search across any object type."""
        payload: dict = {"limit": min(limit, 100)}
        if filters:
            payload["filterGroups"] = [{"filters": filters}]
        if sorts:
            payload["sorts"] = sorts
        if properties:
            payload["properties"] = properties
        if after:
            payload["after"] = after

        try:
            resp = await self._request_with_backoff(
                "POST", f"/crm/v3/objects/{object_type}/search",
                user_id=user_id,
                json=payload,
            )
            body = resp.json()
            return {
                "results": [
                    {"id": r.get("id"), "properties": r.get("properties", {})}
                    for r in body.get("results", [])
                ],
                "total": body.get("total", 0),
                "paging": body.get("paging"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot crm_search error: %s", exc)
            return {"error": str(exc)}


    # ── Imports / Exports ─────────────────────────────────────────────────────

    async def import_contacts(
        self, file_url: str, mapping: dict, user_id: UUID | None = None,
    ) -> dict:
        """Start a contact import job.

        mapping: column-to-property mapping, e.g. {"Email": "email", "First Name": "firstname"}
        """
        import_request = {
            "name": f"import_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}",
            "importOperations": {"0-1": "CREATE"},
            "dateFormat": "YEAR_MONTH_DAY",
            "files": [
                {
                    "fileName": "contacts.csv",
                    "fileImportPage": {
                        "hasHeader": True,
                        "columnMappings": [
                            {
                                "columnObjectTypeId": "0-1",
                                "columnName": col,
                                "propertyName": prop,
                            }
                            for col, prop in mapping.items()
                        ],
                    },
                }
            ],
        }

        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/imports",
                user_id=user_id,
                json=import_request,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "state": data.get("state"),
                "created_at": data.get("createdAt"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot import_contacts error: %s", exc)
            return {"error": str(exc)}


    async def get_import_status(
        self, import_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Check the status of an import job."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/crm/v3/imports/{import_id}",
                user_id=user_id,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "state": data.get("state"),
                "opt_out_import": data.get("optOutImport"),
                "metadata": data.get("metadata"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_import_status error: %s", exc)
            return {"error": str(exc)}


    async def export_contacts(
        self,
        filters: list | None = None,
        properties: list[str] | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Export contacts by searching and building a result set."""
        props = properties or ["email", "firstname", "lastname", "phone", "company"]
        search_result = await self.crm_search(
            object_type="contacts",
            filters=filters,
            properties=props,
            limit=100,
            user_id=user_id,
        )
        if "error" in search_result:
            return search_result

        return {
            "contacts": search_result.get("results", []),
            "total": search_result.get("total", 0),
            "properties_exported": props,
            "exported_at": datetime.now(UTC).isoformat(),
        }


    # ── Marketing ─────────────────────────────────────────────────────────────

    async def send_transactional_email(
        self,
        email_id: str,
        to_email: str,
        contact_properties: dict | None = None,
        custom_properties: dict | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Send a transactional email."""
        payload: dict = {
            "emailId": int(email_id),
            "message": {"to": to_email},
        }
        if contact_properties:
            payload["contactProperties"] = contact_properties
        if custom_properties:
            payload["customProperties"] = custom_properties

        try:
            resp = await self._request_with_backoff(
                "POST", "/marketing/v3/transactional/single-email/send",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "status": data.get("status"),
                "send_result": data.get("sendResult"),
                "requested_at": data.get("requestedAt"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot send_transactional_email error: %s", exc)
            return {"error": str(exc)}


    async def get_marketing_emails(
        self, limit: int = 50, offset: int = 0, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get marketing emails."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/marketing/v3/emails",
                user_id=user_id,
                params={"limit": min(limit, 100), "offset": offset},
            )
            body = resp.json()
            return [
                {
                    "id": e.get("id"),
                    "name": e.get("name"),
                    "subject": e.get("subject"),
                    "state": e.get("state"),
                    "type": e.get("type"),
                }
                for e in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_marketing_emails error: %s", exc)
            return []


    async def get_email_statistics(
        self, email_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Get statistics for a marketing email."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/marketing/v3/emails/{email_id}/statistics",
                user_id=user_id,
            )
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_email_statistics error: %s", exc)
            return {"error": str(exc)}


    async def create_campaign(
        self,
        name: str,
        budget: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a marketing campaign."""
        payload: dict = {"name": name}
        if budget is not None:
            payload["budget"] = budget
        if start_date:
            payload["startDate"] = start_date
        if end_date:
            payload["endDate"] = end_date

        try:
            resp = await self._request_with_backoff(
                "POST", "/marketing/v3/campaigns",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "budget": data.get("budget"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_campaign error: %s", exc)
            return {"error": str(exc)}


    async def get_campaign_report(
        self, campaign_id: str, user_id: UUID | None = None,
    ) -> dict:
        """Get a campaign's performance report."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/marketing/v3/campaigns/{campaign_id}/reports",
                user_id=user_id,
            )
            return resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_campaign_report error: %s", exc)
            return {"error": str(exc)}


    # ── Forms ─────────────────────────────────────────────────────────────────

    async def list_forms(self, user_id: UUID | None = None) -> list[dict]:
        """List all marketing forms."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/marketing/v3/forms", user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": f.get("id"),
                    "name": f.get("name"),
                    "formType": f.get("formType"),
                    "createdAt": f.get("createdAt"),
                }
                for f in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_forms error: %s", exc)
            return []


    async def get_form_submissions(
        self, form_id: str, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get form submissions."""
        try:
            resp = await self._request_with_backoff(
                "GET", f"/marketing/v3/forms/{form_id}/submissions",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "submittedAt": s.get("submittedAt"),
                    "values": s.get("values", []),
                }
                for s in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_form_submissions error: %s", exc)
            return []


    async def create_form(
        self,
        name: str,
        form_type: str = "hubspot",
        fields: list[dict] | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a marketing form."""
        payload: dict = {"name": name, "formType": form_type}
        if fields:
            payload["fieldGroups"] = [{"fields": fields}]

        try:
            resp = await self._request_with_backoff(
                "POST", "/marketing/v3/forms",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "name": data.get("name"),
                "formType": data.get("formType"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_form error: %s", exc)
            return {"error": str(exc)}


    # ── Engagements (expand) ──────────────────────────────────────────────────

    async def log_postal_mail(
        self,
        contact_id: str,
        body: str,
        associations: list | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Log a postal mail engagement against a contact."""
        return await self._create_engagement(
            "postal_mail",
            {"hs_postal_mail_body": body},
            contact_id, 453, user_id,  # 453 = postal_mail-to-contact
        )


    async def create_task_with_queue(
        self,
        contact_id: str,
        subject: str,
        body: str | None = None,
        due_date: str | None = None,
        priority: str = "MEDIUM",
        queue_id: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a task with optional queue assignment and priority."""
        properties: dict = {
            "hs_task_subject": subject,
            "hs_task_status": "NOT_STARTED",
            "hs_task_priority": priority,
        }
        if body:
            properties["hs_task_body"] = body
        if due_date:
            properties["hs_timestamp"] = due_date
        if queue_id:
            properties["hs_queue_membership_ids"] = queue_id

        return await self._create_engagement(
            "tasks", properties, contact_id, 204, user_id,
        )


    # ── Automation ────────────────────────────────────────────────────────────

    async def get_workflows(
        self, limit: int = 50, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get automation workflows."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/automation/v4/flows",
                user_id=user_id,
                params={"limit": min(limit, 100)},
            )
            body = resp.json()
            return [
                {
                    "id": w.get("id"),
                    "name": w.get("name"),
                    "type": w.get("type"),
                    "enabled": w.get("enabled"),
                }
                for w in body.get("results", body.get("flows", []))
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_workflows error: %s", exc)
            return []


    async def trigger_workflow(
        self,
        workflow_id: str,
        contact_email: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Trigger (enroll a contact in) a workflow."""
        try:
            await self._request_with_backoff(
                "POST",
                f"/automation/v2/workflows/{workflow_id}/enrollments/contacts/{contact_email}",
                user_id=user_id,
            )
            return {"success": True, "workflow_id": workflow_id, "contact": contact_email}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot trigger_workflow error: %s", exc)
            return {"error": str(exc)}


    async def create_sequence_enrollment(
        self,
        sequence_id: str,
        contact_id: str,
        sender_email: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Enroll a contact in a sequence."""
        try:
            resp = await self._request_with_backoff(
                "POST", "/automation/v1/sequences/enroll",
                user_id=user_id,
                json={
                    "sequenceId": sequence_id,
                    "contactId": contact_id,
                    "senderEmail": sender_email,
                },
            )
            data = resp.json()
            return {
                "enrollment_id": data.get("id"),
                "sequence_id": sequence_id,
                "contact_id": contact_id,
                "status": data.get("status"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_sequence_enrollment error: %s", exc)
            return {"error": str(exc)}


    # ── Conversations ─────────────────────────────────────────────────────────

    async def list_inboxes(self, user_id: UUID | None = None) -> list[dict]:
        """List conversation inboxes."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/conversations/v3/conversations/inboxes",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": i.get("id"),
                    "name": i.get("name"),
                    "type": i.get("type"),
                }
                for i in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_inboxes error: %s", exc)
            return []


    async def get_threads(
        self, inbox_id: str, user_id: UUID | None = None,
    ) -> list[dict]:
        """Get conversation threads for an inbox."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/conversations/v3/conversations/threads",
                user_id=user_id,
                params={"inboxId": inbox_id},
            )
            body = resp.json()
            return [
                {
                    "id": t.get("id"),
                    "status": t.get("status"),
                    "created_at": t.get("createdAt"),
                    "latest_message_timestamp": t.get("latestMessageTimestamp"),
                }
                for t in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot get_threads error: %s", exc)
            return []


    async def send_message(
        self,
        thread_id: str,
        text: str,
        channel_type: str = "EMAIL",
        user_id: UUID | None = None,
    ) -> dict:
        """Send a message in a conversation thread."""
        try:
            resp = await self._request_with_backoff(
                "POST",
                f"/conversations/v3/conversations/threads/{thread_id}/messages",
                user_id=user_id,
                json={"type": "MESSAGE", "text": text, "channelAccountId": channel_type},
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "thread_id": thread_id,
                "text": text,
                "created_at": data.get("createdAt"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot send_message error: %s", exc)
            return {"error": str(exc)}


    # ── Commerce ──────────────────────────────────────────────────────────────

    async def create_invoice(
        self,
        contact_id: str,
        line_items: list[dict],
        due_date: str | None = None,
        user_id: UUID | None = None,
    ) -> dict:
        """Create an invoice linked to a contact."""
        properties: dict = {}
        if due_date:
            properties["hs_due_date"] = due_date

        payload: dict = {"properties": properties}
        associations = [
            {
                "to": {"id": contact_id},
                "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 87}],
            }
        ]
        payload["associations"] = associations

        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/invoices",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_invoice error: %s", exc)
            return {"error": str(exc)}


    async def create_payment(
        self, amount: float, contact_id: str | None = None, user_id: UUID | None = None,
    ) -> dict:
        """Create a payment record."""
        properties: dict = {"hs_payment_amount": str(amount)}
        payload: dict = {"properties": properties}

        if contact_id:
            payload["associations"] = [
                {
                    "to": {"id": contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 89}],
                }
            ]

        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/payments",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_payment error: %s", exc)
            return {"error": str(exc)}


    async def create_subscription(
        self,
        name: str,
        contact_id: str | None = None,
        line_items: list[dict] | None = None,
        billing_frequency: str = "monthly",
        user_id: UUID | None = None,
    ) -> dict:
        """Create a subscription record."""
        properties: dict = {
            "hs_subscription_name": name,
            "hs_billing_frequency": billing_frequency,
        }
        payload: dict = {"properties": properties}

        if contact_id:
            payload["associations"] = [
                {
                    "to": {"id": contact_id},
                    "types": [{"associationCategory": "HUBSPOT_DEFINED", "associationTypeId": 91}],
                }
            ]

        try:
            resp = await self._request_with_backoff(
                "POST", "/crm/v3/objects/subscriptions",
                user_id=user_id,
                json=payload,
            )
            data = resp.json()
            return {"id": data.get("id"), "properties": data.get("properties", {})}
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_subscription error: %s", exc)
            return {"error": str(exc)}


    # ── Settings ──────────────────────────────────────────────────────────────

    async def list_users(self, user_id: UUID | None = None) -> list[dict]:
        """List users in the HubSpot account."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/settings/v3/users", user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": u.get("id"),
                    "email": u.get("email"),
                    "role_id": u.get("roleId"),
                    "primary_team_id": u.get("primaryTeamId"),
                }
                for u in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_users error: %s", exc)
            return []


    async def list_teams(self, user_id: UUID | None = None) -> list[dict]:
        """List teams in the HubSpot account."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/settings/v3/users/teams", user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": t.get("id"),
                    "name": t.get("name"),
                }
                for t in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_teams error: %s", exc)
            return []


    async def list_currencies(self, user_id: UUID | None = None) -> list[dict]:
        """List currencies configured in the account."""
        try:
            resp = await self._request_with_backoff(
                "GET", "/settings/v3/account-info/currencies", user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "code": c.get("code"),
                    "name": c.get("name"),
                    "exchange_rate": c.get("exchangeRate"),
                }
                for c in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_currencies error: %s", exc)
            return []


    # ── Webhooks ──────────────────────────────────────────────────────────────

    async def create_webhook_subscription(
        self,
        event_type: str,
        webhook_url: str,
        user_id: UUID | None = None,
    ) -> dict:
        """Create a webhook subscription for CRM events.

        event_type: e.g. "contact.creation", "deal.propertyChange"
        """
        app_id = getattr(settings, "HUBSPOT_APP_ID", None)
        if not app_id:
            return {"error": "HUBSPOT_APP_ID not configured"}

        try:
            resp = await self._request_with_backoff(
                "POST", f"/webhooks/v3/{app_id}/subscriptions",
                user_id=user_id,
                json={
                    "eventType": event_type,
                    "propertyName": None,
                    "active": True,
                },
            )
            data = resp.json()
            return {
                "id": data.get("id"),
                "event_type": data.get("eventType"),
                "active": data.get("active"),
                "created_at": data.get("createdAt"),
            }
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot create_webhook_subscription error: %s", exc)
            return {"error": str(exc)}


    async def list_webhook_subscriptions(
        self, user_id: UUID | None = None,
    ) -> list[dict]:
        """List webhook subscriptions."""
        app_id = getattr(settings, "HUBSPOT_APP_ID", None)
        if not app_id:
            return []

        try:
            resp = await self._request_with_backoff(
                "GET", f"/webhooks/v3/{app_id}/subscriptions",
                user_id=user_id,
            )
            body = resp.json()
            return [
                {
                    "id": s.get("id"),
                    "event_type": s.get("eventType"),
                    "active": s.get("active"),
                }
                for s in body.get("results", [])
            ]
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot list_webhook_subscriptions error: %s", exc)
            return []


    async def delete_webhook_subscription(
        self, subscription_id: str, user_id: UUID | None = None,
    ) -> bool:
        """Delete a webhook subscription."""
        app_id = getattr(settings, "HUBSPOT_APP_ID", None)
        if not app_id:
            return False

        try:
            await self._request_with_backoff(
                "DELETE", f"/webhooks/v3/{app_id}/subscriptions/{subscription_id}",
                user_id=user_id,
            )
            return True
        except httpx.HTTPStatusError as exc:
            logger.error("HubSpot delete_webhook_subscription error: %s", exc)
            return False

