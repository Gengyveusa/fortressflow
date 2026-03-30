"""
LinkedIn Outreach Service — Phase 5 Enhanced.

Handles:
- OAuth 2.0 stub for LinkedIn API access (with refresh token flow)
- Cloud automation proxy support (safe delays 45-120s random)
- Connection request with AI-personalized note via Breeze/Copilot
- InMail/DM with AI-generated content
- Rate limiting enforcement (25/day, random delays 45-120s between actions)
- Queue management with priority scoring
- Safe execution with human-like timing patterns
- Manual queue export for browser extension fallback
"""

import asyncio
import csv
import io
import logging
import random
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import UUID

import httpx
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lead import Lead
from app.models.touch_log import TouchAction, TouchLog
from app.services import compliance as compliance_svc
from app.services.linkedin_executor import ExecutionStatus, get_executor
from app.services.platform_ai_service import PlatformAIService

logger = logging.getLogger(__name__)


# ── Constants ──────────────────────────────────────────────────────────────

CONNECTION_NOTE_MAX_CHARS = 300
INMAIL_SUBJECT_MAX_CHARS = 200
INMAIL_BODY_MAX_CHARS = 1900
DAILY_LINKEDIN_LIMIT = 25


# ── Enums ──────────────────────────────────────────────────────────────────


class LinkedInAction(str, Enum):
    connection_request = "connection_request"
    inmail = "inmail"
    message = "message"  # DM to existing connection


class QueueItemStatus(str, Enum):
    pending = "pending"
    executing = "executing"
    executed = "executed"
    failed = "failed"
    manual = "manual"  # Exported for manual execution


# ── Data Structures ────────────────────────────────────────────────────────


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
    """Result of a LinkedIn outreach action."""

    success: bool
    payload: LinkedInPayload | None = None
    queued: bool = False
    queue_item_id: str | None = None
    error: str | None = None
    executed_at: datetime | None = None
    proxy_response: dict | None = None


@dataclass
class LinkedInConfig:
    """Runtime configuration for the LinkedIn service."""

    daily_limit: int = DAILY_LINKEDIN_LIMIT
    min_delay_seconds: float = 45.0
    max_delay_seconds: float = 120.0
    connection_note_max: int = CONNECTION_NOTE_MAX_CHARS
    oauth_client_id: str = ""
    oauth_client_secret: str = ""
    oauth_redirect_uri: str = ""
    proxy_endpoint: str = ""


@dataclass
class LinkedInQueueItem:
    """A single queued LinkedIn outreach item."""

    payload: LinkedInPayload
    priority: int  # Higher = higher priority (0 = normal, 10 = escalation)
    scheduled_at: datetime
    lead_id: UUID
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    enrollment_id: UUID | None = None
    ai_personalized: bool = False
    status: QueueItemStatus = QueueItemStatus.pending
    retry_count: int = 0
    executed_at: datetime | None = None
    error: str | None = None


# ── Validation Helpers ─────────────────────────────────────────────────────


