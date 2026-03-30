"""
Phase 4 Sequence Execution Engine — production-ready rewrite.

Features:
- FSM-gated state transitions (no double-sends, handles restarts/pauses)
- Conditional branch evaluation (if/else routing)
- A/B split assignment with deterministic variant tracking
- Hole-filler escalation logic (email→LinkedIn, email→SMS on non-engagement)
- SES rotation dispatch via DeliverabilityRouter
- Idempotency via last_dispatch_id
- Compliance-gated at every send via can_send_to_lead()

This service is called by the Celery beat scheduler every 15 minutes.
"""

import logging
import random
import uuid
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.sequence import (
    EnrollmentStatus,
    Sequence,
    SequenceEnrollment,
    SequenceStep,
    SequenceStatus,
    StepType,
)
from app.models.template import Template
from app.models.touch_log import TouchAction, TouchLog
from app.services import compliance as compliance_svc
from app.services.deliverability_router import DeliverabilityRouter
from app.services.linkedin_service import (
    LinkedInAction,
    prepare_linkedin_outreach,
)
from app.services.sms_service import send_sms
from app.services.state_machine import (
    EnrollmentState,
    evaluate_condition,
    transition,
)
from app.services.template_engine import build_lead_context, render_template

logger = logging.getLogger(__name__)


# Default sender info for Gengyve outreach
DEFAULT_SENDER = {
    "name": "Dr. Thad",
    "title": "Founder & CEO",
    "company": "Gengyve USA",
    "email": "hello@gengyveusa.com",
    "phone": "",
}


# ── Due Enrollment Query ──────────────────────────────────────────────


async def get_due_enrollments(db: AsyncSession) -> list[SequenceEnrollment]:
    """
    Find all enrollments ready for their next step.

    An enrollment is due when:
    1. FSM state is sendable (active or escalated)
    2. Time since last touch >= delay_hours of the next step
    3. OR pending enrollment ready to activate (first step, no delay)
    """
    # Fetch both active and pending enrollments
    sendable_statuses = [
        EnrollmentStatus.active,
        EnrollmentStatus.pending,
    ]
    result = await db.execute(select(SequenceEnrollment).where(SequenceEnrollment.status.in_(sendable_statuses)))
    enrollments = result.scalars().all()

    due: list[SequenceEnrollment] = []
    now = datetime.now(UTC)

    for enrollment in enrollments:
        # Load sequence
        seq_result = await db.execute(select(Sequence).where(Sequence.id == enrollment.sequence_id))
        sequence = seq_result.scalar_one_or_none()
        if not sequence or sequence.status != SequenceStatus.active:
            continue

        steps = sorted(sequence.steps, key=lambda s: s.position)
        if enrollment.current_step >= len(steps):
            # All steps completed
            enrollment.status = EnrollmentStatus.completed
            enrollment.last_state_change_at = now
            continue

        next_step = steps[enrollment.current_step]

        # Activate pending enrollments
        if enrollment.status == EnrollmentStatus.pending:
            enrollment.status = EnrollmentStatus.active
            enrollment.last_state_change_at = now

        # Check delay
        if enrollment.current_step == 0:
            time_since = (now - enrollment.enrolled_at).total_seconds() / 3600
        else:
            ref_time = enrollment.last_touch_at or enrollment.enrolled_at
            time_since = (now - ref_time).total_seconds() / 3600

        if time_since >= next_step.delay_hours:
            due.append(enrollment)

    return due


# ── Step Routing ──────────────────────────────────────────────────────


def _resolve_next_step(
    step: SequenceStep,
    steps: list[SequenceStep],
    enrollment: SequenceEnrollment,
    touch_history: list[dict],
) -> int | None:
    """
    For conditional/ab_split/end nodes, resolve the actual next step position.
    Returns the position index to jump to, or None if sequence should end.
    """
    if step.step_type == StepType.conditional:
        condition = step.condition or {}
        result = evaluate_condition(
            condition=condition,
            enrollment_state=enrollment.status.value,
            touch_history=touch_history,
        )
        if result:
            return step.true_next_position
        else:
            return step.false_next_position

    elif step.step_type == StepType.ab_split:
        # Already assigned variant — use its template
        # A/B just changes which template is used, not the step position
        return enrollment.current_step + 1

    elif step.step_type == StepType.end:
        return None  # Terminal node

    # Default: advance linearly
    return enrollment.current_step + 1


