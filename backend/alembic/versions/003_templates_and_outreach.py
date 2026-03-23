"""Add templates table and outreach channel support.

Revision ID: 003_templates_and_outreach
Revises: 002_lead_enrichment_columns
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB

revision = "003_templates_and_outreach"
down_revision = "002_lead_enrichment"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create enum types
    op.execute("CREATE TYPE template_channel AS ENUM ('email', 'sms', 'linkedin')")
    op.execute(
        "CREATE TYPE template_category AS ENUM ('cold_outreach', 'follow_up', 're_engagement', 'custom')"
    )

    # Create templates table
    op.create_table(
        "templates",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column(
            "channel",
            sa.Enum("email", "sms", "linkedin", name="template_channel", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "category",
            sa.Enum("cold_outreach", "follow_up", "re_engagement", "custom", name="template_category", create_type=False),
            nullable=False,
            server_default="custom",
        ),
        sa.Column("subject", sa.String(500), nullable=True),
        sa.Column("html_body", sa.Text, nullable=True),
        sa.Column("plain_body", sa.Text, nullable=False),
        sa.Column("linkedin_action", sa.String(50), nullable=True),
        sa.Column("variables", JSONB, nullable=True),
        sa.Column("variant_group", sa.String(100), nullable=True),
        sa.Column("variant_label", sa.String(50), nullable=True),
        sa.Column("is_system", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # Add indexes
    op.create_index("ix_templates_channel", "templates", ["channel"])
    op.create_index("ix_templates_category", "templates", ["category"])
    op.create_index("ix_templates_is_active", "templates", ["is_active"])
    op.create_index("ix_templates_variant_group", "templates", ["variant_group"])


def downgrade() -> None:
    op.drop_index("ix_templates_variant_group")
    op.drop_index("ix_templates_is_active")
    op.drop_index("ix_templates_category")
    op.drop_index("ix_templates_channel")
    op.drop_table("templates")
    op.execute("DROP TYPE IF EXISTS template_category")
    op.execute("DROP TYPE IF EXISTS template_channel")
