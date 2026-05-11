#!/bin/sh
# scripts/minio-bootstrap.sh
#
# Slice:  P00-S02-T001 — Docker compose services
# Phase:  P00 Scaffold + Design System
# Source: TECHNICAL_GUIDE §11 Deploy; instrucciones.md §3.3 Foundation propia#infra
#
# Purpose: One-shot MinIO bootstrap sidecar.
#   - Runs after `minio` service is healthy (depends_on condition in compose).
#   - Configures mc alias pointing to the minio service.
#   - Creates the default documents bucket (S3_BUCKET_DOCUMENTS).
#   - Exits 0 on success. compose restart: "no" prevents looping.
#
# Env vars (passed by docker-compose.yml from .env):
#   MINIO_ROOT_USER       — admin user (MINIO_ROOT_USER in .env.example)
#   MINIO_ROOT_PASSWORD   — admin password
#   S3_BUCKET_DOCUMENTS   — bucket name (e.g. hilo-docs-dev)
#
# Logging: BEFORE/AFTER/ERROR pattern per 01-non-negotiables.md §Logging.

set -e

MINIO_ENDPOINT="http://minio:9000"
ALIAS="local"
BUCKET="${S3_BUCKET_DOCUMENTS:-hilo-docs-dev}"

echo "[minio-init] BEFORE: configuring mc alias '${ALIAS}' -> ${MINIO_ENDPOINT}"
mc alias set "${ALIAS}" "${MINIO_ENDPOINT}" "${MINIO_ROOT_USER}" "${MINIO_ROOT_PASSWORD}"
echo "[minio-init] AFTER: alias '${ALIAS}' configured"

echo "[minio-init] BEFORE: creating bucket '${BUCKET}' if not exists"
if mc ls "${ALIAS}/${BUCKET}" >/dev/null 2>&1; then
  echo "[minio-init] INFO: bucket '${BUCKET}' already exists — skipping creation"
else
  mc mb "${ALIAS}/${BUCKET}"
  echo "[minio-init] AFTER: bucket '${BUCKET}' created successfully"
fi

echo "[minio-init] BEFORE: setting bucket '${BUCKET}' policy to private"
mc anonymous set none "${ALIAS}/${BUCKET}"
echo "[minio-init] AFTER: bucket '${BUCKET}' policy set to private"

echo "[minio-init] SUCCESS: MinIO bootstrap complete"
