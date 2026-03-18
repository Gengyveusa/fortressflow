"""Initial schema

Revision ID: 001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enums
    consent_channel = postgresql.ENUM(
        "email", "sms", "linkedin", name="consent_channel", create_type=False
    )
    consent_method = postgresql.ENUM(
        "meeting_card", "web_form", "import_verified", name="consent_method", create_type=False
    )
    touch_action = postgresql.ENUM(
        "sent", "delivered", "opened", "replied", "bounced", "complained", "unsubscribed",
        name="touch_action",
        create_type=False,
    )

    op.execute("CREATE TYPE consent_channel AS ENUM ('email', 'sms', 'linkedin')")
    op.execute("CREATE TYPE consent_method AS ENUM ('meeting_card', 'web_form', 'import_verified')")
    op.execute(
        "CREATE TYPE touch_action AS ENUM "
        "('sent', 'delivered', 'opened', 'replied', 'bounced', 'complained', 'unsubscribed')"
    )

    # leads
    op.create_table(
        "leads",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("company", sa.String(255), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column("meeting_verified", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("proof_data", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_leads_email", "leads", ["email"])

    # consents
    op.create_table(
        "consents",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", consent_channel, nullable=False),
        sa.Column("method", consent_method, nullable=False),
        sa.Column("proof", postgresql.JSONB(), nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consents_lead_id", "consents", ["lead_id"])

    # dnc_blocks
    op.create_table(
        "dnc_blocks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("identifier", sa.String(255), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("reason", sa.String(500), nullable=False),
        sa.Column("blocked_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("source", sa.String(100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_dnc_blocks_identifier", "dnc_blocks", ["identifier"])

    # touch_logs
    op.create_table(
        "touch_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("lead_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("channel", sa.String(50), nullable=False),
        sa.Column("action", touch_action, nullable=False),
        sa.Column("sequence_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("step_number", sa.Integer(), nullable=True),
        sa.Column("metadata", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_touch_logs_lead_id", "touch_logs", ["lead_id"])

    # warmup_queue
    op.create_table(
        "warmup_queue",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("inbox_id", sa.String(255), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("emails_sent", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("emails_target", sa.Integer(), nullable=False),
        sa.Column("bounce_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("spam_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("open_rate", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("status", sa.String(50), nullable=False, server_default="'pending'"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_warmup_queue_inbox_id", "warmup_queue", ["inbox_id"])


def downgrade() -> None:
    op.drop_table("warmup_queue")
    op.drop_table("touch_logs")
    op.drop_table("dnc_blocks")
    op.drop_table("consents")
    op.drop_table("leads")
    op.execute("DROP TYPE IF EXISTS touch_action")
    op.execute("DROP TYPE IF EXISTS consent_method")
    op.execute("DROP TYPE IF EXISTS consent_channel")
