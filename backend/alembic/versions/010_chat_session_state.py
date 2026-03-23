"""Add session_state JSONB column to chat_logs for multi-turn command flows.

Revision ID: 010_chat_session_state
Revises: 009_api_configurations
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = "010_chat_session_state"
down_revision = "009_api_configurations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "chat_logs",
        sa.Column("session_state", JSONB, nullable=True),
    )
    op.add_column(
        "chat_logs",
        sa.Column(
            "response_type",
            sa.String(50),
            nullable=True,
            server_default="text",
        ),
    )
    op.add_column(
        "chat_logs",
        sa.Column("response_metadata", JSONB, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("chat_logs", "response_metadata")
    op.drop_column("chat_logs", "response_type")
    op.drop_column("chat_logs", "session_state")
