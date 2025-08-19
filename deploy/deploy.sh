#!/usr/bin/env bash
set -euo pipefail

# Local deployment script: builds Nexus, syncs common, builds images and starts containers via docker compose.
#
# Optional: provide a config env file path as first argument (defaults to deploy/env if present).
# The env file can define the following variables:
#   CONFIG_DIR           - absolute path where container config files live on the server (e.g., /opt/entropia-nexus)
#   BUILD_MODE           - development | production (default: production)
#   COMPOSE_ENV_FILE     - path to a compose env file to generate/use (default: deploy/compose.env)
#   COMMON_HOST_PATH     - destination path on server for the shared 'common' folder (default: $CONFIG_DIR/common)
#   SYNC_COMMON_FROM_REPO- true/false to copy repo ./common into COMMON_HOST_PATH (default: true)
#   API_ENV_PATH         - path to API .env file on server (default: $CONFIG_DIR/api/.env)
#   NEXUS_ENV_PATH       - path to Nexus .env file on server (default: $CONFIG_DIR/nexus/.env)
#   BOT_ENV_PATH         - path to Bot .env file on server (default: $CONFIG_DIR/nexus-bot/.env)
#   BOT_CONFIG_PATH      - path to Bot config.json on server (default: $CONFIG_DIR/nexus-bot/config.json)
#   GIT_PULL             - true/false to git pull before build (default: false)
#   GIT_REMOTE           - remote name (default: origin)
#   GIT_BRANCH           - branch to pull (default: current branch)


# Determine repository root (where this script resides -> parent dir)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"

# Default env file is 'env' in the script's directory
CFG_FILE="${1:-}"
if [[ -z "${CFG_FILE}" && -f "${SCRIPT_DIR}/env" ]]; then
  CFG_FILE="${SCRIPT_DIR}/env"
fi
if [[ -n "${CFG_FILE}" && -f "${CFG_FILE}" ]]; then
  echo "[deploy] Loading config from ${CFG_FILE}"
  # shellcheck disable=SC1090
  source "${CFG_FILE}"
else
  echo "[deploy] No config file provided. Using defaults and environment.";
fi

# Back-compat: support old PROJECT_DIR, prefer CONFIG_DIR
if [[ -n "${PROJECT_DIR:-}" && -z "${CONFIG_DIR:-}" ]]; then
  CONFIG_DIR="${PROJECT_DIR}"
fi

CONFIG_DIR=${CONFIG_DIR:-"/opt/entropia-nexus"}
BUILD_MODE=${BUILD_MODE:-production}
COMPOSE_ENV_FILE=${COMPOSE_ENV_FILE:-"${CONFIG_DIR}/compose.env"}
COMMON_HOST_PATH=${COMMON_HOST_PATH:-"${CONFIG_DIR}/common"}
SYNC_COMMON_FROM_REPO=${SYNC_COMMON_FROM_REPO:-true}
API_ENV_PATH=${API_ENV_PATH:-"${CONFIG_DIR}/api/.env"}
NEXUS_ENV_PATH=${NEXUS_ENV_PATH:-"${CONFIG_DIR}/nexus/.env"}
BOT_ENV_PATH=${BOT_ENV_PATH:-"${CONFIG_DIR}/nexus-bot/.env"}
BOT_CONFIG_PATH=${BOT_CONFIG_PATH:-"${CONFIG_DIR}/nexus-bot/config.json"}
GIT_PULL=${GIT_PULL:-false}
GIT_REMOTE=${GIT_REMOTE:-origin}
GIT_BRANCH=${GIT_BRANCH:-}

echo "[deploy] Repo dir: ${REPO_DIR}"
echo "[deploy] Config dir: ${CONFIG_DIR}"
cd "${REPO_DIR}"

