"""add diagnostic_runs and fix_suggestions tables

Revision ID: aeb9ed50ccc6
Revises: 012_agent_training
Create Date: 2026-03-29 20:00:32.160587

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "aeb9ed50ccc6"
down_revision: Union[str, None] = "012_agent_training"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "diagnostic_runs",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("run_type", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("summary", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_diagnostic_runs_status", "diagnostic_runs", ["status"], unique=False)
    op.create_index("ix_diagnostic_runs_user_created", "diagnostic_runs", ["user_id", "created_at"], unique=False)

    op.create_table(
        "fix_suggestions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("diagnostic_run_id", sa.UUID(), nullable=True),
        sa.Column("agent_name", sa.String(length=50), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("diagnosis", sa.Text(), nullable=True),
        sa.Column("suggested_fix", sa.Text(), nullable=True),
        sa.Column("fix_type", sa.String(length=30), nullable=True),
        sa.Column("severity", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("applied_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("validation_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=True),
        sa.ForeignKeyConstraint(
            ["diagnostic_run_id"],
            ["diagnostic_runs.id"],
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_fix_suggestions_agent_action", "fix_suggestions", ["agent_name", "action"], unique=False)
    op.create_index("ix_fix_suggestions_status", "fix_suggestions", ["status"], unique=False)
    op.create_index("ix_fix_suggestions_user_created", "fix_suggestions", ["user_id", "created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_fix_suggestions_user_created", table_name="fix_suggestions")
    op.drop_index("ix_fix_suggestions_status", table_name="fix_suggestions")
    op.drop_index("ix_fix_suggestions_agent_action", table_name="fix_suggestions")
    op.drop_table("fix_suggestions")
    op.drop_index("ix_diagnostic_runs_user_created", table_name="diagnostic_runs")
    op.drop_index("ix_diagnostic_runs_status", table_name="diagnostic_runs")
    op.drop_table("diagnostic_runs")
