"""Phase 7: Chat logs table for in-app AI chatbot assistant.

Adds:
- chat_logs table with user_id, session_id, message, response, ai_model, ai_sources
- Indexes on user_id + created_at, session_id

Revision ID: 007_chat_logs_phase7
Revises: 006_phase5_reply_detection
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from migration_helpers import table_exists, index_exists

revision = "007_chat_logs_phase7"
down_revision = "006_phase5_reply_detection"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not table_exists(bind, "chat_logs"):
        op.create_table(
            "chat_logs",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("user_id", sa.String(255), nullable=False),
            sa.Column("session_id", sa.String(255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("response", sa.Text(), nullable=False, server_default=""),
            sa.Column("ai_model", sa.String(100), nullable=True),
            sa.Column("ai_sources", JSONB(), nullable=True),
            sa.Column("context_snapshot", JSONB(), nullable=True),
            sa.Column("tokens_used", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        )

    # Composite index for user history queries
    if not index_exists(bind, "ix_chat_logs_user_created"):
        op.create_index("ix_chat_logs_user_created", "chat_logs", ["user_id", "created_at"])
    # Index for session lookups
    if not index_exists(bind, "ix_chat_logs_session"):
        op.create_index("ix_chat_logs_session", "chat_logs", ["session_id"])
    # Index for user_id alone (for listing user's sessions)
    if not index_exists(bind, "ix_chat_logs_user_id"):
        op.create_index("ix_chat_logs_user_id", "chat_logs", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_chat_logs_user_id", table_name="chat_logs")
    op.drop_index("ix_chat_logs_session", table_name="chat_logs")
    op.drop_index("ix_chat_logs_user_created", table_name="chat_logs")
    op.drop_table("chat_logs")