if [[ "${GIT_PULL}" == "true" ]]; then
  echo "[deploy] Updating repo from ${GIT_REMOTE} ${GIT_BRANCH:-'(current)'}"
  git fetch "${GIT_REMOTE}"
  if [[ -n "${GIT_BRANCH}" ]]; then
    git checkout "${GIT_BRANCH}"
  fi
  git pull --ff-only "${GIT_REMOTE}" ${GIT_BRANCH:-}
fi

echo "[deploy] Building Nexus (${BUILD_MODE})"

# Stage Nexus .env for build-time Vite variables, unless already present in repo
STAGED_NEXUS_ENV="${REPO_DIR}/nexus/.env"
PREEXISTING_NEXUS_ENV=false
if [[ -f "${STAGED_NEXUS_ENV}" ]]; then
  PREEXISTING_NEXUS_ENV=true
  echo "[deploy] Using existing Nexus .env in repo: ${STAGED_NEXUS_ENV}"
else
  echo "[deploy] Ensuring Nexus env exists: ${NEXUS_ENV_PATH}"
  if [[ ! -f "${NEXUS_ENV_PATH}" ]]; then
    echo "[deploy] ERROR: Nexus env file not found at ${NEXUS_ENV_PATH}." >&2
    echo "[deploy] Please create it (e.g., with VITE_API_URL, VITE_DOMAIN, etc.) or set NEXUS_ENV_PATH correctly. Aborting." >&2
    exit 1
  fi
  echo "[deploy] Staging Nexus .env for client build: ${STAGED_NEXUS_ENV}"
  cp "${NEXUS_ENV_PATH}" "${STAGED_NEXUS_ENV}"
fi

# Clean up the staged .env on exit (only if we created it)
cleanup_env() {
  if [[ "${PREEXISTING_NEXUS_ENV}" != "true" && -n "${STAGED_NEXUS_ENV}" && -f "${STAGED_NEXUS_ENV}" ]]; then
    rm -f "${STAGED_NEXUS_ENV}" || true
  fi
}
trap cleanup_env EXIT

pushd nexus >/dev/null
npm ci
if [[ "${BUILD_MODE}" == "development" ]]; then
  npm run build:dev
else
  npm run build:prod
fi
popd >/dev/null

# Remove the staged .env immediately after the build when it wasn't preexisting (trap remains as a safety net)
if [[ "${PREEXISTING_NEXUS_ENV}" != "true" ]]; then
  cleanup_env
fi

if [[ "${SYNC_COMMON_FROM_REPO}" == "true" ]]; then
  echo "[deploy] Syncing common (from repo) -> ${COMMON_HOST_PATH}"
  mkdir -p "${COMMON_HOST_PATH}"
  # copy contents without nesting
  if command -v rsync >/dev/null 2>&1; then
    rsync -a --delete common/ "${COMMON_HOST_PATH}/"
  else
    rm -rf "${COMMON_HOST_PATH}/"*
    cp -a common/. "${COMMON_HOST_PATH}/"
  fi
fi

echo "[deploy] Writing compose env file: ${COMPOSE_ENV_FILE}"
mkdir -p "$(dirname "${COMPOSE_ENV_FILE}")"
cat > "${COMPOSE_ENV_FILE}" <<EOF
COMMON_HOST_PATH=${COMMON_HOST_PATH}
API_ENV_PATH=${API_ENV_PATH}
NEXUS_ENV_PATH=${NEXUS_ENV_PATH}
BOT_ENV_PATH=${BOT_ENV_PATH}
BOT_CONFIG_PATH=${BOT_CONFIG_PATH}
EOF

COMPOSE_CMD=(docker compose --env-file "${COMPOSE_ENV_FILE}")

echo "[deploy] Bringing stack down"
"${COMPOSE_CMD[@]}" down || true

echo "[deploy] Building images"
"${COMPOSE_CMD[@]}" build

echo "[deploy] Starting stack"
"${COMPOSE_CMD[@]}" up -d --remove-orphans

echo "[deploy] Done. Current services:"
"${COMPOSE_CMD[@]}" ps
