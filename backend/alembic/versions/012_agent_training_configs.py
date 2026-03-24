"""012 – Agent training configs table.

Revision ID: 012_agent_training
Revises: 011
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB


revision = "012_agent_training"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agent_training_configs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_name", sa.String(50), nullable=False),
        sa.Column("config_type", sa.String(30), nullable=False),
        sa.Column("config_key", sa.String(100), nullable=False),
        sa.Column("config_value", JSONB, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("priority", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index(
        "ix_atc_user_agent_type_key",
        "agent_training_configs",
        ["user_id", "agent_name", "config_type", "config_key"],
        unique=True,
    )
    op.create_index(
        "ix_atc_agent_active",
        "agent_training_configs",
        ["agent_name", "is_active"],
    )


def downgrade() -> None:
    op.drop_index("ix_atc_agent_active", table_name="agent_training_configs")
    op.drop_index("ix_atc_user_agent_type_key", table_name="agent_training_configs")
    op.drop_table("agent_training_configs")