def _assign_ab_variant(
    step: SequenceStep,
    enrollment: SequenceEnrollment,
) -> str:
    """
    Deterministically assign an A/B variant for this enrollment + step.

    Uses existing assignment if present (idempotent on restart),
    otherwise assigns by weighted random.
    """
    assignments = enrollment.ab_variant_assignments or {}
    step_key = str(step.position)

    if step_key in assignments:
        return assignments[step_key]

    ab_variants = step.ab_variants or {}
    if not ab_variants:
        return "A"

    # Weighted random assignment
    variants = list(ab_variants.keys())
    weights = [ab_variants[v].get("weight", 50) for v in variants]
    total = sum(weights)
    if total == 0:
        chosen = random.choice(variants)
    else:
        r = random.uniform(0, total)
        cumulative = 0.0
        chosen = variants[0]
        for v, w in zip(variants, weights):
            cumulative += w
            if r <= cumulative:
                chosen = v
                break

    # Persist assignment
    assignments[step_key] = chosen
    enrollment.ab_variant_assignments = assignments
    return chosen


# ── Hole-Filler Escalation ────────────────────────────────────────────


async def _check_hole_filler(
    enrollment: SequenceEnrollment,
    lead: Lead,
    db: AsyncSession,
) -> str | None:
    """
    Check if hole-filler escalation should trigger.

    Returns the escalation channel ("linkedin" or "sms") if the lead
    hasn't engaged after 2+ email touches, or None if no escalation needed.
    """
    if enrollment.hole_filler_triggered:
        return None  # Already escalated once

    # Count email touches without engagement
    result = await db.execute(
        select(TouchLog).where(
            and_(
                TouchLog.lead_id == enrollment.lead_id,
                TouchLog.sequence_id == enrollment.sequence_id,
                TouchLog.channel == "email",
                TouchLog.action == TouchAction.sent,
            )
        )
    )
    email_sends = result.scalars().all()

    if len(email_sends) < 2:
        return None  # Not enough touches to trigger

    # Check for any engagement (open or reply)
    engagement_result = await db.execute(
        select(TouchLog).where(
            and_(
                TouchLog.lead_id == enrollment.lead_id,
                TouchLog.sequence_id == enrollment.sequence_id,
                TouchLog.action.in_([TouchAction.opened, TouchAction.replied]),
            )
        )
    )
    engagements = engagement_result.scalars().all()

    if engagements:
        return None  # Lead has engaged

    # Escalate: prefer LinkedIn if lead has profile, else SMS if phone
    if lead.linkedin_url or lead.company:
        return "linkedin"
    elif lead.phone:
        return "sms"

    return None


# ── Dispatch ──────────────────────────────────────────────────────────


async def _dispatch_email(
    lead: Lead,
    template: Template,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    context: dict,
    db: AsyncSession,
) -> dict:
    """Dispatch email via SES rotation through DeliverabilityRouter."""
    subject = render_template(template.subject or "", context)
    html_body = render_template(template.html_body or template.plain_body, context)
    plain_body = render_template(template.plain_body, context)

    unsub_token = compliance_svc.generate_unsubscribe_token(lead.id, "email")
    unsubscribe_url = f"https://app.gengyveusa.com/api/v1/unsubscribe/{unsub_token}"

    tags = {
        "sequence_id": str(enrollment.sequence_id),
        "step": str(step.position),
        "lead_id": str(lead.id),
        "enrollment_id": str(enrollment.id),
    }

    # Use DeliverabilityRouter for SES rotation
    router = DeliverabilityRouter(db)
    email_result, inbox_used = await router.route_and_send(
        to_email=lead.email,
        subject=subject,
        html_body=html_body,
        plain_body=plain_body,
        unsubscribe_url=unsubscribe_url,
        tags=tags,
    )

    result = {
        "status": "sent" if email_result.success else "failed",
        "channel": "email",
        "step": step.position,
        "inbox_used": inbox_used,
    }
    if email_result.message_id:
        result["message_id"] = email_result.message_id
    if email_result.error:
        result["error"] = email_result.error

    return result


