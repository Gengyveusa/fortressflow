from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends
from sqlalchemy import and_, cast, func, select, Date
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.consent import Consent
from app.models.dnc import DNCBlock
from app.models.lead import Lead
from app.models.sequence import (
    EnrollmentStatus,
    Sequence,
    SequenceEnrollment,
    SequenceStatus,
)
from app.models.touch_log import TouchLog
from app.models.warmup import WarmupQueue
from app.schemas.analytics import (
    AnalyticsSequencesResponse,
    DashboardStats,
    DeliverabilityStats,
    SequencePerformance,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardStats)
async def dashboard_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DashboardStats:
    """Aggregate stats: total leads, active consents, touches sent, response rate."""
    total_leads_r = await db.execute(select(func.count(Lead.id)))
    total_leads = total_leads_r.scalar_one()

    active_consents_r = await db.execute(
        select(func.count(Consent.id)).where(Consent.revoked_at.is_(None))
    )
    active_consents = active_consents_r.scalar_one()

    touches_sent_r = await db.execute(
        select(func.count(TouchLog.id)).where(TouchLog.action == "sent")
    )
    touches_sent = touches_sent_r.scalar_one()

    replies_r = await db.execute(
        select(func.count(TouchLog.id)).where(TouchLog.action == "replied")
    )
    replies = replies_r.scalar_one()

    response_rate = (replies / touches_sent * 100) if touches_sent > 0 else 0.0

    return DashboardStats(
        total_leads=total_leads,
        active_consents=active_consents,
        touches_sent=touches_sent,
        response_rate=round(response_rate, 2),
    )


