from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.lead import Lead
from app.models.sequence import (
    EnrollmentStatus,
    Sequence,
    SequenceEnrollment,
    SequenceStatus,
    SequenceStep,
    StepType,
)
from app.models.touch_log import TouchLog
from app.schemas.sequence import (
    EnrollmentResponse,
    EnrollRequest,
    SequenceAnalyticsResponse,
    SequenceCreate,
    SequenceListResponse,
    SequenceResponse,
    SequenceStepCreate,
    SequenceStepResponse,
    SequenceUpdate,
    StepAnalytics,
)
from app.services import compliance as compliance_svc

router = APIRouter(prefix="/sequences", tags=["sequences"])


def _sequence_to_response(seq: Sequence) -> SequenceResponse:
    return SequenceResponse(
        id=seq.id,
        name=seq.name,
        description=seq.description,
        status=seq.status.value if isinstance(seq.status, SequenceStatus) else seq.status,
        created_at=seq.created_at,
        updated_at=seq.updated_at,
        steps=[SequenceStepResponse.model_validate(s) for s in seq.steps],
        enrolled_count=len(seq.enrollments),
    )


@router.post("/", response_model=SequenceResponse, status_code=status.HTTP_201_CREATED)
async def create_sequence(
    body: SequenceCreate,
    db: AsyncSession = Depends(get_db),
) -> SequenceResponse:
    """Create a new sequence."""
    seq = Sequence(
        name=body.name,
        description=body.description,
        status=SequenceStatus(body.status),
    )
    db.add(seq)
    await db.flush()
    await db.refresh(seq)
    return _sequence_to_response(seq)


@router.get("/", response_model=SequenceListResponse)
async def list_sequences(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
) -> SequenceListResponse:
    """List all sequences with pagination."""
    total_result = await db.execute(select(func.count(Sequence.id)))
    total = total_result.scalar_one()

    offset = (page - 1) * page_size
    result = await db.execute(
        select(Sequence).order_by(Sequence.created_at.desc()).offset(offset).limit(page_size)
    )
    sequences = result.scalars().unique().all()

    return SequenceListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[_sequence_to_response(s) for s in sequences],
    )


@router.get("/{sequence_id}", response_model=SequenceResponse)
async def get_sequence(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SequenceResponse:
    """Retrieve a single sequence by ID."""
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    return _sequence_to_response(seq)


@router.put("/{sequence_id}", response_model=SequenceResponse)
async def update_sequence(
    sequence_id: UUID,
    body: SequenceUpdate,
    db: AsyncSession = Depends(get_db),
) -> SequenceResponse:
    """Update an existing sequence."""
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    update_data = body.model_dump(exclude_unset=True)
    if "status" in update_data:
        update_data["status"] = SequenceStatus(update_data["status"])
    for key, value in update_data.items():
        setattr(seq, key, value)
    await db.flush()
    await db.refresh(seq)
    return _sequence_to_response(seq)


@router.delete("/{sequence_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sequence(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a sequence."""
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")
    await db.delete(seq)
    await db.flush()


@router.post("/{sequence_id}/steps", response_model=SequenceStepResponse, status_code=status.HTTP_201_CREATED)
async def add_step(
    sequence_id: UUID,
    body: SequenceStepCreate,
    db: AsyncSession = Depends(get_db),
) -> SequenceStepResponse:
    """Add a step to a sequence."""
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    step = SequenceStep(
        sequence_id=sequence_id,
        step_type=StepType(body.step_type),
        position=body.position,
        config=body.config,
        delay_hours=body.delay_hours,
    )
    db.add(step)
    await db.flush()
    await db.refresh(step)
    return SequenceStepResponse.model_validate(step)


@router.post("/{sequence_id}/enroll", status_code=status.HTTP_201_CREATED)
async def enroll_leads(
    sequence_id: UUID,
    body: EnrollRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Enroll leads into a sequence (checks compliance gate first)."""
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    enrolled = []
    blocked = []

    # Determine channel from first step (default email)
    channel = "email"
    if seq.steps:
        first_step = seq.steps[0]
        if first_step.step_type.value in ("email", "linkedin", "sms"):
            channel = first_step.step_type.value

    for lead_id in body.lead_ids:
        # Check lead exists
        lead_result = await db.execute(select(Lead).where(Lead.id == lead_id))
        lead = lead_result.scalar_one_or_none()
        if lead is None:
            blocked.append({"lead_id": str(lead_id), "reason": "lead_not_found"})
            continue

        # Compliance gate
        can_send, reason = await compliance_svc.can_send_to_lead(lead_id, channel, db)
        if not can_send:
            blocked.append({"lead_id": str(lead_id), "reason": reason})
            continue

        # Check not already enrolled
        existing = await db.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.sequence_id == sequence_id,
                SequenceEnrollment.lead_id == lead_id,
                SequenceEnrollment.status == EnrollmentStatus.active,
            )
        )
        if existing.scalar_one_or_none() is not None:
            blocked.append({"lead_id": str(lead_id), "reason": "already_enrolled"})
            continue

        enrollment = SequenceEnrollment(
            sequence_id=sequence_id,
            lead_id=lead_id,
        )
        db.add(enrollment)
        enrolled.append(str(lead_id))

    await db.flush()
    return {"enrolled": enrolled, "blocked": blocked}


@router.get("/{sequence_id}/analytics", response_model=SequenceAnalyticsResponse)
async def get_sequence_analytics(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SequenceAnalyticsResponse:
    """Get step-by-step analytics for a sequence."""
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    # Enrollment stats
    total_enrolled_r = await db.execute(
        select(func.count(SequenceEnrollment.id)).where(
            SequenceEnrollment.sequence_id == sequence_id
        )
    )
    total_enrolled = total_enrolled_r.scalar_one()

    active_r = await db.execute(
        select(func.count(SequenceEnrollment.id)).where(
            SequenceEnrollment.sequence_id == sequence_id,
            SequenceEnrollment.status == EnrollmentStatus.active,
        )
    )
    active_count = active_r.scalar_one()

    completed_r = await db.execute(
        select(func.count(SequenceEnrollment.id)).where(
            SequenceEnrollment.sequence_id == sequence_id,
            SequenceEnrollment.status == EnrollmentStatus.completed,
        )
    )
    completed_count = completed_r.scalar_one()

    # Per-step analytics from touch_logs
    step_analytics = []
    for step in seq.steps:
        base_filter = [
            TouchLog.sequence_id == sequence_id,
            TouchLog.step_number == step.position,
        ]
        sent_r = await db.execute(
            select(func.count(TouchLog.id)).where(*base_filter, TouchLog.action == "sent")
        )
        opened_r = await db.execute(
            select(func.count(TouchLog.id)).where(*base_filter, TouchLog.action == "opened")
        )
        replied_r = await db.execute(
            select(func.count(TouchLog.id)).where(*base_filter, TouchLog.action == "replied")
        )
        bounced_r = await db.execute(
            select(func.count(TouchLog.id)).where(*base_filter, TouchLog.action == "bounced")
        )

        step_analytics.append(
            StepAnalytics(
                step_position=step.position,
                step_type=step.step_type.value if isinstance(step.step_type, StepType) else step.step_type,
                sent=sent_r.scalar_one(),
                opened=opened_r.scalar_one(),
                replied=replied_r.scalar_one(),
                bounced=bounced_r.scalar_one(),
            )
        )

    return SequenceAnalyticsResponse(
        sequence_id=sequence_id,
        total_enrolled=total_enrolled,
        active=active_count,
        completed=completed_count,
        steps=step_analytics,
    )