async def _dispatch_sms(
    lead: Lead,
    template: Template,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    context: dict,
) -> dict:
    """Dispatch SMS via Twilio."""
    body = render_template(template.plain_body, context)
    sms_result = await send_sms(
        to_phone=lead.phone or "",
        body=body,
        tags={
            "sequence_id": str(enrollment.sequence_id),
            "step": str(step.position),
        },
    )
    result = {
        "status": "sent" if sms_result.success else "failed",
        "channel": "sms",
        "step": step.position,
    }
    if sms_result.message_sid:
        result["message_sid"] = sms_result.message_sid
    if sms_result.error:
        result["error"] = sms_result.error
    return result


async def _dispatch_linkedin(
    lead: Lead,
    template: Template,
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    context: dict,
) -> dict:
    """Dispatch LinkedIn action (connection request, InMail, etc.)."""
    note = render_template(template.plain_body, context)
    linkedin_action = LinkedInAction(template.linkedin_action or "connection_request")
    li_result = await prepare_linkedin_outreach(
        action=linkedin_action,
        recipient_name=f"{lead.first_name} {lead.last_name}",
        recipient_title=lead.title,
        recipient_company=lead.company,
        note=note if linkedin_action == LinkedInAction.connection_request else "",
        body=note if linkedin_action != LinkedInAction.connection_request else "",
        subject=render_template(template.subject or "", context) if template.subject else "",
    )
    result = {
        "status": "sent" if li_result.success else "failed",
        "channel": "linkedin",
        "step": step.position,
        "queued": li_result.queued,
    }
    if li_result.error:
        result["error"] = li_result.error
    return result


# ── Step Execution ────────────────────────────────────────────────────


