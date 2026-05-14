#!/bin/sh
# scripts/minio-bootstrap.sh
#
# Purpose: Idempotently create the RAG document bucket in local-dev MinIO on
#          docker compose boot. Runs as a one-shot sidecar (service minio-init).
#
# Slice/Phase: P02-S06-T003 — wiring (Runtime Follow-up of P02-S06-T001).
#
# Invoked by: docker-compose service `minio-init`
#   image:      minio/mc:latest  (Alpine/BusyBox — /bin/sh only, no bash)
#   entrypoint: ["/bin/sh", "/scripts/minio-bootstrap.sh"]
#   restart:    "no"  — must exit 0 on success and stay exited; looping = failure.
#   depends_on: minio: service_healthy  — compose waits for MinIO healthcheck OK
#                before starting this sidecar.
#
# Reads (env, all required):
#   MINIO_ROOT_USER      — MinIO admin user (compose passes it from .env)
#   MINIO_ROOT_PASSWORD  — MinIO admin password (never echoed)
#   S3_BUCKET_DOCUMENTS  — bucket name to create (default hilo-docs-dev in .env)
#
# Endpoint (fixed): http://minio:9000  (internal docker network; not configurable)
# Alias (ephemeral): "local" — stored in /root/.mc/config.json inside the
#   container; discarded when the sidecar exits (restart: "no").
#
# Idempotency: mc mb --ignore-existing returns 0 when the bucket already exists.
#   Running this script twice in sequence exits 0 both times.
#
# Exit codes:
#   0  — bucket exists or was created successfully
#   1  — any failure (missing env, mc alias error, mc mb error)
#
# Retry rationale (R4 in task pack §9.5):
#   Even with depends_on: service_healthy, the first mc call can hit a transient
#   503 because MinIO's S3 API surface finishes warming up a few ms after the
#   healthcheck endpoint (/minio/health/live) starts responding. A short retry
#   loop absorbs this window without looping the sidecar itself.
#
# Reference: docker-compose.yml lines 133-150 (minio-init service declaration)
#            .env.example lines 33, 46-52 (MINIO_ROOT_USER/PASSWORD/S3_BUCKET_DOCUMENTS)

set -eu

# ── Logging helpers ──────────────────────────────────────────────────────────

log()  { printf '==> %s\n' "$*"; }
warn() { printf '[WARN] %s\n' "$*" >&2; }
fail() { printf '[ERROR] %s\n' "$*" >&2; exit 1; }

# ── Env validation ───────────────────────────────────────────────────────────

require_env() {
  # Usage: require_env VAR_NAME
  # Fails with an actionable message if the variable is unset or empty.
  eval "val=\${$1:-}"
  if [ -z "$val" ]; then
    fail "Required environment variable \$$1 is not set or empty. Set it in .env / docker-compose environment block."
  fi
}

# ── Ready-gate: retry mc alias set ──────────────────────────────────────────

wait_for_alias() {
  # Try to configure the mc alias up to MAX_ATTEMPTS times, with SLEEP_S between
  # attempts. Returns 0 on the first success; exits 1 after all attempts fail.
  MINIO_ENDPOINT="http://minio:9000"
  ALIAS_NAME="local"
  MAX_ATTEMPTS=5
  SLEEP_S=2
  attempt=1
  while [ "$attempt" -le "$MAX_ATTEMPTS" ]; do
    log "BEFORE mc alias set (attempt $attempt/$MAX_ATTEMPTS) — endpoint: $MINIO_ENDPOINT user: $MINIO_ROOT_USER"
    if mc alias set "$ALIAS_NAME" "$MINIO_ENDPOINT" "$MINIO_ROOT_USER" "$MINIO_ROOT_PASSWORD" >/dev/null 2>&1; then
      log "AFTER mc alias set — alias '$ALIAS_NAME' configured successfully"
      return 0
    fi
    warn "mc alias set failed (attempt $attempt/$MAX_ATTEMPTS) — MinIO S3 API may still be warming up"
    attempt=$((attempt + 1))
    if [ "$attempt" -le "$MAX_ATTEMPTS" ]; then
      sleep "$SLEEP_S"
    fi
  done
  fail "mc alias set failed after $MAX_ATTEMPTS attempts. Check MinIO credentials and network (endpoint: $MINIO_ENDPOINT)."
}

# ── Main ─────────────────────────────────────────────────────────────────────

main() {
  log "BEFORE minio-bootstrap — validating required environment variables"
  require_env MINIO_ROOT_USER
  require_env MINIO_ROOT_PASSWORD
  require_env S3_BUCKET_DOCUMENTS
  log "AFTER env validation — MINIO_ROOT_USER=$MINIO_ROOT_USER S3_BUCKET_DOCUMENTS=$S3_BUCKET_DOCUMENTS"

  wait_for_alias

  log "BEFORE mc mb — creating bucket '$S3_BUCKET_DOCUMENTS' (--ignore-existing for idempotency)"
  if mc mb --ignore-existing "local/$S3_BUCKET_DOCUMENTS"; then
    log "AFTER mc mb — bucket 'local/$S3_BUCKET_DOCUMENTS' ready (created or already existed)"
  else
    fail "mc mb failed for bucket '$S3_BUCKET_DOCUMENTS'. Check MinIO logs for details."
  fi

  log "minio-bootstrap complete — bucket '$S3_BUCKET_DOCUMENTS' is available at http://minio:9000"
}

main "$@"
