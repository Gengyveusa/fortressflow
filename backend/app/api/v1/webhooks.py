"""
HubSpot webhook endpoint.

Receives HubSpot event payloads (e.g. contact.propertyChange) and triggers
re-enrichment when relevant properties change.
"""

import logging

from fastapi import APIRouter, Depends, Request, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lead import Lead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


@router.post("/hubspot", status_code=status.HTTP_200_OK)
async def hubspot_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Receive HubSpot webhook events.

    Handles contact.propertyChange events: if a relevant property changed
    on a contact we track, queue a re-enrichment.
    """
    try:
        events = await request.json()
    except Exception:
        logger.warning("HubSpot webhook: invalid JSON body")
        return {"processed": 0}

    if not isinstance(events, list):
        events = [events]

    processed = 0
    re_enrich_properties = {"email", "firstname", "lastname", "company", "jobtitle", "phone"}

    for event in events:
        subscription_type = event.get("subscriptionType", "")
        property_name = event.get("propertyName", "")
        object_id = event.get("objectId")

        if subscription_type != "contact.propertyChange":
            continue

        if property_name not in re_enrich_properties:
            continue

        # Look up lead by HubSpot-synced email if property is email change
        property_value = event.get("propertyValue", "")
        if property_name == "email" and property_value:
            result = await db.execute(
                select(Lead).where(func.lower(Lead.email) == property_value.lower())
            )
            lead = result.scalar_one_or_none()
            if lead:
                # Reset last_enriched_at to trigger re-enrichment
                lead.last_enriched_at = None
                logger.info(
                    "HubSpot webhook: queued re-enrich for lead %s (property %s changed)",
                    lead.id,
                    property_name,
                )
                processed += 1

    await db.flush()
    logger.info("HubSpot webhook: processed %d events", processed)
    return {"processed": processed}
