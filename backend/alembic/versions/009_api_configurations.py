"""Phase 9: API configurations table for encrypted key storage.

Adds:
- api_configurations table with user_id FK, service_name, encrypted_key
- Unique constraint on (user_id, service_name)
- Index on user_id for fast lookups

Revision ID: 009_api_configurations
Revises: 008_users_auth
Create Date: 2026-03-23
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "009_api_configurations"
down_revision = "008_users_auth"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "api_configurations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("service_name", sa.String(100), nullable=False),
        sa.Column("encrypted_key", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    op.create_index("ix_api_configurations_user_id", "api_configurations", ["user_id"])
    op.create_unique_constraint(
        "uq_api_config_user_service",
        "api_configurations",
        ["user_id", "service_name"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_api_config_user_service", "api_configurations")
    op.drop_index("ix_api_configurations_user_id", table_name="api_configurations")
    op.drop_table("api_configurations")
