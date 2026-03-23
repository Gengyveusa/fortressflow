"""
Webhook endpoints — Phase 5 enhanced.

Handles:
- HubSpot contact property change webhooks (Phase 2, unchanged)
- Twilio SMS status callbacks and inbound messages
- Email reply webhooks (Parsio, SES inbound, generic)
- SES event notifications (bounce, complaint, delivery, open)
"""

import hashlib
import hmac
import json
import logging
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import sentry_sdk
from fastapi import APIRouter, Depends, Header, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.utils.sanitize import sanitize_error
from app.models.consent import Consent
from app.models.dnc import DNCBlock
from app.models.lead import Lead
from app.models.sequence import EnrollmentStatus, SequenceEnrollment
from app.models.touch_log import TouchAction, TouchLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])


# ── HubSpot (Phase 2, unchanged) ──────────────────────────────────────


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


# ── Twilio SMS Webhooks (Phase 5) ────────────────────────────────────


def _validate_twilio_signature(request_url: str, params: dict, signature: str) -> bool:
    """
    Validate Twilio webhook signature using HMAC-SHA1.

    https://www.twilio.com/docs/usage/webhooks/webhooks-security#validating-signatures-from-twilio
    """
    if not settings.TWILIO_AUTH_TOKEN:
        logger.warning("TWILIO_AUTH_TOKEN not configured — skipping signature validation")
        return True

    try:
        from twilio.request_validator import RequestValidator

        validator = RequestValidator(settings.TWILIO_AUTH_TOKEN)
        return validator.validate(request_url, params, signature)
    except ImportError:
        # Fallback manual validation if twilio library unavailable
        sorted_params = "".join(
            f"{k}{v}" for k, v in sorted(params.items())
        )
        s = request_url + sorted_params
        mac = hmac.new(
            settings.TWILIO_AUTH_TOKEN.encode("utf-8"),
            s.encode("utf-8"),
            hashlib.sha1,
        ).digest()
        import base64

        computed = base64.b64encode(mac).decode("utf-8")
        return hmac.compare_digest(computed, signature)
    except Exception as exc:
        logger.warning("Twilio signature validation error: %s", exc)
        return False