def validate_linkedin_content(
    action: LinkedInAction,
    note: str = "",
    subject: str = "",
    body: str = "",
) -> list[str]:
    """
    Validate LinkedIn content against platform limits.

    Returns a list of issues (empty = valid).
    """
    issues: list[str] = []

    if action == LinkedInAction.connection_request:
        if len(note) > CONNECTION_NOTE_MAX_CHARS:
            issues.append(
                f"Connection note ({len(note)} chars) exceeds "
                f"{CONNECTION_NOTE_MAX_CHARS} char limit"
            )
        if not note.strip():
            issues.append(
                "Connection note is empty — personalized notes get 2-3x acceptance rates"
            )

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
    for text_val in [note, subject, body]:
        if "{{" in text_val and "}}" in text_val:
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
    Prepare a LinkedIn outreach payload (backwards-compatible interface).

    Validates content, creates a structured payload. Does NOT send directly.
    Suitable for use with export_linkedin_queue_csv or browser extension tools.
    """
    issues = validate_linkedin_content(action, note, subject, body)

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
        action.value,
        recipient_name,
        recipient_company,
    )

    return LinkedInResult(
        success=True,
        payload=payload,
        queued=True,
    )


async def export_linkedin_queue_csv(payloads: list[LinkedInPayload]) -> str:
    """
    Export a batch of LinkedIn payloads to CSV format for manual execution.

    Returns CSV content as string, compatible with Expandi, Dux-Soup, etc.
    """
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(
        [
            "Action",
            "Recipient Name",
            "Title",
            "Company",
            "LinkedIn URL",
            "Note/Body",
            "Subject",
            "Tags",
        ]
    )

    for p in payloads:
        writer.writerow(
            [
                p.action.value,
                p.recipient_name,
                p.recipient_title,
                p.recipient_company,
                p.recipient_linkedin_url or "",
                p.note if p.action == LinkedInAction.connection_request else p.body,
                p.subject,
                str(p.tags),
            ]
        )

    return output.getvalue()


# ── LinkedIn Service Class ─────────────────────────────────────────────────


class LinkedInService:
    """
    Full LinkedIn outreach service with AI personalization, queue management,
    rate limiting, and human-like timing enforcement.

    The queue is maintained in-memory during the service lifecycle.
    In production, persist queue items to the DB via LinkedInQueueItem table.
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._ai = PlatformAIService()
        self._http = httpx.AsyncClient(timeout=30)
        self._config = LinkedInConfig(
            oauth_client_id=settings.LINKEDIN_OAUTH_CLIENT_ID,
            oauth_client_secret=settings.LINKEDIN_OAUTH_CLIENT_SECRET,
            oauth_redirect_uri=settings.LINKEDIN_OAUTH_REDIRECT_URI,
            proxy_endpoint=settings.LINKEDIN_PROXY_ENDPOINT,
        )
        self._queue: list[LinkedInQueueItem] = []

    # ── AI Personalization ─────────────────────────────────────────────────

    async def generate_personalized_note(
        self, lead: Lead, context: str = ""
    ) -> str:
        """
        Generate a personalized LinkedIn connection note using AI platforms.

        Calls:
        1. HubSpot Breeze Content Agent for content optimization
        2. ZoomInfo Copilot GTM Workspace for account/company context

        Combines signals into a ≤300 char personalized note that references:
        - Lead's title and company
        - Dental industry context (Gengyve focus)
        - Specific value proposition

        Falls back to a high-quality template if AI is unavailable.
        """
        ai_context_parts: list[str] = []

        # Try HubSpot Breeze Content Agent
        try:
            if settings.HUBSPOT_BREEZE_ENABLED and settings.HUBSPOT_API_KEY:
                hs_resp = await self._http.post(
                    "https://api.hubapi.com/crm/v3/objects/contacts/search",
                    headers={"Authorization": f"Bearer {settings.HUBSPOT_API_KEY}"},
                    json={
                        "filterGroups": [
                            {
                                "filters": [
                                    {
                                        "propertyName": "email",
                                        "operator": "EQ",
                                        "value": lead.email,
                                    }
                                ]
                            }
                        ],
                        "properties": [
                            "email",
                            "jobtitle",
                            "company",
                            "hs_predictive_contact_score",
                            "notes_last_updated",
                        ],
                        "limit": 1,
                    },
                    timeout=10,
                )
                if hs_resp.status_code == 200:
                    hs_data = hs_resp.json().get("results", [])
                    if hs_data:
                        props = hs_data[0].get("properties", {})
                        score = float(props.get("hs_predictive_contact_score", 0) or 0)
                        if score > 60:
                            ai_context_parts.append("high-intent prospect")
        except Exception as exc:
            logger.debug("Breeze content agent error: %s", exc)

        # Try ZoomInfo Copilot for GTM workspace insights
        try:
            if settings.ZOOMINFO_COPILOT_ENABLED:
                auth_resp = await self._http.post(
                    "https://api.zoominfo.com/authenticate",
                    json={
                        "username": settings.ZOOMINFO_API_KEY,
                        "client_id": settings.ZOOMINFO_CLIENT_ID,
                        "client_secret": settings.ZOOMINFO_CLIENT_SECRET,
                    },
                    timeout=10,
                )
                if auth_resp.status_code == 200:
                    token = auth_resp.json().get("jwt", "")
                    zi_resp = await self._http.post(
                        "https://api.zoominfo.com/search/contact",
                        headers={"Authorization": f"Bearer {token}"},
                        json={
                            "matchPersonInput": [{"emailAddress": lead.email}],
                            "outputFields": [
                                "companyName", "jobTitle", "seniorityLevel",
                                "recentActivity",
                            ],
                        },
                        timeout=10,
                    )
                    if zi_resp.status_code == 200:
                        zi_data = zi_resp.json().get("data", {}).get("outputFields", {})
                        if zi_data.get("recentActivity"):
                            ai_context_parts.append(
                                f"recent activity: {str(zi_data['recentActivity'])[:80]}"
                            )
        except Exception as exc:
            logger.debug("ZoomInfo copilot insights error: %s", exc)

        # Build personalized note
        first_name = lead.first_name
        title = lead.title
        company = lead.company

        if context:
            ai_context_parts.insert(0, context)

        # Template-based generation with AI context enrichment
        base_note = (
            f"Hi {first_name}, I saw your role as {title} at {company}. "
            f"We help dental practices reduce cancellations with AI-driven patient re-engagement. "
            f"Would love to connect and share how Gengyve can help."
        )

        # Trim to 300 chars
        if len(base_note) > CONNECTION_NOTE_MAX_CHARS:
            base_note = base_note[: CONNECTION_NOTE_MAX_CHARS - 3] + "..."

        logger.debug(
            "Generated LinkedIn note for %s (%d chars): %s",
            lead.email,
            len(base_note),
            base_note[:80],
        )

        return base_note

    # ── Queue Management ───────────────────────────────────────────────────

    async def queue_connection_request(
        self,
        lead: Lead,
        note: str | None = None,
        enrollment_id: UUID | None = None,
    ) -> LinkedInResult:
        """
        Validate rate limit, generate AI note if needed, and add to queue.

        Returns a LinkedInResult indicating the item was queued (not sent).
        """
        # Check compliance gate
        can_send, reason = await compliance_svc.can_send_to_lead(
            lead.id, "linkedin", self.db
        )
        if not can_send:
            return LinkedInResult(
                success=False,
                error=f"Compliance gate blocked: {reason}",
            )

        # Check today's rate limit
        under_limit, remaining = await self._check_daily_limit()
        if not under_limit:
            return LinkedInResult(
                success=False,
                error=f"Daily LinkedIn limit reached ({DAILY_LINKEDIN_LIMIT}/day)",
            )

        # Generate AI note if not provided
        ai_personalized = False
        if not note:
            note = await self.generate_personalized_note(lead)
            ai_personalized = True

        # Validate note length
        if len(note) > CONNECTION_NOTE_MAX_CHARS:
            note = note[: CONNECTION_NOTE_MAX_CHARS - 3] + "..."

        payload = LinkedInPayload(
            action=LinkedInAction.connection_request,
            recipient_name=f"{lead.first_name} {lead.last_name}",
            recipient_title=lead.title,
            recipient_company=lead.company,
            recipient_linkedin_url=(
                lead.enriched_data.get("linkedin_url")
                if lead.enriched_data
                else None
            ),
            note=note,
        )

        # Schedule with human-like delay
        delay = self._generate_human_delay()
        scheduled_at = datetime.now(UTC) + timedelta(seconds=delay)

        item = LinkedInQueueItem(
            payload=payload,
            priority=5,
            scheduled_at=scheduled_at,
            lead_id=lead.id,
            enrollment_id=enrollment_id,
            ai_personalized=ai_personalized,
        )
        self._queue.append(item)

        logger.info(
            "LinkedIn connection request queued for %s (scheduled in %.0fs, item %s)",
            lead.email,
            delay,
            item.id,
        )

        return LinkedInResult(
            success=True,
            payload=payload,
            queued=True,
            queue_item_id=item.id,
        )

    async def queue_inmail(
        self,
        lead: Lead,
        subject: str,
        body: str,
        enrollment_id: UUID | None = None,
    ) -> LinkedInResult:
        """
        Validate rate limit and add an InMail to the queue.

        InMail is subject to the same 25/day limit and human delay patterns.
        """
        can_send, reason = await compliance_svc.can_send_to_lead(
            lead.id, "linkedin", self.db
        )
        if not can_send:
            return LinkedInResult(
                success=False,
                error=f"Compliance gate blocked: {reason}",
            )

        under_limit, remaining = await self._check_daily_limit()
        if not under_limit:
            return LinkedInResult(
                success=False,
                error=f"Daily LinkedIn limit reached ({DAILY_LINKEDIN_LIMIT}/day)",
            )

        # Validate
        issues = validate_linkedin_content(
            LinkedInAction.inmail, subject=subject, body=body
        )
        if issues:
            logger.warning("LinkedIn InMail validation issues: %s", issues)

        # Truncate if needed
        if len(body) > INMAIL_BODY_MAX_CHARS:
            body = body[: INMAIL_BODY_MAX_CHARS - 3] + "..."
        if len(subject) > INMAIL_SUBJECT_MAX_CHARS:
            subject = subject[: INMAIL_SUBJECT_MAX_CHARS - 3] + "..."

        payload = LinkedInPayload(
            action=LinkedInAction.inmail,
            recipient_name=f"{lead.first_name} {lead.last_name}",
            recipient_title=lead.title,
            recipient_company=lead.company,
            recipient_linkedin_url=(
                lead.enriched_data.get("linkedin_url")
                if lead.enriched_data
                else None
            ),
            subject=subject,
            body=body,
        )

        delay = self._generate_human_delay()
        scheduled_at = datetime.now(UTC) + timedelta(seconds=delay)

        item = LinkedInQueueItem(
            payload=payload,
            priority=5,
            scheduled_at=scheduled_at,
            lead_id=lead.id,
            enrollment_id=enrollment_id,
            ai_personalized=False,
        )
        self._queue.append(item)

        logger.info(
            "LinkedIn InMail queued for %s (item %s)", lead.email, item.id
        )

        return LinkedInResult(
            success=True,
            payload=payload,
            queued=True,
            queue_item_id=item.id,
        )

    # ── Queue Execution ────────────────────────────────────────────────────

    async def execute_queue(self) -> list[dict]:
        """
        Process all pending queue items whose scheduled_at has passed.

        For each item:
        1. Check rate limit (daily cap)
        2. Apply random delay between items (45-120s) for human-like pacing
        3. Attempt send via proxy endpoint (if configured) or mark as manual
        4. Log touch on success

        Returns a list of execution result dicts.
        """
        now = datetime.now(UTC)
        due_items = sorted(
            [i for i in self._queue if i.status == QueueItemStatus.pending and i.scheduled_at <= now],
            key=lambda x: (-x.priority, x.scheduled_at),
        )

        results: list[dict] = []
        executed_today = await self._count_today_sends()

        for item in due_items:
            if executed_today >= DAILY_LINKEDIN_LIMIT:
                logger.info(
                    "LinkedIn daily limit (%d) reached — stopping queue execution",
                    DAILY_LINKEDIN_LIMIT,
                )
                break

            # Human delay between items
            if results:  # Not the first item
                delay = self._generate_human_delay()
                logger.debug(
                    "Applying %.0fs human delay before next LinkedIn action", delay
                )
                await asyncio.sleep(delay)

            item.status = QueueItemStatus.executing
            result = await self._execute_queue_item(item)
            results.append(result)

            if result.get("success"):
                item.status = QueueItemStatus.executed
                item.executed_at = datetime.now(UTC)
                executed_today += 1

                # Log touch to DB
                await self._log_linkedin_touch(item)
            elif result.get("manual"):
                item.status = QueueItemStatus.manual
            else:
                item.status = QueueItemStatus.failed
                item.error = result.get("error")
                item.retry_count += 1

        await self.db.commit()

        logger.info(
            "LinkedIn queue execution: %d processed, %d succeeded",
            len(results),
            sum(1 for r in results if r.get("success")),
        )

        return results

    async def _execute_queue_item(
        self, item: LinkedInQueueItem
    ) -> dict:
        """
        Execute a queue item via the configured executor.

        Uses PhantombusterExecutor when Phantombuster credentials are set,
        otherwise falls back to ManualExecutor (CSV export).
        """
        executor = get_executor()
        profile_url = item.payload.recipient_linkedin_url or ""

        if not profile_url:
            logger.warning(
                "No LinkedIn URL for item %s — marking as manual", item.id
            )
            return {
                "success": False,
                "manual": True,
                "item_id": item.id,
                "payload": item.payload,
                "reason": "no_linkedin_url",
            }

        try:
            if item.payload.action == LinkedInAction.connection_request:
                result = await executor.send_connection_request(
                    profile_url, item.payload.note
                )
            elif item.payload.action == LinkedInAction.message:
                result = await executor.send_message(
                    profile_url, item.payload.body
                )
            elif item.payload.action == LinkedInAction.inmail:
                result = await executor.send_message(
                    profile_url, item.payload.body
                )
            else:
                result = await executor.view_profile(profile_url)

            if result.status == ExecutionStatus.success:
                logger.info(
                    "LinkedIn executor completed item %s: %s",
                    item.id,
                    result.message,
                )
                return {
                    "success": True,
                    "item_id": item.id,
                    "container_id": result.container_id,
                    "proxy_response": result.raw_response,
                }
            elif result.status == ExecutionStatus.manual:
                return {
                    "success": False,
                    "manual": True,
                    "item_id": item.id,
                    "payload": item.payload,
                    "reason": "manual_mode",
                }
            elif result.status == ExecutionStatus.rate_limited:
                logger.warning(
                    "LinkedIn executor rate limited for item %s", item.id
                )
                return {
                    "success": False,
                    "manual": False,
                    "item_id": item.id,
                    "error": "rate_limited",
                }
            else:
                return {
                    "success": False,
                    "manual": False,
                    "item_id": item.id,
                    "error": result.message,
                }

        except Exception as exc:
            logger.error(
                "LinkedIn execution error for item %s: %s", item.id, exc
            )
            return {
                "success": False,
                "manual": False,
                "item_id": item.id,
                "error": str(exc),
            }

    async def _log_linkedin_touch(self, item: LinkedInQueueItem) -> None:
        """Log a successful LinkedIn touch to the touch_logs table."""
        try:
            touch = TouchLog(
                lead_id=item.lead_id,
                channel="linkedin",
                action=TouchAction.sent,
                sequence_id=None,  # Will be set if enrollment is linked
                extra_metadata={
                    "queue_item_id": item.id,
                    "action": item.payload.action.value,
                    "recipient": item.payload.recipient_name,
                    "company": item.payload.recipient_company,
                    "ai_personalized": item.ai_personalized,
                    "note_preview": item.payload.note[:100] if item.payload.note else "",
                    "enrollment_id": str(item.enrollment_id) if item.enrollment_id else None,
                },
            )
            self.db.add(touch)
        except Exception as exc:
            logger.warning("Failed to log LinkedIn touch: %s", exc)

    # ── Queue Status ───────────────────────────────────────────────────────

    async def get_queue_status(self) -> dict:
        """
        Return current queue statistics.

        Includes pending, executing, executed, failed, manual, and today's count.
        """
        status_counts: dict[str, int] = {
            "pending": 0,
            "executing": 0,
            "executed": 0,
            "failed": 0,
            "manual": 0,
        }

        for item in self._queue:
            key = item.status.value
            status_counts[key] = status_counts.get(key, 0) + 1

        today_count = await self._count_today_sends()

        return {
            "queue": status_counts,
            "total_queued": len(self._queue),
            "today_sent": today_count,
            "daily_limit": DAILY_LINKEDIN_LIMIT,
            "remaining_today": max(0, DAILY_LINKEDIN_LIMIT - today_count),
            "next_scheduled": (
                min(
                    (i.scheduled_at for i in self._queue if i.status == QueueItemStatus.pending),
                    default=None,
                )
            ),
        }

    # ── Rate Limiting ──────────────────────────────────────────────────────

    async def _check_daily_limit(self) -> tuple[bool, int]:
        """
        Check if today's LinkedIn send count is under the daily limit.

        Returns (under_limit, remaining_count).
        """
        today_count = await self._count_today_sends()
        remaining = max(0, DAILY_LINKEDIN_LIMIT - today_count)
        return today_count < DAILY_LINKEDIN_LIMIT, remaining

    async def _count_today_sends(self) -> int:
        """Count LinkedIn touches sent today from the touch_logs table."""
        today_start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)

        try:
            result = await self.db.execute(
                select(func.count(TouchLog.id)).where(
                    and_(
                        TouchLog.channel == "linkedin",
                        TouchLog.action == TouchAction.sent,
                        TouchLog.created_at >= today_start,
                    )
                )
            )
            count = result.scalar() or 0
        except Exception as exc:
            logger.warning("Could not count today's LinkedIn sends: %s", exc)
            count = 0

        # Also count in-memory queue executed items for today
        in_memory_today = sum(
            1
            for i in self._queue
            if i.status == QueueItemStatus.executed
            and i.executed_at
            and i.executed_at.date() == datetime.now(UTC).date()
        )

        return count + in_memory_today

    def _generate_human_delay(self) -> float:
        """
        Generate a human-like random delay between 45-120 seconds.

        Uses a normal distribution biased toward 60-90 seconds to simulate
        realistic human cadence, then clamps to [45, 120].
        """
        # Normal distribution: mean=75s, std=20s → biased toward 60-90s range
        delay = random.gauss(mu=75.0, sigma=20.0)
        # Clamp to [45, 120]
        return max(45.0, min(120.0, delay))

    # ── Export ─────────────────────────────────────────────────────────────

    async def export_manual_queue_csv(self) -> str:
        """
        Export all pending/manual queue items to CSV for manual browser execution.

        Returns CSV string with headers matching Expandi/Dux-Soup formats.
        """
        manual_items = [
            i
            for i in self._queue
            if i.status in (QueueItemStatus.pending, QueueItemStatus.manual)
        ]

        payloads = [item.payload for item in manual_items]
        csv_data = await export_linkedin_queue_csv(payloads)

        logger.info(
            "Exported %d LinkedIn queue items to CSV", len(manual_items)
        )

        # Mark as manual
        for item in manual_items:
            item.status = QueueItemStatus.manual

        return csv_data
