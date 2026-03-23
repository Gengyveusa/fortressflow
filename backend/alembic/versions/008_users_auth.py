"""Phase 8: Users table for real authentication.

Adds:
- users table with email, password_hash, full_name, role, is_active, timestamps
- Unique index on email
- Role enum type (admin, user, viewer)

Revision ID: 008_users_auth
Revises: 007_chat_logs_phase7
Create Date: 2026-03-22
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, ENUM

from migration_helpers import create_enum_idempotent, table_exists, index_exists

revision = "008_users_auth"
down_revision = "007_chat_logs_phase7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    create_enum_idempotent("userrole", ["admin", "user", "viewer"])
    role_enum = ENUM("admin", "user", "viewer", name="userrole", create_type=False)

    if not table_exists(bind, "users"):
        op.create_table(
            "users",
            sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("email", sa.String(320), nullable=False),
            sa.Column("password_hash", sa.String(255), nullable=False),
            sa.Column("full_name", sa.String(255), nullable=True),
            sa.Column("role", role_enum, nullable=False, server_default="user"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        )

    if not index_exists(bind, "ix_users_email"):
        op.create_index("ix_users_email", "users", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS userrole")