@router.post("/twilio/sms", status_code=status.HTTP_200_OK)
async def twilio_sms_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_twilio_signature: str | None = Header(None, alias="X-Twilio-Signature"),
) -> PlainTextResponse:
    """
    Handle Twilio SMS webhooks.

    Receives both:
    - Inbound messages (From, Body) — handle STOP → DNC, or reply → reply pipeline
    - Status callbacks (MessageStatus: delivered/failed/undelivered) — log metrics

    Always returns 200 with TwiML (empty for status callbacks, acknowledgement for inbound).
    Returns 200 even on processing errors to prevent Twilio retries for non-transient issues.
    """
    try:
        form_data = dict(await request.form())
        raw_body = await request.body()
    except Exception as exc:
        logger.error("Twilio SMS webhook: failed to parse form data: %s", exc)
        sentry_sdk.capture_exception(exc)
        return PlainTextResponse(
            content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
            media_type="application/xml",
        )

    logger.debug(
        "Twilio SMS webhook received: MessageSid=%s MessageStatus=%s From=%s",
        form_data.get("MessageSid"),
        form_data.get("MessageStatus"),
        form_data.get("From"),
    )

    # Validate Twilio signature in production
    if settings.TWILIO_AUTH_TOKEN and x_twilio_signature:
        url = str(request.url)
        if not _validate_twilio_signature(url, form_data, x_twilio_signature):
            logger.warning(
                "Twilio SMS webhook: invalid signature from %s",
                request.client.host if request.client else "unknown",
            )
            # Return 200 with empty TwiML to prevent retry loops
            return PlainTextResponse(
                content='<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
                media_type="application/xml",
                status_code=status.HTTP_200_OK,
            )

    # Log raw event to touch_logs asynchronously (best-effort)
    try:
        message_sid = form_data.get("MessageSid", "")
        from_number = form_data.get("From", "")
        body_text = form_data.get("Body", "")
        message_status = form_data.get("MessageStatus", "")

        # Look up lead by phone number for logging
        lead_id_for_log = None
        if from_number:
            lead_result = await db.execute(
                select(Lead).where(Lead.phone == from_number).limit(1)
            )
            lead_for_log = lead_result.scalar_one_or_none()
            if lead_for_log:
                lead_id_for_log = lead_for_log.id

        # Determine action for touch log
        action_map: dict[str, TouchAction] = {
            "delivered": TouchAction.delivered,
            "undelivered": TouchAction.bounced,
            "failed": TouchAction.bounced,
            "sent": TouchAction.sent,
        }

        if message_status and lead_id_for_log:
            log_action = action_map.get(message_status.lower())
            if log_action:
                touch = TouchLog(
                    lead_id=lead_id_for_log,
                    channel="sms",
                    action=log_action,
                    extra_metadata={
                        "message_sid": message_sid,
                        "twilio_status": message_status,
                        "source": "twilio_status_callback",
                    },
                )
                db.add(touch)
                logger.info(
                    "Twilio status callback: %s for lead %s (sid=%s)",
                    message_status,
                    lead_id_for_log,
                    message_sid,
                )
    except Exception as exc:
        logger.warning("Twilio SMS webhook: touch log failed: %s", exc)
        sentry_sdk.capture_exception(exc)

    # Process inbound message via SMS service
    twiml_response = '<?xml version="1.0" encoding="UTF-8"?><Response></Response>'
    try:
        from app.services.sms_service import process_inbound_sms

        result = await process_inbound_sms(dict(form_data), db)
        await db.commit()

        event_type = result.get("type", "unknown")
        logger.info(
            "Twilio SMS webhook: processed event_type=%s from=%s sid=%s",
            event_type,
            form_data.get("From"),
            form_data.get("MessageSid"),
        )

        # For inbound replies (non-STOP), queue full reply processing task
        if event_type == "inbound_reply":
            from app.workers.tasks import process_reply_full_task

            body_snippet = form_data.get("Body", "")[:500]
            process_reply_full_task.delay(
                {
                    "channel": "sms",
                    "body": body_snippet,
                    "sender_phone": form_data.get("From", ""),
                    "message_id": form_data.get("MessageSid", ""),
                    "received_at": datetime.now(UTC).isoformat(),
                }
            )

        # Acknowledge STOP with TwiML message
        if event_type == "stop_request":
            twiml_response = (
                '<?xml version="1.0" encoding="UTF-8"?>'
                "<Response>"
                "<Message>You have been unsubscribed. Reply START to re-subscribe.</Message>"
                "</Response>"
            )

    except Exception as exc:
        logger.error("Twilio SMS webhook: processing error: %s", exc, exc_info=True)
        sentry_sdk.capture_exception(exc)
        # Return 200 so Twilio doesn't retry
        try:
            await db.rollback()
        except Exception:
            pass

    return PlainTextResponse(
        content=twiml_response,
        media_type="application/xml",
        status_code=status.HTTP_200_OK,
    )


# ── Email Reply Webhooks (Phase 5) ────────────────────────────────────


