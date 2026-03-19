"""
Sequence API — enhanced for Phase 4 visual builder, AI generation,
conditional branching, A/B testing, and state machine.
"""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import and_, func, select
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
    ABVariantAnalytics,
    EnrollmentResponse,
    EnrollRequest,
    SequenceAnalyticsResponse,
    SequenceCreate,
    SequenceGenerateRequest,
    SequenceGenerateResponse,
    SequenceListResponse,
    SequenceResponse,
    SequenceStepCreate,
    SequenceStepResponse,
    SequenceUpdate,
    StepAnalytics,
    VisualConfigResponse,
    VisualConfigSaveRequest,
)
from app.services import compliance as compliance_svc

router = APIRouter(prefix="/sequences", tags=["sequences"])


# ── Helpers ───────────────────────────────────────────────────────────


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
        visual_config=seq.visual_config,
        ai_generated=seq.ai_generated,
        ai_generation_prompt=seq.ai_generation_prompt,
        ai_generation_metadata=seq.ai_generation_metadata,
    )


# ── CRUD ──────────────────────────────────────────────────────────────


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
        visual_config=body.visual_config,
        ai_generated=body.ai_generated,
        ai_generation_prompt=body.ai_generation_prompt,
        ai_generation_metadata=body.ai_generation_metadata,
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


# ── Steps ─────────────────────────────────────────────────────────────


@router.post(
    "/{sequence_id}/steps",
    response_model=SequenceStepResponse,
    status_code=status.HTTP_201_CREATED,
)
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
        condition=body.condition,
        true_next_position=body.true_next_position,
        false_next_position=body.false_next_position,
        ab_variants=body.ab_variants,
        is_ab_test=body.is_ab_test,
        node_id=body.node_id,
    )
    db.add(step)
    await db.flush()
    await db.refresh(step)
    return SequenceStepResponse.model_validate(step)


@router.delete(
    "/{sequence_id}/steps/{step_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_step(
    sequence_id: UUID,
    step_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> None:
    """Delete a step from a sequence."""
    result = await db.execute(
        select(SequenceStep).where(
            and_(
                SequenceStep.id == step_id,
                SequenceStep.sequence_id == sequence_id,
            )
        )
    )
    step = result.scalar_one_or_none()
    if step is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Step not found")
    await db.delete(step)
    await db.flush()


# ── Enrollment ────────────────────────────────────────────────────────


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

        # Check not already enrolled (any live status)
        existing = await db.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.sequence_id == sequence_id,
                SequenceEnrollment.lead_id == lead_id,
                SequenceEnrollment.status.in_([
                    EnrollmentStatus.active,
                    EnrollmentStatus.pending,
                    EnrollmentStatus.sent,
                    EnrollmentStatus.opened,
                ]),
            )
        )
        if existing.scalar_one_or_none() is not None:
            blocked.append({"lead_id": str(lead_id), "reason": "already_enrolled"})
            continue

        enrollment = SequenceEnrollment(
            sequence_id=sequence_id,
            lead_id=lead_id,
            status=EnrollmentStatus.pending,
        )
        db.add(enrollment)
        enrolled.append(str(lead_id))

    await db.flush()
    return {"enrolled": enrolled, "blocked": blocked}


# ── Enrollment Management ─────────────────────────────────────────────


@router.post("/{sequence_id}/enrollments/{enrollment_id}/pause")
async def pause_enrollment(
    sequence_id: UUID,
    enrollment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Pause an active enrollment."""
    from app.services.state_machine import can_transition, EnrollmentState

    result = await db.execute(
        select(SequenceEnrollment).where(
            and_(
                SequenceEnrollment.id == enrollment_id,
                SequenceEnrollment.sequence_id == sequence_id,
            )
        )
    )
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    if not can_transition(enrollment.status.value, EnrollmentState.paused):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot pause enrollment in state: {enrollment.status.value}",
        )

    enrollment.status = EnrollmentStatus.paused
    from datetime import UTC, datetime
    enrollment.last_state_change_at = datetime.now(UTC)
    await db.flush()
    return {"status": "paused", "enrollment_id": str(enrollment_id)}


@router.post("/{sequence_id}/enrollments/{enrollment_id}/resume")
async def resume_enrollment(
    sequence_id: UUID,
    enrollment_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resume a paused enrollment."""
    result = await db.execute(
        select(SequenceEnrollment).where(
            and_(
                SequenceEnrollment.id == enrollment_id,
                SequenceEnrollment.sequence_id == sequence_id,
            )
        )
    )
    enrollment = result.scalar_one_or_none()
    if enrollment is None:
        raise HTTPException(status_code=404, detail="Enrollment not found")

    if enrollment.status != EnrollmentStatus.paused:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot resume enrollment in state: {enrollment.status.value}",
        )

    enrollment.status = EnrollmentStatus.active
    from datetime import UTC, datetime
    enrollment.last_state_change_at = datetime.now(UTC)
    await db.flush()
    return {"status": "resumed", "enrollment_id": str(enrollment_id)}


