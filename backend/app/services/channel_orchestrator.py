"""
Multi-Channel Orchestrator — Phase 5.

Central dispatch logic with failover, hole-filler escalation,
channel rate limit enforcement, and retry logic.

Called by the sequence engine for each enrollment step, replacing
direct channel dispatch. Provides:
- Channel selection with failover (email fails → try LinkedIn/SMS if consented)
- Global rate limit enforcement (300-400 email/day, 30 SMS/day, 25 LinkedIn/day)
- Hole-filler escalation (2+ unanswered emails → auto-queue LinkedIn/SMS)
- Retry failed touches with exponential backoff
- Channel health monitoring
"""

import asyncio
import logging
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.lead import Lead
from app.models.sequence import (
    EnrollmentStatus,
    SequenceEnrollment,
    SequenceStep,
    StepType,
)
from app.models.template import Template
from app.models.touch_log import TouchAction, TouchLog
from app.services import compliance as compliance_svc
from app.services.state_machine import EnrollmentState, is_sendable, transition

logger = logging.getLogger(__name__)


# ── Channel Limits ─────────────────────────────────────────────────────────

CHANNEL_DAILY_LIMITS: dict[str, int] = {
    "email": settings.GLOBAL_DAILY_EMAIL_LIMIT,
    "sms": settings.GLOBAL_DAILY_SMS_LIMIT,
    "linkedin": settings.GLOBAL_DAILY_LINKEDIN_LIMIT,
}

# Failures that should NOT trigger failover (hard failures)
HARD_FAILURE_REASONS = {
    "bounce",
    "hard_bounce",
    "complaint",
    "spam_complaint",
    "unsubscribe",
    "tcpa_consent",
    "no_active_consent",
    "dnc",
    "lead_not_found",
    "no_sms_consent_record",
}

MAX_RETRIES = settings.MAX_TOUCH_RETRIES
RETRY_BACKOFF_MINUTES = settings.RETRY_BACKOFF_MINUTES


# ── Channel Orchestrator ───────────────────────────────────────────────────


