#!/usr/bin/env bash
set -euo pipefail

# Deploy Entropia Nexus via Docker Compose
#
# Usage:
#   REGISTRY=ghcr.io IMAGE_OWNER=amryu IMAGE_TAG=latest \
#   PROJECT_DIR=/opt/entropia-nexus \
#   COMMON_SRC_DIR=/tmp/common-new \
#   CLEAN_OLD_IMAGES=true \
#   ./deploy.sh
#
# Or provide COMMON_SRC_ARCHIVE=/path/to/common.tar.gz instead of COMMON_SRC_DIR.

REGISTRY=${REGISTRY:-ghcr.io}
IMAGE_OWNER=${IMAGE_OWNER:-amryu}
IMAGE_TAG=${IMAGE_TAG:-latest}
PROJECT_DIR=${PROJECT_DIR:-}
COMMON_SRC_DIR=${COMMON_SRC_DIR:-}
COMMON_SRC_ARCHIVE=${COMMON_SRC_ARCHIVE:-}
CLEAN_OLD_IMAGES=${CLEAN_OLD_IMAGES:-false}

if [[ -z "${PROJECT_DIR}" ]]; then
  echo "[deploy] ERROR: PROJECT_DIR is required" >&2
  exit 1
fi

if [[ -z "${COMMON_SRC_DIR}" && -z "${COMMON_SRC_ARCHIVE}" ]]; then
  echo "[deploy] NOTE: No COMMON_SRC_DIR or COMMON_SRC_ARCHIVE provided — common directory will not be updated."
fi

export REGISTRY IMAGE_OWNER IMAGE_TAG

echo "[deploy] Using registry=${REGISTRY} owner=${IMAGE_OWNER} tag=${IMAGE_TAG}"

echo "[deploy] Project dir: ${PROJECT_DIR}"

cd "${PROJECT_DIR}"

COMPOSE_FILES=(-f docker-compose.yml -f docker-compose.deploy.yml)

echo "[deploy] Bringing stack down"
 docker compose "${COMPOSE_FILES[@]}" down || true

# Replace common directory if provided
COMMON_DEST="${PROJECT_DIR}/common"
if [[ -n "${COMMON_SRC_DIR}" ]]; then
  echo "[deploy] Replacing common from dir: ${COMMON_SRC_DIR} -> ${COMMON_DEST}"
  mkdir -p "${COMMON_DEST}"
  rm -rf "${COMMON_DEST}/"*
  cp -a "${COMMON_SRC_DIR}/." "${COMMON_DEST}/"
elif [[ -n "${COMMON_SRC_ARCHIVE}" ]]; then
  echo "[deploy] Replacing common from archive: ${COMMON_SRC_ARCHIVE} -> ${COMMON_DEST}"
  mkdir -p "${COMMON_DEST}"
  rm -rf "${COMMON_DEST}/"*
  tar -xzf "${COMMON_SRC_ARCHIVE}" -C "${COMMON_DEST}" --strip-components=1 || {
    echo "[deploy] WARN: Failed to extract with strip-components=1, retrying without";
    tar -xzf "${COMMON_SRC_ARCHIVE}" -C "${COMMON_DEST}";
  }
fi

if [[ "${CLEAN_OLD_IMAGES}" == "true" ]]; then
  echo "[deploy] Removing old images matching entropia-nexus-* (optional clean)"
  old_images=$(docker images --format '{{.Repository}}:{{.Tag}}' | grep -E "(${REGISTRY}/${IMAGE_OWNER}/entropia-nexus-(api|nexus|bot)):") || true
  if [[ -n "${old_images}" ]]; then
    echo "[deploy] Removing:\n${old_images}"
    echo "${old_images}" | xargs -r docker rmi -f || true
  fi
fi

echo "[deploy] Pulling images"
 docker compose "${COMPOSE_FILES[@]}" pull

echo "[deploy] Starting stack"
 docker compose "${COMPOSE_FILES[@]}" up -d --remove-orphans

echo "[deploy] Done. Current services:"
 docker compose "${COMPOSE_FILES[@]}" ps
