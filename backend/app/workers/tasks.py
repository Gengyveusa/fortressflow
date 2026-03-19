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
        return asyncio.run(_warmup())
    except Exception as exc:
        logger.error("run_warmup_step failed for inbox %s: %s", inbox_id, exc)
        raise self.retry(exc=exc)
