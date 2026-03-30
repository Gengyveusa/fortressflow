"""
Amazon SES email sending service.

Handles:
- HTML + plain text email composition
- Tracking pixel injection
- One-click unsubscribe header (RFC 8058)
- Bounce/complaint webhook processing
- Per-lead rate limiting via compliance gate
"""

import logging
from dataclasses import dataclass
from typing import Any

from app.config import settings

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    success: bool
    message_id: str | None = None
    error: str | None = None


def _get_ses_client():
    """Lazy-load boto3 SES client."""
    import boto3

    return boto3.client(
        "ses",
        region_name=settings.AWS_REGION,
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
    )


def _inject_tracking_pixel(html: str, tracking_url: str) -> str:
    """Insert a 1x1 tracking pixel before </body>."""
    pixel = f'<img src="{tracking_url}" width="1" height="1" style="display:none;" alt="" />'
    if "</body>" in html.lower():
        idx = html.lower().rfind("</body>")
        return html[:idx] + pixel + html[idx:]
    return html + pixel


def _inject_unsubscribe_footer(html: str, unsubscribe_url: str) -> str:
    """Add unsubscribe link to the bottom of the email."""
    footer = f"""
    <div style="margin-top:32px; padding-top:16px; border-top:1px solid #e5e7eb; text-align:center;">
        <p style="font-size:12px; color:#9ca3af; margin:0;">
            You're receiving this because you opted in to communications from Gengyve USA.<br/>
            <a href="{unsubscribe_url}" style="color:#6b7280; text-decoration:underline;">Unsubscribe</a>
            &nbsp;|&nbsp;
            Gengyve USA, San Francisco, CA
        </p>
    </div>
    """
    if "</body>" in html.lower():
        idx = html.lower().rfind("</body>")
        return html[:idx] + footer + html[idx:]
    return html + footer


async def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    plain_body: str,
    from_email: str | None = None,
    reply_to: str | None = None,
    unsubscribe_url: str | None = None,
    tracking_url: str | None = None,
    tags: dict[str, str] | None = None,
) -> EmailResult:
    """
    Send an email via Amazon SES.

    Injects tracking pixel and unsubscribe footer if URLs are provided.
    Adds List-Unsubscribe headers per RFC 8058 for one-click unsubscribe.
    """
    from_addr = from_email or settings.SES_FROM_EMAIL
    if not from_addr:
        return EmailResult(success=False, error="SES_FROM_EMAIL not configured")

    # Inject tracking + unsubscribe
    final_html = html_body
    if tracking_url:
        final_html = _inject_tracking_pixel(final_html, tracking_url)
    if unsubscribe_url:
        final_html = _inject_unsubscribe_footer(final_html, unsubscribe_url)

    # Build SES message
    message: dict[str, Any] = {
        "Source": from_addr,
        "Destination": {"ToAddresses": [to_email]},
        "Message": {
            "Subject": {"Data": subject, "Charset": "UTF-8"},
            "Body": {
                "Text": {"Data": plain_body, "Charset": "UTF-8"},
                "Html": {"Data": final_html, "Charset": "UTF-8"},
            },
        },
    }

    if reply_to:
        message["ReplyToAddresses"] = [reply_to]

    # Add List-Unsubscribe header for RFC 8058 compliance
    headers = []
    if unsubscribe_url:
        headers.append({"Name": "List-Unsubscribe", "Value": f"<{unsubscribe_url}>"})
        headers.append({"Name": "List-Unsubscribe-Post", "Value": "List-Unsubscribe=One-Click"})

    # Build tags for SES
    ses_tags = []
    if tags:
        ses_tags = [{"Name": k, "Value": v} for k, v in tags.items()]

    try:
        client = _get_ses_client()

        # Use SendRawMessage for custom headers, or SendEmail for basic
        if headers:
            # Need raw email for custom headers
            import email.mime.multipart
            import email.mime.text

            msg = email.mime.multipart.MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = from_addr
            msg["To"] = to_email
            if reply_to:
                msg["Reply-To"] = reply_to

            for h in headers:
                msg[h["Name"]] = h["Value"]

            msg.attach(email.mime.text.MIMEText(plain_body, "plain", "utf-8"))
            msg.attach(email.mime.text.MIMEText(final_html, "html", "utf-8"))

            response = client.send_raw_email(
                Source=from_addr,
                Destinations=[to_email],
                RawMessage={"Data": msg.as_string()},
                Tags=ses_tags if ses_tags else [],
            )
        else:
            response = client.send_email(
                **message,
                Tags=ses_tags if ses_tags else [],
            )

        message_id = response.get("MessageId", "")
        logger.info("Email sent to %s, MessageId: %s", to_email, message_id)
        return EmailResult(success=True, message_id=message_id)

    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return EmailResult(success=False, error=str(exc))


async def process_ses_notification(notification: dict) -> dict:
    """
    Process SES bounce/complaint/delivery notifications from SNS webhook.

    Returns action taken dict.
    """
    notif_type = notification.get("notificationType") or notification.get("eventType")

    if notif_type == "Bounce":
        bounce = notification.get("bounce", {})
        bounced_recipients = bounce.get("bouncedRecipients", [])
        return {
            "type": "bounce",
            "bounce_type": bounce.get("bounceType"),
            "recipients": [r.get("emailAddress") for r in bounced_recipients],
        }
    elif notif_type == "Complaint":
        complaint = notification.get("complaint", {})
        complained_recipients = complaint.get("complainedRecipients", [])
        return {
            "type": "complaint",
            "recipients": [r.get("emailAddress") for r in complained_recipients],
        }
    elif notif_type == "Delivery":
        delivery = notification.get("delivery", {})
        return {
            "type": "delivery",
            "recipients": delivery.get("recipients", []),
        }

    return {"type": "unknown", "raw": notif_type}