# ── AI Generation ─────────────────────────────────────────────────────


@router.post("/generate", response_model=SequenceGenerateResponse)
async def generate_sequence(
    body: SequenceGenerateRequest,
    db: AsyncSession = Depends(get_db),
) -> SequenceGenerateResponse:
    """
    AI-powered sequence generation.

    Accepts a natural-language prompt and uses HubSpot Breeze, ZoomInfo Copilot,
    and Apollo AI to generate a complete, optimized outreach sequence with
    visual builder config.
    """
    from app.services.sequence_ai_service import SequenceAIService

    ai_service = SequenceAIService()
    result = await ai_service.generate_sequence(
        prompt=body.prompt,
        target_industry=body.target_industry,
        num_steps=body.num_steps,
        channels=body.channels,
        include_ab_test=body.include_ab_test,
        include_conditionals=body.include_conditionals,
    )

    if not result.success:
        return SequenceGenerateResponse(
            success=False,
            error=result.error,
        )

    # Create the sequence in the database
    config = result.sequence_config
    seq = Sequence(
        name=config["name"],
        description=config.get("description"),
        status=SequenceStatus.draft,
        visual_config=result.visual_config,
        ai_generated=True,
        ai_generation_prompt=body.prompt,
        ai_generation_metadata=result.ai_metadata,
    )
    db.add(seq)
    await db.flush()
    await db.refresh(seq)

    # Create steps
    for step_config in config.get("steps", []):
        step = SequenceStep(
            sequence_id=seq.id,
            step_type=StepType(step_config["step_type"]),
            position=step_config["position"],
            config=step_config.get("config"),
            delay_hours=step_config.get("delay_hours", 0),
            condition=step_config.get("condition"),
            true_next_position=step_config.get("true_next_position"),
            false_next_position=step_config.get("false_next_position"),
            ab_variants=step_config.get("ab_variants"),
            is_ab_test=step_config.get("is_ab_test", False),
            node_id=step_config.get("node_id"),
        )
        db.add(step)

    await db.flush()

    return SequenceGenerateResponse(
        success=True,
        sequence_id=seq.id,
        sequence_name=seq.name,
        steps_generated=len(config.get("steps", [])),
        channels_used=result.ai_metadata.get("channels_used", []),
        ai_platforms_consulted=result.ai_metadata.get("platforms_consulted", []),
        visual_config=result.visual_config,
    )


# ── Visual Builder ────────────────────────────────────────────────────


@router.get("/{sequence_id}/visual", response_model=VisualConfigResponse)
async def get_visual_config(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> VisualConfigResponse:
    """Load the visual builder config for a sequence."""
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=404, detail="Sequence not found")

    return VisualConfigResponse(
        sequence_id=seq.id,
        visual_config=seq.visual_config,
        steps=[SequenceStepResponse.model_validate(s) for s in seq.steps],
    )


