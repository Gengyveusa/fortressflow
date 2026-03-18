from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lead import Lead
from app.models.touch_log import TouchLog, TouchAction
from app.schemas.compliance import UnsubscribeResponse
from app.services import compliance as compliance_svc

router = APIRouter(tags=["unsubscribe"])


@router.post("/unsubscribe/{token}", response_model=UnsubscribeResponse)
async def handle_unsubscribe(
    token: str,
    db: AsyncSession = Depends(get_db),
) -> UnsubscribeResponse:
    """
    Process a one-click unsubscribe via HMAC token.
    Adds the lead's email (or phone for SMS) to DNC and logs an unsubscribed touch.
    """
    lead_id, channel = compliance_svc.verify_unsubscribe_token(token)
    if lead_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or tampered unsubscribe token",
        )

    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Lead not found")

    # Use the actual contact identifier (email or phone), not the UUID
    identifier = lead.phone if channel == "sms" and lead.phone else lead.email

    await compliance_svc.add_to_dnc(
        identifier=identifier,
        channel=channel,
        reason="user_unsubscribed",
        source="unsubscribe_link",
        db=db,
    )
    await compliance_svc.revoke_consent(lead_id, channel, db)

    log = TouchLog(
        lead_id=lead_id,
        channel=channel,
        action=TouchAction.unsubscribed,
        extra_metadata={"token": token},
    )
    db.add(log)

    return UnsubscribeResponse(unsubscribed=True, message="You have been unsubscribed successfully.")
