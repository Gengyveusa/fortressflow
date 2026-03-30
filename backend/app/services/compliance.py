"""
Compliance service — hard gate for all outbound communication.

All send decisions MUST pass through can_send_to_lead before any message
is dispatched. No code path should bypass this function.
"""

import hashlib
import hmac
import json
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.consent import Consent, ConsentChannel, ConsentMethod
from app.models.dnc import DNCBlock
from app.models.lead import Lead
from app.models.touch_log import TouchLog


async def can_send_to_lead(
    lead_id: UUID,
    channel: str,
    db: AsyncSession,
) -> tuple[bool, str]:
    """
    Hard gate: returns (bool, reason_string).

    Checks in order:
    1. Lead exists
    2. Active consent for channel (not revoked)
    3. Not on DNC list for channel or identifier
    4. Email/phone not empty/malformed
    5. Not over daily limits (100 emails, 30 SMS, 25 LinkedIn per lead per day)

    Returns (True, "approved") or (False, "reason why blocked").
    """
    # 1. Lead exists
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        return False, "lead_not_found"

    # 2. Active consent
    result = await db.execute(
        select(Consent).where(
            and_(
                Consent.lead_id == lead_id,
                Consent.channel == channel,
                Consent.revoked_at.is_(None),
            )
        )
    )
    consent = result.scalar_one_or_none()
    if consent is None:
        return False, "no_active_consent"

    # 3. DNC check (by lead identifier — email or phone)
    identifier = lead.email if channel in ("email", "linkedin") else (lead.phone or lead.email)
    result = await db.execute(
        select(DNCBlock).where(
            and_(
                DNCBlock.identifier == identifier,
                DNCBlock.channel == channel,
            )
        )
    )
    dnc = result.scalar_one_or_none()
    if dnc is not None:
        return False, f"on_dnc_list: {dnc.reason}"

    # 4. Validate contact info
    if channel == "email" and not lead.email:
        return False, "missing_email"
    if channel == "sms" and not lead.phone:
        return False, "missing_phone"

    # 5. Daily limits
    limit_map = {
        "email": settings.DAILY_EMAIL_LIMIT,
        "sms": settings.DAILY_SMS_LIMIT,
        "linkedin": settings.DAILY_LINKEDIN_LIMIT,
    }
    limit = limit_map.get(channel, 0)

    today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    result = await db.execute(
        select(func.count(TouchLog.id)).where(
            and_(
                TouchLog.lead_id == lead_id,
                TouchLog.channel == channel,
                TouchLog.action == "sent",
                TouchLog.created_at >= today_start,
            )
        )
    )
    count = result.scalar_one()
    if count >= limit:
        return False, f"daily_limit_exceeded: {count}/{limit} for {channel}"

    return True, "approved"


async def record_consent(
    lead_id: UUID,
    channel: str,
    method: str,
    proof: dict,
    db: AsyncSession,
) -> Consent:
    """Record a new consent grant for a lead/channel pair."""
    consent = Consent(
        lead_id=lead_id,
        channel=ConsentChannel(channel),
        method=ConsentMethod(method),
        proof=proof,
        granted_at=datetime.now(UTC),
    )
    db.add(consent)
    await db.flush()
    await db.refresh(consent)
    return consent


async def revoke_consent(
    lead_id: UUID,
    channel: str,
    db: AsyncSession,
) -> bool:
    """Revoke all active consents for a lead/channel. Returns True if any were revoked."""
    result = await db.execute(
        select(Consent).where(
            and_(
                Consent.lead_id == lead_id,
                Consent.channel == channel,
                Consent.revoked_at.is_(None),
            )
        )
    )
    consents = result.scalars().all()
    if not consents:
        return False
    now = datetime.now(UTC)
    for c in consents:
        c.revoked_at = now
    await db.flush()
    return True


