"""
AI-powered warmup engine.

Implements a 4-6 week progressive ramp for each sending inbox, using
Platform AI services (HubSpot Breeze, ZoomInfo Copilot, Apollo AI) for:
- Smart seed selection (high-engagement contacts)
- Dynamic ramp adjustments based on reputation signals
- Bi-directional learning loops (outcome feedback → AI platforms)

All sends are gated through can_send_to_lead() from Phase 1 compliance.
"""

import logging
import math
from datetime import UTC, date, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lead import Lead
from app.models.sending_inbox import InboxStatus, SendingInbox
from app.models.warmup import WarmupConfig, WarmupQueue, WarmupSeedLog
from app.services.compliance import can_send_to_lead
from app.services.platform_ai_service import PlatformAIService, SeedRecommendation

logger = logging.getLogger(__name__)


# ── Ramp Schedule ──────────────────────────────────────────────────────


def compute_daily_volume(
    warmup_day: int,
    initial_volume: int = 5,
    ramp_multiplier: float = 1.15,
    target_volume: int = 50,
) -> int:
    """
    Compute target daily send volume for a given warmup day.

    Uses exponential ramp: volume = initial * multiplier^day, capped at target.
    Day 0 = initial_volume, Day N = min(target, initial * 1.15^N).
    """
    raw = initial_volume * (ramp_multiplier**warmup_day)
    return min(target_volume, max(initial_volume, int(math.ceil(raw))))


def compute_ramp_schedule(
    duration_weeks: int = 6,
    initial_volume: int = 5,
    ramp_multiplier: float = 1.15,
    target_volume: int = 50,
) -> list[dict[str, Any]]:
    """
    Generate the full warmup ramp schedule for visibility.

    Returns list of {day, week, daily_volume} dicts.
    """
    total_days = duration_weeks * 7
    schedule = []
    for day in range(total_days):
        vol = compute_daily_volume(day, initial_volume, ramp_multiplier, target_volume)
        schedule.append(
            {
                "day": day,
                "week": day // 7 + 1,
                "daily_volume": vol,
            }
        )
    return schedule


# ── Health Checks ──────────────────────────────────────────────────────


async def check_inbox_health(
    inbox: SendingInbox,
    config: WarmupConfig,
) -> tuple[bool, dict[str, Any]]:
    """
    Evaluate inbox health against safety thresholds.

    Returns (healthy, details_dict). If unhealthy, the inbox should be paused.
    """
    issues: list[str] = []

    if inbox.bounce_rate_7d > config.max_bounce_rate:
        issues.append(f"Bounce rate {inbox.bounce_rate_7d:.3%} exceeds threshold {config.max_bounce_rate:.3%}")

    if inbox.spam_rate_7d > config.max_spam_rate:
        issues.append(f"Spam rate {inbox.spam_rate_7d:.3%} exceeds threshold {config.max_spam_rate:.3%}")

    if inbox.total_sent > 50 and inbox.open_rate_7d < config.min_open_rate:
        issues.append(f"Open rate {inbox.open_rate_7d:.1%} below minimum {config.min_open_rate:.1%}")

    details = {
        "bounce_rate_7d": inbox.bounce_rate_7d,
        "spam_rate_7d": inbox.spam_rate_7d,
        "open_rate_7d": inbox.open_rate_7d,
        "health_score": inbox.health_score,
        "issues": issues,
        "checked_at": datetime.now(UTC).isoformat(),
    }

    healthy = len(issues) == 0
    return healthy, details


# ── Seed Selection ─────────────────────────────────────────────────────


