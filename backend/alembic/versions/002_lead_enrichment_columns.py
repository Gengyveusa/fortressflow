"""Add enrichment columns to leads table.

Revision ID: 002_lead_enrichment
Revises: 001_initial_schema
Create Date: 2026-03-19
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from migration_helpers import column_exists, index_exists

# revision identifiers
revision = "002_lead_enrichment"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()

    if not column_exists(bind, "leads", "enriched_data"):
        op.add_column("leads", sa.Column("enriched_data", JSONB, nullable=True))
    if not column_exists(bind, "leads", "last_enriched_at"):
        op.add_column("leads", sa.Column("last_enriched_at", sa.DateTime(timezone=True), nullable=True))
    if not column_exists(bind, "leads", "meeting_proof"):
        op.add_column("leads", sa.Column("meeting_proof", JSONB, nullable=True))

    # Change source from String(100) to Text to allow longer source descriptions
    # Safe to re-run: altering to the same type is a no-op in PostgreSQL
    result = bind.execute(sa.text(
        "SELECT data_type FROM information_schema.columns "
        "WHERE table_schema = 'public' AND table_name = 'leads' AND column_name = 'source'"
    ))
    row = result.fetchone()
    if row and row[0] != "text":
        op.alter_column("leads", "source", type_=sa.Text(), existing_type=sa.String(100))

    # Case-insensitive unique index on email
    if not index_exists(bind, "ix_leads_email_lower"):
        op.create_index(
            "ix_leads_email_lower",
            "leads",
            [sa.text("lower(email)")],
            unique=True,
        )

    # Index on last_enriched_at for stale-lead queries
    if not index_exists(bind, "ix_leads_last_enriched_at"):
        op.create_index("ix_leads_last_enriched_at", "leads", ["last_enriched_at"])


def downgrade() -> None:
    op.drop_index("ix_leads_last_enriched_at", table_name="leads")
    op.drop_index("ix_leads_email_lower", table_name="leads")
    op.alter_column("leads", "source", type_=sa.String(100), existing_type=sa.Text())
    op.drop_column("leads", "meeting_proof")
    op.drop_column("leads", "last_enriched_at")
    op.drop_column("leads", "enriched_data")