class ChannelOrchestrator:
    """
    Central dispatcher for all outbound sequence touches.

    Responsibilities:
    1. Determine target channel from sequence step
    2. Enforce global daily limits per channel
    3. Run compliance gate before any send
    4. Dispatch via appropriate service (email, SMS, LinkedIn)
    5. Handle failover on soft failures
    6. Trigger hole-filler escalation after unanswered email runs
    7. Retry logic with exponential backoff
    """

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    # ── Primary Dispatch ───────────────────────────────────────────────────

    async def dispatch(
        self,
        enrollment: SequenceEnrollment,
        step: SequenceStep,
        lead: Lead,
        template: Template,
    ) -> dict[str, Any]:
        """
        Main dispatch entry point for a sequence step.

        1. Determine channel from step.step_type
        2. Check global daily limit for channel
        3. Run compliance gate (can_send_to_lead)
        4. Dispatch via appropriate service
        5. On failure: attempt failover (soft failures only)
        6. Log result

        Returns dispatch result dict with keys:
        - success: bool
        - channel: str
        - channel_result: dict (service-specific result)
        - failover_used: bool
        - failover_channel: str | None
        - error: str | None
        """
        channel = self._resolve_channel(step)

        logger.info(
            "Orchestrator dispatch: enrollment=%s lead=%s channel=%s step=%d",
            enrollment.id,
            lead.id,
            channel,
            step.position,
        )

        # Check global limits
        under_limit, remaining = await self.check_global_limits(channel)
        if not under_limit:
            return {
                "success": False,
                "channel": channel,
                "error": f"Global daily limit reached for {channel}",
                "limit_exhausted": True,
            }

        # Compliance gate
        can_send, compliance_reason = await compliance_svc.can_send_to_lead(
            lead.id, channel, self.db
        )
        if not can_send:
            logger.info(
                "Compliance gate blocked %s for lead %s: %s",
                channel, lead.id, compliance_reason,
            )
            return {
                "success": False,
                "channel": channel,
                "error": compliance_reason,
                "compliance_blocked": True,
            }

        # Dispatch to channel service
        try:
            result = await self._dispatch_to_channel(
                channel=channel,
                enrollment=enrollment,
                step=step,
                lead=lead,
                template=template,
            )

            if result.get("success"):
                return {
                    "success": True,
                    "channel": channel,
                    "channel_result": result,
                    "failover_used": False,
                    "failover_channel": None,
                }

            # Soft failure — try failover
            error = result.get("error", "unknown_error")
            if not self._is_hard_failure(error):
                logger.info(
                    "Soft failure on %s for lead %s (%s) — attempting failover",
                    channel, lead.id, error,
                )
                failover_result = await self.attempt_failover(
                    enrollment=enrollment,
                    lead=lead,
                    original_channel=channel,
                    error=error,
                )
                if failover_result:
                    return {
                        "success": True,
                        "channel": channel,
                        "channel_result": result,
                        "failover_used": True,
                        "failover_channel": failover_result.get("channel"),
                        "failover_result": failover_result,
                    }

            return {
                "success": False,
                "channel": channel,
                "channel_result": result,
                "error": error,
                "failover_used": False,
            }

        except Exception as exc:
            logger.error(
                "Dispatch exception for enrollment %s channel %s: %s",
                enrollment.id, channel, exc, exc_info=True,
            )
            return {
                "success": False,
                "channel": channel,
                "error": str(exc),
            }

    def _resolve_channel(self, step: SequenceStep) -> str:
        """Map StepType to a channel string."""
        step_channel_map = {
            StepType.email: "email",
            StepType.sms: "sms",
            StepType.linkedin: "linkedin",
        }
        return step_channel_map.get(step.step_type, "email")

    def _is_hard_failure(self, error: str) -> bool:
        """Check if an error reason is a hard failure (no failover)."""
        error_lower = error.lower()
        for hard in HARD_FAILURE_REASONS:
            if hard in error_lower:
                return True
        return False

    async def _dispatch_to_channel(
        self,
        channel: str,
        enrollment: SequenceEnrollment,
        step: SequenceStep,
        lead: Lead,
        template: Template,
    ) -> dict[str, Any]:
        """
        Dispatch a touch to the appropriate channel service.

        Returns a dict with at minimum: success (bool), error (str|None).
        """
        if channel == "email":
            return await self._dispatch_email(enrollment, step, lead, template)
        elif channel == "sms":
            return await self._dispatch_sms(enrollment, step, lead, template)
        elif channel == "linkedin":
            return await self._dispatch_linkedin(enrollment, step, lead, template)
        else:
            return {"success": False, "error": f"Unknown channel: {channel}"}

    async def _dispatch_email(
        self,
        enrollment: SequenceEnrollment,
        step: SequenceStep,
        lead: Lead,
        template: Template,
    ) -> dict[str, Any]:
        """Dispatch via email service (SES via DeliverabilityRouter)."""
        try:
            from app.services.deliverability_router import DeliverabilityRouter
            from app.services.email_service import send_email
            from app.services.template_engine import build_lead_context, render_template

            router = DeliverabilityRouter(self.db)
            sending_inbox = await router.select_inbox()

            if not sending_inbox:
                return {"success": False, "error": "no_sending_inbox_available"}

            sender_info = {
                "name": sending_inbox.display_name or "Dr. Thad",
                "email": sending_inbox.email_address,
            }

            lead_ctx = await build_lead_context(lead)
            subject = render_template(template.subject or "", lead_ctx)
            body_html = render_template(template.body_html or template.body or "", lead_ctx)
            body_text = render_template(template.body or "", lead_ctx)

            message_id = f"<{uuid.uuid4()}@fortressflow>"

            result = await send_email(
                to_email=lead.email,
                subject=subject,
                body_html=body_html,
                body_text=body_text,
                from_email=sender_info["email"],
                from_name=sender_info["name"],
                message_id=message_id,
            )

            if hasattr(result, "success"):
                return {
                    "success": result.success,
                    "message_id": message_id,
                    "error": result.error if not result.success else None,
                }
            return {"success": bool(result), "message_id": message_id}

        except Exception as exc:
            logger.error("Email dispatch error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def _dispatch_sms(
        self,
        enrollment: SequenceEnrollment,
        step: SequenceStep,
        lead: Lead,
        template: Template,
    ) -> dict[str, Any]:
        """Dispatch via Twilio SMS service with full TZ/TCPA gate."""
        try:
            from app.services.sms_service import send_sms
            from app.services.template_engine import build_lead_context, render_template

            if not lead.phone:
                return {"success": False, "error": "lead_no_phone_number"}

            lead_ctx = await build_lead_context(lead)
            body = render_template(template.body or "", lead_ctx)

            result = await send_sms(
                to_phone=lead.phone,
                body=body,
                lead=lead,
                db=self.db,
            )

            return {
                "success": result.success,
                "message_sid": result.message_sid,
                "segments": result.segments,
                "error": result.error,
            }

        except Exception as exc:
            logger.error("SMS dispatch error: %s", exc)
            return {"success": False, "error": str(exc)}

    async def _dispatch_linkedin(
        self,
        enrollment: SequenceEnrollment,
        step: SequenceStep,
        lead: Lead,
        template: Template,
    ) -> dict[str, Any]:
        """Dispatch via LinkedIn service (queue connection request or InMail)."""
        try:
            from app.services.linkedin_service import LinkedInService

            li_svc = LinkedInService(self.db)
            step_config = step.config or {}
            action = step_config.get("linkedin_action", "connection_request")

            if action == "inmail":
                from app.services.template_engine import build_lead_context, render_template

                lead_ctx = await build_lead_context(lead)
                subject = render_template(template.subject or "", lead_ctx)
                body = render_template(template.body or "", lead_ctx)

                li_result = await li_svc.queue_inmail(
                    lead=lead,
                    subject=subject,
                    body=body,
                    enrollment_id=enrollment.id,
                )
            else:
                note = step_config.get("linkedin_note", "")
                li_result = await li_svc.queue_connection_request(
                    lead=lead,
                    note=note or None,
                    enrollment_id=enrollment.id,
                )

            return {
                "success": li_result.success,
                "queued": li_result.queued,
                "queue_item_id": li_result.queue_item_id,
                "error": li_result.error,
            }

        except Exception as exc:
            logger.error("LinkedIn dispatch error: %s", exc)
            return {"success": False, "error": str(exc)}

    # ── Global Rate Limits ─────────────────────────────────────────────────

    async def check_global_limits(self, channel: str) -> tuple[bool, int]:
        """
        Check if the global daily limit for a channel has been reached.

        Returns (under_limit, remaining_today).
        """
        limit = CHANNEL_DAILY_LIMITS.get(channel, 100)
        today_start = datetime.now(UTC).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

        try:
            result = await self.db.execute(
                select(func.count(TouchLog.id)).where(
                    and_(
                        TouchLog.channel == channel,
                        TouchLog.action == TouchAction.sent,
                        TouchLog.created_at >= today_start,
                    )
                )
            )
            today_count = result.scalar() or 0
        except Exception as exc:
            logger.warning("Could not count today's %s sends: %s", channel, exc)
            today_count = 0

        remaining = max(0, limit - today_count)
        under_limit = today_count < limit

        logger.debug(
            "Global limit check: channel=%s today=%d limit=%d remaining=%d",
            channel, today_count, limit, remaining,
        )

        return under_limit, remaining

    # ── Failover ───────────────────────────────────────────────────────────

    async def attempt_failover(
        self,
        enrollment: SequenceEnrollment,
        lead: Lead,
        original_channel: str,
        error: str,
    ) -> dict[str, Any] | None:
        """
        Attempt to send via an alternate channel when the original fails.

        Failover order:
        - email fails → try LinkedIn (if consented) → try SMS (if consented)
        - sms fails → try email
        - linkedin fails → try email

        Only attempts failover for soft failures (not bounce/complaint/DNC).

        Returns failover result dict or None if no failover available.
        """
        if original_channel == "email":
            # Try LinkedIn first
            li_can, li_reason = await compliance_svc.can_send_to_lead(
                lead.id, "linkedin", self.db
            )
            if li_can:
                li_under, _ = await self.check_global_limits("linkedin")
                if li_under:
                    logger.info(
                        "Failover: email→linkedin for lead %s", lead.id
                    )
                    try:
                        from app.services.linkedin_service import LinkedInService

                        li_svc = LinkedInService(self.db)
                        li_result = await li_svc.queue_connection_request(
                            lead=lead, enrollment_id=enrollment.id
                        )
                        if li_result.success:
                            return {
                                "success": True,
                                "channel": "linkedin",
                                "result": li_result,
                                "failover_reason": error,
                            }
                    except Exception as exc:
                        logger.warning("LinkedIn failover error: %s", exc)

            # Try SMS
            sms_can, sms_reason = await compliance_svc.can_send_to_lead(
                lead.id, "sms", self.db
            )
            if sms_can and lead.phone:
                sms_under, _ = await self.check_global_limits("sms")
                if sms_under:
                    logger.info(
                        "Failover: email→sms for lead %s", lead.id
                    )
                    try:
                        from app.services.sms_service import send_sms

                        sms_result = await send_sms(
                            to_phone=lead.phone,
                            body=(
                                f"Hi {lead.first_name}, just wanted to follow up "
                                f"on my email about Gengyve. Worth a quick chat?"
                            ),
                            lead=lead,
                            db=self.db,
                        )
                        if sms_result.success:
                            return {
                                "success": True,
                                "channel": "sms",
                                "result": sms_result,
                                "failover_reason": error,
                            }
                    except Exception as exc:
                        logger.warning("SMS failover error: %s", exc)

        elif original_channel in ("sms", "linkedin"):
            # Fallback to email
            email_can, email_reason = await compliance_svc.can_send_to_lead(
                lead.id, "email", self.db
            )
            if email_can:
                email_under, _ = await self.check_global_limits("email")
                if email_under:
                    logger.info(
                        "Failover: %s→email for lead %s", original_channel, lead.id
                    )
                    # Email failover handled by the sequence engine on next cycle
                    return {
                        "success": True,
                        "channel": "email",
                        "result": {"queued_for_email": True},
                        "failover_reason": error,
                    }

        logger.info(
            "No failover available for lead %s (original: %s)", lead.id, original_channel
        )
        return None

    # ── Hole-Filler Escalation ─────────────────────────────────────────────

    async def execute_hole_filler(
        self,
        enrollment: SequenceEnrollment,
        lead: Lead,
    ) -> dict[str, Any] | None:
        """
        Hole-filler escalation: after 2+ unanswered emails, escalate to
        LinkedIn or SMS to break through.

        Logic:
        1. Count unanswered email touches for this enrollment
        2. If ≥ 2 unanswered → check LinkedIn consent → queue AI-personalized connect
        3. If no LinkedIn consent → check SMS consent → send nudge
        4. Mark enrollment.hole_filler_triggered = True

        Returns escalation result or None if no escalation possible.
        """
        if enrollment.hole_filler_triggered:
            logger.debug(
                "Hole filler already triggered for enrollment %s", enrollment.id
            )
            return None

        # Count unanswered email sends (sent but no reply/open follow-up)
        unanswered_count = await self._count_unanswered_emails(enrollment)

        if unanswered_count < 2:
            logger.debug(
                "Enrollment %s: only %d unanswered emails — hole filler not triggered",
                enrollment.id, unanswered_count,
            )
            return None

        logger.info(
            "Hole filler triggered for enrollment %s (%d unanswered emails)",
            enrollment.id, unanswered_count,
        )

        result: dict[str, Any] | None = None

        # 1. Try LinkedIn escalation
        li_can, _ = await compliance_svc.can_send_to_lead(
            lead.id, "linkedin", self.db
        )
        li_under, _ = await self.check_global_limits("linkedin")

        if li_can and li_under:
            try:
                from app.services.linkedin_service import LinkedInService

                li_svc = LinkedInService(self.db)
                li_result = await li_svc.queue_connection_request(
                    lead=lead,
                    enrollment_id=enrollment.id,
                )

                if li_result.success:
                    result = {
                        "escalation_channel": "linkedin",
                        "queue_item_id": li_result.queue_item_id,
                        "unanswered_emails": unanswered_count,
                    }
                    enrollment.escalation_channel = "linkedin"
                    logger.info(
                        "Hole filler: queued LinkedIn for enrollment %s", enrollment.id
                    )
            except Exception as exc:
                logger.warning("Hole filler LinkedIn error: %s", exc)

        # 2. Fallback to SMS if no LinkedIn
        if not result:
            sms_can, _ = await compliance_svc.can_send_to_lead(
                lead.id, "sms", self.db
            )
            sms_under, _ = await self.check_global_limits("sms")

            if sms_can and sms_under and lead.phone:
                try:
                    from app.services.sms_service import send_sms

                    nudge_body = (
                        f"Hi {lead.first_name}! I sent a few emails about "
                        f"Gengyve's AI dental re-engagement platform. "
                        f"Worth 5 mins? {settings.BASE_URL if hasattr(settings, 'BASE_URL') else 'gengyveusa.com'}"
                    )

                    sms_result = await send_sms(
                        to_phone=lead.phone,
                        body=nudge_body,
                        lead=lead,
                        db=self.db,
                    )

                    if sms_result.success:
                        result = {
                            "escalation_channel": "sms",
                            "message_sid": sms_result.message_sid,
                            "unanswered_emails": unanswered_count,
                        }
                        enrollment.escalation_channel = "sms"
                        logger.info(
                            "Hole filler: SMS nudge sent for enrollment %s", enrollment.id
                        )
                except Exception as exc:
                    logger.warning("Hole filler SMS error: %s", exc)

        if result:
            enrollment.hole_filler_triggered = True

            # Transition enrollment to escalated state
            try:
                new_state = transition(
                    str(enrollment.status.value), EnrollmentState.escalated
                )
                enrollment.status = EnrollmentStatus(new_state)
                enrollment.last_state_change_at = datetime.now(UTC)
            except Exception as exc:
                logger.warning(
                    "Could not transition enrollment %s to escalated: %s",
                    enrollment.id, exc,
                )

            await self.db.commit()

        return result

    async def _count_unanswered_emails(
        self, enrollment: SequenceEnrollment
    ) -> int:
        """
        Count email touches for this enrollment that had no reply.

        "Unanswered" = sent email with no subsequent replied action for same lead.
        """
        try:
            # Count sent email touches for this enrollment's lead + sequence
            sent_result = await self.db.execute(
                select(func.count(TouchLog.id)).where(
                    and_(
                        TouchLog.lead_id == enrollment.lead_id,
                        TouchLog.channel == "email",
                        TouchLog.action == TouchAction.sent,
                        TouchLog.sequence_id == enrollment.sequence_id,
                    )
                )
            )
            sent_count = sent_result.scalar() or 0

            # Check for any replies
            replied_result = await self.db.execute(
                select(func.count(TouchLog.id)).where(
                    and_(
                        TouchLog.lead_id == enrollment.lead_id,
                        TouchLog.action == TouchAction.replied,
                        TouchLog.sequence_id == enrollment.sequence_id,
                    )
                )
            )
            replied_count = replied_result.scalar() or 0

            return max(0, sent_count - replied_count)

        except Exception as exc:
            logger.warning(
                "Could not count unanswered emails for enrollment %s: %s",
                enrollment.id, exc,
            )
            return 0

    # ── Retry Logic ────────────────────────────────────────────────────────

    async def retry_failed_touch(
        self,
        enrollment_id: UUID,
        step_position: int,
        channel: str,
    ) -> dict[str, Any]:
        """
        Retry a previously failed touch with exponential backoff.

        Backoff: RETRY_BACKOFF_MINUTES * (2 ^ retry_attempt).
        Max retries: MAX_TOUCH_RETRIES (default 3).

        Returns retry result dict.
        """
        # Load enrollment
        enr_result = await self.db.execute(
            select(SequenceEnrollment).where(
                SequenceEnrollment.id == enrollment_id
            )
        )
        enrollment = enr_result.scalar_one_or_none()

        if not enrollment:
            return {"success": False, "error": "enrollment_not_found"}

        # Count previous retries for this step
        retry_count = await self._count_retries(enrollment_id, step_position, channel)

        if retry_count >= MAX_RETRIES:
            logger.info(
                "Max retries (%d) reached for enrollment %s step %d channel %s",
                MAX_RETRIES, enrollment_id, step_position, channel,
            )
            return {
                "success": False,
                "error": "max_retries_exceeded",
                "retry_count": retry_count,
            }

        # Compute backoff wait
        backoff_minutes = RETRY_BACKOFF_MINUTES * (2 ** retry_count)
        next_attempt_at = datetime.now(UTC) + timedelta(minutes=backoff_minutes)

        logger.info(
            "Scheduling retry %d for enrollment %s step %d channel %s "
            "(backoff: %d mins, next at %s)",
            retry_count + 1,
            enrollment_id,
            step_position,
            channel,
            backoff_minutes,
            next_attempt_at.isoformat(),
        )

        # Log the retry scheduling
        retry_log = TouchLog(
            lead_id=enrollment.lead_id,
            channel=channel,
            action=TouchAction.sent,
            sequence_id=enrollment.sequence_id,
            step_number=step_position,
            extra_metadata={
                "retry_attempt": retry_count + 1,
                "scheduled_retry_at": next_attempt_at.isoformat(),
                "backoff_minutes": backoff_minutes,
                "enrollment_id": str(enrollment_id),
                "is_retry_schedule": True,
            },
        )
        self.db.add(retry_log)
        await self.db.commit()

        return {
            "success": True,
            "retry_attempt": retry_count + 1,
            "next_attempt_at": next_attempt_at.isoformat(),
            "backoff_minutes": backoff_minutes,
        }

    async def _count_retries(
        self,
        enrollment_id: UUID,
        step_position: int,
        channel: str,
    ) -> int:
        """Count previous retry attempts for a specific step."""
        try:
            result = await self.db.execute(
                select(func.count(TouchLog.id)).where(
                    and_(
                        TouchLog.channel == channel,
                        TouchLog.step_number == step_position,
                        TouchLog.extra_metadata["enrollment_id"].astext == str(enrollment_id),
                        TouchLog.extra_metadata["is_retry_schedule"].astext == "true",
                    )
                )
            )
            return result.scalar() or 0
        except Exception as exc:
            logger.warning("Could not count retries: %s", exc)
            return 0

    # ── Channel Health ─────────────────────────────────────────────────────

    async def get_channel_health(self) -> dict[str, Any]:
        """
        Return per-channel health metrics for the last 24 hours.

        Includes: sent, delivered, bounced, replied, failed, delivery rate.
        """
        cutoff = datetime.now(UTC) - timedelta(hours=24)
        health: dict[str, Any] = {}

        for channel in ("email", "sms", "linkedin"):
            try:
                # Sent
                sent_r = await self.db.execute(
                    select(func.count(TouchLog.id)).where(
                        and_(
                            TouchLog.channel == channel,
                            TouchLog.action == TouchAction.sent,
                            TouchLog.created_at >= cutoff,
                        )
                    )
                )
                sent = sent_r.scalar() or 0

                # Delivered
                delivered_r = await self.db.execute(
                    select(func.count(TouchLog.id)).where(
                        and_(
                            TouchLog.channel == channel,
                            TouchLog.action == TouchAction.delivered,
                            TouchLog.created_at >= cutoff,
                        )
                    )
                )
                delivered = delivered_r.scalar() or 0

                # Bounced
                bounced_r = await self.db.execute(
                    select(func.count(TouchLog.id)).where(
                        and_(
                            TouchLog.channel == channel,
                            TouchLog.action == TouchAction.bounced,
                            TouchLog.created_at >= cutoff,
                        )
                    )
                )
                bounced = bounced_r.scalar() or 0

                # Replied
                replied_r = await self.db.execute(
                    select(func.count(TouchLog.id)).where(
                        and_(
                            TouchLog.channel == channel,
                            TouchLog.action == TouchAction.replied,
                            TouchLog.created_at >= cutoff,
                        )
                    )
                )
                replied = replied_r.scalar() or 0

                daily_limit = CHANNEL_DAILY_LIMITS.get(channel, 100)

                health[channel] = {
                    "sent_24h": sent,
                    "delivered_24h": delivered,
                    "bounced_24h": bounced,
                    "replied_24h": replied,
                    "delivery_rate": round(delivered / sent, 4) if sent > 0 else 0.0,
                    "bounce_rate": round(bounced / sent, 4) if sent > 0 else 0.0,
                    "reply_rate": round(replied / sent, 4) if sent > 0 else 0.0,
                    "daily_limit": daily_limit,
                    "remaining_today": max(
                        0,
                        daily_limit - (await self.check_global_limits(channel))[1]
                        # Note: remaining from check_global_limits
                    ),
                    "healthy": (
                        (bounced / sent < 0.05) if sent > 0 else True
                    ),
                }

            except Exception as exc:
                logger.error(
                    "Channel health check error for %s: %s", channel, exc
                )
                health[channel] = {
                    "error": str(exc),
                    "healthy": False,
                }

        return health
