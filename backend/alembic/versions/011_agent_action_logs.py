"""Create agent_action_logs table for agent audit trail.

Revision ID: 011_agent_action_logs
Revises: 010_chat_session_state
Create Date: 2026-03-24
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migration_helpers import table_exists, index_exists

revision = "011_agent_action_logs"
down_revision = "010_chat_session_state"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "agent_action_logs"):
        op.create_table(
            "agent_action_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("agent_name", sa.String(50), nullable=False),
            sa.Column("action", sa.String(100), nullable=False),
            sa.Column("params", JSONB, nullable=True),
            sa.Column("result_summary", JSONB, nullable=True),
            sa.Column("status", sa.String(20), nullable=False),
            sa.Column("latency_ms", sa.Integer, nullable=True),
            sa.Column("error_message", sa.Text, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    if not index_exists(bind, "ix_agent_action_logs_user_created"):
        op.create_index(
            "ix_agent_action_logs_user_created",
            "agent_action_logs",
            ["user_id", "created_at"],
        )

    if not index_exists(bind, "ix_agent_action_logs_agent_created"):
        op.create_index(
            "ix_agent_action_logs_agent_created",
            "agent_action_logs",
            ["agent_name", "created_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_agent_action_logs_agent_created", table_name="agent_action_logs")
    op.drop_index("ix_agent_action_logs_user_created", table_name="agent_action_logs")
    op.drop_table("agent_action_logs")
