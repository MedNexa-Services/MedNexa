#!/bin/sh
# MedNexa database restore (Part 5, task 5.12).
#
#   ./scripts/restore.sh ./backups/mednexa_backup_<timestamp>.sql.gz [-y]
#
# Replaces the contents of the database with the backup, in ONE transaction: if anything
# fails, nothing changes. Stop the services that use the database first:
#   docker compose stop api telephony dashboard
# and start them again afterwards.

set -eu

BACKUP_FILE="${1:-}"
ASSUME_YES="${2:-}"
CONTAINER="${DB_CONTAINER:-mednexa-db}"
DB_USER="${POSTGRES_USER:-mednexa}"
DB_NAME="${POSTGRES_DB:-mednexa}"
REMOTE="/tmp/mednexa_restore.sql.gz"

if [ -z "${BACKUP_FILE}" ] || [ ! -f "${BACKUP_FILE}" ]; then
  echo "Usage: $0 ./backups/mednexa_backup_<timestamp>.sql.gz [-y]" >&2
  exit 1
fi
gzip -t "${BACKUP_FILE}" || { echo "[ERROR] ${BACKUP_FILE} is not a valid gzip file." >&2; exit 1; }
if ! docker inspect -f '{{.State.Running}}' "${CONTAINER}" 2>/dev/null | grep -q true; then
  echo "[ERROR] Container '${CONTAINER}' is not running (set DB_CONTAINER to its name)." >&2
  exit 1
fi

echo "[WARNING] This replaces ALL data in database '${DB_NAME}' with ${BACKUP_FILE}."
if [ "${ASSUME_YES}" != "-y" ]; then
  printf "Continue? (y/N) "
  read -r CONFIRM
  case "${CONFIRM}" in y | Y) ;; *) echo "[INFO] Restore aborted."; exit 0 ;; esac
fi

trap 'docker exec "${CONTAINER}" rm -f "${REMOTE}" >/dev/null 2>&1 || true' EXIT
docker cp "${BACKUP_FILE}" "${CONTAINER}:${REMOTE}"
docker exec "${CONTAINER}" sh -c "
  set -e
  gunzip -c '${REMOTE}' | psql -v ON_ERROR_STOP=1 --single-transaction -q -o /dev/null -U '${DB_USER}' -d '${DB_NAME}'
"
echo "[SUCCESS] Database '${DB_NAME}' restored from ${BACKUP_FILE}."