@router.post("/email/reply", status_code=status.HTTP_200_OK)
async def email_reply_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_webhook_secret: str | None = Header(None, alias="X-Webhook-Secret"),
) -> dict:
    """
    Handle inbound email reply webhooks (Parsio or generic email parser).

    Validates the X-Webhook-Secret header against settings.REPLY_WEBHOOK_SECRET,
    then parses the payload into a ReplySignal and processes through the full
    reply pipeline (sentiment analysis, AI analysis, FSM transition).

    Returns 200 even on processing errors to prevent webhook provider retries.
    """
    # Validate webhook secret
    if settings.REPLY_WEBHOOK_SECRET:
        if not x_webhook_secret:
            logger.warning("Email reply webhook: missing X-Webhook-Secret header")
            # Still return 200 to avoid triggering retries, but log for investigation
            return {"status": "rejected", "reason": "missing_secret"}

        if not secrets.compare_digest(x_webhook_secret, settings.REPLY_WEBHOOK_SECRET):
            logger.warning("Email reply webhook: invalid X-Webhook-Secret")
            return {"status": "rejected", "reason": "invalid_secret"}

    try:
        payload: dict[str, Any] = await request.json()
    except Exception as exc:
        logger.warning("Email reply webhook: invalid JSON body: %s", exc)
        return {"status": "error", "reason": "invalid_json"}

    logger.debug(
        "Email reply webhook received: from=%s subject=%s",
        payload.get("from") or payload.get("sender"),
        payload.get("subject"),
    )

    try:
        from app.services.reply_service import ReplyService, ReplySignal

        # Build ReplySignal from Parsio / generic payload
        # Parsio fields: from_email, subject, body_text, headers, message_id
        # Generic fields: from, subject, body, thread_id
        sender_email = (
            payload.get("from_email")
            or payload.get("from")
            or payload.get("sender_email")
            or ""
        )
        subject = payload.get("subject", "")
        body = (
            payload.get("body_text")
            or payload.get("body")
            or payload.get("text")
            or payload.get("html_body")
            or ""
        )
        thread_id = (
            payload.get("thread_id")
            or payload.get("in_reply_to")
            or payload.get("references", "").split()[-1]
            if payload.get("references")
            else None
        )
        message_id = payload.get("message_id") or payload.get("msg_id")
        raw_headers = payload.get("headers", {})
        if isinstance(raw_headers, str):
            # Some parsers send headers as raw string; skip parsing
            raw_headers = {}

        signal = ReplySignal(
            channel="email",
            body=body,
            sender_email=sender_email,
            subject=subject,
            thread_id=thread_id,
            message_id=message_id,
            raw_headers=raw_headers,
            received_at=datetime.now(UTC),
        )

        # Queue full reply processing as a Celery task (non-blocking)
        from app.workers.tasks import process_reply_full_task

        process_reply_full_task.delay(
            {
                "channel": "email",
                "body": body,
                "sender_email": sender_email,
                "subject": subject,
                "thread_id": thread_id,
                "message_id": message_id,
                "raw_headers": raw_headers,
                "received_at": datetime.now(UTC).isoformat(),
            }
        )

        logger.info(
            "Email reply webhook: queued processing for from=%s subject=%s",
            sender_email,
            subject,
        )
        return {"status": "queued", "sender": sender_email, "subject": subject}

    except Exception as exc:
        logger.error("Email reply webhook: processing error: %s", exc, exc_info=True)
        sentry_sdk.capture_exception(exc)
        # Return 200 to prevent retries
        return {"status": "error", "reason": sanitize_error(exc)[:200]}


# ── SES Event Notifications (Phase 5) ────────────────────────────────


_SES_EVENT_ACTION_MAP: dict[str, TouchAction] = {
    "Bounce": TouchAction.bounced,
    "Complaint": TouchAction.complained,
    "Delivery": TouchAction.delivered,
    "Open": TouchAction.opened,
    "Send": TouchAction.sent,
}


