#!/bin/sh
# MedNexa Database Restore Script (Part 5 - Task 5.12)
# Usage: ./scripts/restore.sh ./backups/mednexa_backup_YYYYMMDD_HHMMSS.sql.gz

set -e

BACKUP_FILE="$1"
CONTAINER_NAME="${DB_CONTAINER:-mednexa-db}"
DB_USER="${POSTGRES_USER:-mednexa}"
DB_NAME="${POSTGRES_DB:-mednexa}"

if [ -z "${BACKUP_FILE}" ] || [ ! -f "${BACKUP_FILE}" ]; then
  echo "[ERROR] Please specify a valid backup file to restore."
  echo "Usage: $0 ./backups/mednexa_backup_<timestamp>.sql.gz"
  exit 1
fi

echo "[WARNING] This will overwrite current database '${DB_NAME}'."
read -p "Continue with database restore? (y/N) " CONFIRM
if [ "$CONFIRM" != "y" ] && [ "$CONFIRM" != "Y" ]; then
  echo "[INFO] Restore aborted."
  exit 0
fi

echo "[INFO] Restoring from ${BACKUP_FILE}..."

if docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
  gunzip -c "${BACKUP_FILE}" | docker exec -i "${CONTAINER_NAME}" psql -U "${DB_USER}" -d "${DB_NAME}"
else
  gunzip -c "${BACKUP_FILE}" | psql -h "${PGHOST:-localhost}" -p "${PGPORT:-5434}" -U "${DB_USER}" -d "${DB_NAME}"
fi

echo "[SUCCESS] Database restore completed successfully."
