"""
Deliverability API — domain management, inbox rotation, warmup monitoring,
DNS setup instructions, and AI-powered dashboard.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user
from app.database import get_db
from app.models.user import User
from app.models.domain import SendingDomain
from app.models.sending_inbox import InboxStatus, SendingInbox
from app.models.warmup import WarmupConfig, WarmupQueue
from app.schemas.deliverability import (
    DeliverabilityDashboard,
    DomainCreate,
    DomainDNSInstructions,
    DomainResponse,
    InboxCreate,
    InboxResponse,
    RampScheduleEntry,
    WarmupConfigCreate,
    WarmupConfigResponse,
    WarmupStatus,
)

router = APIRouter(prefix="/deliverability", tags=["deliverability"])


# ── Domains ────────────────────────────────────────────────────────────


@router.get("/domains", response_model=list[DomainResponse])
async def list_domains(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[DomainResponse]:
    """List all sending domains with health scores and verification status."""
    result = await db.execute(select(SendingDomain).order_by(SendingDomain.created_at.desc()))
    domains = result.scalars().all()
    return [DomainResponse.model_validate(d) for d in domains]


@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def add_domain(
    body: DomainCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DomainResponse:
    """Add a new sending domain and initiate SES verification."""
    existing = await db.execute(select(SendingDomain).where(SendingDomain.domain == body.domain))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Domain already exists",
        )

    domain = SendingDomain(domain=body.domain)
    db.add(domain)
    await db.flush()

    # Trigger SES domain verification
    from app.services.ses_service import SESInfrastructureService

    ses = SESInfrastructureService()
    verification = await ses.verify_domain(body.domain)
    if verification.success:
        domain.ses_dkim_tokens = verification.dkim_tokens

    await db.refresh(domain)
    return DomainResponse.model_validate(domain)


@router.get("/domains/{domain_name}/dns", response_model=DomainDNSInstructions)
async def get_dns_instructions(
    domain_name: str,
    current_user: User = Depends(get_current_user),
) -> DomainDNSInstructions:
    """Get DNS record setup instructions for SPF, DKIM, DMARC, and BIMI."""
    from app.services.ses_service import SESInfrastructureService

    ses = SESInfrastructureService()
    instructions = await ses.get_dns_setup_instructions(domain_name)
    return DomainDNSInstructions(**instructions)


# ── Sending Inboxes ───────────────────────────────────────────────────


@router.get("/inboxes", response_model=list[InboxResponse])
async def list_inboxes(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[InboxResponse]:
    """List all sending inboxes with status and health metrics."""
    result = await db.execute(select(SendingInbox).order_by(SendingInbox.created_at.desc()))
    inboxes = result.scalars().all()
    return [InboxResponse.model_validate(i) for i in inboxes]


@router.post("/inboxes", response_model=InboxResponse, status_code=status.HTTP_201_CREATED)
async def create_inbox(
    body: InboxCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> InboxResponse:
    """Create a new sending inbox and initiate SES email identity verification."""
    # Check for duplicate
    existing = await db.execute(select(SendingInbox).where(SendingInbox.email_address == body.email_address))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Inbox already exists",
        )

    # Enforce max identities
    count_result = await db.execute(select(SendingInbox))
    count = len(count_result.scalars().all())
    from app.config import settings

    if count >= settings.MAX_SENDING_IDENTITIES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum {settings.MAX_SENDING_IDENTITIES} sending identities allowed",
        )

    inbox = SendingInbox(
        email_address=body.email_address,
        display_name=body.display_name,
        domain=body.domain,
        status=InboxStatus.warming,
    )
    db.add(inbox)
    await db.flush()

    # Trigger SES email identity verification
    from app.services.ses_service import SESInfrastructureService

    ses = SESInfrastructureService()
    verification = await ses.verify_email_identity(body.email_address)
    if verification.success:
        inbox.ses_identity_arn = verification.identity_arn

    # Auto-create warmup config
    config = WarmupConfig(
        inbox_id=inbox.id,
        ramp_duration_weeks=settings.WARMUP_DURATION_WEEKS,
        initial_daily_volume=settings.WARMUP_INITIAL_DAILY_VOLUME,
        ramp_multiplier=settings.WARMUP_RAMP_MULTIPLIER,
    )
    db.add(config)

    await db.refresh(inbox)
    return InboxResponse.model_validate(inbox)


@router.post("/inboxes/{inbox_id}/pause")
async def pause_inbox(
    inbox_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Pause a sending inbox (stops warmup and sending)."""
    result = await db.execute(select(SendingInbox).where(SendingInbox.id == inbox_id))
    inbox = result.scalar_one_or_none()
    if inbox is None:
        raise HTTPException(status_code=404, detail="Inbox not found")

    inbox.status = InboxStatus.paused

    # Also pause warmup config
    config_result = await db.execute(select(WarmupConfig).where(WarmupConfig.inbox_id == inbox_id))
    config = config_result.scalar_one_or_none()
    if config:
        config.is_active = False
        config.paused_reason = "Manually paused"

    return {"status": "paused", "inbox": inbox.email_address}


