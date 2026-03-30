"""Deal routes — HubSpot deal tracking for leads."""

import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.lead import Lead
from app.models.user import User
from app.services.hubspot import HubSpotService

logger = logging.getLogger(__name__)

router = APIRouter(tags=["deals"])


# ── Schemas ────────────────────────────────────────────────


class DealCreate(BaseModel):
    deal_name: str
    pipeline: str = "default"
    stage: str = "appointmentscheduled"
    amount: float | None = None


class DealStageUpdate(BaseModel):
    stage: str


class DealResponse(BaseModel):
    deal_id: str
    deal_name: str
    pipeline: str
    stage: str
    amount: float | None = None
    created_at: str | None = None
    updated_at: str | None = None
    hs_deal_id: str | None = None


class PipelineStage(BaseModel):
    stage_id: str
    label: str


class PipelineResponse(BaseModel):
    pipeline_id: str
    label: str
    stages: list[PipelineStage]


# ── Helpers ────────────────────────────────────────────────


def _deal_from_hs_props(props: dict) -> DealResponse:
    """Convert HubSpot deal properties to DealResponse."""
    amount_raw = props.get("amount")
    amount = float(amount_raw) if amount_raw else None
    return DealResponse(
        deal_id=props.get("hs_object_id", ""),
        deal_name=props.get("dealname", ""),
        pipeline=props.get("pipeline", ""),
        stage=props.get("dealstage", ""),
        amount=amount,
        created_at=props.get("createdate"),
        updated_at=props.get("hs_lastmodifieddate"),
        hs_deal_id=props.get("hs_object_id"),
    )


async def _get_hs_contact_id(lead: Lead, hs: HubSpotService) -> str:
    """Get or create the HubSpot contact ID for a lead."""
    # Check enriched_data for existing hs_object_id
    if lead.enriched_data and lead.enriched_data.get("hs_object_id"):
        return str(lead.enriched_data["hs_object_id"])
    # Push lead to HubSpot to get the contact ID
    return await hs.push_lead_to_hubspot(lead)


# ── Endpoints ──────────────────────────────────────────────


@router.get("/leads/{lead_id}/deals", response_model=list[DealResponse])
async def list_deals_for_lead(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """List deals associated with a lead (from HubSpot)."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    hs = HubSpotService()
    hs_contact_id = await _get_hs_contact_id(lead, hs)
    if not hs_contact_id:
        return []

    hs_deals = await hs.sync_deals(hs_contact_id)
    return [_deal_from_hs_props(d) for d in hs_deals]


@router.post(
    "/leads/{lead_id}/deals",
    response_model=DealResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_deal_for_lead(
    lead_id: UUID,
    body: DealCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Create a deal in HubSpot for a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    hs = HubSpotService()
    hs_contact_id = await _get_hs_contact_id(lead, hs)
    if not hs_contact_id:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Could not resolve HubSpot contact for this lead",
        )

    props = await hs.create_deal(
        hs_contact_id=hs_contact_id,
        deal_name=body.deal_name,
        pipeline=body.pipeline,
        stage=body.stage,
        amount=body.amount,
    )
    if not props:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to create deal in HubSpot",
        )

    return _deal_from_hs_props(props)


@router.put("/deals/{deal_id}/stage", response_model=DealResponse)
async def update_deal_stage(
    deal_id: str,
    body: DealStageUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update the pipeline stage of a deal in HubSpot."""
    hs = HubSpotService()
    props = await hs.update_deal_stage(deal_id, body.stage)
    if not props:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Failed to update deal stage in HubSpot",
        )
    return _deal_from_hs_props(props)


@router.get("/deals/pipelines", response_model=list[PipelineResponse])
async def list_pipelines(
    current_user: User = Depends(get_current_user),
):
    """Get available HubSpot deal pipelines and stages."""
    hs = HubSpotService()
    pipelines = await hs.list_pipelines()
    return [
        PipelineResponse(
            pipeline_id=p["pipeline_id"],
            label=p["label"],
            stages=[PipelineStage(**s) for s in p["stages"]],
        )
        for p in pipelines
    ]
