#!/usr/bin/env bash
set -e

echo "=== FortressFlow Backend Startup ==="
echo "Running database migrations..."

# ── Pre-migration: detect and fix corrupted partial-migration state ──────────
# If a previous deploy half-ran migrations (enums exist but tables like
# 'users' are missing), Alembic cannot recover on its own.  This block
# detects that situation and performs a nuclear wipe so migrations can
# re-run cleanly from revision 001.
python -c "
import sys
import sqlalchemy as sa
from app.config import settings

url = settings.DATABASE_URL.replace('postgresql+asyncpg://', 'postgresql://', 1)

try:
    engine = sa.create_engine(url, connect_args={'connect_timeout': 5})
except Exception as exc:
    print(f'Could not create engine: {exc}')
    sys.exit(0)  # non-fatal — let alembic try on its own

try:
    with engine.connect() as conn:
        # 1. Check alembic_version
        result = conn.execute(sa.text(
            \"SELECT 1 FROM information_schema.tables \"
            \"WHERE table_schema = 'public' AND table_name = 'alembic_version'\"
        ))
        has_alembic = result.scalar() is not None

        current_rev = None
        if has_alembic:
            row = conn.execute(sa.text('SELECT version_num FROM alembic_version')).fetchone()
            current_rev = row[0] if row else None

        # 2. Check if the users table exists (created in migration 008)
        result = conn.execute(sa.text(
            \"SELECT 1 FROM information_schema.tables \"
            \"WHERE table_schema = 'public' AND table_name = 'users'\"
        ))
        has_users = result.scalar() is not None

        # 3. Check for orphaned enum types left by partial migration runs
        KNOWN_ENUMS = [
            'template_channel', 'template_category', 'step_type',
            'enrollment_status', 'sequence_status', 'consent_channel',
            'consent_method', 'touch_action', 'userrole',
        ]
        placeholders = ', '.join(f':e{i}' for i in range(len(KNOWN_ENUMS)))
        params = {f'e{i}': v for i, v in enumerate(KNOWN_ENUMS)}
        result = conn.execute(
            sa.text(f'SELECT typname FROM pg_type WHERE typname IN ({placeholders})'),
            params,
        )
        orphaned_enums = [r[0] for r in result.fetchall()]

        # ── Decision logic ──────────────────────────────────────────────
        if not has_users and orphaned_enums:
            # Classic corrupted state: enums were created but the migration
            # that stamps alembic_version either never ran or a later
            # migration crashed, leaving the DB half-built.
            print(f'CORRUPTED STATE DETECTED: no users table, but found enums: {orphaned_enums}')
            print('Performing full database reset so migrations can run cleanly...')

            # Drop tables in reverse-FK order (children first)
            TABLES = [
                'api_configurations',
                'chat_logs',
                'channel_metrics',
                'linkedin_queue',
                'reply_webhook_events',
                'reply_logs',
                'warmup_seed_logs',
                'warmup_configs',
                'sending_inboxes',
                'sequence_enrollments',
                'sequence_steps',
                'sequences',
                'sending_domains',
                'templates',
                'warmup_queue',
                'touch_logs',
                'dnc_blocks',
                'consents',
                'leads',
                'users',
                'alembic_version',
            ]
            for t in TABLES:
                conn.execute(sa.text(f'DROP TABLE IF EXISTS {t} CASCADE'))

            for e in KNOWN_ENUMS:
                conn.execute(sa.text(f'DROP TYPE IF EXISTS {e} CASCADE'))

            conn.commit()
            print('Database reset complete. Migrations will run fresh.')

        elif not has_alembic and not has_users and not orphaned_enums:
            print('Fresh database — migrations will create everything.')

        elif has_users:
            print(f'Database looks healthy. alembic revision: {current_rev}')

        else:
            print(f'Unexpected state — has_alembic={has_alembic}, has_users={has_users}, '
                  f'current_rev={current_rev}, enums={orphaned_enums}. '
                  'Proceeding with migrations and hoping for the best.')

    engine.dispose()
except Exception as exc:
    print(f'Database state check failed: {exc}')
    print('Proceeding with migrations anyway.')
" 2>&1 || echo "Pre-migration check script exited non-zero — proceeding with migrations anyway."

# ── Run Alembic migrations with retry + backoff ──────────────────────────────
MIGRATION_OK=0
for i in 1 2 3 4 5; do
  if python -m alembic upgrade head; then
    echo "Migrations complete."
    MIGRATION_OK=1
    break
  else
    echo "Migration attempt $i failed, retrying in ${i}0 seconds..."
    sleep $((i * 10))
  fi
done

if [ "$MIGRATION_OK" -ne 1 ]; then
  echo "ERROR: All migration attempts failed. Starting server anyway for health checks."
  echo "The database may be in a partial state — check logs and re-deploy after fixing."
fi

echo "Starting uvicorn..."
exec uvicorn app.main:app \
  --host 0.0.0.0 \
  --port "${PORT:-8000}" \
  --workers 2 \
  --loop uvloop \
  --http httptools \
  --proxy-headers \
  --forwarded-allow-ips='*' \
  --access-log
