from celery import Celery
from celery.schedules import crontab

from app.config import settings

celery_app = Celery(
    "fortressflow",
    broker=settings.RABBITMQ_URL,
    backend=settings.REDIS_URL,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "app.workers.tasks.process_lead_enrichment": {"queue": "enrichment"},
        "app.workers.tasks.enrich_lead_task": {"queue": "enrichment"},
        "app.workers.tasks.bulk_enrich_task": {"queue": "enrichment"},
        "app.workers.tasks.re_verify_stale_leads": {"queue": "enrichment"},
        "app.workers.tasks.send_sequence_step": {"queue": "sequences"},
        "app.workers.tasks.run_sequence_engine": {"queue": "sequences"},
        "app.workers.tasks.run_warmup_step": {"queue": "warmup"},
    },
    beat_schedule={
        "re-verify-stale-leads-daily": {
            "task": "app.workers.tasks.re_verify_stale_leads",
            "schedule": crontab(hour=2, minute=0),  # Run daily at 2:00 AM UTC
        },
        "run-sequence-engine": {
            "task": "app.workers.tasks.run_sequence_engine",
            "schedule": crontab(minute=f"*/{settings.SEQUENCE_ENGINE_INTERVAL_MINUTES}"),
        },
    },
)
