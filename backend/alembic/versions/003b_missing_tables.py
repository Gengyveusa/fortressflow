"""Create sending_domains, sequences, sequence_steps, sequence_enrollments tables
that were accidentally omitted from earlier migrations but are required by
migrations 004 and 005 which ALTER them.

Revision ID: 003b_missing_tables
Revises: 003_templates_and_outreach
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB, ENUM

from migration_helpers import create_enum_idempotent, table_exists, index_exists

revision = "003b_missing_tables"
down_revision = "003_templates_and_outreach"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    # ── Enum types — use DO blocks so creation is idempotent at the SQL level
    create_enum_idempotent(
        "step_type", ["email", "sms", "linkedin", "delay", "condition"]
    )
    create_enum_idempotent(
        "enrollment_status",
        ["active", "paused", "completed", "bounced", "replied", "unsubscribed", "failed"],
    )
    create_enum_idempotent(
        "sequence_status", ["draft", "active", "paused", "archived"]
    )

    # ── sending_domains ─────────────────────────────────────────────────
    if not table_exists(bind, "sending_domains"):
        op.create_table(
            "sending_domains",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("domain", sa.String(255), unique=True, nullable=False),
            sa.Column(
                "health_score",
                sa.Float,
                nullable=False,
                server_default=sa.text("100.0"),
            ),
            sa.Column(
                "warmup_progress",
                sa.Float,
                nullable=False,
                server_default=sa.text("0.0"),
            ),
            sa.Column(
                "total_sent",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "total_bounced",
                sa.Integer,
                nullable=False,
                server_default=sa.text("0"),
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    if not index_exists(bind, "ix_sending_domains_domain"):
        op.create_index("ix_sending_domains_domain", "sending_domains", ["domain"], unique=True)

    # ── sequences ───────────────────────────────────────────────────────
    if not table_exists(bind, "sequences"):
        op.create_table(
            "sequences",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column("name", sa.String(255), nullable=False),
            sa.Column("description", sa.Text, nullable=True),
            sa.Column(
                "status",
                ENUM(
                    "draft", "active", "paused", "archived",
                    name="sequence_status",
                    create_type=False,
                ),
                nullable=False,
                server_default="draft",
            ),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )

    # ── sequence_steps ──────────────────────────────────────────────────
    if not table_exists(bind, "sequence_steps"):
        op.create_table(
            "sequence_steps",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "sequence_id",
                UUID(as_uuid=True),
                sa.ForeignKey("sequences.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "step_type",
                ENUM(
                    "email", "sms", "linkedin", "delay", "condition",
                    name="step_type",
                    create_type=False,
                ),
                nullable=False,
            ),
            sa.Column("position", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column("config", JSONB, nullable=True),
            sa.Column("delay_hours", sa.Float, nullable=False, server_default=sa.text("0")),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    if not index_exists(bind, "ix_sequence_steps_sequence_id"):
        op.create_index("ix_sequence_steps_sequence_id", "sequence_steps", ["sequence_id"])

    # ── sequence_enrollments ────────────────────────────────────────────
    if not table_exists(bind, "sequence_enrollments"):
        op.create_table(
            "sequence_enrollments",
            sa.Column(
                "id",
                UUID(as_uuid=True),
                primary_key=True,
                server_default=sa.text("gen_random_uuid()"),
            ),
            sa.Column(
                "sequence_id",
                UUID(as_uuid=True),
                sa.ForeignKey("sequences.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "lead_id",
                UUID(as_uuid=True),
                sa.ForeignKey("leads.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("current_step", sa.Integer, nullable=False, server_default=sa.text("0")),
            sa.Column(
                "status",
                ENUM(
                    "active", "paused", "completed", "bounced", "replied",
                    "unsubscribed", "failed",
                    name="enrollment_status",
                    create_type=False,
                ),
                nullable=False,
                server_default="active",
            ),
            sa.Column(
                "enrolled_at",
                sa.DateTime(timezone=True),
                server_default=sa.func.now(),
                nullable=False,
            ),
        )
    if not index_exists(bind, "ix_sequence_enrollments_sequence_id"):
        op.create_index("ix_sequence_enrollments_sequence_id", "sequence_enrollments", ["sequence_id"])
    if not index_exists(bind, "ix_sequence_enrollments_lead_id"):
        op.create_index("ix_sequence_enrollments_lead_id", "sequence_enrollments", ["lead_id"])


def downgrade() -> None:
    op.drop_index("ix_sequence_enrollments_lead_id", table_name="sequence_enrollments")
    op.drop_index("ix_sequence_enrollments_sequence_id", table_name="sequence_enrollments")
    op.drop_table("sequence_enrollments")
    op.drop_index("ix_sequence_steps_sequence_id", table_name="sequence_steps")
    op.drop_table("sequence_steps")
    op.drop_table("sequences")
    op.drop_index("ix_sending_domains_domain", table_name="sending_domains")
    op.drop_table("sending_domains")
    op.execute("DROP TYPE IF EXISTS sequence_status")
    op.execute("DROP TYPE IF EXISTS enrollment_status")
    op.execute("DROP TYPE IF EXISTS step_type")
