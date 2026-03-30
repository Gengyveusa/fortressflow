"""
Reply Detection Service — Phase 5.

Handles:
- IMAP polling for inbound email replies (configurable mailbox)
- Webhook-based reply ingestion (Parsio, email parser APIs)
- Sender/thread matching to sequence enrollments
- Sentiment analysis (positive/neutral/negative) via simple keyword NLP + AI platforms
- AI-powered reply analysis (HubSpot Breeze engagement context, Apollo AI next-action, ZoomInfo account update)
- FSM state transitions on reply detection (→ replied → paused)
- Touch history logging + HubSpot Note creation
"""

import asyncio
import email
import email.header
import email.message
import imaplib
import logging
import re
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import and_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lead import Lead
from app.models.sequence import EnrollmentStatus, SequenceEnrollment
from app.models.touch_log import TouchAction, TouchLog
from app.services.platform_ai_service import PlatformAIService
from app.services.state_machine import (
    EnrollmentState,
    handle_reply_signal,
    transition,
)

logger = logging.getLogger(__name__)

_HUBSPOT_BASE = "https://api.hubapi.com"
_ZOOMINFO_BASE = "https://api.zoominfo.com"
_APOLLO_BASE = "https://api.apollo.io"


# ── Data Structures ────────────────────────────────────────────────────────


@dataclass
class ReplySignal:
    """Inbound reply signal from any channel."""

    channel: str  # "email" | "sms" | "linkedin"
    body: str
    received_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    sender_email: str | None = None
    sender_phone: str | None = None
    subject: str | None = None
    thread_id: str | None = None  # References or In-Reply-To header value
    message_id: str | None = None
    raw_headers: dict[str, str] = field(default_factory=dict)


class ReplySentiment(StrEnum):
    positive = "positive"
    negative = "negative"
    neutral = "neutral"
    out_of_office = "out_of_office"
    unsubscribe = "unsubscribe"


@dataclass
class ReplyAnalysisResult:
    """Full analysis result for a detected reply."""

    signal: ReplySignal
    sentiment: ReplySentiment
    confidence: float  # 0.0 – 1.0
    ai_suggestions: dict[str, Any] = field(default_factory=dict)
    matched_enrollment_id: UUID | None = None
    matched_sequence_id: UUID | None = None
    hubspot_note_id: str | None = None
    apollo_action: str | None = None
    zoominfo_update: dict[str, Any] | None = None


# ── Keyword Lists ──────────────────────────────────────────────────────────

_POSITIVE_KEYWORDS = {
    "interested",
    "yes",
    "sure",
    "definitely",
    "absolutely",
    "love to",
    "schedule",
    "meeting",
    "call",
    "demo",
    "chat",
    "connect",
    "tell me more",
    "sounds good",
    "great",
    "happy to",
    "looking forward",
    "available",
    "learn more",
    "curious",
    "perfect",
    "when",
    "how much",
    "pricing",
    "can we",
    "would love",
    "thanks for reaching out",
    "appreciate",
    "open to",
    "let's",
    "let us",
    "works for me",
}

_NEGATIVE_KEYWORDS = {
    "not interested",
    "no thanks",
    "no thank you",
    "don't contact",
    "do not contact",
    "not relevant",
    "wrong person",
    "wrong company",
    "don't reach out",
    "not a fit",
    "already have",
    "using another",
    "not the right time",
    "budget",
    "no budget",
    "remove me",
    "please remove",
    "opt out",
    "unsubscribe",
    "stop emailing",
    "stop contacting",
    "leave me alone",
    "never contact",
}

_OOO_KEYWORDS = {
    "out of office",
    "out of the office",
    "auto-reply",
    "automatic reply",
    "autoreply",
    "away from",
    "on vacation",
    "on leave",
    "annual leave",
    "maternity leave",
    "paternity leave",
    "currently unavailable",
    "i am out",
    "i'm out",
    "will be back",
    "returning on",
    "back on",
    "limited access",
    "limited availability",
}

