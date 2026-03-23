#!/usr/bin/env bash
set -e

echo "=== FortressFlow Backend Startup ==="
echo "Running database migrations..."

# Retry migrations up to 5 times with backoff (DB might not be ready yet)
for i in 1 2 3 4 5; do
  if python -m alembic upgrade head; then
    echo "Migrations complete."
    break
  else
    echo "Migration attempt $i failed, retrying in ${i}0 seconds..."
    sleep $((i * 10))
  fi
done

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
