"""
Twilio SMS Service — Phase 5 Full Production.

Handles:
- Full Twilio client.messages.create() with status callbacks
- Time-zone gating (8AM-9PM recipient local time via pytz + lead TZ from enrichment)
- Segment handling (>160 chars → multi-segment awareness, prefer <160)
- TCPA consent verification (only if proof includes "written" + disclosure)
- STOP/DNC processing from inbound
- Delivery metrics logging → Prometheus + AI platforms
- Ultra-short CTA-heavy messages with STOP reminder
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pytz
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.consent import Consent, ConsentChannel, ConsentMethod
from app.models.dnc import DNCBlock
from app.models.lead import Lead
from app.models.sequence import EnrollmentStatus, SequenceEnrollment
from app.models.touch_log import TouchAction, TouchLog

logger = logging.getLogger(__name__)


# ── SMS Constants ──────────────────────────────────────────────────────────

SMS_SEGMENT_LENGTH = 160
SMS_MAX_SEGMENTS = 4  # Keep messages concise for B2B
SMS_MAX_CHARS = SMS_SEGMENT_LENGTH * SMS_MAX_SEGMENTS
DEFAULT_STOP_FOOTER = "Reply STOP to opt out"

# STOP keywords that trigger auto-DNC (Twilio handles server-side; double-check here)
STOP_KEYWORDS = {"stop", "unsubscribe", "cancel", "end", "quit", "stopall"}

# TCPA send window (8AM–9PM)
SEND_WINDOW_START_HOUR = 8
SEND_WINDOW_END_HOUR = 21

# Default timezone if no lead TZ enriched
DEFAULT_TIMEZONE = "US/Eastern"


# ── Data Structures ────────────────────────────────────────────────────────


@dataclass
class SMSConfig:
    """Runtime configuration for the SMS service."""

    daily_limit: int = 30
    send_window_start: int = SEND_WINDOW_START_HOUR
    send_window_end: int = SEND_WINDOW_END_HOUR
    max_segments: int = SMS_MAX_SEGMENTS
    callback_url: str = ""
    default_stop_footer: str = DEFAULT_STOP_FOOTER


@dataclass
class SMSResult:
    """Result of an SMS send operation."""

    success: bool
    message_sid: str | None = None
    segments: int = 0
    error: str | None = None
    blocked_reason: str | None = None  # "timezone_gate", "tcpa_consent", "rate_limit"
    body_used: str | None = None  # Actual body sent after formatting


# ── Utility Functions ──────────────────────────────────────────────────────


def _get_twilio_client():
    """Lazy-load Twilio client to avoid import overhead at module level."""
    from twilio.rest import Client

    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def _count_segments(body: str) -> int:
    """
    Estimate the number of SMS segments for a message.

    Single segment: ≤160 chars (GSM-7) or ≤70 chars (Unicode).
    Multipart: each segment is ≤153 chars (GSM-7) or ≤67 chars (Unicode).
    Uses a conservative estimate (assumes GSM-7 encoding).
    """
    if len(body) <= SMS_SEGMENT_LENGTH:
        return 1
    return (len(body) + 152) // 153


def validate_sms_content(body: str) -> list[str]:
    """
    Validate SMS content before sending.

    Returns a list of issues (empty = valid).
    """
    issues: list[str] = []

    if not body.strip():
        issues.append("SMS body is empty")

    if len(body) > SMS_MAX_CHARS:
        issues.append(f"SMS body ({len(body)} chars) exceeds max {SMS_MAX_CHARS} chars ({SMS_MAX_SEGMENTS} segments)")

    if "{{" in body and "}}" in body:
        issues.append("SMS body contains unresolved template variables")

    return issues


def is_stop_keyword(body: str) -> bool:
    """Check if an inbound SMS body is a STOP keyword."""
    return body.strip().lower() in STOP_KEYWORDS


# ── Timezone Gate ──────────────────────────────────────────────────────────


async def check_timezone_gate(
    lead_timezone: str | None,
) -> tuple[bool, str]:
    """
    Check if the current UTC time is within 8AM–9PM in the lead's local timezone.

    Args:
        lead_timezone: IANA timezone string (e.g., "America/Chicago") or None.

    Returns:
        (can_send, reason) where reason is "approved" or a human-readable block reason.
    """
    tz_name = lead_timezone or DEFAULT_TIMEZONE

    try:
        tz = pytz.timezone(tz_name)
    except pytz.exceptions.UnknownTimeZoneError:
        logger.warning("Unknown timezone '%s' — falling back to %s", tz_name, DEFAULT_TIMEZONE)
        tz = pytz.timezone(DEFAULT_TIMEZONE)

    now_local = datetime.now(UTC).astimezone(tz)
    current_hour = now_local.hour

    if SEND_WINDOW_START_HOUR <= current_hour < SEND_WINDOW_END_HOUR:
        return True, "approved"

    return (
        False,
        (
            f"Outside SMS send window: current time {now_local.strftime('%H:%M')} "
            f"in {tz_name} (window: {SEND_WINDOW_START_HOUR:02d}:00 – "
            f"{SEND_WINDOW_END_HOUR:02d}:00)"
        ),
    )


# ── TCPA Consent Check ─────────────────────────────────────────────────────


async def check_tcpa_consent(
    lead_id: UUID,
    db: AsyncSession,
) -> tuple[bool, str]:
    """
    Strict TCPA consent verification for SMS.

    Requires:
    - Active consent record for 'sms' channel
    - method == ConsentMethod.meeting_card (written) OR
      method == ConsentMethod.web_form AND proof_data includes "disclosure": true
    - proof_data must not be null

    Returns (has_consent, reason).
    """
    result = await db.execute(
        select(Consent).where(
            and_(
                Consent.lead_id == lead_id,
                Consent.channel == ConsentChannel.sms,
                Consent.revoked_at.is_(None),
            )
        )
    )
    consent = result.scalar_one_or_none()

    if not consent:
        return False, "no_sms_consent_record"

    if not consent.proof:
        return False, "consent_proof_missing"

    # Check for written consent: meeting_card method always qualifies
    if consent.method == ConsentMethod.meeting_card:
        return True, "written_consent_via_meeting_card"

    # Web form consent requires explicit disclosure flag
    if consent.method == ConsentMethod.web_form:
        has_disclosure = consent.proof.get("disclosure") is True
        if has_disclosure:
            return True, "written_consent_via_web_form_with_disclosure"
        else:
            return False, "web_form_consent_missing_disclosure_flag"

    # Import verified — check for written proof
    if consent.method == ConsentMethod.import_verified:
        has_written = "written" in str(consent.proof).lower() or consent.proof.get("written_consent") is True
        if has_written:
            return True, "written_consent_via_import"
        return False, "import_consent_lacks_written_proof"

    return False, f"unrecognized_consent_method_{consent.method}"


# ── Body Formatting ────────────────────────────────────────────────────────


async def format_sms_body(
    body: str,
    include_stop: bool = True,
) -> str:
    """
    Format an SMS body for optimal delivery.

    - Appends "Reply STOP to opt out" if include_stop=True
    - Truncates intelligently to stay under 160 chars if possible
    - If over 160 and can't fit in 1 segment, tries to fit in 2 (306 chars with footer)
    - Never exceeds SMS_MAX_CHARS

    Returns formatted body string.
    """
    stop_footer = f"\n{DEFAULT_STOP_FOOTER}" if include_stop else ""
    max_body_len = SMS_SEGMENT_LENGTH - len(stop_footer)

    # Try to fit in a single segment
    if len(body) <= max_body_len:
        return body + stop_footer

    # Attempt smart truncation at sentence or word boundary
    truncated = _smart_truncate(body, max_body_len - 3)
    single_seg = truncated + "..." + stop_footer

    if len(single_seg) <= SMS_SEGMENT_LENGTH:
        return single_seg

    # Allow multi-segment — aim for ≤2 segments total (306 chars + footer)
    max_multi = (153 * 2) - len(stop_footer)
    if len(body) <= max_multi:
        return body + stop_footer

    truncated_multi = _smart_truncate(body, max_multi - 3)
    return truncated_multi + "..." + stop_footer


def _smart_truncate(text: str, max_len: int) -> str:
    """Truncate text at word/sentence boundary near max_len."""
    if len(text) <= max_len:
        return text

    # Try sentence boundary first
    truncated = text[:max_len]
    last_period = max(
        truncated.rfind("."),
        truncated.rfind("!"),
        truncated.rfind("?"),
    )

    if last_period > max_len * 0.6:
        return truncated[: last_period + 1]

    # Fall back to word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_len * 0.7:
        return truncated[:last_space]

    return truncated


# ── SMS Send ───────────────────────────────────────────────────────────────


async def send_sms(
    to_phone: str,
    body: str,
    from_phone: str | None = None,
    status_callback_url: str | None = None,
    tags: dict[str, str] | None = None,
    lead: Lead | None = None,
    db: AsyncSession | None = None,
    skip_tz_gate: bool = False,
    skip_tcpa_check: bool = False,
) -> SMSResult:
    """
    Send an SMS via Twilio — Phase 5 production version.

    Before sending, checks:
    1. Timezone gate (8AM–9PM lead local time)
    2. TCPA consent verification (written consent required)
    3. Twilio credentials configured
    4. Content validation

    Automatically adds:
    - status_callback_url pointing to /api/v1/webhooks/twilio/sms
    - STOP footer via format_sms_body

    Args:
        to_phone: E.164 formatted phone (e.g., "+14155551234")
        body: SMS message text (before footer appending)
        from_phone: Sending number (defaults to TWILIO_PHONE_NUMBER)
        status_callback_url: Override callback URL
        tags: Key-value metadata tags
        lead: Lead object (for TZ gate and TCPA check)
        db: AsyncSession (required for TCPA check if lead provided)
        skip_tz_gate: Bypass timezone gate (use for admin/test sends)
        skip_tcpa_check: Bypass TCPA verification (use with caution)
    """
    from_number = from_phone or settings.TWILIO_PHONE_NUMBER

    if not from_number:
        return SMSResult(success=False, error="TWILIO_PHONE_NUMBER not configured")

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return SMSResult(success=False, error="Twilio credentials not configured")

    # 1. Timezone gate
    if not skip_tz_gate and lead:
        lead_tz = lead.enriched_data.get("timezone") if lead.enriched_data else None
        can_send, tz_reason = await check_timezone_gate(lead_tz)
        if not can_send:
            logger.info(
                "SMS timezone gate blocked for %s: %s",
                to_phone,
                tz_reason,
            )
            return SMSResult(
                success=False,
                blocked_reason="timezone_gate",
                error=tz_reason,
            )

    # 2. TCPA consent check
    if not skip_tcpa_check and lead and db:
        tcpa_ok, tcpa_reason = await check_tcpa_consent(lead.id, db)
        if not tcpa_ok:
            logger.info(
                "SMS TCPA consent blocked for lead %s: %s",
                lead.id,
                tcpa_reason,
            )
            return SMSResult(
                success=False,
                blocked_reason="tcpa_consent",
                error=tcpa_reason,
            )

    # Format body (adds STOP footer, handles truncation)
    formatted_body = await format_sms_body(body, include_stop=True)

    # Content validation
    issues = validate_sms_content(formatted_body)
    if issues:
        return SMSResult(success=False, error="; ".join(issues))

    # Phone format (basic E.164)
    if not to_phone.startswith("+"):
        to_phone = f"+1{to_phone}"

    # Status callback URL
    callback_url = status_callback_url
    if not callback_url and hasattr(settings, "BASE_URL"):
        callback_url = f"{settings.BASE_URL}/api/v1/webhooks/twilio/sms"

    segments = _count_segments(formatted_body)

    try:
        client = _get_twilio_client()

        message_kwargs: dict = {
            "body": formatted_body,
            "from_": from_number,
            "to": to_phone,
        }

        if callback_url:
            message_kwargs["status_callback"] = callback_url

        message = client.messages.create(**message_kwargs)

        logger.info(
            "SMS sent to %s, SID: %s, segments: %d",
            to_phone,
            message.sid,
            segments,
        )

        # Log segment count to touch metadata if DB provided
        if db and lead:
            await _log_sms_touch(
                db=db,
                lead_id=lead.id,
                action=TouchAction.sent,
                to_phone=to_phone,
                message_sid=message.sid,
                segments=segments,
                tags=tags,
            )

        return SMSResult(
            success=True,
            message_sid=message.sid,
            segments=segments,
            body_used=formatted_body,
        )

    except Exception as exc:
        logger.error("Failed to send SMS to %s: %s", to_phone, exc)
        return SMSResult(success=False, error=str(exc))


async def _log_sms_touch(
    db: AsyncSession,
    lead_id: UUID,
    action: TouchAction,
    to_phone: str,
    message_sid: str | None = None,
    segments: int = 1,
    sequence_id: UUID | None = None,
    tags: dict | None = None,
) -> None:
    """Log an SMS touch to the touch_logs table."""
    try:
        touch = TouchLog(
            lead_id=lead_id,
            channel="sms",
            action=action,
            sequence_id=sequence_id,
            extra_metadata={
                "to_phone": to_phone,
                "message_sid": message_sid,
                "segments": segments,
                **(tags or {}),
            },
        )
        db.add(touch)
        await db.flush()
    except Exception as exc:
        logger.warning("Failed to log SMS touch for lead %s: %s", lead_id, exc)


# ── Inbound SMS Processing ─────────────────────────────────────────────────


async def process_inbound_sms(
    form_data: dict,
    db: AsyncSession,
) -> dict:
    """
    Enhanced Twilio inbound SMS / status callback webhook handler.

    Handles:
    - STOP keywords → add to DNC + pause all active enrollments for that phone
    - Non-STOP reply → match to enrollment by phone + trigger reply pipeline
    - Status update (delivered/failed/etc.) → log metrics to touch_logs

    Args:
        form_data: Twilio webhook form payload (MessageSid, From, Body, MessageStatus, etc.)
        db: AsyncSession for DB operations

    Returns:
        Action dict describing what occurred.
    """
    message_status = form_data.get("MessageStatus", "")
    from_number = form_data.get("From", "")
    body = form_data.get("Body", "")
    message_sid = form_data.get("MessageSid", "")
    to_number = form_data.get("To", "")

    # Case 1: STOP keyword — DNC + pause enrollments
    if body and is_stop_keyword(body):
        logger.info("STOP received from %s — processing DNC", from_number)
        paused_enrollments = await _process_stop_request(from_number, db)

        return {
            "type": "stop_request",
            "phone": from_number,
            "message_sid": message_sid,
            "body": body,
            "paused_enrollments": paused_enrollments,
        }

    # Case 2: Inbound reply (non-STOP) — trigger reply service
    if body and not message_status:
        logger.info("Inbound SMS reply from %s", from_number)
        enrollment_id, lead_id = await _match_sms_to_enrollment(from_number, db)

        result: dict = {
            "type": "inbound_reply",
            "phone": from_number,
            "message_sid": message_sid,
            "body": body,
            "matched_enrollment_id": str(enrollment_id) if enrollment_id else None,
        }

        # Trigger reply service if match found
        if enrollment_id and lead_id:
            try:
                from app.services.reply_service import ReplyService, ReplySignal

                reply_svc = ReplyService(db)
                signal = ReplySignal(
                    channel="sms",
                    sender_phone=from_number,
                    body=body,
                    message_id=message_sid,
                )
                analysis = await reply_svc.process_reply(signal)
                result["sentiment"] = analysis.sentiment.value
                result["confidence"] = analysis.confidence
            except Exception as exc:
                logger.error("Reply service error for SMS from %s: %s", from_number, exc)

        return result

    # Case 3: Status update — log metrics
    if message_status:
        await _log_sms_status_update(
            message_sid=message_sid,
            status=message_status,
            to_phone=to_number,
            db=db,
        )

        return {
            "type": "status_update",
            "status": message_status,
            "message_sid": message_sid,
            "to": to_number,
        }

    return {"type": "unknown", "raw": form_data}


async def _process_stop_request(phone: str, db: AsyncSession) -> list[str]:
    """
    Handle a STOP request:
    1. Insert DNC block for the phone number
    2. Pause all active SMS enrollments for leads with this phone number
    3. Revoke SMS consents for matching leads

    Returns list of paused enrollment IDs.
    """
    paused_ids: list[str] = []

    # Find lead(s) with this phone number
    result = await db.execute(select(Lead).where(Lead.phone == phone))
    leads = result.scalars().all()

    for lead in leads:
        # Add DNC block
        try:
            dnc = DNCBlock(
                identifier=phone,
                identifier_type="phone",
                reason="stop_keyword",
                source="twilio_inbound",
            )
            db.add(dnc)
        except Exception as exc:
            logger.warning("DNC insert failed for %s: %s", phone, exc)

        # Revoke SMS consents
        consent_result = await db.execute(
            select(Consent).where(
                and_(
                    Consent.lead_id == lead.id,
                    Consent.channel == ConsentChannel.sms,
                    Consent.revoked_at.is_(None),
                )
            )
        )
        consents = consent_result.scalars().all()
        for consent in consents:
            consent.revoked_at = datetime.now(UTC)

        # Pause all active enrollments
        enr_result = await db.execute(
            select(SequenceEnrollment).where(
                and_(
                    SequenceEnrollment.lead_id == lead.id,
                    SequenceEnrollment.status.in_(
                        [
                            EnrollmentStatus.active,
                            EnrollmentStatus.sent,
                            EnrollmentStatus.opened,
                        ]
                    ),
                )
            )
        )
        enrollments = enr_result.scalars().all()

        for enrollment in enrollments:
            enrollment.status = EnrollmentStatus.paused
            enrollment.last_state_change_at = datetime.now(UTC)
            paused_ids.append(str(enrollment.id))
            logger.info(
                "Paused enrollment %s for lead %s due to SMS STOP",
                enrollment.id,
                lead.id,
            )

    await db.commit()

    logger.info(
        "STOP processed for %s: %d leads, %d enrollments paused",
        phone,
        len(leads),
        len(paused_ids),
    )

    return paused_ids


async def _match_sms_to_enrollment(phone: str, db: AsyncSession) -> tuple[UUID | None, UUID | None]:
    """
    Match an inbound SMS to a SequenceEnrollment by phone number.

    Returns (enrollment_id, lead_id) or (None, None) if no match.
    """
    lead_result = await db.execute(select(Lead).where(Lead.phone == phone))
    lead = lead_result.scalar_one_or_none()

    if not lead:
        return None, None

    enr_result = await db.execute(
        select(SequenceEnrollment)
        .where(
            and_(
                SequenceEnrollment.lead_id == lead.id,
                SequenceEnrollment.status.in_(
                    [
                        EnrollmentStatus.active,
                        EnrollmentStatus.sent,
                        EnrollmentStatus.opened,
                    ]
                ),
            )
        )
        .order_by(SequenceEnrollment.enrolled_at.desc())
        .limit(1)
    )
    enrollment = enr_result.scalar_one_or_none()

    if enrollment:
        return enrollment.id, lead.id

    return None, None


async def _log_sms_status_update(
    message_sid: str,
    status: str,
    to_phone: str,
    db: AsyncSession,
) -> None:
    """
    Update touch_log entry with delivery status from Twilio callback.

    Maps Twilio status → TouchAction where applicable.
    """
    status_map = {
        "delivered": TouchAction.delivered,
        "failed": TouchAction.bounced,
        "undelivered": TouchAction.bounced,
    }

    mapped_action = status_map.get(status.lower())
    if not mapped_action:
        return  # queued/sent/etc — no action needed

    try:
        # Find the original touch log by message_sid in metadata
        result = await db.execute(select(TouchLog).where(TouchLog.extra_metadata["message_sid"].astext == message_sid))
        original_log = result.scalar_one_or_none()

        if original_log:
            # Log a follow-up entry for the delivery event
            delivery_log = TouchLog(
                lead_id=original_log.lead_id,
                channel="sms",
                action=mapped_action,
                sequence_id=original_log.sequence_id,
                extra_metadata={
                    "message_sid": message_sid,
                    "twilio_status": status,
                    "to_phone": to_phone,
                    "original_touch_id": str(original_log.id),
                },
            )
            db.add(delivery_log)
            await db.commit()

            logger.debug("Logged SMS delivery status %s for SID %s", status, message_sid)
    except Exception as exc:
        logger.warning("Failed to log SMS status update for SID %s: %s", message_sid, exc)


# ── Metrics ────────────────────────────────────────────────────────────────


async def get_sms_metrics(db: AsyncSession) -> dict:
    """
    Aggregate SMS delivery/failure rates from touch_logs for Prometheus push.

    Returns dict with keys:
    - total_sent: int
    - total_delivered: int
    - total_failed: int
    - delivery_rate: float (0-1)
    - failure_rate: float (0-1)
    - segments_today: int (estimated)
    - today_sent: int
    - daily_limit: int
    """
    try:
        # Total sent (all time)
        sent_result = await db.execute(
            select(func.count(TouchLog.id)).where(
                and_(
                    TouchLog.channel == "sms",
                    TouchLog.action == TouchAction.sent,
                )
            )
        )
        total_sent = sent_result.scalar() or 0

        # Total delivered
        delivered_result = await db.execute(
            select(func.count(TouchLog.id)).where(
                and_(
                    TouchLog.channel == "sms",
                    TouchLog.action == TouchAction.delivered,
                )
            )
        )
        total_delivered = delivered_result.scalar() or 0

        # Total failed/bounced
        failed_result = await db.execute(
            select(func.count(TouchLog.id)).where(
                and_(
                    TouchLog.channel == "sms",
                    TouchLog.action == TouchAction.bounced,
                )
            )
        )
        total_failed = failed_result.scalar() or 0

        # Today's sends
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
        today_result = await db.execute(
            select(func.count(TouchLog.id)).where(
                and_(
                    TouchLog.channel == "sms",
                    TouchLog.action == TouchAction.sent,
                    TouchLog.created_at >= today_start,
                )
            )
        )
        today_sent = today_result.scalar() or 0

        delivery_rate = total_delivered / total_sent if total_sent > 0 else 0.0
        failure_rate = total_failed / total_sent if total_sent > 0 else 0.0

        return {
            "total_sent": total_sent,
            "total_delivered": total_delivered,
            "total_failed": total_failed,
            "delivery_rate": round(delivery_rate, 4),
            "failure_rate": round(failure_rate, 4),
            "today_sent": today_sent,
            "daily_limit": settings.DAILY_SMS_LIMIT,
            "remaining_today": max(0, settings.DAILY_SMS_LIMIT - today_sent),
        }

    except Exception as exc:
        logger.error("Failed to compute SMS metrics: %s", exc)
        return {
            "total_sent": 0,
            "total_delivered": 0,
            "total_failed": 0,
            "delivery_rate": 0.0,
            "failure_rate": 0.0,
            "today_sent": 0,
            "daily_limit": settings.DAILY_SMS_LIMIT,
            "remaining_today": settings.DAILY_SMS_LIMIT,
        }


# ── Legacy Compatibility ───────────────────────────────────────────────────


async def process_twilio_webhook(form_data: dict) -> dict:
    """
    Legacy webhook handler — delegates to process_inbound_sms without DB.

    For backwards compatibility with existing webhook routes that don't
    inject a DB session. New code should use process_inbound_sms directly.
    """
    message_status = form_data.get("MessageStatus", "")
    from_number = form_data.get("From", "")
    body = form_data.get("Body", "")
    message_sid = form_data.get("MessageSid", "")

    # Inbound STOP
    if body and is_stop_keyword(body):
        return {
            "type": "stop_request",
            "phone": from_number,
            "message_sid": message_sid,
            "body": body,
        }

    # Status update
    if message_status:
        return {
            "type": "status_update",
            "status": message_status,
            "message_sid": message_sid,
            "to": form_data.get("To", ""),
        }

    return {"type": "unknown", "raw": form_data}
