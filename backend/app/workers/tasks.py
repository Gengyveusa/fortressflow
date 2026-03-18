"""
Celery tasks for FortressFlow.

All tasks that send messages MUST call can_send_to_lead before dispatching.
"""

import asyncio
import logging
from uuid import UUID

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _run_async(coro):
    """Run an async coroutine from a sync Celery task."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
def process_lead_enrichment(self, lead_id: str) -> dict:
    """
    Enrich a lead via ZoomInfo (primary) / Apollo (fallback).
    Stores the result in leads.proof_data.
    """
    async def _enrich():
        from app.database import AsyncSessionLocal
        from app.models.lead import Lead
        from app.services.enrichment import EnrichmentService
        from sqlalchemy import select

        async with AsyncSessionLocal() as db:
            result = await db.execute(select(Lead).where(Lead.id == UUID(lead_id)))
            lead = result.scalar_one_or_none()
            if lead is None:
                logger.warning("process_lead_enrichment: lead %s not found", lead_id)
                return {"status": "lead_not_found"}

            svc = EnrichmentService()
            data = await svc.enrich_lead(lead.email)
            if data:
                lead.proof_data = data
                await db.commit()
                logger.info("Enriched lead %s via %s", lead_id, data.get("source"))
            return {"status": "ok", "source": data.get("source", "none")}

    try:
        return _run_async(_enrich())
    except Exception as exc:
        logger.error("process_lead_enrichment failed for %s: %s", lead_id, exc)
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
        return _run_async(_send())
    except Exception as exc:
        logger.error("send_sequence_step failed: %s", exc)
        raise self.retry(exc=exc)


@celery_app.task(bind=True, max_retries=2, default_retry_delay=120)
def run_warmup_step(self, inbox_id: str) -> dict:
    """
    Advance the warmup schedule for an inbox by one step.
    Increments emails_sent and evaluates health metrics.
    """
    async def _warmup():
        from datetime import UTC, date
        from app.database import AsyncSessionLocal
        from app.models.warmup import WarmupQueue
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
            await db.commit()
            logger.info("Warmup step for inbox %s: %d/%d", inbox_id, warmup.emails_sent, warmup.emails_target)
            return {"status": "ok", "emails_sent": warmup.emails_sent}

    try:
        return _run_async(_warmup())
    except Exception as exc:
        logger.error("run_warmup_step failed for inbox %s: %s", inbox_id, exc)
        raise self.retry(exc=exc)
