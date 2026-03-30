"""Phase 3: Deliverability Fortress — sending inboxes, enhanced warmup, AI models.

Revision ID: 004_deliverability_fortress
Revises: 003_templates_and_outreach
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

from migration_helpers import table_exists, index_exists, column_exists

revision = "004_deliverability_fortress"
down_revision = "003b_missing_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── sending_inboxes ────────────────────────────────────────────────
    if not table_exists(bind, "sending_inboxes"):
        op.create_table(
            "sending_inboxes",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("email_address", sa.String(255), unique=True, nullable=False),
            sa.Column("display_name", sa.String(255), nullable=False),
            sa.Column("domain", sa.String(255), nullable=False),
            sa.Column("ses_identity_arn", sa.String(512), nullable=True),
            sa.Column("ses_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("dkim_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("dmarc_verified", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("status", sa.String(50), nullable=False, server_default="warming"),
            sa.Column("warmup_day", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("warmup_start_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("daily_sent", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("daily_limit", sa.Integer, nullable=False, server_default=sa.text("5")),
            sa.Column("bounce_rate_7d", sa.Float, nullable=False, server_default=sa.text("0.0")),
            sa.Column("spam_rate_7d", sa.Float, nullable=False, server_default=sa.text("0.0")),
            sa.Column("open_rate_7d", sa.Float, nullable=False, server_default=sa.text("0.0")),
            sa.Column("reply_rate_7d", sa.Float, nullable=False, server_default=sa.text("0.0")),
            sa.Column("health_score", sa.Float, nullable=False, server_default=sa.text("100.0")),
            sa.Column("total_sent", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("total_bounced", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("total_complaints", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("total_opens", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("total_replies", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("ai_sender_reputation_score", sa.Float, nullable=True),
            sa.Column("ai_optimal_send_hour", sa.Integer, nullable=True),
            sa.Column("ai_metadata", JSONB, nullable=True),
            sa.Column("notes", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not index_exists(bind, "ix_sending_inboxes_email_address"):
        op.create_index("ix_sending_inboxes_email_address", "sending_inboxes", ["email_address"])
    if not index_exists(bind, "ix_sending_inboxes_domain"):
        op.create_index("ix_sending_inboxes_domain", "sending_inboxes", ["domain"])
    if not index_exists(bind, "ix_sending_inboxes_status"):
        op.create_index("ix_sending_inboxes_status", "sending_inboxes", ["status"])

    # ── warmup_configs ─────────────────────────────────────────────────
    if not table_exists(bind, "warmup_configs"):
        op.create_table(
            "warmup_configs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "inbox_id",
                UUID(as_uuid=True),
                sa.ForeignKey("sending_inboxes.id", ondelete="CASCADE"),
                unique=True,
                nullable=False,
            ),
            sa.Column("ramp_duration_weeks", sa.Integer, nullable=False, server_default=sa.text("6")),
            sa.Column("initial_daily_volume", sa.Integer, nullable=False, server_default=sa.text("5")),
            sa.Column("target_daily_volume", sa.Integer, nullable=False, server_default=sa.text("50")),
            sa.Column("ramp_multiplier", sa.Float, nullable=False, server_default=sa.text("1.15")),
            sa.Column("ai_tuned", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("ai_ramp_adjustments", JSONB, nullable=True),
            sa.Column("ai_seed_profile", JSONB, nullable=True),
            sa.Column("max_bounce_rate", sa.Float, nullable=False, server_default=sa.text("0.05")),
            sa.Column("max_spam_rate", sa.Float, nullable=False, server_default=sa.text("0.001")),
            sa.Column("min_open_rate", sa.Float, nullable=False, server_default=sa.text("0.15")),
            sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
            sa.Column("paused_reason", sa.Text, nullable=True),
            sa.Column("last_ai_review", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # ── warmup_seed_logs ───────────────────────────────────────────────
    if not table_exists(bind, "warmup_seed_logs"):
        op.create_table(
            "warmup_seed_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "inbox_id", UUID(as_uuid=True), sa.ForeignKey("sending_inboxes.id", ondelete="CASCADE"), nullable=False
            ),
            sa.Column("lead_id", UUID(as_uuid=True), sa.ForeignKey("leads.id", ondelete="CASCADE"), nullable=False),
            sa.Column("warmup_date", sa.Date, nullable=False),
            sa.Column("selected_by", sa.String(100), nullable=False),
            sa.Column("selection_score", sa.Float, nullable=True),
            sa.Column("selection_reason", sa.Text, nullable=True),
            sa.Column("opened", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("replied", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("bounced", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("complained", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("feedback_sent", sa.Boolean, nullable=False, server_default=sa.text("false")),
            sa.Column("feedback_payload", JSONB, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )
    if not index_exists(bind, "ix_warmup_seed_logs_inbox_id"):
        op.create_index("ix_warmup_seed_logs_inbox_id", "warmup_seed_logs", ["inbox_id"])
    if not index_exists(bind, "ix_warmup_seed_logs_lead_id"):
        op.create_index("ix_warmup_seed_logs_lead_id", "warmup_seed_logs", ["lead_id"])
    if not index_exists(bind, "ix_warmup_seed_logs_warmup_date"):
        op.create_index("ix_warmup_seed_logs_warmup_date", "warmup_seed_logs", ["warmup_date"])

    # ── Alter warmup_queue: change inbox_id to UUID FK ─────────────────
    # Check if inbox_id is still the old string type (from migration 001)
    result = bind.execute(
        sa.text(
            "SELECT data_type FROM information_schema.columns "
            "WHERE table_name = 'warmup_queue' AND column_name = 'inbox_id'"
        )
    )
    row = result.fetchone()
    if row and row[0] in ("character varying", "text"):
        op.drop_index("ix_warmup_queue_inbox_id", table_name="warmup_queue", if_exists=True)
        op.drop_column("warmup_queue", "inbox_id")
        op.add_column(
            "warmup_queue",
            sa.Column(
                "inbox_id", UUID(as_uuid=True), sa.ForeignKey("sending_inboxes.id", ondelete="CASCADE"), nullable=False
            ),
        )
        if not index_exists(bind, "ix_warmup_queue_inbox_id"):
            op.create_index("ix_warmup_queue_inbox_id", "warmup_queue", ["inbox_id"])

    # Add new columns to warmup_queue
    if not column_exists(bind, "warmup_queue", "reply_rate"):
        op.add_column("warmup_queue", sa.Column("reply_rate", sa.Float, nullable=False, server_default=sa.text("0.0")))
    if not column_exists(bind, "warmup_queue", "seed_selection_method"):
        op.add_column("warmup_queue", sa.Column("seed_selection_method", sa.String(100), nullable=True))
    if not column_exists(bind, "warmup_queue", "seed_criteria"):
        op.add_column("warmup_queue", sa.Column("seed_criteria", JSONB, nullable=True))
    if not column_exists(bind, "warmup_queue", "seed_lead_ids"):
        op.add_column("warmup_queue", sa.Column("seed_lead_ids", JSONB, nullable=True))
    if not column_exists(bind, "warmup_queue", "health_check_passed"):
        op.add_column(
            "warmup_queue", sa.Column("health_check_passed", sa.Boolean, nullable=False, server_default=sa.text("true"))
        )
    if not column_exists(bind, "warmup_queue", "health_check_details"):
        op.add_column("warmup_queue", sa.Column("health_check_details", JSONB, nullable=True))

    # ── Enhance sending_domains ────────────────────────────────────────
    if not column_exists(bind, "sending_domains", "spf_verified"):
        op.add_column(
            "sending_domains", sa.Column("spf_verified", sa.Boolean, nullable=False, server_default=sa.text("false"))
        )
    if not column_exists(bind, "sending_domains", "dkim_verified"):
        op.add_column(
            "sending_domains", sa.Column("dkim_verified", sa.Boolean, nullable=False, server_default=sa.text("false"))
        )
    if not column_exists(bind, "sending_domains", "dmarc_verified"):
        op.add_column(
            "sending_domains", sa.Column("dmarc_verified", sa.Boolean, nullable=False, server_default=sa.text("false"))
        )
    if not column_exists(bind, "sending_domains", "bimi_verified"):
        op.add_column(
            "sending_domains", sa.Column("bimi_verified", sa.Boolean, nullable=False, server_default=sa.text("false"))
        )
    if not column_exists(bind, "sending_domains", "ses_domain_arn"):
        op.add_column("sending_domains", sa.Column("ses_domain_arn", sa.String(512), nullable=True))
    if not column_exists(bind, "sending_domains", "ses_dkim_tokens"):
        op.add_column("sending_domains", sa.Column("ses_dkim_tokens", JSONB, nullable=True))
    if not column_exists(bind, "sending_domains", "total_complaints"):
        op.add_column(
            "sending_domains", sa.Column("total_complaints", sa.Integer, nullable=False, server_default=sa.text("0"))
        )
    if not column_exists(bind, "sending_domains", "dedicated_ip_pool"):
        op.add_column("sending_domains", sa.Column("dedicated_ip_pool", sa.String(255), nullable=True))
    if not column_exists(bind, "sending_domains", "dedicated_ips"):
        op.add_column("sending_domains", sa.Column("dedicated_ips", JSONB, nullable=True))
    if not column_exists(bind, "sending_domains", "dmarc_policy"):
        op.add_column("sending_domains", sa.Column("dmarc_policy", sa.String(50), nullable=True))
    if not column_exists(bind, "sending_domains", "dmarc_rua"):
        op.add_column("sending_domains", sa.Column("dmarc_rua", sa.String(255), nullable=True))
    if not column_exists(bind, "sending_domains", "dmarc_ruf"):
        op.add_column("sending_domains", sa.Column("dmarc_ruf", sa.String(255), nullable=True))
    if not column_exists(bind, "sending_domains", "bimi_svg_url"):
        op.add_column("sending_domains", sa.Column("bimi_svg_url", sa.String(512), nullable=True))
    if not column_exists(bind, "sending_domains", "bimi_vmc_url"):
        op.add_column("sending_domains", sa.Column("bimi_vmc_url", sa.String(512), nullable=True))
    if not column_exists(bind, "sending_domains", "notes"):
        op.add_column("sending_domains", sa.Column("notes", sa.Text, nullable=True))
    if not column_exists(bind, "sending_domains", "updated_at"):
        op.add_column(
            "sending_domains",
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        )


def downgrade() -> None:
    # Remove sending_domains additions
    op.drop_column("sending_domains", "updated_at")
    op.drop_column("sending_domains", "notes")
    op.drop_column("sending_domains", "bimi_vmc_url")
    op.drop_column("sending_domains", "bimi_svg_url")
    op.drop_column("sending_domains", "dmarc_ruf")
    op.drop_column("sending_domains", "dmarc_rua")
    op.drop_column("sending_domains", "dmarc_policy")
    op.drop_column("sending_domains", "dedicated_ips")
    op.drop_column("sending_domains", "dedicated_ip_pool")
    op.drop_column("sending_domains", "total_complaints")
    op.drop_column("sending_domains", "ses_dkim_tokens")
    op.drop_column("sending_domains", "ses_domain_arn")
    op.drop_column("sending_domains", "bimi_verified")
    op.drop_column("sending_domains", "dmarc_verified")
    op.drop_column("sending_domains", "dkim_verified")
    op.drop_column("sending_domains", "spf_verified")

    # Revert warmup_queue
    op.drop_column("warmup_queue", "health_check_details")
    op.drop_column("warmup_queue", "health_check_passed")
    op.drop_column("warmup_queue", "seed_lead_ids")
    op.drop_column("warmup_queue", "seed_criteria")
    op.drop_column("warmup_queue", "seed_selection_method")
    op.drop_column("warmup_queue", "reply_rate")
    op.drop_index("ix_warmup_queue_inbox_id", table_name="warmup_queue")
    op.drop_column("warmup_queue", "inbox_id")
    op.add_column(
        "warmup_queue",
        sa.Column("inbox_id", sa.String(255), nullable=False),
    )
    op.create_index("ix_warmup_queue_inbox_id", "warmup_queue", ["inbox_id"])

    # Drop new tables
    op.drop_index("ix_warmup_seed_logs_warmup_date")
    op.drop_index("ix_warmup_seed_logs_lead_id")
    op.drop_index("ix_warmup_seed_logs_inbox_id")
    op.drop_table("warmup_seed_logs")
    op.drop_table("warmup_configs")
    op.drop_index("ix_sending_inboxes_status")
    op.drop_index("ix_sending_inboxes_domain")
    op.drop_index("ix_sending_inboxes_email_address")
    op.drop_table("sending_inboxes")
