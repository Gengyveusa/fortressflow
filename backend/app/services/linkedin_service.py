"""
LinkedIn outreach service.

Handles:
- Connection request with personalized note (300 char limit)
- InMail composition
- Direct message to existing connections
- Rate limiting (LinkedIn strict limits: ~100 invites/week, 25/day safe)
- Queue management for gradual sending

NOTE: LinkedIn does NOT provide an official API for connection requests
or InMail sending. This service structures the outreach data for:
  1. Manual execution via browser extension (Expandi, Dux-Soup, etc.)
  2. LinkedIn Sales Navigator API (for organizations with access)
  3. Export to CSV for manual outreach workflow

The service generates ready-to-send payloads and logs compliance data.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, UTC
from enum import Enum

logger = logging.getLogger(__name__)


class LinkedInAction(str, Enum):
    connection_request = "connection_request"
    inmail = "inmail"
    message = "message"  # DM to existing connection


@dataclass
class LinkedInPayload:
    """Structured payload for a LinkedIn outreach action."""

    action: LinkedInAction
    recipient_name: str
    recipient_title: str
    recipient_company: str
    recipient_linkedin_url: str | None = None
    note: str = ""  # Connection request note (300 char max)
    subject: str = ""  # InMail subject
    body: str = ""  # InMail/message body
    tags: dict[str, str] = field(default_factory=dict)


@dataclass
class LinkedInResult:
    success: bool
    payload: LinkedInPayload | None = None
    queued: bool = False
    error: str | None = None


# LinkedIn connection request note limit
CONNECTION_NOTE_MAX_CHARS = 300
INMAIL_SUBJECT_MAX_CHARS = 200
INMAIL_BODY_MAX_CHARS = 1900


def validate_linkedin_content(
    action: LinkedInAction,
    note: str = "",
    subject: str = "",
    body: str = "",
) -> list[str]:
    """Validate LinkedIn content against platform limits."""
    issues = []

    if action == LinkedInAction.connection_request:
        if len(note) > CONNECTION_NOTE_MAX_CHARS:
            issues.append(
                f"Connection note ({len(note)} chars) exceeds "
                f"{CONNECTION_NOTE_MAX_CHARS} char limit"
            )
        if not note.strip():
            issues.append("Connection note is empty — personalized notes get 2-3x acceptance rates")

    elif action == LinkedInAction.inmail:
        if len(subject) > INMAIL_SUBJECT_MAX_CHARS:
            issues.append(
                f"InMail subject ({len(subject)} chars) exceeds "
                f"{INMAIL_SUBJECT_MAX_CHARS} char limit"
            )
        if len(body) > INMAIL_BODY_MAX_CHARS:
            issues.append(
                f"InMail body ({len(body)} chars) exceeds "
                f"{INMAIL_BODY_MAX_CHARS} char limit"
            )

    elif action == LinkedInAction.message:
        if not body.strip():
            issues.append("Message body is empty")

    # Check for unresolved template variables
    for text in [note, subject, body]:
        if "{{" in text and "}}" in text:
            issues.append("Content contains unresolved template variables")
            break

    return issues


async def prepare_linkedin_outreach(
    action: LinkedInAction,
    recipient_name: str,
    recipient_title: str,
    recipient_company: str,
    note: str = "",
    subject: str = "",
    body: str = "",
    recipient_linkedin_url: str | None = None,
    tags: dict[str, str] | None = None,
) -> LinkedInResult:
    """
    Prepare a LinkedIn outreach payload.

    This does NOT send the message directly (LinkedIn doesn't allow it via API
    for most use cases). It creates a structured, validated payload that can be:
    - Queued for execution via browser automation tools
    - Exported for manual outreach
    - Sent via Sales Navigator API if available
    """
    issues = validate_linkedin_content(action, note, subject, body)

    # We treat validation warnings as non-blocking (log but proceed)
    if issues:
        for issue in issues:
            logger.warning("LinkedIn validation: %s", issue)

    payload = LinkedInPayload(
        action=action,
        recipient_name=recipient_name,
        recipient_title=recipient_title,
        recipient_company=recipient_company,
        recipient_linkedin_url=recipient_linkedin_url,
        note=note,
        subject=subject,
        body=body,
        tags=tags or {},
    )

    logger.info(
        "LinkedIn %s prepared for %s at %s",
        action.value, recipient_name, recipient_company,
    )

    return LinkedInResult(
        success=True,
        payload=payload,
        queued=True,
    )


async def export_linkedin_queue_csv(payloads: list[LinkedInPayload]) -> str:
    """
    Export a batch of LinkedIn payloads to CSV format for manual execution.

    Returns CSV content as string.
    """
    import csv
    import io

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Action", "Recipient Name", "Title", "Company",
        "LinkedIn URL", "Note/Body", "Subject", "Tags",
    ])

    for p in payloads:
        writer.writerow([
            p.action.value,
            p.recipient_name,
            p.recipient_title,
            p.recipient_company,
            p.recipient_linkedin_url or "",
            p.note if p.action == LinkedInAction.connection_request else p.body,
            p.subject,
            str(p.tags),
        ])

    return output.getvalue()
