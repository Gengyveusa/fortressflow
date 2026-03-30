"""Phase 5: Reply detection, multi-channel orchestration, AI feedback loop.

Adds:
- reply_logs table (reply tracking with sentiment and AI analysis)
- reply_webhook_events table (raw webhook event log)
- linkedin_queue table (LinkedIn outreach queue)
- channel_metrics table (daily per-channel metrics aggregation)
- Indexes on sequence_enrollments.last_touch_at, reply_logs.received_at
- Index on touch_logs for channel+date queries

Revision ID: 006_phase5_reply_detection
Revises: 005_sequence_engine_phase4
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from migration_helpers import table_exists, index_exists, constraint_exists  # noqa: F401

revision = "006_phase5_reply_detection"
down_revision = "005_sequence_engine_phase4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── reply_logs ────────────────────────────────────────────────────────
    if not table_exists(bind, "reply_logs"):
        op.create_table(
            "reply_logs",
            sa.Column(
                "id",
                sa.UUID(as_uuid=True),
                primary_key=True,
                default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "enrollment_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("sequence_enrollments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "sequence_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("sequences.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "lead_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("leads.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("channel", sa.String(50), nullable=False),
            sa.Column("sender_email", sa.String(255), nullable=True),
            sa.Column("sender_phone", sa.String(50), nullable=True),
            sa.Column("subject", sa.String(500), nullable=True),
            sa.Column(
                "body_snippet",
                sa.Text,
                nullable=True,
                comment="First 500 chars of the reply body",
            ),
            sa.Column(
                "thread_id",
                sa.String(255),
                nullable=True,
                comment="RFC 2822 In-Reply-To / References for email thread matching",
            ),
            sa.Column("message_id", sa.String(255), nullable=True),
            sa.Column(
                "sentiment",
                sa.String(50),
                nullable=True,
                comment="positive | negative | neutral | out_of_office | unsubscribe",
            ),
            sa.Column(
                "sentiment_confidence",
                sa.Float,
                nullable=False,
                server_default=sa.text("0.0"),
            ),
            sa.Column(
                "ai_analysis",
                JSONB,
                nullable=True,
                comment="Full AI platform analysis results (HubSpot Breeze, Apollo, ZoomInfo)",
            ),
            sa.Column("ai_suggested_action", sa.String(255), nullable=True),
            sa.Column(
                "raw_payload",
                JSONB,
                nullable=True,
                comment="Original webhook / IMAP raw data for debugging",
            ),
            sa.Column(
                "received_at",
                sa.DateTime(timezone=True),
                nullable=False,
            ),
            sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # ── reply_webhook_events ──────────────────────────────────────────────
    if not table_exists(bind, "reply_webhook_events"):
        op.create_table(
            "reply_webhook_events",
            sa.Column(
                "id",
                sa.UUID(as_uuid=True),
                primary_key=True,
                default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "source",
                sa.String(50),
                nullable=False,
                comment="twilio | ses | parsio | imap",
            ),
            sa.Column("event_type", sa.String(100), nullable=False),
            sa.Column("raw_payload", JSONB, nullable=True),
            sa.Column(
                "processed",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("error", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # ── linkedin_queue ────────────────────────────────────────────────────
    if not table_exists(bind, "linkedin_queue"):
        op.create_table(
            "linkedin_queue",
            sa.Column(
                "id",
                sa.UUID(as_uuid=True),
                primary_key=True,
                default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column(
                "lead_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("leads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "enrollment_id",
                sa.UUID(as_uuid=True),
                sa.ForeignKey("sequence_enrollments.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "action",
                sa.String(50),
                nullable=False,
                comment="connection_request | inmail | message",
            ),
            sa.Column(
                "payload",
                JSONB,
                nullable=False,
                comment="Full LinkedInPayload serialized as JSON",
            ),
            sa.Column(
                "priority",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
                comment="Higher value = higher execution priority",
            ),
            sa.Column(
                "status",
                sa.String(50),
                nullable=False,
                server_default=sa.text("'pending'"),
                comment="pending | executing | completed | failed | manual",
            ),
            sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "ai_personalized",
                sa.Boolean,
                nullable=False,
                server_default=sa.text("false"),
            ),
            sa.Column("error", sa.Text, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
        )

    # ── channel_metrics ───────────────────────────────────────────────────
    if not table_exists(bind, "channel_metrics"):
        op.create_table(
            "channel_metrics",
            sa.Column(
                "id",
                sa.UUID(as_uuid=True),
                primary_key=True,
                default=sa.text("gen_random_uuid()"),
                nullable=False,
            ),
            sa.Column("channel", sa.String(50), nullable=False),
            sa.Column("date", sa.Date, nullable=False),
            sa.Column(
                "sent",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "delivered",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "bounced",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "opened",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "replied",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "failed",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "complained",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                nullable=False,
                server_default=sa.func.now(),
            ),
            sa.UniqueConstraint("channel", "date", name="uq_channel_metrics_channel_date"),
        )

    # ── Indexes on new tables ─────────────────────────────────────────────
    if not index_exists(bind, "ix_reply_logs_received_at"):
        op.create_index("ix_reply_logs_received_at", "reply_logs", ["received_at"])
    if not index_exists(bind, "ix_reply_logs_enrollment_id"):
        op.create_index("ix_reply_logs_enrollment_id", "reply_logs", ["enrollment_id"])
    if not index_exists(bind, "ix_reply_logs_sentiment"):
        op.create_index("ix_reply_logs_sentiment", "reply_logs", ["sentiment"])
    if not index_exists(bind, "ix_reply_webhook_events_created_at"):
        op.create_index("ix_reply_webhook_events_created_at", "reply_webhook_events", ["created_at"])
    if not index_exists(bind, "ix_linkedin_queue_status"):
        op.create_index("ix_linkedin_queue_status", "linkedin_queue", ["status"])
    if not index_exists(bind, "ix_linkedin_queue_scheduled_at"):
        op.create_index("ix_linkedin_queue_scheduled_at", "linkedin_queue", ["scheduled_at"])
    if not index_exists(bind, "ix_channel_metrics_channel_date"):
        op.create_index(
            "ix_channel_metrics_channel_date",
            "channel_metrics",
            ["channel", "date"],
            unique=True,
        )

    # ── Indexes on existing tables ────────────────────────────────────────
    if not index_exists(bind, "ix_sequence_enrollments_last_touch_at"):
        op.create_index(
            "ix_sequence_enrollments_last_touch_at",
            "sequence_enrollments",
            ["last_touch_at"],
        )
    if not index_exists(bind, "ix_touch_logs_channel_created"):
        op.create_index(
            "ix_touch_logs_channel_created",
            "touch_logs",
            ["channel", "created_at"],
        )


def downgrade() -> None:
    # ── Remove indexes on existing tables ─────────────────────────────────
    op.drop_index("ix_touch_logs_channel_created", table_name="touch_logs")
    op.drop_index(
        "ix_sequence_enrollments_last_touch_at",
        table_name="sequence_enrollments",
    )

    # ── Remove indexes on new tables ──────────────────────────────────────
    op.drop_index("ix_channel_metrics_channel_date", table_name="channel_metrics")
    op.drop_index("ix_linkedin_queue_scheduled_at", table_name="linkedin_queue")
    op.drop_index("ix_linkedin_queue_status", table_name="linkedin_queue")
    op.drop_index(
        "ix_reply_webhook_events_created_at",
        table_name="reply_webhook_events",
    )
    op.drop_index("ix_reply_logs_sentiment", table_name="reply_logs")
    op.drop_index("ix_reply_logs_enrollment_id", table_name="reply_logs")
    op.drop_index("ix_reply_logs_received_at", table_name="reply_logs")

    # ── Drop new tables (in dependency order) ──────────────────────────────
    op.drop_table("channel_metrics")
    op.drop_table("linkedin_queue")
    op.drop_table("reply_webhook_events")
    op.drop_table("reply_logs")