async def select_seeds_for_inbox(
    inbox: SendingInbox,
    target_count: int,
    db: AsyncSession,
    platform_ai: PlatformAIService | None = None,
) -> list[dict[str, Any]]:
    """
    Select warmup seeds for an inbox using AI platforms + compliance checks.

    Priority:
    1. AI-scored candidates from Platform AI services
    2. Leads with existing engagement history
    3. Random eligible leads (fallback)

    Every seed is checked against can_send_to_lead() before inclusion.
    """
    # Gather candidate leads
    result = await db.execute(
        select(Lead)
        .where(Lead.email.isnot(None))
        .order_by(func.random())
        .limit(target_count * 5)  # Over-fetch to account for compliance filtering
    )
    candidates = result.scalars().all()

    if not candidates:
        logger.warning("No candidate leads available for warmup seeds")
        return []

    candidate_emails = [c.email for c in candidates if c.email]
    email_to_lead = {c.email: c for c in candidates if c.email}

    # 1. AI-powered seed selection
    ai_seeds: list[SeedRecommendation] = []
    selection_method = "fallback"

    if platform_ai:
        try:
            ai_seeds = await platform_ai.select_warmup_seeds(
                candidate_emails=candidate_emails,
                batch_size=target_count * 2,
                criteria={"industry": "Dental"},
            )
            if ai_seeds:
                selection_method = ai_seeds[0].platform
        except Exception as exc:
            logger.error("AI seed selection failed, falling back: %s", exc)

    # 2. Build ordered seed list
    selected: list[dict[str, Any]] = []
    used_emails: set[str] = set()

    # First: AI-recommended seeds
    for seed in ai_seeds:
        if seed.email in used_emails or seed.email not in email_to_lead:
            continue

        lead = email_to_lead[seed.email]
        can_send, reason = await can_send_to_lead(lead.id, "email", db)
        if not can_send:
            logger.debug("Seed %s blocked: %s", seed.email, reason)
            continue

        selected.append(
            {
                "lead_id": str(lead.id),
                "email": seed.email,
                "score": seed.score,
                "reason": seed.reason,
                "platform": seed.platform,
                "engagement_likelihood": seed.engagement_likelihood,
            }
        )
        used_emails.add(seed.email)

        if len(selected) >= target_count:
            break

    # Second: fill remaining with random eligible leads
    if len(selected) < target_count:
        for lead in candidates:
            if lead.email in used_emails:
                continue

            can_send, reason = await can_send_to_lead(lead.id, "email", db)
            if not can_send:
                continue

            selected.append(
                {
                    "lead_id": str(lead.id),
                    "email": lead.email,
                    "score": 30.0,
                    "reason": "Fallback random selection",
                    "platform": "fallback",
                    "engagement_likelihood": 0.3,
                }
            )
            used_emails.add(lead.email)

            if len(selected) >= target_count:
                break

    logger.info(
        "Selected %d warmup seeds for inbox %s (method: %s)",
        len(selected),
        inbox.email_address,
        selection_method,
    )

    return selected


# ── Core Warmup Engine ─────────────────────────────────────────────────