async def add_to_dnc(
    identifier: str,
    channel: str,
    reason: str,
    source: str,
    db: AsyncSession,
) -> DNCBlock:
    """Add an identifier (email or phone) to the DNC list for a channel."""
    block = DNCBlock(
        identifier=identifier,
        channel=channel,
        reason=reason,
        blocked_at=datetime.now(UTC),
        source=source,
    )
    db.add(block)
    await db.flush()
    await db.refresh(block)
    return block


async def get_audit_trail(lead_id: UUID, db: AsyncSession) -> dict:
    """Return all consents, touch logs, and DNC records associated with a lead."""
    result = await db.execute(select(Lead).where(Lead.id == lead_id))
    lead = result.scalar_one_or_none()
    if lead is None:
        return {"lead_id": lead_id, "consents": [], "touch_logs": [], "dnc_records": []}

    result = await db.execute(
        select(Consent).where(Consent.lead_id == lead_id).order_by(Consent.created_at)
    )
    consents = result.scalars().all()

    result = await db.execute(
        select(TouchLog).where(TouchLog.lead_id == lead_id).order_by(TouchLog.created_at)
    )
    touch_logs = result.scalars().all()

    identifier = lead.email
    result = await db.execute(
        select(DNCBlock).where(DNCBlock.identifier == identifier).order_by(DNCBlock.created_at)
    )
    dnc_records = result.scalars().all()
    if lead.phone:
        result = await db.execute(
            select(DNCBlock)
            .where(DNCBlock.identifier == lead.phone)
            .order_by(DNCBlock.created_at)
        )
        phone_dnc = result.scalars().all()
        dnc_records = list(dnc_records) + list(phone_dnc)

    return {
        "lead_id": lead_id,
        "consents": [
            {
                "id": str(c.id),
                "channel": c.channel,
                "method": c.method,
                "proof": c.proof,
                "granted_at": c.granted_at.isoformat(),
                "revoked_at": c.revoked_at.isoformat() if c.revoked_at else None,
                "created_at": c.created_at.isoformat(),
            }
            for c in consents
        ],
        "touch_logs": [
            {
                "id": str(t.id),
                "channel": t.channel,
                "action": t.action,
                "sequence_id": str(t.sequence_id) if t.sequence_id else None,
                "step_number": t.step_number,
                "metadata": t.extra_metadata,
                "created_at": t.created_at.isoformat(),
            }
            for t in touch_logs
        ],
        "dnc_records": [
            {
                "id": str(d.id),
                "identifier": d.identifier,
                "channel": d.channel,
                "reason": d.reason,
                "blocked_at": d.blocked_at.isoformat(),
                "source": d.source,
            }
            for d in dnc_records
        ],
    }


def generate_unsubscribe_token(lead_id: UUID, channel: str) -> str:
    """Generate a signed HMAC-SHA256 token encoding lead_id and channel."""
    import base64
    payload = json.dumps({"lead_id": str(lead_id), "channel": channel}, sort_keys=True)
    sig = hmac.new(
        settings.UNSUBSCRIBE_HMAC_KEY.encode(),
        payload.encode(),
        hashlib.sha256,
    ).hexdigest()
    token_data = base64.urlsafe_b64encode(
        json.dumps({"payload": payload, "sig": sig}).encode()
    ).decode()
    return token_data


def verify_unsubscribe_token(token: str) -> tuple[UUID, str] | tuple[None, None]:
    """
    Verify HMAC token and return (lead_id, channel) or (None, None) if invalid.
    """
    import base64
    try:
        decoded = json.loads(base64.urlsafe_b64decode(token.encode()).decode())
        payload = decoded["payload"]
        provided_sig = decoded["sig"]
        expected_sig = hmac.new(
            settings.UNSUBSCRIBE_HMAC_KEY.encode(),
            payload.encode(),
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(provided_sig, expected_sig):
            return None, None
        data = json.loads(payload)
        return UUID(data["lead_id"]), data["channel"]
    except Exception:
        return None, None
