#!/usr/bin/env bash
# scripts/dev-restart.profile.sh
#
# Neutral stack profile for a fresh orchestrator checkout.
#
# This repository no longer ships a default product/base app. A generated app
# must replace this file with stack-specific commands derived from
# docs/source-of-truth/STACK_PROFILE.yaml and the technical guide. Keep
# scripts/dev-restart.sh untouched; only this profile changes per project.
#
# Required functions (contract enforced by scripts/dev-restart.sh):
#   back_health   -> exit 0 if backend healthy
#   back_start    -> start backend in background, write PID to BACK_PID_FILE
#   back_url      -> human-readable URL for the status table
#   front_health  -> exit 0 if frontend healthy
#   front_start   -> start frontend in background, write PID to FRONT_PID_FILE
#   front_url     -> human-readable URL for the status table
#   db_health     -> 0 = up, 1 = down, 2 = unknown
#   db_reset      -> migrate/reset/load real provided data when implemented

back_health() { return 1; }
front_health() { return 1; }
db_health() { return 2; }

back_url() { printf 'none'; }
front_url() { printf 'none'; }

back_start() {
  fail "No backend dev profile configured. Generate docs/source-of-truth from templates, implement scripts/dev-restart.profile.sh for the declared stack, then retry."
}

front_start() {
  fail "No frontend dev profile configured. Generate docs/source-of-truth from templates, implement scripts/dev-restart.profile.sh for the declared stack, then retry."
}

db_reset() {
  warn "No database reset profile configured; skipping."
  return 0
}