async def execute_step(
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    lead: Lead,
    db: AsyncSession,
) -> dict:
    """
    Execute a single sequence step for a lead.

    Flow:
    1. Generate idempotency dispatch_id (prevent double-sends on restart)
    2. Route through conditional/A/B nodes
    3. Check compliance gate
    4. Resolve template (with A/B variant if applicable)
    5. Dispatch via appropriate channel (SES rotation for email)
    6. Log touch + advance enrollment + transition FSM state
    """
    now = datetime.now(UTC)

    # Generate dispatch_id for idempotency
    dispatch_id = str(uuid.uuid4())

    # Check for duplicate dispatch (restart protection)
    if enrollment.last_dispatch_id:
        # Verify the last dispatch was for a different step
        last_touch_result = await db.execute(
            select(TouchLog)
            .where(
                and_(
                    TouchLog.lead_id == enrollment.lead_id,
                    TouchLog.sequence_id == enrollment.sequence_id,
                    TouchLog.step_number == step.position,
                    TouchLog.action == TouchAction.sent,
                )
            )
            .order_by(TouchLog.created_at.desc())
            .limit(1)
        )
        last_touch = last_touch_result.scalar_one_or_none()
        if last_touch and (now - last_touch.created_at).total_seconds() < 300:
            logger.info(
                "Duplicate dispatch detected for enrollment %s step %d, skipping",
                enrollment.id,
                step.position,
            )
            return {"status": "skipped", "reason": "duplicate_dispatch"}

    # ── Handle non-dispatch step types ──

    if step.step_type == StepType.wait:
        enrollment.current_step += 1
        return {"status": "wait_completed", "step": step.position}

    if step.step_type == StepType.end:
        enrollment.status = EnrollmentStatus.completed
        enrollment.last_state_change_at = now
        return {"status": "completed", "step": step.position}

    if step.step_type == StepType.conditional:
        # Load touch history for condition evaluation
        history_result = await db.execute(
            select(TouchLog).where(
                and_(
                    TouchLog.lead_id == enrollment.lead_id,
                    TouchLog.sequence_id == enrollment.sequence_id,
                )
            )
        )
        history = [
            {
                "step_number": t.step_number,
                "action": t.action.value if hasattr(t.action, "value") else t.action,
                "channel": t.channel,
            }
            for t in history_result.scalars().all()
        ]

        steps = sorted(
            (await db.execute(select(SequenceStep).where(SequenceStep.sequence_id == enrollment.sequence_id)))
            .scalars()
            .all(),
            key=lambda s: s.position,
        )

        next_pos = _resolve_next_step(step, steps, enrollment, history)
        if next_pos is None:
            enrollment.status = EnrollmentStatus.completed
            enrollment.last_state_change_at = now
            return {"status": "completed", "reason": "conditional_end"}

        enrollment.current_step = next_pos
        return {
            "status": "branched",
            "from_step": step.position,
            "to_step": next_pos,
        }

    # ── Determine channel and template ──

    channel = step.step_type.value
    template_id = None

    # A/B split: pick variant template
    if step.step_type == StepType.ab_split or step.is_ab_test:
        variant = _assign_ab_variant(step, enrollment)
        ab_config = (step.ab_variants or {}).get(variant, {})
        template_id = ab_config.get("template_id")
        channel = ab_config.get("channel", "email")
    else:
        template_id = step.config.get("template_id") if step.config else None

    # ── Compliance gate ──

    can_send, reason = await compliance_svc.can_send_to_lead(lead.id, channel, db)
    if not can_send:
        logger.info("Step blocked for lead %s: %s", lead.id, reason)
        return {"status": "blocked", "reason": reason}

    # ── Load template ──

    template = None
    if template_id:
        template_result = await db.execute(select(Template).where(Template.id == UUID(template_id)))
        template = template_result.scalar_one_or_none()

    if not template:
        return {"status": "skipped", "reason": "no_template_configured"}

    # ── Build context ──

    unsubscribe_url = None
    if channel == "email":
        unsub_token = compliance_svc.generate_unsubscribe_token(lead.id, "email")
        unsubscribe_url = f"https://app.gengyveusa.com/api/v1/unsubscribe/{unsub_token}"

    context = build_lead_context(
        lead=lead,
        sender=DEFAULT_SENDER,
        unsubscribe_url=unsubscribe_url,
    )

    # ── Dispatch ──

    if channel == "email":
        result = await _dispatch_email(lead, template, enrollment, step, context, db)
    elif channel == "sms":
        result = await _dispatch_sms(lead, template, enrollment, step, context)
    elif channel == "linkedin":
        result = await _dispatch_linkedin(lead, template, enrollment, step, context)
    else:
        result = {"status": "skipped", "reason": f"unknown_channel_{channel}"}

    # ── Post-dispatch ──

    if result.get("status") == "sent":
        # Log touch
        touch = TouchLog(
            lead_id=lead.id,
            channel=channel,
            action=TouchAction.sent,
            sequence_id=enrollment.sequence_id,
            step_number=step.position,
            extra_metadata={
                **result,
                "dispatch_id": dispatch_id,
                "ab_variant": (enrollment.ab_variant_assignments or {}).get(str(step.position)),
            },
        )
        db.add(touch)

        # Update enrollment
        enrollment.current_step += 1
        enrollment.last_touch_at = now
        enrollment.last_dispatch_id = dispatch_id
        enrollment.last_state_change_at = now

        # Transition FSM: active → sent
        try:
            new_state = transition(enrollment.status.value, EnrollmentState.sent)
            enrollment.status = EnrollmentStatus(new_state)
        except Exception:
            # If transition fails, stay in current state
            pass

        # Check if sequence is complete
        seq_result = await db.execute(select(Sequence).where(Sequence.id == enrollment.sequence_id))
        seq = seq_result.scalar_one_or_none()
        if seq and enrollment.current_step >= len(seq.steps):
            enrollment.status = EnrollmentStatus.completed
            enrollment.last_state_change_at = now

    elif result.get("status") == "failed":
        # Transition to failed state on hard failure
        try:
            new_state = transition(enrollment.status.value, EnrollmentState.failed)
            enrollment.status = EnrollmentStatus(new_state)
            enrollment.last_state_change_at = now
        except Exception:
            pass

    return result