@router.post("/inboxes/{inbox_id}/resume")
async def resume_inbox(
    inbox_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resume a paused sending inbox."""
    result = await db.execute(select(SendingInbox).where(SendingInbox.id == inbox_id))
    inbox = result.scalar_one_or_none()
    if inbox is None:
        raise HTTPException(status_code=404, detail="Inbox not found")

    inbox.status = InboxStatus.warming if inbox.warmup_day < 42 else InboxStatus.active

    config_result = await db.execute(select(WarmupConfig).where(WarmupConfig.inbox_id == inbox_id))
    config = config_result.scalar_one_or_none()
    if config:
        config.is_active = True
        config.paused_reason = None

    return {"status": inbox.status, "inbox": inbox.email_address}


# ── Warmup ─────────────────────────────────────────────────────────────


@router.get("/warmup", response_model=list[WarmupStatus])
async def warmup_status(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[WarmupStatus]:
    """Get warmup queue status and progress."""
    result = await db.execute(select(WarmupQueue).order_by(WarmupQueue.date.desc()).limit(50))
    entries = result.scalars().all()
    return [
        WarmupStatus(
            inbox_id=str(e.inbox_id),
            date=e.date.isoformat(),
            emails_sent=e.emails_sent,
            emails_target=e.emails_target,
            bounce_rate=e.bounce_rate,
            spam_rate=e.spam_rate,
            open_rate=e.open_rate,
            reply_rate=e.reply_rate,
            status=e.status,
            seed_selection_method=e.seed_selection_method,
        )
        for e in entries
    ]


@router.get("/warmup/config/{inbox_id}", response_model=WarmupConfigResponse)
async def get_warmup_config(
    inbox_id: UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WarmupConfigResponse:
    """Get warmup configuration for an inbox."""
    result = await db.execute(select(WarmupConfig).where(WarmupConfig.inbox_id == inbox_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Warmup config not found")
    return WarmupConfigResponse.model_validate(config)


@router.put("/warmup/config/{inbox_id}", response_model=WarmupConfigResponse)
async def update_warmup_config(
    inbox_id: UUID,
    body: WarmupConfigCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> WarmupConfigResponse:
    """Update warmup configuration for an inbox."""
    result = await db.execute(select(WarmupConfig).where(WarmupConfig.inbox_id == inbox_id))
    config = result.scalar_one_or_none()
    if config is None:
        raise HTTPException(status_code=404, detail="Warmup config not found")

    config.ramp_duration_weeks = body.ramp_duration_weeks
    config.initial_daily_volume = body.initial_daily_volume
    config.target_daily_volume = body.target_daily_volume
    config.ramp_multiplier = body.ramp_multiplier
    config.max_bounce_rate = body.max_bounce_rate
    config.max_spam_rate = body.max_spam_rate
    config.min_open_rate = body.min_open_rate

    await db.flush()
    await db.refresh(config)
    return WarmupConfigResponse.model_validate(config)


@router.get("/warmup/ramp-schedule", response_model=list[RampScheduleEntry])
async def get_ramp_schedule(
    duration_weeks: int = 6,
    initial_volume: int = 5,
    target_volume: int = 50,
    ramp_multiplier: float = 1.15,
    current_user: User = Depends(get_current_user),
) -> list[RampScheduleEntry]:
    """Preview the warmup ramp schedule for given parameters."""
    from app.services.warmup_ai import compute_ramp_schedule

    schedule = compute_ramp_schedule(
        duration_weeks=duration_weeks,
        initial_volume=initial_volume,
        ramp_multiplier=ramp_multiplier,
        target_volume=target_volume,
    )
    return [RampScheduleEntry(**entry) for entry in schedule]


# ── Dashboard ──────────────────────────────────────────────────────────


@router.get("/dashboard", response_model=DeliverabilityDashboard)
async def deliverability_dashboard(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> DeliverabilityDashboard:
    """Comprehensive deliverability status dashboard."""
    from app.services.deliverability_router import DeliverabilityRouter

    router_svc = DeliverabilityRouter(db)
    data = await router_svc.get_deliverability_dashboard()
    return DeliverabilityDashboard(**data)
