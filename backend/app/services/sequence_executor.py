"""
Sequence execution engine.

Advances enrolled leads through their sequence steps based on:
- Delay timers between steps
- Compliance gates at every send
- Channel-specific dispatch (email/SMS/LinkedIn)
- Bounce/reply detection for auto-pause

This service is called by the Celery beat scheduler.
"""

import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.lead import Lead
from app.models.sequence import (
    EnrollmentStatus,
    Sequence,
    SequenceEnrollment,
    SequenceStep,
    StepType,
)
from app.models.template import Template
from app.models.touch_log import TouchAction, TouchLog
from app.services import compliance as compliance_svc
from app.services.email_service import send_email
from app.services.linkedin_service import (
    LinkedInAction,
    prepare_linkedin_outreach,
)
from app.services.sms_service import send_sms
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


async def get_due_enrollments(db: AsyncSession) -> list[SequenceEnrollment]:
    """
    Find all active enrollments where the next step is due.

    An enrollment is due when:
    1. Status is 'active'
    2. Time since last touch >= delay_hours of the next step
    3. OR it has 0 touches (just enrolled, first step due immediately)
    """
    result = await db.execute(
        select(SequenceEnrollment).where(
            SequenceEnrollment.status == EnrollmentStatus.active
        )
    )
    enrollments = result.scalars().all()

    due = []
    now = datetime.now(UTC)

    for enrollment in enrollments:
        # Load sequence and steps
        seq_result = await db.execute(
            select(Sequence).where(Sequence.id == enrollment.sequence_id)
        )
        sequence = seq_result.scalar_one_or_none()
        if not sequence or sequence.status.value != "active":
            continue

        steps = sorted(sequence.steps, key=lambda s: s.position)
        if enrollment.current_step >= len(steps):
            # Completed all steps
            enrollment.status = EnrollmentStatus.completed
            continue

        next_step = steps[enrollment.current_step]

        # Check delay
        if enrollment.current_step == 0:
            # First step: check time since enrollment
            time_since = (now - enrollment.enrolled_at).total_seconds() / 3600
        else:
            # Subsequent steps: check time since last touch
            last_touch_result = await db.execute(
                select(TouchLog)
                .where(
                    and_(
                        TouchLog.lead_id == enrollment.lead_id,
                        TouchLog.sequence_id == enrollment.sequence_id,
                    )
                )
                .order_by(TouchLog.created_at.desc())
                .limit(1)
            )
            last_touch = last_touch_result.scalar_one_or_none()
            if last_touch:
                time_since = (now - last_touch.created_at).total_seconds() / 3600
            else:
                time_since = float("inf")

        if time_since >= next_step.delay_hours:
            due.append(enrollment)

    return due