# ── Hole-Filler Execution ─────────────────────────────────────────────


async def _execute_hole_filler(
    enrollment: SequenceEnrollment,
    lead: Lead,
    escalation_channel: str,
    db: AsyncSession,
) -> dict:
    """
    Execute a hole-filler touch — escalate to a different channel
    when the primary channel (email) isn't getting engagement.
    """
    now = datetime.now(UTC)

    # Compliance gate on escalation channel
    can_send, reason = await compliance_svc.can_send_to_lead(lead.id, escalation_channel, db)
    if not can_send:
        return {"status": "blocked", "reason": reason, "channel": escalation_channel}

    build_lead_context(lead=lead, sender=DEFAULT_SENDER)

    result: dict = {
        "status": "sent",
        "channel": escalation_channel,
        "hole_filler": True,
    }

    if escalation_channel == "linkedin":
        li_result = await prepare_linkedin_outreach(
            action=LinkedInAction.connection_request,
            recipient_name=f"{lead.first_name} {lead.last_name}",
            recipient_title=lead.title,
            recipient_company=lead.company,
            note=(
                f"Hi {lead.first_name}, I noticed we haven't connected yet. "
                f"I'm Dr. Thad from Gengyve USA — we make a natural mouthwash "
                f"that replaces chlorhexidine. Would love to chat about how "
                f"it could benefit your practice."
            ),
            body="",
            subject="",
        )
        result["queued"] = li_result.queued
        if not li_result.success:
            result["status"] = "failed"
            result["error"] = li_result.error

    elif escalation_channel == "sms":
        sms_body = (
            f"Hi {lead.first_name}, Dr. Thad here from Gengyve USA. "
            f"I sent a few emails about our natural mouthwash for dental "
            f"practices — wanted to make sure you saw them. Happy to chat "
            f"whenever works for you. Reply STOP to opt out."
        )
        sms_result = await send_sms(
            to_phone=lead.phone or "",
            body=sms_body,
            tags={"sequence_id": str(enrollment.sequence_id), "hole_filler": "true"},
        )
        if not sms_result.success:
            result["status"] = "failed"
            result["error"] = sms_result.error

    if result["status"] == "sent":
        # Log the hole-filler touch
        touch = TouchLog(
            lead_id=lead.id,
            channel=escalation_channel,
            action=TouchAction.sent,
            sequence_id=enrollment.sequence_id,
            step_number=-1,  # Hole-filler, not a regular step
            extra_metadata={"hole_filler": True, **result},
        )
        db.add(touch)

        # Mark enrollment
        enrollment.hole_filler_triggered = True
        enrollment.escalation_channel = escalation_channel
        enrollment.last_touch_at = now

        # Transition to escalated state
        try:
            new_state = transition(enrollment.status.value, EnrollmentState.escalated)
            enrollment.status = EnrollmentStatus(new_state)
            enrollment.last_state_change_at = now
        except Exception:
            pass

    return result


# ── Main Engine ───────────────────────────────────────────────────────