_UNSUBSCRIBE_KEYWORDS = {
    "unsubscribe",
    "remove me from",
    "take me off",
    "opt out",
    "opt-out",
    "do not email",
    "stop emailing me",
    "please stop",
    "cease and desist",
    "no more emails",
    "remove from list",
}


# ── Service ────────────────────────────────────────────────────────────────


class ReplyService:
    """
    Full reply detection, matching, sentiment analysis, and FSM pipeline.

    Designed to be instantiated per-request with a shared AsyncSession.
    The IMAP polling method should be called from a Celery beat task at
    IMAP_POLL_INTERVAL_MINUTES (default: 5).
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self._ai = PlatformAIService()
        self._http = httpx.AsyncClient(timeout=30)

    # ── IMAP Polling ───────────────────────────────────────────────────────

    async def poll_imap_inbox(self) -> list[ReplySignal]:
        """
        Connect to IMAP inbox and fetch UNSEEN messages from the last 24 hours.

        Uses asyncio.to_thread to avoid blocking the event loop.
        Marks fetched messages as SEEN.

        Returns a list of ReplySignal objects ready for processing.
        """
        if not settings.IMAP_HOST or not settings.IMAP_USER or not settings.IMAP_PASSWORD:
            logger.warning("IMAP credentials not configured — skipping poll")
            return []

        signals: list[ReplySignal] = []

        try:
            signals = await asyncio.to_thread(self._fetch_imap_blocking)
            logger.info("IMAP poll: fetched %d reply signals", len(signals))
        except Exception as exc:
            logger.error("IMAP poll failed: %s", exc, exc_info=True)

        return signals

    def _fetch_imap_blocking(self) -> list[ReplySignal]:
        """
        Blocking IMAP fetch — run in a thread via asyncio.to_thread.

        Fetches UNSEEN emails from the last 24 hours, parses them into
        ReplySignal objects, and marks them SEEN.
        """
        signals: list[ReplySignal] = []
        folder = settings.IMAP_FOLDER or "INBOX"

        with imaplib.IMAP4_SSL(settings.IMAP_HOST) as conn:
            conn.login(settings.IMAP_USER, settings.IMAP_PASSWORD)
            conn.select(folder)

            # Search for UNSEEN messages since yesterday
            since_date = (datetime.now(UTC) - timedelta(hours=24)).strftime("%d-%b-%Y")
            _status, msg_ids = conn.search(None, f"(UNSEEN SINCE {since_date})")

            if not msg_ids or not msg_ids[0]:
                return signals

            id_list = msg_ids[0].split()
            logger.info("IMAP: found %d unseen messages", len(id_list))

            for msg_id_bytes in id_list:
                try:
                    _status, msg_data = conn.fetch(msg_id_bytes, "(RFC822)")
                    if not msg_data or not msg_data[0]:
                        continue

                    raw_email = msg_data[0][1]
                    signal = self._parse_raw_email(raw_email)
                    if signal:
                        signals.append(signal)

                    # Mark as SEEN
                    conn.store(msg_id_bytes, "+FLAGS", "\\Seen")

                except Exception as exc:
                    logger.warning("Failed to parse IMAP message %s: %s", msg_id_bytes, exc)

        return signals

    def _parse_raw_email(self, raw: bytes) -> ReplySignal | None:
        """Parse a raw RFC822 email into a ReplySignal."""
        try:
            msg = email.message_from_bytes(raw)

            # Decode sender
            from_header = msg.get("From", "")
            sender_email = self._extract_email_address(from_header)

            # Subject
            subject_raw = msg.get("Subject", "")
            subject = self._decode_header_value(subject_raw)

            # Thread references (for matching)
            in_reply_to = msg.get("In-Reply-To", "").strip()
            references = msg.get("References", "").strip()
            thread_id = in_reply_to or (references.split()[-1] if references else None)

            message_id = msg.get("Message-ID", "").strip()

            # Extract body
            body = self._extract_body(msg)
            if not body:
                return None

            raw_headers: dict[str, str] = {
                "From": from_header,
                "Subject": subject or "",
                "In-Reply-To": in_reply_to,
                "References": references,
                "Date": msg.get("Date", ""),
            }

            return ReplySignal(
                channel="email",
                sender_email=sender_email,
                subject=subject,
                thread_id=thread_id,
                message_id=message_id,
                body=body,
                raw_headers=raw_headers,
            )

        except Exception as exc:
            logger.warning("Email parse error: %s", exc)
            return None

    def _extract_email_address(self, header: str) -> str | None:
        """Extract raw email address from a From: header."""
        match = re.search(r"<([^>]+)>", header)
        if match:
            return match.group(1).strip().lower()
        # No angle brackets — might just be bare email
        bare = header.strip()
        if "@" in bare:
            return bare.lower()
        return None

    def _decode_header_value(self, value: str) -> str:
        """Decode RFC2047-encoded header values."""
        try:
            parts = email.header.decode_header(value)
            decoded = ""
            for part, charset in parts:
                if isinstance(part, bytes):
                    decoded += part.decode(charset or "utf-8", errors="replace")
                else:
                    decoded += part
            return decoded
        except Exception:
            return value

    def _extract_body(self, msg: email.message.Message) -> str:
        """Extract plain-text body from email message."""
        body = ""

        if msg.is_multipart():
            for part in msg.walk():
                ctype = part.get_content_type()
                disposition = str(part.get("Content-Disposition", ""))
                if ctype == "text/plain" and "attachment" not in disposition:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break
        else:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="replace")

        return body.strip()

    # ── Webhook Ingestion ──────────────────────────────────────────────────

    async def process_webhook_reply(self, payload: dict[str, Any]) -> ReplySignal:
        """
        Parse a webhook payload into a ReplySignal.

        Supports:
        - Parsio format: {from_email, subject, text, headers, ...}
        - Generic format: {sender, subject, body, thread_id, message_id, ...}

        Raises ValueError on missing required fields.
        """
        # Detect Parsio format
        if "from_email" in payload or ("headers" in payload and "text" in payload):
            return self._parse_parsio_payload(payload)

        # Generic / custom format
        return self._parse_generic_payload(payload)

    def _parse_parsio_payload(self, payload: dict[str, Any]) -> ReplySignal:
        """Parse Parsio webhook format."""
        sender_email = payload.get("from_email") or payload.get("from", {}).get("email")
        headers_raw = payload.get("headers", {})

        in_reply_to = headers_raw.get("In-Reply-To", "") if isinstance(headers_raw, dict) else ""
        references = headers_raw.get("References", "") if isinstance(headers_raw, dict) else ""
        thread_id = in_reply_to or (references.split()[-1] if references else None)

        body = payload.get("text") or payload.get("body") or payload.get("plain_text", "")
        subject = payload.get("subject", "")
        message_id = headers_raw.get("Message-ID", "") if isinstance(headers_raw, dict) else ""

        if not sender_email:
            raise ValueError("Parsio payload missing sender email")

        return ReplySignal(
            channel="email",
            sender_email=sender_email.lower().strip(),
            subject=subject,
            body=body,
            thread_id=thread_id,
            message_id=message_id,
            raw_headers=headers_raw if isinstance(headers_raw, dict) else {},
        )

    def _parse_generic_payload(self, payload: dict[str, Any]) -> ReplySignal:
        """Parse generic webhook payload."""
        channel = payload.get("channel", "email")
        sender_email = payload.get("sender_email") or payload.get("from_email") or payload.get("sender")
        sender_phone = payload.get("sender_phone") or payload.get("from_phone")
        body = payload.get("body") or payload.get("text") or payload.get("content", "")
        subject = payload.get("subject", "")
        thread_id = payload.get("thread_id") or payload.get("in_reply_to")
        message_id = payload.get("message_id", "")

        if not body:
            raise ValueError("Webhook payload missing reply body")

        return ReplySignal(
            channel=channel,
            sender_email=sender_email.lower().strip() if sender_email else None,
            sender_phone=sender_phone,
            subject=subject,
            body=body,
            thread_id=thread_id,
            message_id=message_id,
        )

    # ── Enrollment Matching ────────────────────────────────────────────────

    async def match_to_enrollment(self, signal: ReplySignal) -> tuple[UUID | None, UUID | None]:
        """
        Match a reply signal to a SequenceEnrollment.

        Matching order (first match wins):
        1. thread_id matching in touch_log metadata (message_id field)
        2. sender email matching to lead.email + active enrollment
        3. Subject line pattern matching (e.g., "Re: [original subject]")

        Returns (enrollment_id, sequence_id) or (None, None) if no match.
        """
        # 1. Thread ID match via touch_log metadata
        if signal.thread_id:
            result = await self._match_by_thread_id(signal.thread_id)
            if result[0]:
                logger.debug(
                    "Reply matched via thread_id %s → enrollment %s",
                    signal.thread_id,
                    result[0],
                )
                return result

        # 2. Sender email → lead → active enrollment
        if signal.sender_email:
            result = await self._match_by_sender_email(signal.sender_email)
            if result[0]:
                logger.debug(
                    "Reply matched via sender email %s → enrollment %s",
                    signal.sender_email,
                    result[0],
                )
                return result

        # 3. Subject line pattern matching
        if signal.subject:
            result = await self._match_by_subject(signal.subject, signal.sender_email)
            if result[0]:
                logger.debug("Reply matched via subject pattern → enrollment %s", result[0])
                return result

        logger.info(
            "No enrollment match for reply from %s (thread: %s)",
            signal.sender_email,
            signal.thread_id,
        )
        return None, None

    async def _match_by_thread_id(self, thread_id: str) -> tuple[UUID | None, UUID | None]:
        """Find enrollment via thread_id stored in touch_log metadata."""
        # Clean angle brackets from message IDs
        clean_thread = thread_id.strip("<>")

        result = await self.db.execute(
            select(TouchLog).where(TouchLog.extra_metadata["message_id"].astext == clean_thread)
        )
        log = result.scalar_one_or_none()

        if log and log.sequence_id:
            # Find active enrollment for this lead + sequence
            enr_result = await self.db.execute(
                select(SequenceEnrollment).where(
                    and_(
                        SequenceEnrollment.lead_id == log.lead_id,
                        SequenceEnrollment.sequence_id == log.sequence_id,
                        SequenceEnrollment.status.not_in(
                            [
                                EnrollmentStatus.completed,
                                EnrollmentStatus.failed,
                                EnrollmentStatus.bounced,
                                EnrollmentStatus.unsubscribed,
                            ]
                        ),
                    )
                )
            )
            enrollment = enr_result.scalar_one_or_none()
            if enrollment:
                return enrollment.id, enrollment.sequence_id

        return None, None

    async def _match_by_sender_email(self, sender_email: str) -> tuple[UUID | None, UUID | None]:
        """Match sender email to a lead's active enrollment."""
        lead_result = await self.db.execute(select(Lead).where(Lead.email == sender_email.lower()))
        lead = lead_result.scalar_one_or_none()
        if not lead:
            return None, None

        # Find most recent active enrollment
        enr_result = await self.db.execute(
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
            return enrollment.id, enrollment.sequence_id

        return None, None

    async def _match_by_subject(self, subject: str, sender_email: str | None) -> tuple[UUID | None, UUID | None]:
        """
        Match via subject line pattern.

        Strips "Re:" / "Fwd:" prefixes and searches touch_log for
        emails with matching subject in metadata.
        """
        clean_subject = re.sub(r"^(re:|fwd:|fw:)\s*", "", subject, flags=re.IGNORECASE).strip()
        if len(clean_subject) < 5:
            return None, None

        # Search touch_log metadata for matching subject
        result = await self.db.execute(
            select(TouchLog)
            .where(
                and_(
                    TouchLog.channel == "email",
                    TouchLog.extra_metadata["subject"].astext.ilike(f"%{clean_subject}%"),
                )
            )
            .order_by(TouchLog.created_at.desc())
            .limit(1)
        )
        log = result.scalar_one_or_none()

        if log and log.sequence_id:
            enr_result = await self.db.execute(
                select(SequenceEnrollment).where(
                    and_(
                        SequenceEnrollment.lead_id == log.lead_id,
                        SequenceEnrollment.sequence_id == log.sequence_id,
                        SequenceEnrollment.status.not_in(
                            [
                                EnrollmentStatus.completed,
                                EnrollmentStatus.failed,
                                EnrollmentStatus.bounced,
                                EnrollmentStatus.unsubscribed,
                            ]
                        ),
                    )
                )
            )
            enrollment = enr_result.scalar_one_or_none()
            if enrollment:
                return enrollment.id, enrollment.sequence_id

        return None, None

    # ── Sentiment Analysis ─────────────────────────────────────────────────

    async def analyze_sentiment(self, body: str) -> tuple[ReplySentiment, float]:
        """
        Keyword-based NLP sentiment analysis.

        Evaluation order:
        1. Unsubscribe detection (highest priority — any mention → unsubscribe)
        2. OOO detection
        3. Positive / negative scoring
        4. Neutral fallback

        Returns (ReplySentiment, confidence 0.0-1.0).
        """
        body_lower = body.lower()

        # 1. Unsubscribe (hard check — overrides everything)
        for kw in _UNSUBSCRIBE_KEYWORDS:
            if kw in body_lower:
                return ReplySentiment.unsubscribe, 0.95

        # 2. Out-of-office detection
        ooo_hits = sum(1 for kw in _OOO_KEYWORDS if kw in body_lower)
        if ooo_hits >= 1:
            # Auto-replies often contain both OOO phrase + have short replies
            confidence = min(0.95, 0.7 + (ooo_hits * 0.1))
            return ReplySentiment.out_of_office, confidence

        # 3. Positive / negative scoring
        set(re.findall(r"\b[\w\s']+\b", body_lower))
        body_text = body_lower

        positive_hits = sum(1 for kw in _POSITIVE_KEYWORDS if kw in body_text)
        negative_hits = sum(1 for kw in _NEGATIVE_KEYWORDS if kw in body_text)

        total_hits = positive_hits + negative_hits
        if total_hits == 0:
            return ReplySentiment.neutral, 0.5

        positive_ratio = positive_hits / total_hits

        if positive_ratio >= 0.7:
            confidence = min(0.92, 0.6 + (positive_hits * 0.08))
            return ReplySentiment.positive, confidence
        elif positive_ratio <= 0.3:
            confidence = min(0.92, 0.6 + (negative_hits * 0.08))
            return ReplySentiment.negative, confidence

        # Mixed signals — lean positive if positives > negatives
        if positive_hits > negative_hits:
            return ReplySentiment.positive, 0.55
        elif negative_hits > positive_hits:
            return ReplySentiment.negative, 0.55

        return ReplySentiment.neutral, 0.5

    # ── AI Platform Analysis ───────────────────────────────────────────────

    async def ai_analyze_reply(
        self,
        signal: ReplySignal,
        enrollment_id: UUID,
        lead: Lead,
    ) -> dict[str, Any]:
        """
        Call 3 AI platforms in parallel to analyze the reply and get next-action suggestions.

        1. HubSpot Breeze Data Agent — create engagement note on contact
        2. Apollo AI — log reply engagement + get next-action recommendation
        3. ZoomInfo Copilot — log interaction outcome for account update

        Returns aggregated suggestions dict with keys:
        - hubspot_note_id: str | None
        - apollo_action: str | None
        - zoominfo_update: dict | None
        - combined_next_action: str
        """
        results: dict[str, Any] = {
            "hubspot_note_id": None,
            "apollo_action": None,
            "zoominfo_update": None,
            "combined_next_action": "follow_up",
        }

        tasks = [
            self._create_hubspot_engagement_note(lead, signal),
            self._apollo_log_reply(lead, signal),
            self._zoominfo_log_interaction(lead, signal),
        ]

        platform_results = await asyncio.gather(*tasks, return_exceptions=True)

        hs_result, apollo_result, zi_result = platform_results

        if isinstance(hs_result, dict):
            results["hubspot_note_id"] = hs_result.get("note_id")
        elif isinstance(hs_result, Exception):
            logger.warning("HubSpot AI analyze error: %s", hs_result)

        if isinstance(apollo_result, dict):
            results["apollo_action"] = apollo_result.get("recommended_action")
        elif isinstance(apollo_result, Exception):
            logger.warning("Apollo AI analyze error: %s", apollo_result)

        if isinstance(zi_result, dict):
            results["zoominfo_update"] = zi_result
        elif isinstance(zi_result, Exception):
            logger.warning("ZoomInfo AI analyze error: %s", zi_result)

        # Determine combined next action
        apollo_action = results.get("apollo_action")
        if apollo_action:
            results["combined_next_action"] = apollo_action
        elif results.get("hubspot_note_id"):
            results["combined_next_action"] = "crm_follow_up"

        return results

    async def _create_hubspot_engagement_note(self, lead: Lead, signal: ReplySignal) -> dict[str, Any]:
        """Create a HubSpot engagement note via Breeze Data Agent."""
        if not settings.HUBSPOT_BREEZE_ENABLED or not settings.HUBSPOT_API_KEY:
            return {}

        try:
            # First find the contact ID
            resp = await self._http.post(
                f"{_HUBSPOT_BASE}/crm/v3/objects/contacts/search",
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
                    "limit": 1,
                },
                timeout=15,
            )
            resp.raise_for_status()
            contacts = resp.json().get("results", [])
            if not contacts:
                return {}

            hs_contact_id = contacts[0]["id"]

            # Create engagement note with reply context
            note_body = (
                f"[FortressFlow Reply Detected]\n"
                f"Channel: {signal.channel}\n"
                f"Subject: {signal.subject or 'N/A'}\n"
                f"Body Preview: {signal.body[:500]}\n"
                f"Received: {signal.received_at.isoformat()}"
            )

            note_resp = await self._http.post(
                f"{_HUBSPOT_BASE}/crm/v3/objects/notes",
                headers={"Authorization": f"Bearer {settings.HUBSPOT_API_KEY}"},
                json={
                    "properties": {
                        "hs_note_body": note_body,
                        "hs_timestamp": str(int(signal.received_at.timestamp() * 1000)),
                    },
                    "associations": [
                        {
                            "to": {"id": hs_contact_id},
                            "types": [
                                {
                                    "associationCategory": "HUBSPOT_DEFINED",
                                    "associationTypeId": 202,
                                }
                            ],
                        }
                    ],
                },
                timeout=15,
            )
            note_resp.raise_for_status()
            note_data = note_resp.json()

            return {"note_id": note_data.get("id")}

        except Exception as exc:
            logger.error("HubSpot note creation failed for %s: %s", lead.email, exc)
            return {}

    async def _apollo_log_reply(self, lead: Lead, signal: ReplySignal) -> dict[str, Any]:
        """Log reply engagement to Apollo AI and retrieve next-action suggestion."""
        if not settings.APOLLO_AI_ENABLED or not settings.APOLLO_API_KEY:
            return {}

        try:
            resp = await self._http.post(
                f"{_APOLLO_BASE}/v1/emailer_campaigns/log_engagement",
                json={
                    "api_key": settings.APOLLO_API_KEY,
                    "email": lead.email,
                    "engagement_type": "reply",
                    "metadata": {
                        "source": "fortressflow_sequence",
                        "channel": signal.channel,
                        "subject": signal.subject,
                        "body_preview": signal.body[:300],
                        "received_at": signal.received_at.isoformat(),
                        "first_name": lead.first_name,
                        "company": lead.company,
                        "title": lead.title,
                    },
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()

            return {
                "recommended_action": data.get("recommended_action", "schedule_call"),
                "raw": data,
            }

        except Exception as exc:
            logger.error("Apollo reply log failed for %s: %s", lead.email, exc)
            return {}

    async def _zoominfo_log_interaction(self, lead: Lead, signal: ReplySignal) -> dict[str, Any]:
        """Log reply interaction to ZoomInfo Copilot for account update."""
        if not settings.ZOOMINFO_COPILOT_ENABLED:
            return {}

        try:
            # Get ZoomInfo auth token
            auth_resp = await self._http.post(
                f"{_ZOOMINFO_BASE}/authenticate",
                json={
                    "username": settings.ZOOMINFO_API_KEY,
                    "client_id": settings.ZOOMINFO_CLIENT_ID,
                    "client_secret": settings.ZOOMINFO_CLIENT_SECRET,
                },
                timeout=15,
            )
            auth_resp.raise_for_status()
            token = auth_resp.json().get("jwt", "")

            interaction_resp = await self._http.post(
                f"{_ZOOMINFO_BASE}/engage/v1/interactions",
                headers={"Authorization": f"Bearer {token}"},
                json={
                    "interactions": [
                        {
                            "emailAddress": lead.email,
                            "interactionType": "EMAIL",
                            "outcome": "REPLIED",
                            "timestamp": signal.received_at.isoformat(),
                            "metadata": {
                                "source": "fortressflow_sequence",
                                "channel": signal.channel,
                                "company": lead.company,
                                "title": lead.title,
                                "body_preview": signal.body[:300],
                            },
                        }
                    ]
                },
                timeout=15,
            )
            interaction_resp.raise_for_status()

            return {
                "status": "logged",
                "contact": lead.email,
                "outcome": "REPLIED",
            }

        except Exception as exc:
            logger.error("ZoomInfo interaction log failed for %s: %s", lead.email, exc)
            return {}

    # ── Full Pipeline ──────────────────────────────────────────────────────

    async def process_reply(self, signal: ReplySignal) -> ReplyAnalysisResult:
        """
        Full reply processing pipeline:

        1. Match reply to a SequenceEnrollment
        2. Analyze sentiment
        3. AI analyze (all 3 platforms in parallel)
        4. FSM transition: current → replied → paused
        5. Log touch
        6. Insert into reply_logs table
        7. Return ReplyAnalysisResult

        This method is idempotent via message_id deduplication.
        """
        # Sentiment analysis (no DB needed)
        sentiment, confidence = await self.analyze_sentiment(signal.body)

        # Match to enrollment
        enrollment_id, sequence_id = await self.match_to_enrollment(signal)

        ai_suggestions: dict[str, Any] = {}
        hubspot_note_id: str | None = None
        apollo_action: str | None = None
        zoominfo_update: dict[str, Any] | None = None

        if enrollment_id:
            # Load the enrollment and lead
            enr_result = await self.db.execute(select(SequenceEnrollment).where(SequenceEnrollment.id == enrollment_id))
            enrollment = enr_result.scalar_one_or_none()

            lead_result = (
                await self.db.execute(select(Lead).where(Lead.id == enrollment.lead_id)) if enrollment else None
            )

            lead: Lead | None = lead_result.scalar_one_or_none() if lead_result else None

            if enrollment and lead:
                # AI analysis (non-blocking — log errors internally)
                ai_suggestions = await self.ai_analyze_reply(signal, enrollment_id, lead)
                hubspot_note_id = ai_suggestions.get("hubspot_note_id")
                apollo_action = ai_suggestions.get("apollo_action")
                zoominfo_update = ai_suggestions.get("zoominfo_update")

                # FSM transition: current → replied
                current_state = str(enrollment.status.value)
                try:
                    new_state = handle_reply_signal(current_state)
                    if new_state != current_state:
                        enrollment.status = EnrollmentStatus(new_state)
                        enrollment.last_state_change_at = datetime.now(UTC)
                        logger.info(
                            "Enrollment %s: %s → %s (reply detected)",
                            enrollment_id,
                            current_state,
                            new_state,
                        )
                except Exception as exc:
                    logger.warning("FSM transition failed for enrollment %s: %s", enrollment_id, exc)

                # Auto-pause after reply
                replied_state = str(enrollment.status.value)
                if replied_state == EnrollmentState.replied:
                    try:
                        paused_state = transition(replied_state, EnrollmentState.paused)
                        enrollment.status = EnrollmentStatus(paused_state)
                        enrollment.last_state_change_at = datetime.now(UTC)
                        logger.info(
                            "Enrollment %s auto-paused after reply (sentiment: %s)",
                            enrollment_id,
                            sentiment.value,
                        )
                    except Exception as exc:
                        logger.warning(
                            "Auto-pause transition failed for enrollment %s: %s",
                            enrollment_id,
                            exc,
                        )

                # Log touch
                touch = TouchLog(
                    lead_id=lead.id,
                    channel=signal.channel,
                    action=TouchAction.replied,
                    sequence_id=sequence_id,
                    extra_metadata={
                        "sentiment": sentiment.value,
                        "confidence": confidence,
                        "message_id": signal.message_id,
                        "thread_id": signal.thread_id,
                        "subject": signal.subject,
                        "body_preview": signal.body[:300],
                        "hubspot_note_id": hubspot_note_id,
                        "apollo_action": apollo_action,
                    },
                )
                self.db.add(touch)

                await self.db.flush()

        # Build result
        result = ReplyAnalysisResult(
            signal=signal,
            sentiment=sentiment,
            confidence=confidence,
            ai_suggestions=ai_suggestions,
            matched_enrollment_id=enrollment_id,
            matched_sequence_id=sequence_id,
            hubspot_note_id=hubspot_note_id,
            apollo_action=apollo_action,
            zoominfo_update=zoominfo_update,
        )

        # Log to reply_logs table
        await self.log_reply(signal, result)

        await self.db.commit()

        logger.info(
            "Reply processed: sender=%s sentiment=%s confidence=%.2f enrollment=%s",
            signal.sender_email,
            sentiment.value,
            confidence,
            enrollment_id,
        )

        return result

    async def log_reply(self, signal: ReplySignal, result: ReplyAnalysisResult) -> None:
        """
        Insert a record into the reply_logs table.

        Uses raw SQL via text() to avoid requiring a SQLAlchemy model
        for the reply_logs table (created via migration).
        """
        try:
            await self.db.execute(
                text(
                    """
                    INSERT INTO reply_logs (
                        id, channel, sender_email, sender_phone, subject,
                        thread_id, message_id, body_preview,
                        sentiment, confidence,
                        matched_enrollment_id, matched_sequence_id,
                        hubspot_note_id, apollo_action,
                        ai_suggestions, received_at, created_at
                    ) VALUES (
                        :id, :channel, :sender_email, :sender_phone, :subject,
                        :thread_id, :message_id, :body_preview,
                        :sentiment, :confidence,
                        :matched_enrollment_id, :matched_sequence_id,
                        :hubspot_note_id, :apollo_action,
                        :ai_suggestions::jsonb, :received_at, NOW()
                    )
                    ON CONFLICT (message_id) DO NOTHING
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "channel": signal.channel,
                    "sender_email": signal.sender_email,
                    "sender_phone": signal.sender_phone,
                    "subject": signal.subject,
                    "thread_id": signal.thread_id,
                    "message_id": signal.message_id or str(uuid.uuid4()),
                    "body_preview": signal.body[:500],
                    "sentiment": result.sentiment.value,
                    "confidence": result.confidence,
                    "matched_enrollment_id": (
                        str(result.matched_enrollment_id) if result.matched_enrollment_id else None
                    ),
                    "matched_sequence_id": (str(result.matched_sequence_id) if result.matched_sequence_id else None),
                    "hubspot_note_id": result.hubspot_note_id,
                    "apollo_action": result.apollo_action,
                    "ai_suggestions": __import__("json").dumps(result.ai_suggestions),
                    "received_at": signal.received_at,
                },
            )
        except Exception as exc:
            # Non-fatal — the main processing succeeded; table may not exist yet
            logger.warning("reply_logs insert failed (table may need migration): %s", exc)