@router.post("/ses/events", status_code=status.HTTP_200_OK)
async def ses_events_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_amz_sns_message_type: str | None = Header(None, alias="X-Amz-Sns-Message-Type"),
) -> dict:
    """
    Handle AWS SES event notifications delivered via SNS.

    Handles:
    - SubscriptionConfirmation: fetch SubscribeURL to confirm the SNS subscription
    - Notification: parse the inner SES event (Bounce/Complaint/Delivery/Open)
      and update enrollment FSM state + touch_logs

    Always returns 200 to prevent SNS retries on non-transient failures.
    """
    try:
        raw_body = await request.body()
        sns_payload: dict[str, Any] = json.loads(raw_body)
    except Exception as exc:
        logger.warning("SES events webhook: invalid JSON body: %s", exc)
        return {"status": "error", "reason": "invalid_json"}

    message_type = x_amz_sns_message_type or sns_payload.get("Type", "")
    logger.debug("SES events webhook: SNS message type=%s", message_type)

    # ── SNS Subscription Confirmation ─────────────────────────────────
    if message_type == "SubscriptionConfirmation":
        subscribe_url = sns_payload.get("SubscribeURL")
        if subscribe_url:
            try:
                import httpx

                async with httpx.AsyncClient(timeout=10) as client:
                    resp = await client.get(subscribe_url)
                    if resp.status_code == 200:
                        logger.info(
                            "SES events webhook: SNS subscription confirmed via %s",
                            subscribe_url,
                        )
                    else:
                        logger.warning(
                            "SES events webhook: SNS confirmation returned %d",
                            resp.status_code,
                        )
            except Exception as exc:
                logger.error(
                    "SES events webhook: SNS confirmation request failed: %s", exc
                )
                sentry_sdk.capture_exception(exc)
        return {"status": "subscription_confirmed"}

    # ── SNS Notification (SES event payload) ──────────────────────────
    if message_type != "Notification" and message_type != "":
        logger.debug("SES events webhook: unhandled SNS type=%s", message_type)
        return {"status": "ignored", "type": message_type}

    try:
        # Unwrap SNS Notification: the actual SES event JSON is in the Message field
        message_body = sns_payload.get("Message", "{}")
        if isinstance(message_body, str):
            ses_event: dict[str, Any] = json.loads(message_body)
        else:
            ses_event = message_body

        event_type = ses_event.get("eventType") or ses_event.get("notificationType", "")
        mail_obj = ses_event.get("mail", {})
        destination = mail_obj.get("destination", [])  # list of recipient emails
        message_id = mail_obj.get("messageId", "")
        timestamp_str = mail_obj.get("timestamp", "")
        headers_list = mail_obj.get("headers", [])

        # Extract custom headers we inject at send time
        custom_headers: dict[str, str] = {}
        for hdr in headers_list:
            name = hdr.get("name", "").lower()
            value = hdr.get("value", "")
            custom_headers[name] = value

        enrollment_id_str = custom_headers.get("x-fortressflow-enrollment-id")
        lead_id_str = custom_headers.get("x-fortressflow-lead-id")
        sequence_id_str = custom_headers.get("x-fortressflow-sequence-id")

        logger.info(
            "SES event: type=%s message_id=%s enrollment_id=%s",
            event_type,
            message_id,
            enrollment_id_str,
        )

        touch_action = _SES_EVENT_ACTION_MAP.get(event_type)

        # Log touch event for each destination
        for recipient_email in destination:
            try:
                # Resolve lead by email if not in custom headers
                lead_id_resolved = None
                if lead_id_str:
                    import uuid as _uuid

                    lead_id_resolved = _uuid.UUID(lead_id_str)
                else:
                    lr = await db.execute(
                        select(Lead).where(
                            func.lower(Lead.email) == recipient_email.lower()
                        )
                    )
                    lead_obj = lr.scalar_one_or_none()
                    if lead_obj:
                        lead_id_resolved = lead_obj.id

                if lead_id_resolved and touch_action:
                    import uuid as _uuid

                    touch = TouchLog(
                        lead_id=lead_id_resolved,
                        channel="email",
                        action=touch_action,
                        sequence_id=_uuid.UUID(sequence_id_str) if sequence_id_str else None,
                        extra_metadata={
                            "ses_message_id": message_id,
                            "ses_event_type": event_type,
                            "enrollment_id": enrollment_id_str,
                            "source": "ses_webhook",
                        },
                    )
                    db.add(touch)

                # Handle Bounce and Complaint → update enrollment FSM + DNC
                if event_type == "Bounce":
                    bounce_type = (
                        ses_event.get("bounce", {}).get("bounceType", "")
                    )
                    is_hard_bounce = bounce_type == "Permanent"

                    if lead_id_resolved:
                        await _handle_ses_bounce(
                            lead_id=lead_id_resolved,
                            enrollment_id_str=enrollment_id_str,
                            hard_bounce=is_hard_bounce,
                            db=db,
                        )

                elif event_type == "Complaint":
                    if lead_id_resolved:
                        await _handle_ses_complaint(
                            lead_id=lead_id_resolved,
                            enrollment_id_str=enrollment_id_str,
                            db=db,
                        )

                # Handle Open → transition enrollment to "opened"
                elif event_type == "Open":
                    if enrollment_id_str:
                        await _handle_ses_open(
                            enrollment_id_str=enrollment_id_str,
                            db=db,
                        )

            except Exception as inner_exc:
                logger.warning(
                    "SES events webhook: error processing recipient %s: %s",
                    recipient_email,
                    inner_exc,
                )
                sentry_sdk.capture_exception(inner_exc)

        await db.commit()
        logger.info(
            "SES events webhook: processed %s event for %d recipients",
            event_type,
            len(destination),
        )
        return {
            "status": "processed",
            "event_type": event_type,
            "recipients": len(destination),
        }

    except Exception as exc:
        logger.error("SES events webhook: fatal error: %s", exc, exc_info=True)
        sentry_sdk.capture_exception(exc)
        try:
            await db.rollback()
        except Exception:
            pass
        # Return 200 to prevent SNS retries
        return {"status": "error", "reason": sanitize_error(exc)[:200]}


