from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user, require_role
from app.database import get_db
from app.models.user import User, UserRole
from app.models.dnc import DNCBlock
from app.schemas.compliance import (
    AuditTrailResponse,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ConsentGrantRequest,
    ConsentGrantResponse,
    ConsentRevokeRequest,
    ConsentRevokeResponse,
    DNCAddRequest,
)
from app.services import compliance as compliance_svc

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    body: ComplianceCheckRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ComplianceCheckResponse:
    """Hard gate: determine whether a message may be sent to a lead on a channel."""
    can_send, reason = await compliance_svc.can_send_to_lead(body.lead_id, body.channel, db)
    return ComplianceCheckResponse(can_send=can_send, reason=reason)


@router.post(
    "/consent",
    response_model=ConsentGrantResponse,
    status_code=status.HTTP_201_CREATED,
)
async def grant_consent(
    body: ConsentGrantRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentGrantResponse:
    """Record explicit consent for a lead/channel combination."""
    consent = await compliance_svc.record_consent(body.lead_id, body.channel, body.method, body.proof, db)
    return ConsentGrantResponse(consent_id=consent.id, granted_at=consent.granted_at)


@router.post("/revoke", response_model=ConsentRevokeResponse)
async def revoke_consent(
    body: ConsentRevokeRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> ConsentRevokeResponse:
    """Revoke all active consents for a lead/channel."""
    revoked = await compliance_svc.revoke_consent(body.lead_id, body.channel, db)
    return ConsentRevokeResponse(revoked=revoked)


@router.get("/audit/{lead_id}", response_model=AuditTrailResponse)
async def get_audit_trail(
    lead_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AuditTrailResponse:
    """Return the full audit trail for a lead (consents, touch logs, DNC records)."""
    trail = await compliance_svc.get_audit_trail(lead_id, db)
    return AuditTrailResponse(**trail)


# ── DNC Management Endpoints ───────────────────────────────────────────────


@router.get("/dnc")
async def list_dnc(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    search: str = Query("", description="Filter by identifier (email/phone)"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List all DNC entries with optional search and pagination."""
    query = select(DNCBlock).order_by(DNCBlock.created_at.desc())
    count_query = select(func.count(DNCBlock.id))

    if search:
        query = query.where(DNCBlock.identifier.ilike(f"%{search}%"))
        count_query = count_query.where(DNCBlock.identifier.ilike(f"%{search}%"))

    total_r = await db.execute(count_query)
    total = total_r.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(query.offset(offset).limit(page_size))
    entries = result.scalars().all()

    return {
        "items": [
            {
                "id": str(e.id),
                "identifier": e.identifier,
                "channel": e.channel,
                "reason": e.reason,
                "source": e.source,
                "blocked_at": e.blocked_at.isoformat(),
                "created_at": e.created_at.isoformat(),
            }
            for e in entries
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/dnc", status_code=status.HTTP_201_CREATED)
async def add_dnc(
    body: DNCAddRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add an email or phone to the DNC list."""
    block = await compliance_svc.add_to_dnc(body.identifier, body.channel, body.reason, body.source, db)
    return {
        "id": str(block.id),
        "identifier": block.identifier,
        "channel": block.channel,
        "reason": block.reason,
        "source": block.source,
        "blocked_at": block.blocked_at.isoformat(),
    }


@router.delete("/dnc/{dnc_id}", status_code=status.HTTP_200_OK)
async def remove_dnc(
    dnc_id: UUID,
    current_user: User = Depends(require_role(UserRole.admin)),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Remove a DNC entry by ID."""
    result = await db.execute(select(DNCBlock).where(DNCBlock.id == dnc_id))
    block = result.scalar_one_or_none()
    if block is None:
        raise HTTPException(status_code=404, detail="DNC entry not found")
    await db.delete(block)
    await db.flush()
    return {"deleted": True, "id": str(dnc_id)}
