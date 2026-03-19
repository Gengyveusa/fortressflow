from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.consent import Consent
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
