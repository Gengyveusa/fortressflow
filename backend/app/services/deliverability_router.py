"""
Deliverability router — the outbound traffic control layer.

Manages:
- Round-robin rotation across 5-10 sending identities
- Per-identity throttling and daily volume caps
- 300-400 total email touches/day across all identities
- Health-aware routing (skip unhealthy inboxes)
- SES event processing for reputation tracking

All sends are gated through can_send_to_lead() via the warmup/sequence engine.
"""

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.domain import SendingDomain
from app.models.sending_inbox import InboxStatus, SendingInbox
from app.models.warmup import WarmupQueue, WarmupSeedLog
from app.services.email_service import EmailResult, send_email

logger = logging.getLogger(__name__)


class DeliverabilityRouter:
    """
    Routes outbound emails through the healthiest sending identity
    using round-robin rotation with health-aware fallback.
    """

    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._rotation_index = 0  # Simple in-memory rotation counter

    async def get_available_inboxes(self) -> list[SendingInbox]:
        """
        Load all active/warming inboxes that haven't hit their daily limit,
        ordered by health_score descending (healthiest first).
        """
        result = await self._db.execute(
            select(SendingInbox)
            .where(
                and_(
                    SendingInbox.status.in_([InboxStatus.active, InboxStatus.warming]),
                    SendingInbox.ses_verified.is_(True),
                    SendingInbox.daily_sent < SendingInbox.daily_limit,
                )
            )
            .order_by(SendingInbox.health_score.desc())
        )
        return list(result.scalars().all())

    async def select_next_inbox(self) -> SendingInbox | None:
        """
        Round-robin select the next available inbox.

        Skips inboxes that are paused, over daily limit, or have low health.
        Prioritizes healthiest inboxes.
        """
        inboxes = await self.get_available_inboxes()
        if not inboxes:
            logger.warning("No available sending inboxes for routing")
            return None

        # Check total daily cap across all identities
        total_sent_today = sum(i.daily_sent for i in inboxes)
        if total_sent_today >= settings.DAILY_WARMUP_VOLUME_CAP:
            logger.info(
                "Daily volume cap reached: %d/%d",
                total_sent_today,
                settings.DAILY_WARMUP_VOLUME_CAP,
            )
            return None

        # Round-robin with health awareness
        # Skip any inbox with health_score < 50
        healthy_inboxes = [i for i in inboxes if i.health_score >= 50]
        if not healthy_inboxes:
            logger.warning("No healthy inboxes available (all below score 50)")
            return None

        # Rotate through healthy inboxes
        idx = self._rotation_index % len(healthy_inboxes)
        self._rotation_index += 1
        selected = healthy_inboxes[idx]

        logger.debug(
            "Selected inbox %s (health: %.1f, sent: %d/%d)",
            selected.email_address,
            selected.health_score,
            selected.daily_sent,
            selected.daily_limit,
        )
        return selected

    async def route_and_send(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        plain_body: str,
        reply_to: str | None = None,
        unsubscribe_url: str | None = None,
        tracking_url: str | None = None,
        tags: dict[str, str] | None = None,
    ) -> tuple[EmailResult, str | None]:
        """
        Route an email through the next available sending identity and send it.

        Returns (EmailResult, inbox_email_used) tuple.
        """
        inbox = await self.select_next_inbox()
        if inbox is None:
            return (
                EmailResult(success=False, error="No available sending inboxes"),
                None,
            )

        # Send via the selected identity
        result = await send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
            from_email=inbox.email_address,
            reply_to=reply_to,
            unsubscribe_url=unsubscribe_url,
            tracking_url=tracking_url,
            tags={
                **(tags or {}),
                "inbox_id": str(inbox.id),
                "warmup_day": str(inbox.warmup_day),
            },
        )

        if result.success:
            # Increment daily counter + lifetime counter
            inbox.daily_sent += 1
            inbox.total_sent += 1
            await self._db.flush()
            logger.info(
                "Routed email to %s via %s (message_id: %s)",
                to_email,
                inbox.email_address,
                result.message_id,
            )
        else:
            logger.error(
                "Send via %s failed for %s: %s",
                inbox.email_address,
                to_email,
                result.error,
            )

        return result, inbox.email_address

    # ── SES Event Processing ───────────────────────────────────────────

    async def process_ses_event(
        self, event_type: str, inbox_email: str, recipient_email: str
    ) -> None:
        """
        Process an SES event (bounce, complaint, delivery, open, click)
        and update inbox + seed log metrics.
        """
        # Find the inbox
        result = await self._db.execute(
            select(SendingInbox).where(
                SendingInbox.email_address == inbox_email
            )
        )
        inbox = result.scalar_one_or_none()

        if inbox is None:
            logger.warning(
                "SES event for unknown inbox %s: %s", inbox_email, event_type
            )
            return

        if event_type == "Bounce":
            inbox.total_bounced += 1
            await self._update_seed_outcome(
                inbox.id, recipient_email, bounced=True
            )
        elif event_type == "Complaint":
            inbox.total_complaints += 1
            await self._update_seed_outcome(
                inbox.id, recipient_email, complained=True
            )
        elif event_type == "Open":
            inbox.total_opens += 1
            await self._update_seed_outcome(
                inbox.id, recipient_email, opened=True
            )
        elif event_type == "Click":
            # Clicks imply opens
            inbox.total_opens += 1
        elif event_type == "Reply":
            inbox.total_replies += 1
            await self._update_seed_outcome(
                inbox.id, recipient_email, replied=True
            )

        # Recalculate 7-day rolling rates
        await self._recalculate_rolling_rates(inbox)
        await self._db.flush()

    async def _update_seed_outcome(
        self,
        inbox_id: UUID,
        recipient_email: str,
        opened: bool = False,
        replied: bool = False,
        bounced: bool = False,
        complained: bool = False,
    ) -> None:
        """Update WarmupSeedLog with outcome data for learning loops."""
        # Find the lead by email
        lead_result = await self._db.execute(
            select(SendingInbox).where(SendingInbox.id == inbox_id)
        )

        from app.models.lead import Lead

        lead_result = await self._db.execute(
            select(Lead).where(Lead.email == recipient_email)
        )
        lead = lead_result.scalar_one_or_none()
        if not lead:
            return

        # Find most recent seed log for this inbox + lead
        result = await self._db.execute(
            select(WarmupSeedLog)
            .where(
                and_(
                    WarmupSeedLog.inbox_id == inbox_id,
                    WarmupSeedLog.lead_id == lead.id,
                )
            )
            .order_by(WarmupSeedLog.warmup_date.desc())
            .limit(1)
        )
        seed_log = result.scalar_one_or_none()
        if not seed_log:
            return

        if opened:
            seed_log.opened = True
        if replied:
            seed_log.replied = True
        if bounced:
            seed_log.bounced = True
        if complained:
            seed_log.complained = True

    async def _recalculate_rolling_rates(self, inbox: SendingInbox) -> None:
        """Recalculate 7-day rolling rates for an inbox."""
        if inbox.total_sent == 0:
            return

        # Simple lifetime-based rates (will be refined with time-windowed queries)
        inbox.bounce_rate_7d = inbox.total_bounced / max(1, inbox.total_sent)
        inbox.spam_rate_7d = inbox.total_complaints / max(1, inbox.total_sent)
        inbox.open_rate_7d = inbox.total_opens / max(1, inbox.total_sent)
        inbox.reply_rate_7d = inbox.total_replies / max(1, inbox.total_sent)

        # Health score recalculation
        bounce_penalty = min(50.0, inbox.bounce_rate_7d * 1000)
        spam_penalty = min(40.0, inbox.spam_rate_7d * 40000)
        low_open_penalty = (
            max(0.0, (0.15 - inbox.open_rate_7d) * 100)
            if inbox.total_sent > 50
            else 0.0
        )
        inbox.health_score = max(
            0.0, min(100.0, 100.0 - bounce_penalty - spam_penalty - low_open_penalty)
        )

    # ── Daily Reset ────────────────────────────────────────────────────

    async def reset_daily_counters(self) -> int:
        """Reset daily_sent counters for all inboxes. Called by scheduler at midnight."""
        result = await self._db.execute(
            update(SendingInbox)
            .where(SendingInbox.daily_sent > 0)
            .values(daily_sent=0)
        )
        count = result.rowcount or 0
        logger.info("Reset daily counters for %d inboxes", count)
        return count

    # ── Domain Monitoring ──────────────────────────────────────────────

    async def update_domain_metrics(self) -> int:
        """Aggregate inbox metrics to domain level."""
        result = await self._db.execute(select(SendingDomain))
        domains = result.scalars().all()
        updated = 0

        for domain in domains:
            # Sum metrics from all inboxes on this domain
            inbox_result = await self._db.execute(
                select(SendingInbox).where(SendingInbox.domain == domain.domain)
            )
            inboxes = inbox_result.scalars().all()

            if not inboxes:
                continue

            domain.total_sent = sum(i.total_sent for i in inboxes)
            domain.total_bounced = sum(i.total_bounced for i in inboxes)
            domain.total_complaints = sum(i.total_complaints for i in inboxes)

            # Weighted average health score
            if domain.total_sent > 0:
                weighted_health = sum(
                    i.health_score * i.total_sent for i in inboxes
                ) / domain.total_sent
                domain.health_score = weighted_health

            # Warmup progress: average across inboxes
            warming_inboxes = [
                i for i in inboxes if i.status == InboxStatus.warming
            ]
            if warming_inboxes:
                max_days = settings.WARMUP_DURATION_WEEKS * 7
                avg_progress = sum(i.warmup_day for i in warming_inboxes) / len(
                    warming_inboxes
                )
                domain.warmup_progress = min(100.0, (avg_progress / max_days) * 100)
            elif all(i.status == InboxStatus.active for i in inboxes):
                domain.warmup_progress = 100.0

            updated += 1

        await self._db.flush()
        logger.info("Updated domain metrics for %d domains", updated)
        return updated

    # ── Status Dashboard ───────────────────────────────────────────────

    async def get_deliverability_dashboard(self) -> dict[str, Any]:
        """
        Return a comprehensive deliverability status dashboard.
        """
        inboxes = await self.get_available_inboxes()

        # Also get all inboxes regardless of status
        all_result = await self._db.execute(select(SendingInbox))
        all_inboxes = all_result.scalars().all()

        domain_result = await self._db.execute(select(SendingDomain))
        domains = domain_result.scalars().all()

        total_daily_sent = sum(i.daily_sent for i in all_inboxes)
        total_daily_limit = sum(i.daily_limit for i in all_inboxes)

        return {
            "summary": {
                "total_inboxes": len(all_inboxes),
                "active_inboxes": sum(
                    1 for i in all_inboxes if i.status == InboxStatus.active
                ),
                "warming_inboxes": sum(
                    1 for i in all_inboxes if i.status == InboxStatus.warming
                ),
                "paused_inboxes": sum(
                    1 for i in all_inboxes if i.status == InboxStatus.paused
                ),
                "total_sent_today": total_daily_sent,
                "total_daily_limit": total_daily_limit,
                "daily_cap": settings.DAILY_WARMUP_VOLUME_CAP,
                "capacity_pct": (
                    total_daily_sent / settings.DAILY_WARMUP_VOLUME_CAP * 100
                    if settings.DAILY_WARMUP_VOLUME_CAP
                    else 0
                ),
            },
            "inboxes": [
                {
                    "id": str(i.id),
                    "email": i.email_address,
                    "status": i.status,
                    "health_score": i.health_score,
                    "warmup_day": i.warmup_day,
                    "daily_sent": i.daily_sent,
                    "daily_limit": i.daily_limit,
                    "bounce_rate_7d": i.bounce_rate_7d,
                    "spam_rate_7d": i.spam_rate_7d,
                    "open_rate_7d": i.open_rate_7d,
                    "ses_verified": i.ses_verified,
                    "dkim_verified": i.dkim_verified,
                }
                for i in all_inboxes
            ],
            "domains": [
                {
                    "id": str(d.id),
                    "domain": d.domain,
                    "health_score": d.health_score,
                    "warmup_progress": d.warmup_progress,
                    "total_sent": d.total_sent,
                    "spf_verified": d.spf_verified,
                    "dkim_verified": d.dkim_verified,
                    "dmarc_verified": d.dmarc_verified,
                    "bimi_verified": d.bimi_verified,
                }
                for d in domains
            ],
        }
