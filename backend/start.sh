#!/usr/bin/env bash
set -e

echo "=== FortressFlow Backend Startup ==="
echo "Running database migrations..."

# Diagnostic: show current alembic revision (if any) before migrating.
# Uses the async settings URL but converts to sync psycopg2 for the check.
python -c "
import sqlalchemy as sa
from app.config import settings

url = settings.DATABASE_URL
# Convert async URL to sync for this lightweight check
url = url.replace('postgresql+asyncpg://', 'postgresql://', 1)

try:
    engine = sa.create_engine(url, connect_args={'connect_timeout': 5})
    with engine.connect() as conn:
        result = conn.execute(sa.text(
            \"SELECT 1 FROM information_schema.tables \"
            \"WHERE table_schema = 'public' AND table_name = 'alembic_version'\"
        ))
        if result.scalar() is None:
            print('Fresh database — no alembic_version table yet.')
        else:
            result = conn.execute(sa.text('SELECT version_num FROM alembic_version'))
            row = result.fetchone()
            if row:
                print(f'Current alembic revision: {row[0]}')
            else:
                print('alembic_version table exists but is empty.')
    engine.dispose()
except Exception as e:
    print(f'Could not check migration state: {e}')
" 2>&1 || true

# Retry migrations up to 5 times with backoff (DB might not be ready yet)
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
