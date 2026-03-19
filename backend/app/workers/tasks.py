"""
Celery tasks for FortressFlow.

All tasks that send messages MUST call can_send_to_lead before dispatching.
"""

import asyncio
import logging
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_lead_enrichment(self, lead_id: str) -> dict:
    """
    Enrich a lead via ZoomInfo (primary) / Apollo (fallback).
    Stores the result in leads.enriched_data.
    """
    async def _enrich():
        from app.database import AsyncSessionLocal
        from app.services.enrichment import EnrichmentService

        async with AsyncSessionLocal() as db:
            svc = EnrichmentService()
            result = await svc.enrich_lead(UUID(lead_id), db)
            await db.commit()
            return result

    try:
        return asyncio.run(_enrich())
    except Exception as exc:
        logger.error("process_lead_enrichment failed for %s: %s", lead_id, exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def enrich_lead_task(self, lead_id: str) -> dict:
    """Celery task wrapping enrichment_service.enrich_lead.

    Alias for process_lead_enrichment for Phase 2 naming consistency.
    """
    return process_lead_enrichment(lead_id)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def bulk_enrich_task(self, lead_ids: list[str]) -> dict:
    """Batch enrichment of multiple leads with rate limiting.

    Processes leads sequentially to respect external API rate limits.
    """
    async def _bulk_enrich():
        from app.database import AsyncSessionLocal
        from app.services.enrichment import EnrichmentService

        results = {"enriched": 0, "failed": 0, "skipped": 0}
        svc = EnrichmentService()

        async with AsyncSessionLocal() as db:
            for lid in lead_ids:
                try:
                    result = await svc.enrich_lead(UUID(lid), db)
                    if result.get("success"):
                        results["enriched"] += 1
                    else:
                        results["skipped"] += 1
                except Exception as exc:
                    logger.error("bulk_enrich: failed for %s: %s", lid, exc)
                    results["failed"] += 1
            await db.commit()
        return results

    try:
        return asyncio.run(_bulk_enrich())
    except Exception as exc:
        logger.error("bulk_enrich_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def re_verify_stale_leads(self) -> dict:
    """Find leads where last_enriched_at > 90 days ago and re-enrich them.

    Runs as a periodic Celery Beat task.
    """
    async def _re_verify():
        from app.database import AsyncSessionLocal
        from app.models.lead import Lead
        from app.services.enrichment import EnrichmentService
        from sqlalchemy import or_, select

        cutoff = datetime.now(UTC) - timedelta(days=settings.ENRICHMENT_TTL_DAYS)
        svc = EnrichmentService()
        results = {"re_enriched": 0, "failed": 0, "total_stale": 0}

        async with AsyncSessionLocal() as db:
            stmt = select(Lead).where(
                or_(
                    Lead.last_enriched_at < cutoff,
                    Lead.last_enriched_at.is_(None),
                )
            ).limit(500)  # Process in batches to avoid overloading
            result = await db.execute(stmt)
            stale_leads = result.scalars().all()
            results["total_stale"] = len(stale_leads)

            for lead in stale_leads:
                try:
                    enrich_result = await svc.enrich_lead(lead.id, db)
                    if enrich_result.get("success"):
                        results["re_enriched"] += 1
                    else:
                        results["failed"] += 1
                except Exception as exc:
                    logger.error("re_verify: failed for %s: %s", lead.id, exc)
                    results["failed"] += 1

            await db.commit()
        logger.info("re_verify_stale_leads: %s", results)
        return results

    try:
        return asyncio.run(_re_verify())
    except Exception as exc:
        logger.error("re_verify_stale_leads failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=30)
def send_sequence_step(
    self,
    lead_id: str,
    sequence_id: str,
    step_number: int,
    channel: str,
) -> dict:
    """
    Send a single sequence step to a lead.
    Performs compliance check before dispatching.
    """
    async def _send():
        from app.database import AsyncSessionLocal
        from app.models.touch_log import TouchLog, TouchAction
        from app.services.compliance import can_send_to_lead

        async with AsyncSessionLocal() as db:
            can_send, reason = await can_send_to_lead(UUID(lead_id), channel, db)
            if not can_send:
                logger.info(
                    "Sequence step blocked for lead %s on %s: %s",
                    lead_id, channel, reason,
                )
                return {"status": "blocked", "reason": reason}

            log = TouchLog(
                lead_id=UUID(lead_id),
                channel=channel,
                action=TouchAction.sent,
                sequence_id=UUID(sequence_id),
                step_number=step_number,
                extra_metadata={"task": "send_sequence_step"},
            )
            db.add(log)
            await db.commit()
            logger.info("Logged sequence step for lead %s, step %d", lead_id, step_number)
            return {"status": "sent"}

    try:
        return asyncio.run(_send())
    except Exception as exc:
        logger.error("send_sequence_step failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def run_sequence_engine(self) -> dict:
    """
    Main sequence engine tick.

    Finds all due enrollments and advances them through their sequence steps.
    Should be called by Celery Beat every 15 minutes.
    """
    async def _run():
        from app.database import AsyncSessionLocal
        from app.services.sequence_executor import run_sequence_engine as engine_run

        async with AsyncSessionLocal() as db:
            result = await engine_run(db)
            await db.commit()
            return result

    try:
        return asyncio.run(_run())
    except Exception as exc:
        logger.error("run_sequence_engine failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def run_warmup_step(self, inbox_id: str) -> dict:
    """
    Advance the warmup schedule for an inbox by one step.
    Increments emails_sent and evaluates health metrics.
    """
    async def _warmup():
        from datetime import date
        from app.database import AsyncSessionLocal
        from app.models.warmup import WarmupQueue
        from app.models.sending_inbox import SendingInbox
        from sqlalchemy import select, and_

        async with AsyncSessionLocal() as db:
            today = date.today()
            result = await db.execute(
                select(WarmupQueue).where(
                    and_(
                        WarmupQueue.inbox_id == inbox_id,
                        WarmupQueue.date == today,
                        WarmupQueue.status == "pending",
                    )
                )
            )
            warmup = result.scalar_one_or_none()
            if warmup is None:
                return {"status": "no_pending_warmup"}

            warmup.emails_sent += 1
            if warmup.emails_sent >= warmup.emails_target:
                warmup.status = "completed"

            # Update inbox daily counter
            inbox_result = await db.execute(
                select(SendingInbox).where(SendingInbox.id == inbox_id)
            )
            inbox = inbox_result.scalar_one_or_none()
            if inbox:
                inbox.daily_sent = warmup.emails_sent

            await db.commit()
            logger.info("Warmup step for inbox %s: %d/%d", inbox_id, warmup.emails_sent, warmup.emails_target)
            return {"status": "ok", "emails_sent": warmup.emails_sent}

    try:
        return asyncio.run(_warmup())
    except Exception as exc:
        logger.error("run_warmup_step failed for inbox %s: %s", inbox_id, exc)
        raise self.retry(exc=exc)


# ── Phase 3: New warmup + deliverability tasks ────────────────────────


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def run_warmup_cycle_task(self) -> dict:
    """
    Run the AI-powered warmup cycle for all warming inboxes.

    Runs daily via Celery Beat:
    1. Advances each inbox's warmup schedule
    2. Selects AI-scored seeds
    3. Creates warmup queue entries
    4. Checks health metrics and pauses unhealthy inboxes
    """
    async def _cycle():
        from app.database import AsyncSessionLocal
        from app.services.warmup_ai import run_warmup_cycle

        async with AsyncSessionLocal() as db:
            result = await run_warmup_cycle(db)
            await db.commit()
            return result

    try:
        return asyncio.run(_cycle())
    except Exception as exc:
        logger.error("run_warmup_cycle_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def process_warmup_feedback_task(self) -> dict:
    """
    Process warmup outcomes and send feedback to AI platforms.

    Runs daily via Celery Beat (after warmup cycle):
    - Finds seed logs with tracked outcomes
    - Pushes data back to HubSpot Breeze / ZoomInfo Copilot / Apollo AI
    - Closes the bi-directional learning loop
    """
    async def _feedback():
        from app.database import AsyncSessionLocal
        from app.services.warmup_ai import process_warmup_feedback

        async with AsyncSessionLocal() as db:
            result = await process_warmup_feedback(db)
            await db.commit()
            return result

    try:
        return asyncio.run(_feedback())
    except Exception as exc:
        logger.error("process_warmup_feedback_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def reset_daily_counters_task(self) -> dict:
    """Reset daily_sent counters for all sending inboxes. Runs at midnight UTC."""
    async def _reset():
        from app.database import AsyncSessionLocal
        from app.services.deliverability_router import DeliverabilityRouter

        async with AsyncSessionLocal() as db:
            router = DeliverabilityRouter(db)
            count = await router.reset_daily_counters()
            await db.commit()
            return {"reset_count": count}

    try:
        return asyncio.run(_reset())
    except Exception as exc:
        logger.error("reset_daily_counters_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=120)
def update_domain_metrics_task(self) -> dict:
    """Aggregate inbox metrics to domain level. Runs hourly."""
    async def _update():
        from app.database import AsyncSessionLocal
        from app.services.deliverability_router import DeliverabilityRouter

        async with AsyncSessionLocal() as db:
            router = DeliverabilityRouter(db)
            count = await router.update_domain_metrics()
            await db.commit()
            return {"domains_updated": count}

    try:
        return asyncio.run(_update())
    except Exception as exc:
        logger.error("update_domain_metrics_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=120)
def recalculate_health_scores_task(self) -> dict:
    """Recalculate health scores for all inboxes. Runs every 6 hours."""
    async def _recalc():
        from app.database import AsyncSessionLocal
        from app.services.warmup_ai import recalculate_inbox_health_scores

        async with AsyncSessionLocal() as db:
            count = await recalculate_inbox_health_scores(db)
            await db.commit()
            return {"inboxes_updated": count}

    try:
        return asyncio.run(_recalc())
    except Exception as exc:
        logger.error("recalculate_health_scores_task failed: %s", exc)
        raise self.retry(exc=exc)


# ── Phase 4: Sequence AI + Reply Detection ────────────────────────────


@celery_app.task(bind=True, max_retries=1, default_retry_delay=60)
def process_reply_signal_task(
    self, lead_id: str, sequence_id: str
) -> dict:
    """
    Handle a reply signal for an enrollment.

    Transitions enrollment: sent/opened → replied → paused (auto-pause).
    Called by webhook or IMAP polling when a lead replies.
    """
    async def _process():
        from app.database import AsyncSessionLocal
        from app.services.sequence_executor import process_reply_signal

        async with AsyncSessionLocal() as db:
            result = await process_reply_signal(
                lead_id=UUID(lead_id),
                sequence_id=UUID(sequence_id),
                db=db,
            )
            await db.commit()
            return result

    try:
        return asyncio.run(_process())
    except Exception as exc:
        logger.error(
            "process_reply_signal_task failed for lead %s: %s",
            lead_id, exc,
        )
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def generate_ai_sequence_task(
    self,
    prompt: str,
    target_industry: str = "dental",
    channels: list[str] | None = None,
) -> dict:
    """
    Generate an AI-powered sequence from a natural-language prompt.

    Uses HubSpot Breeze, ZoomInfo Copilot, and Apollo AI platforms.
    Returns the sequence ID and generation metadata.
    """
    async def _generate():
        from app.database import AsyncSessionLocal
        from app.services.sequence_ai_service import SequenceAIService

        ai_svc = SequenceAIService()
        result = await ai_svc.generate_sequence(
            prompt=prompt,
            target_industry=target_industry,
            channels=channels or ["email", "linkedin", "sms"],
        )
        return {
            "success": result.success,
            "steps_generated": len(result.sequence_config.get("steps", [])),
            "error": result.error,
        }

    try:
        return asyncio.run(_generate())
    except Exception as exc:
        logger.error("generate_ai_sequence_task failed: %s", exc)
        raise self.retry(exc=exc)


# ── Phase 5: Reply Detection + Multi-Channel + AI Feedback ────────────


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def poll_imap_replies_task(self) -> dict:
    """
    Poll IMAP inbox for new replies. Runs every 5 minutes via Celery Beat.

    Fetches UNSEEN messages, creates ReplySignal for each, and processes
    through the full reply pipeline (sentiment → AI analysis → FSM transition).
    """
    async def _poll():
        import sentry_sdk
        from app.database import AsyncSessionLocal
        from app.services.reply_service import ReplyService

        stats = {"polled": 0, "processed": 0, "failed": 0}

        async with AsyncSessionLocal() as db:
            svc = ReplyService(db)
            try:
                signals = await svc.poll_imap_inbox()
            except Exception as exc:
                logger.error("poll_imap_replies_task: IMAP poll error: %s", exc)
                sentry_sdk.capture_exception(exc)
                raise

            stats["polled"] = len(signals)

            for signal in signals:
                try:
                    result = await svc.process_reply(signal)
                    stats["processed"] += 1
                    logger.info(
                        "IMAP reply processed: enrollment=%s sentiment=%s",
                        result.matched_enrollment_id,
                        result.sentiment,
                    )
                except Exception as exc:
                    logger.error(
                        "poll_imap_replies_task: reply processing failed: %s", exc
                    )
                    sentry_sdk.capture_exception(exc)
                    stats["failed"] += 1

            await db.commit()

        logger.info("poll_imap_replies_task: %s", stats)
        return stats

    try:
        return asyncio.run(_poll())
    except Exception as exc:
        logger.error("poll_imap_replies_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def process_reply_full_task(self, reply_data: dict) -> dict:
    """
    Full reply processing: match enrollment, analyze sentiment, AI analysis, FSM transition.

    Called from webhook handlers with raw reply data dict. Reconstructs a ReplySignal
    and runs the complete ReplyService.process_reply() pipeline.

    Args:
        reply_data: dict with keys: channel, body, sender_email, sender_phone,
                    subject, thread_id, message_id, raw_headers, received_at (ISO string)
    """
    async def _process():
        import sentry_sdk
        from datetime import datetime, UTC
        from app.database import AsyncSessionLocal
        from app.services.reply_service import ReplyService, ReplySignal

        # Parse received_at from ISO string
        received_at_raw = reply_data.get("received_at")
        try:
            received_at = (
                datetime.fromisoformat(received_at_raw)
                if received_at_raw
                else datetime.now(UTC)
            )
        except (ValueError, TypeError):
            received_at = datetime.now(UTC)

        signal = ReplySignal(
            channel=reply_data.get("channel", "email"),
            body=reply_data.get("body", ""),
            sender_email=reply_data.get("sender_email") or None,
            sender_phone=reply_data.get("sender_phone") or None,
            subject=reply_data.get("subject") or None,
            thread_id=reply_data.get("thread_id") or None,
            message_id=reply_data.get("message_id") or None,
            raw_headers=reply_data.get("raw_headers") or {},
            received_at=received_at,
        )

        async with AsyncSessionLocal() as db:
            svc = ReplyService(db)
            try:
                result = await svc.process_reply(signal)
                await db.commit()
            except Exception as exc:
                logger.error(
                    "process_reply_full_task: process_reply failed for channel=%s from=%s: %s",
                    signal.channel,
                    signal.sender_email or signal.sender_phone,
                    exc,
                )
                sentry_sdk.capture_exception(exc)
                await db.rollback()
                raise

        logger.info(
            "process_reply_full_task: enrollment=%s sentiment=%s channel=%s",
            result.matched_enrollment_id,
            result.sentiment,
            signal.channel,
        )
        return {
            "matched_enrollment_id": str(result.matched_enrollment_id)
            if result.matched_enrollment_id
            else None,
            "matched_sequence_id": str(result.matched_sequence_id)
            if result.matched_sequence_id
            else None,
            "sentiment": result.sentiment,
            "confidence": result.confidence,
            "channel": signal.channel,
        }

    try:
        return asyncio.run(_process())
    except Exception as exc:
        logger.error("process_reply_full_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def execute_linkedin_queue_task(self) -> dict:
    """
    Execute pending LinkedIn queue items. Runs every 30 minutes.

    Processes the LinkedIn action queue respecting the daily 25-action limit
    and human-like random delays (45-120s) between actions.
    """
    async def _execute():
        import sentry_sdk
        from app.database import AsyncSessionLocal
        from app.services.linkedin_service import LinkedInService

        async with AsyncSessionLocal() as db:
            svc = LinkedInService(db)
            try:
                results = await svc.execute_queue()
                await db.commit()
            except Exception as exc:
                logger.error(
                    "execute_linkedin_queue_task: queue execution failed: %s", exc
                )
                sentry_sdk.capture_exception(exc)
                await db.rollback()
                raise

        executed = len([r for r in results if r.get("status") == "executed"])
        failed = len([r for r in results if r.get("status") == "failed"])
        skipped = len([r for r in results if r.get("status") not in ("executed", "failed")])

        stats = {
            "total": len(results),
            "executed": executed,
            "failed": failed,
            "skipped": skipped,
        }
        logger.info("execute_linkedin_queue_task: %s", stats)
        return stats

    try:
        return asyncio.run(_execute())
    except Exception as exc:
        logger.error("execute_linkedin_queue_task failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def push_ai_feedback_task(self, sequence_id: str) -> dict:
    """
    Push sequence metrics to AI platforms after completion.

    Aggregates performance data (reply rates, open rates, bounce rates)
    and pushes back to HubSpot Breeze, ZoomInfo Copilot, and Apollo AI
    to close the bi-directional learning loop.
    """
    async def _push():
        import sentry_sdk
        from uuid import UUID
        from app.database import AsyncSessionLocal
        from app.services.ai_feedback_service import AIFeedbackService

        async with AsyncSessionLocal() as db:
            svc = AIFeedbackService(db)
            try:
                result = await svc.push_completion_feedback(UUID(sequence_id))
                await db.commit()
            except Exception as exc:
                logger.error(
                    "push_ai_feedback_task: feedback push failed for sequence %s: %s",
                    sequence_id,
                    exc,
                )
                sentry_sdk.capture_exception(exc)
                await db.rollback()
                raise

        logger.info(
            "push_ai_feedback_task: sequence=%s result=%s",
            sequence_id,
            result,
        )
        return result

    try:
        return asyncio.run(_push())
    except Exception as exc:
        logger.error("push_ai_feedback_task failed for sequence %s: %s", sequence_id, exc)
        raise self.retry(exc=exc)


# ── Phase 7: Chat Feedback + Topic Categorization ─────────────────────


def _categorize_chat_topic(message: str) -> str:
    """
    Categorize a chat message into a topic bucket for analytics.

    Returns one of: sequences, deliverability, leads, compliance, templates,
    analytics, setup, general.
    """
    msg = message.lower()

    if any(kw in msg for kw in ["sequence", "enroll", "outreach", "campaign"]):
        return "sequences"

    if any(kw in msg for kw in [
        "warmup", "bounce", "spam", "deliverability", "inbox", "domain",
        "reputation", "open rate",
    ]):
        return "deliverability"

    if any(kw in msg for kw in ["lead", "import", "contact", "prospect", "csv"]):
        return "leads"

    if any(kw in msg for kw in ["compliance", "gdpr", "can-spam", "tcpa", "consent", "unsubscribe", "dnc"]):
        return "compliance"

    if any(kw in msg for kw in ["template", "email subject", "subject line", "copy", "write"]):
        return "templates"

    if any(kw in msg for kw in ["dashboard", "metric", "analytic", "report", "stat", "kpi"]):
        return "analytics"

    if any(kw in msg for kw in ["setup", "install", "configure", "start", "how do i", "getting started"]):
        return "setup"

    return "general"


@celery_app.task(bind=True, max_retries=2, default_retry_delay=60)
def push_chat_feedback_task(self, user_id: str, session_id: str, message: str, response: str) -> dict:
    """
    Push chat interaction feedback to AI platforms and analytics.

    Categorizes the topic and sends anonymized feedback to improve
    HubSpot Breeze / ZoomInfo Copilot / Apollo AI routing.
    """
    topic = _categorize_chat_topic(message)
    logger.info(
        "push_chat_feedback_task: user=%s session=%s topic=%s",
        user_id, session_id, topic,
    )
    return {"topic": topic, "status": "logged"}


@celery_app.task(bind=True, max_retries=1, default_retry_delay=300)
def aggregate_channel_metrics_task(self) -> dict:
    """
    Aggregate channel health metrics for monitoring. Runs hourly.

    Collects per-channel stats (sent/bounced/replied/delivered) over the last 24h
    and logs a consolidated health snapshot for dashboards and alerting.
    """
    async def _aggregate():
        import sentry_sdk
        from app.database import AsyncSessionLocal
        from app.services.channel_orchestrator import ChannelOrchestrator

        async with AsyncSessionLocal() as db:
            orchestrator = ChannelOrchestrator(db)
            try:
                health = await orchestrator.get_channel_health()
                # Commit any metric writes (orchestrator may update counters)
                await db.commit()
            except Exception as exc:
                logger.error(
                    "aggregate_channel_metrics_task: health aggregation failed: %s", exc
                )
                sentry_sdk.capture_exception(exc)
                await db.rollback()
                raise

        logger.info("aggregate_channel_metrics_task: %s", health)
        return health

    try:
        return asyncio.run(_aggregate())
    except Exception as exc:
        logger.error("aggregate_channel_metrics_task failed: %s", exc)
        raise self.retry(exc=exc)


# ── Phase 7: In-App AI Chatbot ────────────────────────────────────────


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def push_chat_feedback_task(
    self,
    session_id: str,
    message: str,
    response_snippet: str,
    ai_sources: list[str],
) -> dict:
    """
    Phase 7: Push anonymized chat interaction metrics to AI platforms
    for bi-directional learning loops.

    Strips PII before sending — only sends topic categories and engagement patterns.
    """
    async def _push():
        from app.services.platform_ai_service import PlatformAIService

        # Anonymize: categorize the message topic without sending raw content
        topic = _categorize_chat_topic(message)

        svc = PlatformAIService()
        results = {}

        # Push to HubSpot Breeze for engagement learning
        if "hubspot_breeze" in ai_sources and settings.HUBSPOT_BREEZE_ENABLED:
            try:
                await svc.push_interaction_feedback(
                    platform="hubspot",
                    feedback_type="chat_interaction",
                    data={
                        "topic": topic,
                        "session_id": session_id,
                        "had_response": bool(response_snippet),
                        "sources_used": ai_sources,
                    },
                )
                results["hubspot"] = "pushed"
            except Exception as e:
                logger.warning("HubSpot chat feedback failed: %s", e)
                results["hubspot"] = f"failed: {e}"

        # Push to Apollo AI for recommendation improvement
        if "apollo_ai" in ai_sources and settings.APOLLO_AI_ENABLED:
            try:
                await svc.push_interaction_feedback(
                    platform="apollo",
                    feedback_type="chat_interaction",
                    data={
                        "topic": topic,
                        "session_id": session_id,
                        "sources_used": ai_sources,
                    },
                )
                results["apollo"] = "pushed"
            except Exception as e:
                logger.warning("Apollo chat feedback failed: %s", e)
                results["apollo"] = f"failed: {e}"

        return results

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    return loop.run_until_complete(_push())


def _categorize_chat_topic(message: str) -> str:
    """Categorize chat message into broad topics for anonymized feedback."""
    msg_lower = message.lower()
    if any(kw in msg_lower for kw in ["sequence", "outreach", "campaign", "step"]):
        return "sequences"
    if any(kw in msg_lower for kw in ["warmup", "warm up", "deliverability", "bounce", "spam"]):
        return "deliverability"
    if any(kw in msg_lower for kw in ["lead", "import", "contact", "enrich"]):
        return "leads"
    if any(kw in msg_lower for kw in ["reply", "response", "inbox"]):
        return "replies"
    if any(kw in msg_lower for kw in ["complian", "consent", "gdpr", "can-spam", "tcpa"]):
        return "compliance"
    if any(kw in msg_lower for kw in ["template", "email", "content", "subject"]):
        return "templates"
    if any(kw in msg_lower for kw in ["analytic", "metric", "dashboard", "report"]):
        return "analytics"
    if any(kw in msg_lower for kw in ["setup", "config", "install", "deploy", "start"]):
        return "setup"
    return "general"
