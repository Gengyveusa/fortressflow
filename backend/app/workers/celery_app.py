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
        # Phase 2: Enrichment
        "app.workers.tasks.process_lead_enrichment": {"queue": "enrichment"},
        "app.workers.tasks.enrich_lead_task": {"queue": "enrichment"},
        "app.workers.tasks.bulk_enrich_task": {"queue": "enrichment"},
        "app.workers.tasks.re_verify_stale_leads": {"queue": "enrichment"},
        # Phase 3 (prev session): Sequences
        "app.workers.tasks.send_sequence_step": {"queue": "sequences"},
        "app.workers.tasks.run_sequence_engine": {"queue": "sequences"},
        # Phase 3: Warmup & Deliverability
        "app.workers.tasks.run_warmup_step": {"queue": "warmup"},
        "app.workers.tasks.run_warmup_cycle_task": {"queue": "warmup"},
        "app.workers.tasks.process_warmup_feedback_task": {"queue": "warmup"},
        "app.workers.tasks.reset_daily_counters_task": {"queue": "warmup"},
        "app.workers.tasks.update_domain_metrics_task": {"queue": "warmup"},
        "app.workers.tasks.recalculate_health_scores_task": {"queue": "warmup"},
        # Phase 4: Sequence AI + Reply Detection
        "app.workers.tasks.process_reply_signal_task": {"queue": "sequences"},
        "app.workers.tasks.generate_ai_sequence_task": {"queue": "sequences"},
        # Phase 5: Reply Detection + Multi-Channel + AI Feedback
        "app.workers.tasks.poll_imap_replies_task": {"queue": "sequences"},
        "app.workers.tasks.process_reply_full_task": {"queue": "sequences"},
        "app.workers.tasks.execute_linkedin_queue_task": {"queue": "sequences"},
        "app.workers.tasks.push_ai_feedback_task": {"queue": "warmup"},
        "app.workers.tasks.aggregate_channel_metrics_task": {"queue": "warmup"},
    },
    beat_schedule={
        # Enrichment: re-verify stale leads daily at 2 AM UTC
        "re-verify-stale-leads-daily": {
            "task": "app.workers.tasks.re_verify_stale_leads",
            "schedule": crontab(hour=2, minute=0),
        },
        # Sequences: run engine every 15 minutes
        "run-sequence-engine": {
            "task": "app.workers.tasks.run_sequence_engine",
            "schedule": crontab(minute=f"*/{settings.SEQUENCE_ENGINE_INTERVAL_MINUTES}"),
        },
        # Warmup: run AI warmup cycle daily at 6 AM UTC (before business hours)
        "run-warmup-cycle": {
            "task": "app.workers.tasks.run_warmup_cycle_task",
            "schedule": crontab(hour=6, minute=0),
        },
        # Warmup: process feedback loop daily at 7 AM UTC
        "process-warmup-feedback": {
            "task": "app.workers.tasks.process_warmup_feedback_task",
            "schedule": crontab(hour=7, minute=0),
        },
        # Deliverability: reset daily counters at midnight UTC
        "reset-daily-counters": {
            "task": "app.workers.tasks.reset_daily_counters_task",
            "schedule": crontab(hour=0, minute=0),
        },
        # Deliverability: update domain metrics every hour
        "update-domain-metrics": {
            "task": "app.workers.tasks.update_domain_metrics_task",
            "schedule": crontab(minute=30),
        },
        # Deliverability: recalculate health scores every 6 hours
        "recalculate-health-scores": {
            "task": "app.workers.tasks.recalculate_health_scores_task",
            "schedule": crontab(hour="*/6", minute=15),
        },
        # Phase 5: Poll IMAP inbox for replies every 5 minutes
        "poll-imap-replies": {
            "task": "app.workers.tasks.poll_imap_replies_task",
            "schedule": crontab(minute="*/5"),
        },
        # Phase 5: Execute LinkedIn queue every 30 minutes (at :00 and :30)
        "execute-linkedin-queue": {
            "task": "app.workers.tasks.execute_linkedin_queue_task",
            "schedule": crontab(minute="0,30"),
        },
        # Phase 5: Aggregate channel health metrics every hour at :45
        "aggregate-channel-metrics": {
            "task": "app.workers.tasks.aggregate_channel_metrics_task",
            "schedule": crontab(minute=45),
        },
    },
)
