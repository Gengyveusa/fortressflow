#!/bin/bash
set -euo pipefail
BACKUP_DIR="/backups"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="${BACKUP_DIR}/fortressflow_${TIMESTAMP}.sql.gz"
RETENTION_DAYS=${BACKUP_RETENTION_DAYS:-30}

# Create backup
pg_dump -h postgres -U ${POSTGRES_USER:-fortressflow} ${POSTGRES_DB:-fortressflow} | gzip > "${BACKUP_FILE}"

# Optional: upload to S3
if [ -n "${AWS_S3_BACKUP_BUCKET:-}" ]; then
  aws s3 cp "${BACKUP_FILE}" "s3://${AWS_S3_BACKUP_BUCKET}/fortressflow/${TIMESTAMP}.sql.gz"
fi

# Cleanup old backups
find ${BACKUP_DIR} -name "*.sql.gz" -mtime +${RETENTION_DAYS} -delete

echo "Backup completed: ${BACKUP_FILE}"