async def execute_step(
    enrollment: SequenceEnrollment,
    step: SequenceStep,
    lead: Lead,
    db: AsyncSession,
) -> dict:
    """
    Execute a single sequence step for a lead.

    1. Check compliance gate
    2. Load and render template
    3. Dispatch via appropriate channel
    4. Log the touch
    5. Advance the enrollment
    """
    channel = step.step_type.value if step.step_type != StepType.wait else None

    # Wait steps just advance the enrollment
    if step.step_type == StepType.wait:
        enrollment.current_step += 1
        return {"status": "wait_completed", "step": step.position}

    # Compliance gate
    can_send, reason = await compliance_svc.can_send_to_lead(
        lead.id, channel, db
    )
    if not can_send:
        logger.info(
            "Step blocked for lead %s: %s", lead.id, reason
        )
        return {"status": "blocked", "reason": reason}

    # Load template from step config
    template_id = step.config.get("template_id") if step.config else None
    template = None
    if template_id:
        template_result = await db.execute(
            select(Template).where(Template.id == UUID(template_id))
        )
        template = template_result.scalar_one_or_none()

    # Build context
    unsubscribe_url = None
    if channel == "email":
        unsub_token = compliance_svc.generate_unsubscribe_token(lead.id, "email")
        # In production, this would be your actual unsubscribe endpoint
        unsubscribe_url = f"https://app.gengyveusa.com/api/v1/unsubscribe/{unsub_token}"

    context = build_lead_context(
        lead=lead,
        sender=DEFAULT_SENDER,
        unsubscribe_url=unsubscribe_url,
    )

    # Dispatch based on channel
    result = {"status": "sent", "channel": channel, "step": step.position}

    if channel == "email" and template:
        subject = render_template(template.subject or "", context)
        html_body = render_template(template.html_body or template.plain_body, context)
        plain_body = render_template(template.plain_body, context)

        email_result = await send_email(
            to_email=lead.email,
            subject=subject,
            html_body=html_body,
            plain_body=plain_body,
            unsubscribe_url=unsubscribe_url,
            tags={
                "sequence_id": str(enrollment.sequence_id),
                "step": str(step.position),
                "lead_id": str(lead.id),
            },
        )
        result["message_id"] = email_result.message_id
        if not email_result.success:
            result["status"] = "failed"
            result["error"] = email_result.error

    elif channel == "sms" and template:
        body = render_template(template.plain_body, context)
        sms_result = await send_sms(
            to_phone=lead.phone or "",
            body=body,
            tags={
                "sequence_id": str(enrollment.sequence_id),
                "step": str(step.position),
            },
        )
        result["message_sid"] = sms_result.message_sid
        if not sms_result.success:
            result["status"] = "failed"
            result["error"] = sms_result.error

    elif channel == "linkedin" and template:
        note = render_template(template.plain_body, context)
        linkedin_action = LinkedInAction(
            template.linkedin_action or "connection_request"
        )
        li_result = await prepare_linkedin_outreach(
            action=linkedin_action,
            recipient_name=f"{lead.first_name} {lead.last_name}",
            recipient_title=lead.title,
            recipient_company=lead.company,
            note=note if linkedin_action == LinkedInAction.connection_request else "",
            body=note if linkedin_action != LinkedInAction.connection_request else "",
            subject=render_template(template.subject or "", context) if template.subject else "",
        )
        result["queued"] = li_result.queued
        if not li_result.success:
            result["status"] = "failed"
            result["error"] = li_result.error
    else:
        # No template configured — log but skip
        result["status"] = "skipped"
        result["reason"] = "no_template_configured"

    # Log the touch
    if result["status"] == "sent":
        touch = TouchLog(
            lead_id=lead.id,
            channel=channel,
            action=TouchAction.sent,
            sequence_id=enrollment.sequence_id,
            step_number=step.position,
            extra_metadata=result,
        )
        db.add(touch)

        # Advance enrollment
        enrollment.current_step += 1

        # Check if sequence is complete
        seq_result = await db.execute(
            select(Sequence).where(Sequence.id == enrollment.sequence_id)
        )
        seq = seq_result.scalar_one_or_none()
        if seq and enrollment.current_step >= len(seq.steps):
            enrollment.status = EnrollmentStatus.completed

    return result


async def run_sequence_engine(db: AsyncSession) -> dict:
    """
    Main entry point: find all due enrollments and execute their next step.

    Called by Celery beat (e.g., every 15 minutes).
    """
    stats = {"processed": 0, "sent": 0, "blocked": 0, "failed": 0, "skipped": 0}

    due_enrollments = await get_due_enrollments(db)
    logger.info("Found %d due enrollments", len(due_enrollments))

    for enrollment in due_enrollments:
        stats["processed"] += 1

        # Load sequence and step
        seq_result = await db.execute(
            select(Sequence).where(Sequence.id == enrollment.sequence_id)
        )
        sequence = seq_result.scalar_one_or_none()
        if not sequence:
            continue

        steps = sorted(sequence.steps, key=lambda s: s.position)
        if enrollment.current_step >= len(steps):
            enrollment.status = EnrollmentStatus.completed
            continue

        step = steps[enrollment.current_step]

        # Load lead
        lead_result = await db.execute(
            select(Lead).where(Lead.id == enrollment.lead_id)
        )
        lead = lead_result.scalar_one_or_none()
        if not lead:
            continue

        result = await execute_step(enrollment, step, lead, db)

        status = result.get("status", "unknown")
        if status == "sent":
            stats["sent"] += 1
        elif status == "blocked":
            stats["blocked"] += 1
        elif status == "failed":
            stats["failed"] += 1
        else:
            stats["skipped"] += 1

    await db.flush()
    logger.info("Sequence engine run complete: %s", stats)
    return stats
