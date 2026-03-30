"""Helpers for making Alembic migrations idempotent.

These functions check for the existence of database objects before creating
them, allowing migrations to be safely re-run on partially-migrated databases.

The create_enum_idempotent function uses a PL/pgSQL DO block with exception
handling, which is the most reliable approach when running through asyncpg's
run_sync bridge — the EXCEPTION WHEN duplicate_object guard works regardless
of driver quirks with parameterised catalog queries.
"""

import sqlalchemy as sa
from alembic import op


def create_enum_idempotent(enum_name: str, values: list[str]) -> None:
    """Create a PostgreSQL ENUM type, silently skipping if it already exists.

    Uses a DO block so the CREATE TYPE is guarded at the SQL level — no
    Python-side catalog query needed.
    """
    values_sql = ", ".join(f"'{v}'" for v in values)
    op.execute(
        f"DO $$ BEGIN "
        f"CREATE TYPE {enum_name} AS ENUM ({values_sql}); "
        f"EXCEPTION WHEN duplicate_object THEN null; "
        f"END $$;"
    )


def enum_exists(bind, enum_name: str) -> bool:
    result = bind.execute(
        sa.text("SELECT 1 FROM pg_type WHERE typname = :name"),
        {"name": enum_name},
    )
    return result.scalar() is not None


def table_exists(bind, table_name: str) -> bool:
    result = bind.execute(
        sa.text("SELECT 1 FROM information_schema.tables WHERE table_schema = 'public' AND table_name = :name"),
        {"name": table_name},
    )
    return result.scalar() is not None


def index_exists(bind, index_name: str) -> bool:
    result = bind.execute(
        sa.text("SELECT 1 FROM pg_indexes WHERE indexname = :name"),
        {"name": index_name},
    )
    return result.scalar() is not None


def column_exists(bind, table_name: str, column_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_schema = 'public' AND table_name = :table AND column_name = :col"
        ),
        {"table": table_name, "col": column_name},
    )
    return result.scalar() is not None


def constraint_exists(bind, constraint_name: str) -> bool:
    result = bind.execute(
        sa.text(
            "SELECT 1 FROM information_schema.table_constraints "
            "WHERE constraint_schema = 'public' AND constraint_name = :name"
        ),
        {"name": constraint_name},
    )
    return result.scalar() is not None