# ── SES Event Helpers ─────────────────────────────────────────────────


async def _handle_ses_bounce(
    lead_id: Any,
    enrollment_id_str: str | None,
    hard_bounce: bool,
    db: AsyncSession,
) -> None:
    """Process SES bounce event.

    Hard bounce:
      - Add email to dnc_blocks with reason 'hard_bounce'
      - Update lead status to 'bounced' (via email_deliverable flag)
      - Pause ALL active sequence enrollments for the lead
      - Log for audit trail

    Soft bounce:
      - Increment soft bounce counter (tracked in lead.enriched_data)
      - After 3 soft bounces within 7 days, escalate to hard bounce treatment
    """
    import uuid as _uuid

    try:
        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalar_one_or_none()

        if hard_bounce:
            # ── Hard bounce: DNC + status update + pause all enrollments ──
            if lead:
                # Add to DNC list
                existing_dnc = await db.execute(
                    select(DNCBlock).where(
                        DNCBlock.identifier == lead.email,
                        DNCBlock.channel == "email",
                        DNCBlock.reason == "hard_bounce",
                    )
                )
                if existing_dnc.scalar_one_or_none() is None:
                    dnc = DNCBlock(
                        identifier=lead.email,
                        channel="email",
                        reason="hard_bounce",
                        blocked_at=datetime.now(UTC),
                        source="ses_webhook",
                    )
                    db.add(dnc)
                    logger.info("SES hard bounce: added %s to DNC (hard_bounce)", lead.email)

                # Mark lead email as undeliverable
                if hasattr(lead, "email_deliverable"):
                    lead.email_deliverable = False
                logger.info("SES hard bounce: marked lead %s as bounced", lead_id)

            # Pause ALL active enrollments for this lead
            enr_result = await db.execute(
                select(SequenceEnrollment).where(
                    SequenceEnrollment.lead_id == lead_id,
                    SequenceEnrollment.status.in_([
                        EnrollmentStatus.active,
                        EnrollmentStatus.pending,
                        EnrollmentStatus.sent,
                        EnrollmentStatus.opened,
                    ]),
                )
            )
            for enrollment in enr_result.scalars().all():
                enrollment.status = EnrollmentStatus.bounced
                enrollment.last_state_change_at = datetime.now(UTC)
                logger.info("SES hard bounce: enrollment %s → bounced", enrollment.id)

        else:
            # ── Soft bounce: track counter, escalate after 3 in 7 days ───
            if lead:
                # Count soft bounces in last 7 days from touch_logs
                seven_days_ago = datetime.now(UTC) - timedelta(days=7)
                count_result = await db.execute(
                    select(func.count(TouchLog.id)).where(
                        TouchLog.lead_id == lead_id,
                        TouchLog.channel == "email",
                        TouchLog.action == TouchAction.bounced,
                        TouchLog.created_at >= seven_days_ago,
                    )
                )
                soft_bounce_count = count_result.scalar_one()
                logger.info(
                    "SES soft bounce: lead %s has %d bounces in last 7 days",
                    lead_id,
                    soft_bounce_count,
                )

                # The current bounce is already logged in touch_logs by the caller,
                # so count includes it. Escalate at 3+.
                if soft_bounce_count >= 3:
                    logger.info(
                        "SES soft bounce: escalating lead %s to hard bounce (%d soft bounces in 7 days)",
                        lead_id,
                        soft_bounce_count,
                    )
                    await _handle_ses_bounce(
                        lead_id=lead_id,
                        enrollment_id_str=enrollment_id_str,
                        hard_bounce=True,
                        db=db,
                    )
                    return

            # Pause only the specific enrollment (if any) on soft bounce
            if enrollment_id_str:
                enr_result = await db.execute(
                    select(SequenceEnrollment).where(
                        SequenceEnrollment.id == _uuid.UUID(enrollment_id_str)
                    )
                )
                enrollment = enr_result.scalar_one_or_none()
                if enrollment and enrollment.status not in (
                    EnrollmentStatus.completed,
                    EnrollmentStatus.bounced,
                    EnrollmentStatus.unsubscribed,
                    EnrollmentStatus.failed,
                ):
                    enrollment.status = EnrollmentStatus.paused
                    enrollment.last_state_change_at = datetime.now(UTC)
                    logger.info("SES soft bounce: paused enrollment %s", enrollment_id_str)

    except Exception as exc:
        logger.warning("SES bounce handler error: %s", exc)
        raise


