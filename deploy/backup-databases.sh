#!/usr/bin/env bash
set -euo pipefail

# Database backup script for Entropia Nexus
# Backs up one or more PostgreSQL databases from a Docker container.
# Intended to run as a daily cron job with rolling retention.
#
# Usage:
#   ./backup-databases.sh [config-file]
#   ./backup-databases.sh --container postgres-db-1 --user postgres --databases nexus,nexus_users
#   ./backup-databases.sh --config /path/to/env --container postgres-db-1 --databases nexus
#
# Cron:
#   0 3 * * * /opt/entropia-nexus/deploy/backup-databases.sh >> /var/log/nexus-backup.log 2>&1

# --- Configuration (override via env file or environment) ---
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

CFG_FILE=""
CLI_DB_CONTAINER=""
CLI_DB_USER=""
CLI_DATABASES=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --config)
      [[ $# -ge 2 ]] || { echo "Missing value for --config" >&2; exit 1; }
      CFG_FILE="$2"
      shift 2
      ;;
    --container)
      [[ $# -ge 2 ]] || { echo "Missing value for --container" >&2; exit 1; }
      CLI_DB_CONTAINER="$2"
      shift 2
      ;;
    --user)
      [[ $# -ge 2 ]] || { echo "Missing value for --user" >&2; exit 1; }
      CLI_DB_USER="$2"
      shift 2
      ;;
    --databases)
      [[ $# -ge 2 ]] || { echo "Missing value for --databases" >&2; exit 1; }
      CLI_DATABASES="$2"
      shift 2
      ;;
    --help|-h)
      sed -n '1,14p' "$0"
      exit 0
      ;;
    *)
      if [[ -z "${CFG_FILE}" ]]; then
        CFG_FILE="$1"
        shift
      else
        echo "Unknown argument: $1" >&2
        exit 1
      fi
      ;;
  esac
done

if [[ -z "${CFG_FILE}" && -f "${SCRIPT_DIR}/env" ]]; then
  CFG_FILE="${SCRIPT_DIR}/env"
fi
if [[ -n "${CFG_FILE}" && -f "${CFG_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${CFG_FILE}"
fi

BACKUP_DIR="${BACKUP_DIR:-/var/backups/postgres}"
RETAIN_DAILY_DAYS="${RETAIN_DAILY_DAYS:-30}"      # Keep all dailies for this many days
RETAIN_WEEKLY_DAYS="${RETAIN_WEEKLY_DAYS:-365}"    # Beyond daily, keep 1/week up to this many days
                                                   # Beyond weekly, keep 1/month forever
DB_CONTAINER="${CLI_DB_CONTAINER:-${DB_CONTAINER:-828a6804235c_postgres-db-1}}"
DB_USER="${CLI_DB_USER:-${DB_USER:-postgres}}"

normalize_databases() {
  local raw="${1:-}"
  local -n out_ref=$2
  out_ref=()

  if [[ -z "${raw}" ]]; then
    return
  fi

  raw="${raw//,/ }"
  # shellcheck disable=SC2206
  local parts=( $raw )
  local db
  for db in "${parts[@]}"; do
    [[ -n "${db}" ]] || continue
    out_ref+=("${db}")
  done
}

if [[ -n "${CLI_DATABASES}" ]]; then
  normalize_databases "${CLI_DATABASES}" DATABASES
elif declare -p DATABASES >/dev/null 2>&1; then
  if [[ "$(declare -p DATABASES 2>/dev/null)" != declare\ -a* ]]; then
    normalize_databases "${DATABASES}" DATABASES
  fi
else
  DATABASES=("nexus" "nexus_users")
fi

if [[ ${#DATABASES[@]} -eq 0 ]]; then
  fail "No databases configured. Use --databases or set DATABASES."
fi

DATE="$(date +%Y-%m-%d_%H%M%S)"
LOG_PREFIX="[backup ${DATE}]"

log()  { echo "${LOG_PREFIX} $*"; }
fail() { echo "${LOG_PREFIX} ERROR: $*" >&2; exit 1; }

# --- Resolve container ---
if [[ -z "${DB_CONTAINER}" ]]; then
  DB_CONTAINER="$(docker ps --filter ancestor=postgis/postgis --format '{{.Names}}' | head -n1)"
  if [[ -z "${DB_CONTAINER}" ]]; then
    fail "Could not auto-detect PostGIS container. Set DB_CONTAINER in env."
  fi
  log "Auto-detected container: ${DB_CONTAINER}"
fi

# Verify container is running
if ! docker inspect --format '{{.State.Running}}' "${DB_CONTAINER}" 2>/dev/null | grep -q true; then
  fail "Container '${DB_CONTAINER}' is not running."
fi

# --- Prepare backup directory ---
mkdir -p "${BACKUP_DIR}"

# --- Dump databases ---
FAILED=0
for DB in "${DATABASES[@]}"; do
  SAFE_DB="${DB//-/_}"  # safety: normalize any hyphens in DB names for filenames
  OUTFILE="${BACKUP_DIR}/${SAFE_DB}_${DATE}.sql.gz"

  log "Dumping ${DB} ..."
  if docker exec "${DB_CONTAINER}" pg_dump -U "${DB_USER}" -d "${DB}" --no-owner --no-privileges \
    | gzip > "${OUTFILE}"; then

    SIZE="$(du -h "${OUTFILE}" | cut -f1)"
    log "  -> ${OUTFILE} (${SIZE})"
  else
    log "  FAILED to dump ${DB}"
    rm -f "${OUTFILE}"
    FAILED=$((FAILED + 1))
  fi
done

# --- Prune old backups (tiered retention) ---
# Retention tiers:
#   0 .. RETAIN_DAILY_DAYS   -> keep all (daily)
#   RETAIN_DAILY_DAYS .. RETAIN_WEEKLY_DAYS -> keep 1 per ISO week (oldest in each week)
#   beyond RETAIN_WEEKLY_DAYS              -> keep 1 per month   (oldest in each month)
#
# For each database prefix we process files independently so that both DBs
# always have matching retention.

NOW_EPOCH="$(date +%s)"
DAILY_CUTOFF=$(( NOW_EPOCH - RETAIN_DAILY_DAYS  * 86400 ))
WEEKLY_CUTOFF=$(( NOW_EPOCH - RETAIN_WEEKLY_DAYS * 86400 ))

PRUNED=0

for DB_NAME in "${DATABASES[@]}"; do
  PREFIX="${DB_NAME//-/_}"
  # Collect files for this DB sorted oldest-first
  mapfile -t FILES < <(find "${BACKUP_DIR}" -maxdepth 1 -name "${PREFIX}_*.sql.gz" -type f -printf '%T@ %p\n' 2>/dev/null \
    | sort -n | cut -d' ' -f2-)

  # Track which week/month buckets we've already kept
  declare -A KEPT_WEEKS=()
  declare -A KEPT_MONTHS=()

  for F in "${FILES[@]}"; do
    FILE_EPOCH="$(stat -c '%Y' "${F}" 2>/dev/null)" || continue

    if (( FILE_EPOCH >= DAILY_CUTOFF )); then
      # Daily tier: keep everything
      continue
    fi

    if (( FILE_EPOCH >= WEEKLY_CUTOFF )); then
      # Weekly tier: keep first (oldest) backup per ISO week
      WEEK_KEY="$(date -d "@${FILE_EPOCH}" +%G-W%V)"
      if [[ -z "${KEPT_WEEKS[${WEEK_KEY}]+x}" ]]; then
        KEPT_WEEKS["${WEEK_KEY}"]=1
      else
        rm -f "${F}"
        PRUNED=$((PRUNED + 1))
      fi
    else
      # Monthly tier: keep first (oldest) backup per month
      MONTH_KEY="$(date -d "@${FILE_EPOCH}" +%Y-%m)"
      if [[ -z "${KEPT_MONTHS[${MONTH_KEY}]+x}" ]]; then
        KEPT_MONTHS["${MONTH_KEY}"]=1
      else
        rm -f "${F}"
        PRUNED=$((PRUNED + 1))
      fi
    fi
  done

  unset KEPT_WEEKS KEPT_MONTHS
done

if [[ ${PRUNED} -gt 0 ]]; then
  log "Pruned ${PRUNED} backup(s) via tiered retention (daily=${RETAIN_DAILY_DAYS}d, weekly=${RETAIN_WEEKLY_DAYS}d, then monthly)."
fi

# --- Summary ---
TOTAL="$(find "${BACKUP_DIR}" -name "*.sql.gz" -type f | wc -l)"
DISK="$(du -sh "${BACKUP_DIR}" | cut -f1)"
log "Done. ${TOTAL} backup file(s) on disk, using ${DISK}."

if [[ ${FAILED} -gt 0 ]]; then
  fail "${FAILED} database(s) failed to back up."
fi
