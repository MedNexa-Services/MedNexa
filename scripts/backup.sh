#!/bin/sh
# MedNexa Database Automated Backup Script (Part 5 - Task 5.12)
# Usage: ./scripts/backup.sh

set -e

BACKUP_DIR="${BACKUP_DIR:-./backups}"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="${BACKUP_DIR}/mednexa_backup_${TIMESTAMP}.sql.gz"
CONTAINER_NAME="${DB_CONTAINER:-mednexa-db}"
DB_USER="${POSTGRES_USER:-mednexa}"
DB_NAME="${POSTGRES_DB:-mednexa}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

mkdir -p "${BACKUP_DIR}"

echo "[INFO] Starting MedNexa database backup: ${TIMESTAMP}..."

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  docker exec -t "${CONTAINER_NAME}" pg_dump -U "${DB_USER}" "${DB_NAME}" | gzip > "${BACKUP_FILE}"
else
  # Direct fallback if running outside Docker
  pg_dump -h "${PGHOST:-localhost}" -p "${PGPORT:-5434}" -U "${DB_USER}" "${DB_NAME}" | gzip > "${BACKUP_FILE}"
fi

FILESIZE=$(du -h "${BACKUP_FILE}" | cut -f1)
echo "[SUCCESS] Backup created successfully: ${BACKUP_FILE} (${FILESIZE})"

# Prune older backups beyond retention policy (HIPAA data storage rule)
echo "[INFO] Cleaning backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "mednexa_backup_*.sql.gz" -mtime +"${RETENTION_DAYS}" -exec rm -f {} \;

echo "[INFO] Backup routine complete."