async def advance_warmup_for_inbox(
    inbox_id: UUID,
    db: AsyncSession,
    platform_ai: PlatformAIService | None = None,
) -> dict[str, Any]:
    """
    Advance the warmup schedule for a single inbox by one day.

    Steps:
    1. Load inbox and config
    2. Health check (pause if unhealthy)
    3. Compute today's target volume
    4. Select seeds via AI
    5. Create WarmupQueue entry
    6. Record seed selections in WarmupSeedLog
    7. Update inbox warmup_day

    Returns summary dict.
    """
    # Load inbox
    result = await db.execute(select(SendingInbox).where(SendingInbox.id == inbox_id))
    inbox = result.scalar_one_or_none()
    if inbox is None:
        return {"status": "error", "reason": "inbox_not_found"}

    if inbox.status not in (InboxStatus.warming, InboxStatus.active):
        return {"status": "skipped", "reason": f"inbox_status_{inbox.status}"}

    # Load or create config
    result = await db.execute(select(WarmupConfig).where(WarmupConfig.inbox_id == inbox_id))
    config = result.scalar_one_or_none()
    if config is None:
        config = WarmupConfig(
            inbox_id=inbox_id,
            ramp_duration_weeks=settings.WARMUP_DURATION_WEEKS,
            initial_daily_volume=settings.WARMUP_INITIAL_DAILY_VOLUME,
            ramp_multiplier=settings.WARMUP_RAMP_MULTIPLIER,
        )
        db.add(config)
        await db.flush()

    if not config.is_active:
        return {"status": "skipped", "reason": "warmup_paused"}

    # Health check
    healthy, health_details = await check_inbox_health(inbox, config)
    if not healthy:
        inbox.status = InboxStatus.paused
        config.is_active = False
        config.paused_reason = "; ".join(health_details.get("issues", []))
        logger.warning(
            "Inbox %s paused due to health issues: %s",
            inbox.email_address,
            config.paused_reason,
        )
        return {
            "status": "paused",
            "reason": "health_check_failed",
            "details": health_details,
        }

    # Compute target volume
    target_volume = compute_daily_volume(
        warmup_day=inbox.warmup_day,
        initial_volume=config.initial_daily_volume,
        ramp_multiplier=config.ramp_multiplier,
        target_volume=config.target_daily_volume,
    )

    # Check if we've completed the warmup period
    total_warmup_days = config.ramp_duration_weeks * 7
    if inbox.warmup_day >= total_warmup_days:
        inbox.status = InboxStatus.active
        logger.info(
            "Inbox %s warmup complete after %d days, now active",
            inbox.email_address,
            inbox.warmup_day,
        )
        return {"status": "completed", "warmup_days": inbox.warmup_day}

    # Check for existing queue entry today (idempotency)
    today = date.today()
    existing = await db.execute(
        select(WarmupQueue).where(
            and_(
                WarmupQueue.inbox_id == inbox_id,
                WarmupQueue.date == today,
            )
        )
    )
    if existing.scalar_one_or_none() is not None:
        return {"status": "already_scheduled", "date": today.isoformat()}

    # Select seeds
    seeds = await select_seeds_for_inbox(
        inbox=inbox,
        target_count=target_volume,
        db=db,
        platform_ai=platform_ai,
    )

    # Determine selection method
    selection_method = "fallback"
    if seeds and seeds[0]["platform"] != "fallback":
        selection_method = seeds[0]["platform"]

    # Create warmup queue entry
    queue_entry = WarmupQueue(
        inbox_id=inbox_id,
        date=today,
        emails_sent=0,
        emails_target=target_volume,
        status="pending",
        seed_selection_method=selection_method,
        seed_criteria={"industry": "Dental", "ai_enabled": platform_ai is not None},
        seed_lead_ids=[s["lead_id"] for s in seeds],
    )
    db.add(queue_entry)

    # Record seed logs for learning
    for seed in seeds:
        if seed["lead_id"]:
            seed_log = WarmupSeedLog(
                inbox_id=inbox_id,
                lead_id=UUID(seed["lead_id"]),
                warmup_date=today,
                selected_by=seed["platform"],
                selection_score=seed["score"],
                selection_reason=seed["reason"],
            )
            db.add(seed_log)

    # Advance warmup day + update daily limit
    inbox.warmup_day += 1
    inbox.daily_limit = target_volume
    inbox.daily_sent = 0  # Reset daily counter

    await db.flush()

    logger.info(
        "Warmup day %d for inbox %s: target=%d, seeds=%d (method: %s)",
        inbox.warmup_day,
        inbox.email_address,
        target_volume,
        len(seeds),
        selection_method,
    )

    return {
        "status": "scheduled",
        "inbox": inbox.email_address,
        "warmup_day": inbox.warmup_day,
        "target_volume": target_volume,
        "seeds_selected": len(seeds),
        "selection_method": selection_method,
        "date": today.isoformat(),
    }


async def run_warmup_cycle(db: AsyncSession) -> dict[str, Any]:
    """
    Run the warmup cycle for ALL warming inboxes.

    Called by Celery beat daily. Advances each inbox by one warmup day.
    """
    # Load all warming/active inboxes
    result = await db.execute(
        select(SendingInbox).where(SendingInbox.status.in_([InboxStatus.warming, InboxStatus.active]))
    )
    inboxes = result.scalars().all()

    if not inboxes:
        return {"status": "no_inboxes", "processed": 0}

    platform_ai = PlatformAIService()
    results: list[dict[str, Any]] = []

    for inbox in inboxes:
        try:
            result = await advance_warmup_for_inbox(
                inbox_id=inbox.id,
                db=db,
                platform_ai=platform_ai,
            )
            results.append({"inbox": inbox.email_address, **result})
        except Exception as exc:
            logger.error("Warmup failed for inbox %s: %s", inbox.email_address, exc)
            results.append(
                {
                    "inbox": inbox.email_address,
                    "status": "error",
                    "error": str(exc),
                }
            )

    summary = {
        "total_inboxes": len(inboxes),
        "processed": len(results),
        "scheduled": sum(1 for r in results if r.get("status") == "scheduled"),
        "paused": sum(1 for r in results if r.get("status") == "paused"),
        "completed": sum(1 for r in results if r.get("status") == "completed"),
        "errors": sum(1 for r in results if r.get("status") == "error"),
        "details": results,
    }

    logger.info(
        "Warmup cycle complete: %d scheduled, %d paused, %d completed, %d errors",
        summary["scheduled"],
        summary["paused"],
        summary["completed"],
        summary["errors"],
    )

    return summary


