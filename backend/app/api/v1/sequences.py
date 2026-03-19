"""
Sequence API — enhanced for Phase 4 visual builder, AI generation,
conditional branching, A/B testing, and state machine.
"""

from typing import Any
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
    ChannelHealthResponse,
    EnrollmentMonitorResponse,
    EnrollmentResponse,
    EnrollRequest,
    ReplyListResponse,
    ReplyLogResponse,
    SequenceAnalyticsResponse,
    SequenceCreate,
    SequenceGenerateRequest,
    SequenceGenerateResponse,
    SequenceListResponse,
    SequenceMonitorResponse,
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


# ── Phase 5: Reply Inbox (MUST be before /{sequence_id} routes) ────────
# FastAPI matches routes in declaration order. These fixed-path routes
# must be declared before any /{sequence_id}/... routes to avoid
# "replies" being interpreted as a sequence_id UUID segment.


@router.get("/replies/inbox", response_model=ReplyListResponse)
async def get_reply_inbox(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    sentiment: str | None = Query(None),
    channel: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> ReplyListResponse:
    """
    List parsed replies with AI-suggested actions.

    Returns a paginated list of reply log entries from all sequences,
    optionally filtered by sentiment (positive/negative/neutral/out_of_office/unsubscribe)
    or channel (email/sms/linkedin).
    """
    from sqlalchemy import desc, text

    # Query reply_logs table with optional filters.
    # The reply_logs table is managed by the ReplyService (raw SQL via text()).
    # We join with leads to enrich with names/email where not stored inline.

    # Build dynamic filter clauses
    filters: list[str] = []
    bind_params: dict = {}

    if sentiment:
        filters.append("rl.sentiment = :sentiment")
        bind_params["sentiment"] = sentiment

    if channel:
        filters.append("rl.channel = :channel")
        bind_params["channel"] = channel

    where_clause = "WHERE " + " AND ".join(filters) if filters else ""

    # Count total
    count_sql = text(
        f"SELECT COUNT(*) FROM reply_logs rl {where_clause}"
    )
    total_result = await db.execute(count_sql, bind_params)
    total = total_result.scalar_one() or 0

    # Fetch page
    offset = (page - 1) * page_size
    rows_sql = text(
        f"""
        SELECT
            rl.id,
            rl.enrollment_id,
            rl.sequence_id,
            rl.lead_id,
            COALESCE(l.first_name || ' ' || l.last_name, l.email) AS lead_name,
            l.email AS lead_email,
            rl.channel,
            rl.subject,
            rl.body_snippet,
            rl.sentiment,
            rl.sentiment_confidence,
            rl.ai_analysis,
            rl.ai_suggested_action,
            rl.received_at,
            rl.processed_at
        FROM reply_logs rl
        LEFT JOIN leads l ON l.id = rl.lead_id
        {where_clause}
        ORDER BY rl.received_at DESC
        LIMIT :limit OFFSET :offset
        """
    )
    bind_params["limit"] = page_size
    bind_params["offset"] = offset

    try:
        rows_result = await db.execute(rows_sql, bind_params)
        rows = rows_result.mappings().all()
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning(
            "reply_inbox: reply_logs table query failed (table may not exist yet): %s", exc
        )
        rows = []
        total = 0

    items: list[ReplyLogResponse] = []
    for row in rows:
        items.append(
            ReplyLogResponse(
                id=row["id"],
                enrollment_id=row.get("enrollment_id"),
                sequence_id=row.get("sequence_id"),
                lead_id=row.get("lead_id"),
                lead_name=row.get("lead_name"),
                lead_email=row.get("lead_email"),
                channel=row["channel"],
                subject=row.get("subject"),
                body_snippet=row.get("body_snippet"),
                sentiment=row.get("sentiment"),
                sentiment_confidence=float(row.get("sentiment_confidence") or 0.0),
                ai_analysis=row.get("ai_analysis"),
                ai_suggested_action=row.get("ai_suggested_action"),
                received_at=row["received_at"],
                processed_at=row.get("processed_at"),
            )
        )

    return ReplyListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=items,
    )


# ── Phase 5: Sequence Monitor ────────────────────────────────────────