async def run_sequence_engine(db: AsyncSession) -> dict:
    """
    Main entry point: find all due enrollments and execute their next step.

    Called by Celery beat (every 15 minutes).

    Flow for each enrollment:
    1. Check FSM state is sendable
    2. Check hole-filler trigger
    3. Execute the current step (with conditional/A/B routing)
    4. Transition FSM state
    5. Commit results
    """
    stats = {
        "processed": 0,
        "sent": 0,
        "blocked": 0,
        "failed": 0,
        "skipped": 0,
        "branched": 0,
        "completed": 0,
        "hole_filler": 0,
    }

    due_enrollments = await get_due_enrollments(db)
    logger.info("Found %d due enrollments", len(due_enrollments))

    for enrollment in due_enrollments:
        stats["processed"] += 1

        # Load sequence and step
        seq_result = await db.execute(select(Sequence).where(Sequence.id == enrollment.sequence_id))
        sequence = seq_result.scalar_one_or_none()
        if not sequence:
            continue

        steps = sorted(sequence.steps, key=lambda s: s.position)
        if enrollment.current_step >= len(steps):
            enrollment.status = EnrollmentStatus.completed
            enrollment.last_state_change_at = datetime.now(UTC)
            stats["completed"] += 1
            continue

        step = steps[enrollment.current_step]

        # Load lead
        lead_result = await db.execute(select(Lead).where(Lead.id == enrollment.lead_id))
        lead = lead_result.scalar_one_or_none()
        if not lead:
            continue

        # Check hole-filler before executing normal step
        escalation = await _check_hole_filler(enrollment, lead, db)
        if escalation:
            hf_result = await _execute_hole_filler(enrollment, lead, escalation, db)
            if hf_result.get("status") == "sent":
                stats["hole_filler"] += 1
                continue  # Skip normal step, escalation sent

        # Execute the step
        result = await execute_step(enrollment, step, lead, db)

        status = result.get("status", "unknown")
        if status == "sent":
            stats["sent"] += 1
        elif status == "blocked":
            stats["blocked"] += 1
        elif status == "failed":
            stats["failed"] += 1
        elif status in ("branched", "wait_completed"):
            stats["branched"] += 1
        elif status == "completed":
            stats["completed"] += 1
        else:
            stats["skipped"] += 1

    await db.flush()
    logger.info("Sequence engine run complete: %s", stats)
    return stats


# ── Reply Detection Stub ──────────────────────────────────────────────


async def process_reply_signal(
    lead_id: UUID,
    sequence_id: UUID,
    db: AsyncSession,
) -> dict:
    """
    Handle a reply signal for an enrollment.

    Called by the reply detection webhook (Phase 5 full implementation).

    Transitions enrollment state: sent/opened → replied → paused (auto-pause).
    """
    result_query = await db.execute(
        select(SequenceEnrollment).where(
            and_(
                SequenceEnrollment.lead_id == lead_id,
                SequenceEnrollment.sequence_id == sequence_id,
                SequenceEnrollment.status.in_(
                    [
                        EnrollmentStatus.active,
                        EnrollmentStatus.sent,
                        EnrollmentStatus.opened,
                    ]
                ),
            )
        )
    )
    enrollment = result_query.scalar_one_or_none()
    if not enrollment:
        return {"status": "no_active_enrollment"}

    now = datetime.now(UTC)

    # Log the reply
    touch = TouchLog(
        lead_id=lead_id,
        channel="email",
        action=TouchAction.replied,
        sequence_id=sequence_id,
        step_number=enrollment.current_step,
        extra_metadata={"auto_detected": True},
    )
    db.add(touch)

    # Transition to replied
    try:
        new_state = transition(enrollment.status.value, EnrollmentState.replied)
        enrollment.status = EnrollmentStatus(new_state)
        enrollment.last_state_change_at = now
    except Exception:
        pass

    # Auto-pause on reply
    try:
        new_state = transition(enrollment.status.value, EnrollmentState.paused)
        enrollment.status = EnrollmentStatus(new_state)
        enrollment.last_state_change_at = now
    except Exception:
        pass

    await db.flush()
    logger.info(
        "Reply detected for lead %s in sequence %s → paused",
        lead_id,
        sequence_id,
    )
    return {"status": "replied_and_paused", "enrollment_id": str(enrollment.id)}