async def _handle_ses_complaint(
    lead_id: Any,
    enrollment_id_str: str | None,
    db: AsyncSession,
) -> None:
    """Process SES complaint (spam report).

    - Add email to dnc_blocks with reason 'spam_complaint'
    - Update lead status to 'unsubscribed'
    - Pause ALL active enrollments for the lead
    - Revoke consent records if any exist
    - Log for audit trail
    """
    try:
        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalar_one_or_none()

        if lead:
            # Add to DNC (idempotent — skip if already blocked for spam_complaint)
            existing_dnc = await db.execute(
                select(DNCBlock).where(
                    DNCBlock.identifier == lead.email,
                    DNCBlock.channel == "email",
                    DNCBlock.reason == "spam_complaint",
                )
            )
            if existing_dnc.scalar_one_or_none() is None:
                dnc = DNCBlock(
                    identifier=lead.email,
                    channel="email",
                    reason="spam_complaint",
                    blocked_at=datetime.now(UTC),
                    source="ses_webhook",
                )
                db.add(dnc)
                logger.info("SES complaint: added %s to DNC (spam_complaint)", lead.email)

            # Mark lead email as undeliverable (unsubscribed)
            if hasattr(lead, "email_deliverable"):
                lead.email_deliverable = False

            # Revoke all active email consents for this lead
            consent_result = await db.execute(
                select(Consent).where(
                    Consent.lead_id == lead_id,
                    Consent.channel == "email",
                    Consent.revoked_at.is_(None),
                )
            )
            now = datetime.now(UTC)
            for consent in consent_result.scalars().all():
                consent.revoked_at = now
                logger.info("SES complaint: revoked consent %s for lead %s", consent.id, lead_id)

        # Pause ALL active enrollments for this lead
        enr_result = await db.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.lead_id == lead_id,
                SequenceEnrollment.status.in_([
                    EnrollmentStatus.active,
                    EnrollmentStatus.pending,
                    EnrollmentStatus.sent,
                    EnrollmentStatus.opened,
                    EnrollmentStatus.paused,
                ]),
            )
        )
        for enrollment in enr_result.scalars().all():
            enrollment.status = EnrollmentStatus.unsubscribed
            enrollment.last_state_change_at = datetime.now(UTC)
            logger.info("SES complaint: enrollment %s → unsubscribed", enrollment.id)

    except Exception as exc:
        logger.warning("SES complaint handler error: %s", exc)
        raise


async def _handle_ses_open(
    enrollment_id_str: str,
    db: AsyncSession,
) -> None:
    """Process SES open event: transition enrollment to 'opened' if applicable."""
    import uuid as _uuid
    from app.services.state_machine import can_transition, EnrollmentState

    try:
        enr_result = await db.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.id == _uuid.UUID(enrollment_id_str)
            )
        )
        enrollment = enr_result.scalar_one_or_none()
        if not enrollment:
            return

        current = enrollment.status.value
        if can_transition(current, EnrollmentState.opened):
            enrollment.status = EnrollmentStatus.opened
            enrollment.last_state_change_at = datetime.now(UTC)
            logger.info(
                "SES open: enrollment %s → opened", enrollment_id_str
            )
    except Exception as exc:
        logger.warning("SES open handler error: %s", exc)
        raise
