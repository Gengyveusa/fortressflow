from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.domain import SendingDomain
from app.models.warmup import WarmupQueue
from app.schemas.deliverability import DomainCreate, DomainResponse, WarmupStatus

router = APIRouter(prefix="/deliverability", tags=["deliverability"])


@router.get("/domains", response_model=list[DomainResponse])
async def list_domains(
    db: AsyncSession = Depends(get_db),
) -> list[DomainResponse]:
    """List all sending domains with health scores."""
    result = await db.execute(
        select(SendingDomain).order_by(SendingDomain.created_at.desc())
    )
    domains = result.scalars().all()
    return [DomainResponse.model_validate(d) for d in domains]


@router.post("/domains", response_model=DomainResponse, status_code=status.HTTP_201_CREATED)
async def add_domain(
    body: DomainCreate,
    db: AsyncSession = Depends(get_db),
) -> DomainResponse:
    """Add a new sending domain."""
    existing = await db.execute(
        select(SendingDomain).where(SendingDomain.domain == body.domain)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Domain already exists",
        )

    domain = SendingDomain(domain=body.domain)
    db.add(domain)
    await db.flush()
    await db.refresh(domain)
    return DomainResponse.model_validate(domain)


@router.get("/warmup", response_model=list[WarmupStatus])
async def warmup_status(
    db: AsyncSession = Depends(get_db),
) -> list[WarmupStatus]:
    """Get warmup queue status and progress."""
    result = await db.execute(
        select(WarmupQueue).order_by(WarmupQueue.date.desc()).limit(50)
    )
    entries = result.scalars().all()
    return [
        WarmupStatus(
            inbox_id=e.inbox_id,
            date=e.date.isoformat(),
            emails_sent=e.emails_sent,
            emails_target=e.emails_target,
            bounce_rate=e.bounce_rate,
            spam_rate=e.spam_rate,
            open_rate=e.open_rate,
            status=e.status,
        )
        for e in entries
    ]