@router.put("/{sequence_id}/visual", response_model=VisualConfigResponse)
async def save_visual_config(
    sequence_id: UUID,
    body: VisualConfigSaveRequest,
    db: AsyncSession = Depends(get_db),
) -> VisualConfigResponse:
    """
    Save the visual builder config for a sequence.

    Optionally syncs step definitions from the visual config,
    replacing all existing steps.
    """
    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=404, detail="Sequence not found")

    seq.visual_config = body.visual_config

    # If steps provided, sync them (replace all)
    if body.steps is not None:
        # Delete existing steps
        existing_steps = await db.execute(
            select(SequenceStep).where(SequenceStep.sequence_id == sequence_id)
        )
        for old_step in existing_steps.scalars().all():
            await db.delete(old_step)
        await db.flush()

        # Create new steps from visual config
        for step_data in body.steps:
            step = SequenceStep(
                sequence_id=sequence_id,
                step_type=StepType(step_data.step_type),
                position=step_data.position,
                config=step_data.config,
                delay_hours=step_data.delay_hours,
                condition=step_data.condition,
                true_next_position=step_data.true_next_position,
                false_next_position=step_data.false_next_position,
                ab_variants=step_data.ab_variants,
                is_ab_test=step_data.is_ab_test,
                node_id=step_data.node_id,
            )
            db.add(step)

    await db.flush()
    await db.refresh(seq)

    return VisualConfigResponse(
        sequence_id=seq.id,
        visual_config=seq.visual_config,
        steps=[SequenceStepResponse.model_validate(s) for s in seq.steps],
    )


# ── Analytics (with A/B results) ──────────────────────────────────────


@router.get("/{sequence_id}/analytics", response_model=SequenceAnalyticsResponse)
async def get_sequence_analytics(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SequenceAnalyticsResponse:
    """Get step-by-step analytics for a sequence, including A/B test results."""
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
            SequenceEnrollment.status.in_([
                EnrollmentStatus.active,
                EnrollmentStatus.pending,
                EnrollmentStatus.sent,
                EnrollmentStatus.opened,
            ]),
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
                step_type=step.step_type.value
                if isinstance(step.step_type, StepType)
                else step.step_type,
                sent=sent_r.scalar_one(),
                opened=opened_r.scalar_one(),
                replied=replied_r.scalar_one(),
                bounced=bounced_r.scalar_one(),
            )
        )

    # A/B test results
    ab_results: list[ABVariantAnalytics] = []
    ab_steps = [s for s in seq.steps if s.is_ab_test or s.step_type == StepType.ab_split]

    for ab_step in ab_steps:
        variants = ab_step.ab_variants or {}
        for variant_key in variants:
            # Count enrollments assigned to this variant at this step
            enrollments_r = await db.execute(
                select(SequenceEnrollment).where(
                    SequenceEnrollment.sequence_id == sequence_id,
                )
            )
            all_enrollments = enrollments_r.scalars().all()

            variant_enrollment_ids = [
                e.id
                for e in all_enrollments
                if (e.ab_variant_assignments or {}).get(str(ab_step.position)) == variant_key
            ]

            if not variant_enrollment_ids:
                ab_results.append(
                    ABVariantAnalytics(
                        step_position=ab_step.position,
                        variant=variant_key,
                    )
                )
                continue

            # Get touch logs for variant enrollments
            variant_lead_ids = [
                e.lead_id for e in all_enrollments
                if e.id in variant_enrollment_ids
            ]

            v_base = [
                TouchLog.sequence_id == sequence_id,
                TouchLog.step_number == ab_step.position,
                TouchLog.lead_id.in_(variant_lead_ids),
            ]

            v_sent = (
                await db.execute(
                    select(func.count(TouchLog.id)).where(
                        *v_base, TouchLog.action == "sent"
                    )
                )
            ).scalar_one()
            v_opened = (
                await db.execute(
                    select(func.count(TouchLog.id)).where(
                        *v_base, TouchLog.action == "opened"
                    )
                )
            ).scalar_one()
            v_replied = (
                await db.execute(
                    select(func.count(TouchLog.id)).where(
                        *v_base, TouchLog.action == "replied"
                    )
                )
            ).scalar_one()
            v_bounced = (
                await db.execute(
                    select(func.count(TouchLog.id)).where(
                        *v_base, TouchLog.action == "bounced"
                    )
                )
            ).scalar_one()

            ab_results.append(
                ABVariantAnalytics(
                    step_position=ab_step.position,
                    variant=variant_key,
                    sent=v_sent,
                    opened=v_opened,
                    replied=v_replied,
                    bounced=v_bounced,
                    open_rate=v_opened / max(1, v_sent),
                    reply_rate=v_replied / max(1, v_sent),
                )
            )

    return SequenceAnalyticsResponse(
        sequence_id=sequence_id,
        total_enrolled=total_enrolled,
        active=active_count,
        completed=completed_count,
        steps=step_analytics,
        ab_results=ab_results,
    )