@router.get("/deliverability", response_model=DeliverabilityStats)
async def deliverability_stats(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeliverabilityStats:
    """Bounce rates, spam complaints, warmup progress."""
    total_sent_r = await db.execute(
        select(func.count(TouchLog.id)).where(
            and_(TouchLog.action == "sent", TouchLog.channel == "email")
        )
    )
    total_sent = total_sent_r.scalar_one()

    total_bounced_r = await db.execute(
        select(func.count(TouchLog.id)).where(TouchLog.action == "bounced")
    )
    total_bounced = total_bounced_r.scalar_one()

    spam_r = await db.execute(
        select(func.count(TouchLog.id)).where(TouchLog.action == "complained")
    )
    spam_complaints = spam_r.scalar_one()

    bounce_rate = (total_bounced / total_sent * 100) if total_sent > 0 else 0.0
    spam_rate = (spam_complaints / total_sent * 100) if total_sent > 0 else 0.0

    warmup_active_r = await db.execute(
        select(func.count(WarmupQueue.id)).where(WarmupQueue.status == "pending")
    )
    warmup_active = warmup_active_r.scalar_one()

    warmup_completed_r = await db.execute(
        select(func.count(WarmupQueue.id)).where(WarmupQueue.status == "completed")
    )
    warmup_completed = warmup_completed_r.scalar_one()

    return DeliverabilityStats(
        total_sent=total_sent,
        total_bounced=total_bounced,
        bounce_rate=round(bounce_rate, 2),
        spam_complaints=spam_complaints,
        spam_rate=round(spam_rate, 2),
        warmup_active=warmup_active,
        warmup_completed=warmup_completed,
    )


@router.get("/sequences", response_model=AnalyticsSequencesResponse)
async def sequences_analytics(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AnalyticsSequencesResponse:
    """Per-sequence performance metrics."""
    result = await db.execute(
        select(Sequence).where(
            Sequence.status.in_([SequenceStatus.active, SequenceStatus.paused])
        )
    )
    sequences = result.scalars().unique().all()

    performances = []
    for seq in sequences:
        enrolled_r = await db.execute(
            select(func.count(SequenceEnrollment.id)).where(
                SequenceEnrollment.sequence_id == seq.id
            )
        )
        enrolled = enrolled_r.scalar_one()

        active_r = await db.execute(
            select(func.count(SequenceEnrollment.id)).where(
                SequenceEnrollment.sequence_id == seq.id,
                SequenceEnrollment.status == EnrollmentStatus.active,
            )
        )
        active_count = active_r.scalar_one()

        completed_r = await db.execute(
            select(func.count(SequenceEnrollment.id)).where(
                SequenceEnrollment.sequence_id == seq.id,
                SequenceEnrollment.status == EnrollmentStatus.completed,
            )
        )
        completed_count = completed_r.scalar_one()

        sent_r = await db.execute(
            select(func.count(TouchLog.id)).where(
                TouchLog.sequence_id == seq.id,
                TouchLog.action == "sent",
            )
        )
        sent = sent_r.scalar_one()

        opened_r = await db.execute(
            select(func.count(TouchLog.id)).where(
                TouchLog.sequence_id == seq.id,
                TouchLog.action == "opened",
            )
        )
        opened = opened_r.scalar_one()

        replied_r = await db.execute(
            select(func.count(TouchLog.id)).where(
                TouchLog.sequence_id == seq.id,
                TouchLog.action == "replied",
            )
        )
        replied = replied_r.scalar_one()

        bounced_r = await db.execute(
            select(func.count(TouchLog.id)).where(
                TouchLog.sequence_id == seq.id,
                TouchLog.action == "bounced",
            )
        )
        bounced = bounced_r.scalar_one()

        open_rate = (opened / sent * 100) if sent > 0 else 0.0
        reply_rate = (replied / sent * 100) if sent > 0 else 0.0
        bounce_rate = (bounced / sent * 100) if sent > 0 else 0.0

        performances.append(
            SequencePerformance(
                sequence_id=seq.id,
                sequence_name=seq.name,
                enrolled=enrolled,
                active=active_count,
                completed=completed_count,
                open_rate=round(open_rate, 2),
                reply_rate=round(reply_rate, 2),
                bounce_rate=round(bounce_rate, 2),
            )
        )

    return AnalyticsSequencesResponse(sequences=performances)


# ── New Real Analytics Endpoints ────────────────────────────────────────────


@router.get("/outreach-daily")
async def outreach_daily(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Last 7 days of outreach volume grouped by channel (email/sms/linkedin)."""
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    result = await db.execute(
        select(
            cast(TouchLog.created_at, Date).label("day"),
            TouchLog.channel,
            func.count(TouchLog.id).label("count"),
        )
        .where(
            and_(
                TouchLog.action == "sent",
                TouchLog.created_at >= seven_days_ago,
            )
        )
        .group_by(cast(TouchLog.created_at, Date), TouchLog.channel)
        .order_by(cast(TouchLog.created_at, Date))
    )
    rows = result.all()

    items = [
        {"date": str(row.day), "channel": row.channel, "count": row.count}
        for row in rows
    ]
    return {"items": items}


@router.get("/recent-activity")
async def recent_activity(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """10 most recent touch_log entries with lead name and action type."""
    result = await db.execute(
        select(TouchLog, Lead.first_name, Lead.last_name, Lead.email)
        .join(Lead, TouchLog.lead_id == Lead.id)
        .order_by(TouchLog.created_at.desc())
        .limit(10)
    )
    rows = result.all()

    items = [
        {
            "id": str(row.TouchLog.id),
            "lead_name": f"{row.first_name} {row.last_name}".strip() or row.email,
            "lead_email": row.email,
            "channel": row.TouchLog.channel,
            "action": row.TouchLog.action.value if hasattr(row.TouchLog.action, "value") else str(row.TouchLog.action),
            "sequence_id": str(row.TouchLog.sequence_id) if row.TouchLog.sequence_id else None,
            "created_at": row.TouchLog.created_at.isoformat(),
        }
        for row in rows
    ]
    return {"items": items}


@router.get("/sequence-performance")
async def sequence_performance(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Per-sequence metrics: total sends, opens, replies, bounces from touch_logs."""
    result = await db.execute(
        select(
            TouchLog.sequence_id,
            TouchLog.action,
            func.count(TouchLog.id).label("count"),
        )
        .where(TouchLog.sequence_id.isnot(None))
        .group_by(TouchLog.sequence_id, TouchLog.action)
    )
    rows = result.all()

    # Aggregate per sequence
    seq_data: dict[str, dict[str, int]] = {}
    for row in rows:
        sid = str(row.sequence_id)
        if sid not in seq_data:
            seq_data[sid] = {"sent": 0, "opened": 0, "replied": 0, "bounced": 0}
        action = row.action.value if hasattr(row.action, "value") else str(row.action)
        if action in seq_data[sid]:
            seq_data[sid][action] = row.count

    # Fetch sequence names
    seq_ids = list(seq_data.keys())
    name_map: dict[str, str] = {}
    if seq_ids:
        from sqlalchemy.dialects.postgresql import UUID as PG_UUID
        import uuid

        seq_uuids = [uuid.UUID(s) for s in seq_ids]
        name_result = await db.execute(
            select(Sequence.id, Sequence.name).where(Sequence.id.in_(seq_uuids))
        )
        for row in name_result.all():
            name_map[str(row.id)] = row.name

    items = [
        {
            "sequence_id": sid,
            "sequence_name": name_map.get(sid, "Unknown"),
            "sent": metrics["sent"],
            "opened": metrics["opened"],
            "replied": metrics["replied"],
            "bounced": metrics["bounced"],
            "open_rate": round(metrics["opened"] / metrics["sent"] * 100, 2) if metrics["sent"] > 0 else 0,
            "reply_rate": round(metrics["replied"] / metrics["sent"] * 100, 2) if metrics["sent"] > 0 else 0,
            "bounce_rate": round(metrics["bounced"] / metrics["sent"] * 100, 2) if metrics["sent"] > 0 else 0,
        }
        for sid, metrics in seq_data.items()
    ]
    return {"items": items}


@router.get("/response-trends")
async def response_trends(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Weekly response rates over the last 8 weeks from touch_logs."""
    eight_weeks_ago = datetime.now(UTC) - timedelta(weeks=8)

    # Get weekly sent and replied counts
    sent_result = await db.execute(
        select(
            func.date_trunc("week", TouchLog.created_at).label("week"),
            func.count(TouchLog.id).label("count"),
        )
        .where(
            and_(
                TouchLog.action == "sent",
                TouchLog.created_at >= eight_weeks_ago,
            )
        )
        .group_by(func.date_trunc("week", TouchLog.created_at))
        .order_by(func.date_trunc("week", TouchLog.created_at))
    )
    sent_rows = {str(row.week.date()): row.count for row in sent_result.all()}

    replied_result = await db.execute(
        select(
            func.date_trunc("week", TouchLog.created_at).label("week"),
            func.count(TouchLog.id).label("count"),
        )
        .where(
            and_(
                TouchLog.action == "replied",
                TouchLog.created_at >= eight_weeks_ago,
            )
        )
        .group_by(func.date_trunc("week", TouchLog.created_at))
        .order_by(func.date_trunc("week", TouchLog.created_at))
    )
    replied_rows = {str(row.week.date()): row.count for row in replied_result.all()}

    all_weeks = sorted(set(list(sent_rows.keys()) + list(replied_rows.keys())))
    items = []
    for week in all_weeks:
        sent = sent_rows.get(week, 0)
        replied = replied_rows.get(week, 0)
        rate = round(replied / sent * 100, 2) if sent > 0 else 0.0
        items.append({"week": week, "sent": sent, "replied": replied, "response_rate": rate})

    return {"items": items}


@router.get("/channel-breakdown")
async def channel_breakdown(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Total sends by channel (email/sms/linkedin) for pie chart."""
    result = await db.execute(
        select(
            TouchLog.channel,
            func.count(TouchLog.id).label("count"),
        )
        .where(TouchLog.action == "sent")
        .group_by(TouchLog.channel)
    )
    rows = result.all()
    items = [{"channel": row.channel, "count": row.count} for row in rows]
    return {"items": items}


@router.get("/bounce-daily")
async def bounce_daily(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Last 7 days of bounce counts from touch_logs."""
    seven_days_ago = datetime.now(UTC) - timedelta(days=7)

    result = await db.execute(
        select(
            cast(TouchLog.created_at, Date).label("day"),
            func.count(TouchLog.id).label("count"),
        )
        .where(
            and_(
                TouchLog.action == "bounced",
                TouchLog.created_at >= seven_days_ago,
            )
        )
        .group_by(cast(TouchLog.created_at, Date))
        .order_by(cast(TouchLog.created_at, Date))
    )
    rows = result.all()
    items = [{"date": str(row.day), "count": row.count} for row in rows]
    return {"items": items}


@router.get("/audit-trail")
async def audit_trail(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Compliance audit trail: recent consent events, DNC additions, compliance check results."""
    items = []

    # Recent consent grants/revocations
    consent_result = await db.execute(
        select(Consent, Lead.email)
        .join(Lead, Consent.lead_id == Lead.id)
        .order_by(Consent.created_at.desc())
        .limit(20)
    )
    for row in consent_result.all():
        c = row.Consent
        items.append({
            "id": str(c.id),
            "who": row.email,
            "when": c.granted_at.isoformat() if c.granted_at else c.created_at.isoformat(),
            "channel": c.channel.value if hasattr(c.channel, "value") else str(c.channel),
            "method": c.method.value if hasattr(c.method, "value") else str(c.method),
            "proof": "Consent revoked" if c.revoked_at else "Consent granted",
        })

    # Recent DNC additions
    dnc_result = await db.execute(
        select(DNCBlock)
        .order_by(DNCBlock.created_at.desc())
        .limit(20)
    )
    for d in dnc_result.scalars().all():
        items.append({
            "id": str(d.id),
            "who": d.identifier,
            "when": d.blocked_at.isoformat(),
            "channel": d.channel,
            "method": f"DNC: {d.source}",
            "proof": d.reason,
        })

    # Sort by when descending and limit to 30
    items.sort(key=lambda x: x["when"], reverse=True)
    return {"items": items[:30]}
