"""
Twilio SMS sending service.

Handles:
- 10DLC-compliant SMS delivery
- STOP keyword auto-DNC processing
- Message status callback handling
- Per-lead rate limiting via compliance gate
- SMS content length validation (160 char segments)
"""

import logging
from dataclasses import dataclass

from app.config import settings

logger = logging.getLogger(__name__)


# SMS segment limits
SMS_SEGMENT_LENGTH = 160
SMS_MAX_SEGMENTS = 4  # Keep messages concise for B2B
SMS_MAX_CHARS = SMS_SEGMENT_LENGTH * SMS_MAX_SEGMENTS

# STOP keywords that trigger auto-DNC (Twilio handles these server-side,
# but we also check in our webhook handler for double safety)
STOP_KEYWORDS = {"stop", "unsubscribe", "cancel", "end", "quit", "stopall"}


@dataclass
class SMSResult:
    success: bool
    message_sid: str | None = None
    segments: int = 0
    error: str | None = None


def _get_twilio_client():
    """Lazy-load Twilio client."""
    from twilio.rest import Client

    return Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)


def _count_segments(body: str) -> int:
    """Estimate the number of SMS segments."""
    if len(body) <= 160:
        return 1
    # For multipart: headers reduce each segment to ~153 chars
    return (len(body) + 152) // 153


def validate_sms_content(body: str) -> list[str]:
    """
    Validate SMS content before sending.
    Returns list of issues (empty = valid).
    """
    issues = []
    if not body.strip():
        issues.append("SMS body is empty")
    if len(body) > SMS_MAX_CHARS:
        issues.append(
            f"SMS body ({len(body)} chars) exceeds max {SMS_MAX_CHARS} chars "
            f"({SMS_MAX_SEGMENTS} segments)"
        )
    # Check for accidental template variables
    if "{{" in body and "}}" in body:
        issues.append("SMS body contains unresolved template variables")
    return issues


async def send_sms(
    to_phone: str,
    body: str,
    from_phone: str | None = None,
    status_callback_url: str | None = None,
    tags: dict[str, str] | None = None,
) -> SMSResult:
    """
    Send an SMS via Twilio.

    Args:
        to_phone: E.164 formatted phone number (e.g., "+14155551234")
        body: SMS message text
        from_phone: Sending phone number (defaults to TWILIO_PHONE_NUMBER)
        status_callback_url: URL for delivery status webhooks
        tags: Key-value metadata tags
    """
    from_number = from_phone or settings.TWILIO_PHONE_NUMBER
    if not from_number:
        return SMSResult(success=False, error="TWILIO_PHONE_NUMBER not configured")

    if not settings.TWILIO_ACCOUNT_SID or not settings.TWILIO_AUTH_TOKEN:
        return SMSResult(success=False, error="Twilio credentials not configured")

    # Validate content
    issues = validate_sms_content(body)
    if issues:
        return SMSResult(success=False, error="; ".join(issues))

    # Validate phone format (basic E.164 check)
    if not to_phone.startswith("+"):
        to_phone = f"+1{to_phone}"  # Assume US if no country code

    try:
        client = _get_twilio_client()

        message_kwargs = {
            "body": body,
            "from_": from_number,
            "to": to_phone,
        }

        if status_callback_url:
            message_kwargs["status_callback"] = status_callback_url

        message = client.messages.create(**message_kwargs)

        segments = _count_segments(body)
        logger.info(
            "SMS sent to %s, SID: %s, segments: %d",
            to_phone, message.sid, segments,
        )
        return SMSResult(
            success=True,
            message_sid=message.sid,
            segments=segments,
        )

    except Exception as exc:
        logger.error("Failed to send SMS to %s: %s", to_phone, exc)
        return SMSResult(success=False, error=str(exc))


def is_stop_keyword(body: str) -> bool:
    """Check if an inbound SMS body is a STOP keyword."""
    return body.strip().lower() in STOP_KEYWORDS


async def process_twilio_webhook(form_data: dict) -> dict:
    """
    Process Twilio status callback or inbound SMS webhook.

    Returns action dict describing what happened.
    """
    message_status = form_data.get("MessageStatus", "")
    from_number = form_data.get("From", "")
    body = form_data.get("Body", "")
    message_sid = form_data.get("MessageSid", "")

    # Inbound message (potential STOP)
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
            "status": message_status,  # queued, sent, delivered, undelivered, failed
            "message_sid": message_sid,
            "to": form_data.get("To", ""),
        }

    return {"type": "unknown", "raw": form_data}
