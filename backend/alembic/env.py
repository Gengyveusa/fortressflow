"""Alembic environment configuration.

Supports both local PostgreSQL and Neon (cloud) database URLs.
Handles the async-to-sync URL conversion needed because:
  - The app uses postgresql+asyncpg:// (async driver)
  - Alembic offline mode and plain sync connections need postgresql:// (psycopg2)
  - Alembic online mode can use async_engine_from_config with asyncpg
"""

import asyncio
import os
import re
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.database import Base

# Import all models so that Base.metadata is fully populated
import app.models  # noqa: F401

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _get_database_url() -> str:
    """Read DATABASE_URL from environment, falling back to app config."""
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        from app.config import settings

        url = settings.DATABASE_URL
    return url


def _async_url(url: str) -> str:
    """Ensure the URL uses the asyncpg driver for async engine usage.

    Converts:
      postgresql://  -> postgresql+asyncpg://
      postgres://    -> postgresql+asyncpg://
    Leaves postgresql+asyncpg:// unchanged.
    Also converts sslmode= to ssl= for asyncpg compatibility.
    """
    url = re.sub(r"^postgres(ql)?://", "postgresql+asyncpg://", url)
    # asyncpg uses 'ssl' not 'sslmode'
    url = url.replace("sslmode=require", "ssl=require")
    return url


def _sync_url(url: str) -> str:
    """Convert any PostgreSQL URL variant to a plain psycopg2 sync URL.

    Converts:
      postgresql+asyncpg://  -> postgresql://
      postgres://            -> postgresql://
    This works with both local PostgreSQL and Neon cloud URLs.
    """
    url = re.sub(r"^postgres(ql)?(\+asyncpg)?://", "postgresql://", url)
    return url


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generates SQL without a live DB).

    Uses the sync URL since no async engine is involved.
    """
    url = _sync_url(_get_database_url())
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    """Execute migrations within a sync connection callback."""
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations through run_sync."""
    db_url = _async_url(_get_database_url())
    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = db_url

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