# ── Learning Loop Processor ────────────────────────────────────────────


async def process_warmup_feedback(db: AsyncSession) -> dict[str, Any]:
    """
    Process warmup outcomes and send feedback to AI platforms.

    Finds WarmupSeedLog entries where feedback hasn't been sent yet,
    then pushes outcome data back to the originating AI platform.
    """
    platform_ai = PlatformAIService()

    # Find seed logs with outcomes but no feedback sent
    lookback = date.today() - timedelta(days=settings.WARMUP_AI_LEARNING_WINDOW_DAYS)
    result = await db.execute(
        select(WarmupSeedLog).where(
            and_(
                WarmupSeedLog.feedback_sent.is_(False),
                WarmupSeedLog.warmup_date >= lookback,
                # At least one outcome recorded
                (
                    WarmupSeedLog.opened.is_(True)
                    | WarmupSeedLog.replied.is_(True)
                    | WarmupSeedLog.bounced.is_(True)
                    | WarmupSeedLog.complained.is_(True)
                ),
            )
        )
    )
    seed_logs = result.scalars().all()

    if not seed_logs:
        return {"status": "no_pending_feedback", "processed": 0}

    sent_count = 0
    failed_count = 0

    for seed_log in seed_logs:
        outcomes = {
            "opened": seed_log.opened,
            "replied": seed_log.replied,
            "bounced": seed_log.bounced,
            "complained": seed_log.complained,
        }

        # Load the lead to get email
        lead_result = await db.execute(select(Lead).where(Lead.id == seed_log.lead_id))
        lead = lead_result.scalar_one_or_none()
        if not lead:
            continue

        success = await platform_ai.send_outcome_feedback(
            platform=seed_log.selected_by,
            contact_email=lead.email,
            outcomes=outcomes,
        )

        if success:
            seed_log.feedback_sent = True
            seed_log.feedback_payload = outcomes
            sent_count += 1
        else:
            failed_count += 1

    await db.flush()

    logger.info(
        "Warmup feedback loop: %d sent, %d failed out of %d",
        sent_count,
        failed_count,
        len(seed_logs),
    )

    return {
        "status": "processed",
        "total": len(seed_logs),
        "sent": sent_count,
        "failed": failed_count,
    }


# ── Reputation Score Calculator ────────────────────────────────────────


async def recalculate_inbox_health_scores(db: AsyncSession) -> int:
    """
    Recalculate health_score for all inboxes based on 7-day rolling metrics.

    health_score = 100 - (bounce_penalty + spam_penalty + low_open_penalty)
    """
    result = await db.execute(select(SendingInbox))
    inboxes = result.scalars().all()
    updated = 0

    for inbox in inboxes:
        if inbox.total_sent == 0:
            inbox.health_score = 100.0
            continue

        # Penalty calculations
        bounce_penalty = min(50.0, inbox.bounce_rate_7d * 1000)  # 5% bounce = 50 pts
        spam_penalty = min(40.0, inbox.spam_rate_7d * 40000)  # 0.1% spam = 40 pts
        low_open_penalty = max(0.0, (0.15 - inbox.open_rate_7d) * 100) if inbox.total_sent > 50 else 0.0

        score = 100.0 - bounce_penalty - spam_penalty - low_open_penalty
        inbox.health_score = max(0.0, min(100.0, score))
        updated += 1

    await db.flush()
    logger.info("Recalculated health scores for %d inboxes", updated)
    return updated