@router.get("/{sequence_id}/monitor", response_model=SequenceMonitorResponse)
async def get_sequence_monitor(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> SequenceMonitorResponse:
    """
    Get full monitoring view for a sequence.

    Returns enrollment states, touch history, reply snippets, per-channel
    breakdown, and daily send counts. Designed for the operations monitor
    dashboard to observe live sequence execution.
    """
    from datetime import date, timedelta, UTC, datetime as dt
    from sqlalchemy import text

    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    # Load enrollments with lead data
    enr_result = await db.execute(
        select(SequenceEnrollment).where(SequenceEnrollment.sequence_id == sequence_id)
    )
    enrollments = enr_result.scalars().unique().all()

    total_steps = len(seq.steps)

    # Enrollment status counts
    active_statuses = {
        EnrollmentStatus.active,
        EnrollmentStatus.pending,
        EnrollmentStatus.sent,
        EnrollmentStatus.opened,
    }
    active_count = sum(1 for e in enrollments if e.status in active_statuses)
    completed_count = sum(1 for e in enrollments if e.status == EnrollmentStatus.completed)
    replied_count = sum(1 for e in enrollments if e.status == EnrollmentStatus.replied)
    failed_count = sum(1 for e in enrollments if e.status in (
        EnrollmentStatus.failed, EnrollmentStatus.bounced,
    ))

    # Channel breakdown from touch_logs for this sequence
    channel_breakdown: dict[str, int] = {}
    try:
        cb_result = await db.execute(
            select(TouchLog.channel, func.count(TouchLog.id))
            .where(
                and_(
                    TouchLog.sequence_id == sequence_id,
                    TouchLog.action == "sent",
                )
            )
            .group_by(TouchLog.channel)
        )
        for ch, cnt in cb_result.all():
            channel_breakdown[ch] = cnt
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning("monitor: channel breakdown query failed: %s", exc)

    # Daily send count for the last 7 days
    daily_send_count: dict[str, int] = {}
    try:
        seven_days_ago = dt.now(UTC) - timedelta(days=7)
        ds_result = await db.execute(
            text(
                """
                SELECT DATE(created_at) as send_date, COUNT(*) as send_count
                FROM touch_logs
                WHERE sequence_id = :seq_id
                  AND action = 'sent'
                  AND created_at >= :cutoff
                GROUP BY DATE(created_at)
                ORDER BY send_date
                """
            ),
            {"seq_id": str(sequence_id), "cutoff": seven_days_ago},
        )
        for send_date, send_count in ds_result.all():
            daily_send_count[str(send_date)] = send_count
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning("monitor: daily send count query failed: %s", exc)

    # Build per-enrollment monitor responses
    enrollment_responses: list[EnrollmentMonitorResponse] = []
    for enr in enrollments:
        # Load lead
        lead_result = await db.execute(select(Lead).where(Lead.id == enr.lead_id))
        lead = lead_result.scalar_one_or_none()

        lead_name = ""
        lead_email = ""
        lead_company = ""
        if lead:
            first = getattr(lead, "first_name", "") or ""
            last = getattr(lead, "last_name", "") or ""
            lead_name = (f"{first} {last}").strip() or lead.email
            lead_email = lead.email or ""
            lead_company = getattr(lead, "company", "") or ""

        # Touch history for this enrollment (lead + sequence)
        touch_history: list[dict] = []
        try:
            th_result = await db.execute(
                select(TouchLog)
                .where(
                    and_(
                        TouchLog.lead_id == enr.lead_id,
                        TouchLog.sequence_id == sequence_id,
                    )
                )
                .order_by(TouchLog.created_at.desc())
                .limit(20)
            )
            for tl in th_result.scalars().all():
                touch_history.append(
                    {
                        "id": str(tl.id),
                        "channel": tl.channel,
                        "action": tl.action.value
                        if hasattr(tl.action, "value")
                        else str(tl.action),
                        "step_number": tl.step_number,
                        "created_at": tl.created_at.isoformat(),
                    }
                )
        except Exception as exc:
            import logging as _log
            _log.getLogger(__name__).warning(
                "monitor: touch history query failed for enr %s: %s", enr.id, exc
            )

        # Reply snippets from reply_logs
        reply_snippets: list[dict] = []
        try:
            rs_result = await db.execute(
                text(
                    """
                    SELECT id, channel, subject, body_snippet, sentiment,
                           received_at, ai_suggested_action
                    FROM reply_logs
                    WHERE lead_id = :lead_id AND sequence_id = :seq_id
                    ORDER BY received_at DESC
                    LIMIT 5
                    """
                ),
                {"lead_id": str(enr.lead_id), "seq_id": str(sequence_id)},
            )
            for rs_row in rs_result.mappings().all():
                reply_snippets.append(
                    {
                        "id": str(rs_row["id"]),
                        "channel": rs_row["channel"],
                        "subject": rs_row.get("subject"),
                        "body_snippet": rs_row.get("body_snippet"),
                        "sentiment": rs_row.get("sentiment"),
                        "received_at": rs_row["received_at"].isoformat()
                        if rs_row.get("received_at")
                        else None,
                        "ai_suggested_action": rs_row.get("ai_suggested_action"),
                    }
                )
        except Exception as exc:
            import logging as _log
            _log.getLogger(__name__).warning(
                "monitor: reply snippets query failed for enr %s: %s", enr.id, exc
            )

        enrollment_responses.append(
            EnrollmentMonitorResponse(
                id=enr.id,
                lead_id=enr.lead_id,
                lead_name=lead_name,
                lead_email=lead_email,
                lead_company=lead_company,
                current_step=enr.current_step,
                total_steps=total_steps,
                status=enr.status.value
                if hasattr(enr.status, "value")
                else str(enr.status),
                enrolled_at=enr.enrolled_at,
                last_touch_at=enr.last_touch_at,
                last_state_change_at=enr.last_state_change_at,
                hole_filler_triggered=enr.hole_filler_triggered,
                escalation_channel=enr.escalation_channel,
                touch_history=touch_history,
                reply_snippets=reply_snippets,
            )
        )

    return SequenceMonitorResponse(
        sequence_id=seq.id,
        sequence_name=seq.name,
        status=seq.status.value if hasattr(seq.status, "value") else str(seq.status),
        total_enrolled=len(enrollments),
        active=active_count,
        completed=completed_count,
        replied=replied_count,
        failed=failed_count,
        enrollments=enrollment_responses,
        channel_breakdown=channel_breakdown,
        daily_send_count=daily_send_count,
    )


@router.get("/{sequence_id}/channel-health", response_model=list[ChannelHealthResponse])
async def get_channel_health(
    sequence_id: UUID,
    db: AsyncSession = Depends(get_db),
) -> list[ChannelHealthResponse]:
    """
    Get per-channel health metrics for a sequence.

    Returns sent-today count, daily limit, utilization, bounce rate,
    and reply rate for each channel used by the sequence.
    Uses the ChannelOrchestrator's health aggregation.
    """
    from datetime import UTC, datetime as dt, timedelta

    result = await db.execute(select(Sequence).where(Sequence.id == sequence_id))
    seq = result.scalar_one_or_none()
    if seq is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Sequence not found")

    try:
        from app.services.channel_orchestrator import ChannelOrchestrator, CHANNEL_DAILY_LIMITS

        orchestrator = ChannelOrchestrator(db)
        global_health = await orchestrator.get_channel_health()
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).error("channel_health: orchestrator failed: %s", exc)
        global_health = {}

    # Determine channels actually used in this sequence's steps
    sequence_channels = {
        step.step_type.value
        for step in seq.steps
        if hasattr(step.step_type, "value")
        and step.step_type.value in ("email", "sms", "linkedin")
    }
    if not sequence_channels:
        sequence_channels = {"email"}  # Default fallback

    # Compute last failure timestamp per channel from touch_logs (bounced/complained)
    last_failure_by_channel: dict[str, Any] = {}
    try:
        cutoff = dt.now(UTC) - timedelta(days=7)
        for ch in sequence_channels:
            lf_result = await db.execute(
                select(func.max(TouchLog.created_at)).where(
                    and_(
                        TouchLog.sequence_id == sequence_id,
                        TouchLog.channel == ch,
                        TouchLog.action.in_(["bounced", "complained"]),
                        TouchLog.created_at >= cutoff,
                    )
                )
            )
            last_failure_by_channel[ch] = lf_result.scalar_one_or_none()
    except Exception as exc:
        import logging as _log
        _log.getLogger(__name__).warning("channel_health: last failure query failed: %s", exc)

    health_responses: list[ChannelHealthResponse] = []
    for channel in sorted(sequence_channels):
        ch_data = global_health.get(channel, {})

        # sent_today: use global health data or fall back to touch_log count
        sent_today = ch_data.get("sent_24h", 0)
        bounce_rate = float(ch_data.get("bounce_rate", 0.0))
        reply_rate = float(ch_data.get("reply_rate", 0.0))

        try:
            from app.services.channel_orchestrator import CHANNEL_DAILY_LIMITS

            daily_limit = CHANNEL_DAILY_LIMITS.get(channel, 100)
        except Exception:
            daily_limit = 100

        utilization = round(sent_today / max(1, daily_limit), 4)

        health_responses.append(
            ChannelHealthResponse(
                channel=channel,
                sent_today=sent_today,
                limit=daily_limit,
                utilization=utilization,
                bounce_rate=bounce_rate,
                reply_rate=reply_rate,
                last_failure=last_failure_by_channel.get(channel),
            )
        )

    return health_responses
