#!/bin/sh
# MedNexa database backup (Part 5, task 5.12).
#
#   ./scripts/backup.sh                 # backup into ./backups
#   BACKUP_DIR=/mnt/usb ./scripts/backup.sh
#
# The dump is made INSIDE the database container (no TTY, no host-side pipe), checked,
# and only then moved into place; retention runs only after a good backup, so a failed run
# can never delete the last good ones. Backups contain patient data: they are created
# readable by you only. Store copies off the machine and encrypt them (e.g. `age` or
# `gpg --symmetric`) before they leave it.

set -eu
umask 077

BACKUP_DIR="${BACKUP_DIR:-./backups}"
CONTAINER="${DB_CONTAINER:-mednexa-db}"
DB_USER="${POSTGRES_USER:-mednexa}"
DB_NAME="${POSTGRES_DB:-mednexa}"
RETENTION_DAYS="${RETENTION_DAYS:-7}"

TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FINAL="${BACKUP_DIR}/mednexa_backup_${TIMESTAMP}.sql.gz"
PARTIAL="${FINAL}.partial"
REMOTE="/tmp/mednexa_backup_${TIMESTAMP}.sql.gz"

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"
trap 'rm -f "${PARTIAL}"; docker exec "${CONTAINER}" rm -f "${REMOTE}" >/dev/null 2>&1 || true' EXIT

echo "[INFO] Backing up database '${DB_NAME}' from container '${CONTAINER}'..."

if ! docker inspect -f '{{.State.Running}}' "${CONTAINER}" 2>/dev/null | grep -q true; then
  echo "[ERROR] Container '${CONTAINER}' is not running (set DB_CONTAINER to its name)." >&2
  exit 1
fi

# --clean --if-exists makes the dump restorable over an existing database.
docker exec "${CONTAINER}" sh -c "
  set -e
  pg_dump -U '${DB_USER}' --clean --if-exists --no-owner --no-acl '${DB_NAME}' > '${REMOTE%.gz}'
  gzip -f '${REMOTE%.gz}'
  gzip -t '${REMOTE}'
  gunzip -c '${REMOTE}' | tail -n 5 | grep -q 'PostgreSQL database dump complete'
"
docker cp "${CONTAINER}:${REMOTE}" "${PARTIAL}"
chmod 600 "${PARTIAL}" # docker cp ignores umask

gzip -t "${PARTIAL}"
mv "${PARTIAL}" "${FINAL}"
echo "[SUCCESS] ${FINAL} ($(du -h "${FINAL}" | cut -f1))"

echo "[INFO] Removing backups older than ${RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "mednexa_backup_*.sql.gz" -mtime +"${RETENTION_DAYS}" -exec rm -f {} \;
echo "[INFO] Done."
