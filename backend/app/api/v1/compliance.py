from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.compliance import (
    AuditTrailResponse,
    ComplianceCheckRequest,
    ComplianceCheckResponse,
    ConsentGrantRequest,
    ConsentGrantResponse,
    ConsentRevokeRequest,
    ConsentRevokeResponse,
)
from app.services import compliance as compliance_svc

router = APIRouter(prefix="/compliance", tags=["compliance"])


@router.post("/check", response_model=ComplianceCheckResponse)
async def check_compliance(
    body: ComplianceCheckRequest,
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
    db: AsyncSession = Depends(get_db),
) -> ConsentGrantResponse:
    """Record explicit consent for a lead/channel combination."""
    consent = await compliance_svc.record_consent(
        body.lead_id, body.channel, body.method, body.proof, db
    )
    return ConsentGrantResponse(consent_id=consent.id, granted_at=consent.granted_at)


@router.post("/revoke", response_model=ConsentRevokeResponse)
async def revoke_consent(
    body: ConsentRevokeRequest,
    db: AsyncSession = Depends(get_db),
) -> ConsentRevokeResponse:
    """Revoke all active consents for a lead/channel."""
    revoked = await compliance_svc.revoke_consent(body.lead_id, body.channel, db)
    return ConsentRevokeResponse(revoked=revoked)


@router.get("/audit/{lead_id}", response_model=AuditTrailResponse)
async def get_audit_trail(
    lead_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> AuditTrailResponse:
    """Return the full audit trail for a lead (consents, touch logs, DNC records)."""
    trail = await compliance_svc.get_audit_trail(lead_id, db)
    return AuditTrailResponse(**trail)
