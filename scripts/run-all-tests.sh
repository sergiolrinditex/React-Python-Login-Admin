#!/usr/bin/env bash
# Stack-aware test runner. Commands come from docs/source-of-truth/STACK_PROFILE.yaml.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PROJECT_ROOT="${CLAUDE_PROJECT_DIR:-$ROOT_DIR}"
STACK="$ROOT_DIR/.claude/bin/stack_profile.py"

log()  { echo "==> $1"; }
fail() { echo "ERROR: $1" >&2; exit 1; }

MODE="${1:-all}"

get_profile() {
  python3 -B -S "$STACK" --root "$PROJECT_ROOT" --get "$1" --default "$2"
}

run_cmd() {
  local label="$1"
  local cmd="$2"
  local module_root="$3"
  if [ -z "$cmd" ] || [ "$cmd" = "none" ]; then
    log "$label: no command declared, skip"
    return
  fi
  if [ -n "$module_root" ] && [ "$module_root" != "none" ] && [ ! -d "$PROJECT_ROOT/$module_root" ]; then
    log "$label: $module_root no existe, skip"
    return
  fi
  log "$label: $cmd"
  ( cd "$PROJECT_ROOT" && bash -lc "$cmd" )
}

BACKEND_ROOT="$(get_profile backend.module_root none)"
FRONTEND_ROOT="$(get_profile frontend.module_root none)"
BACKEND_TEST_CMD="$(get_profile backend.test_cmd none)"
FRONTEND_TEST_CMD="$(get_profile frontend.test_cmd none)"

run_backend_tests() {
  run_cmd "Backend tests" "$BACKEND_TEST_CMD" "$BACKEND_ROOT"
}

run_frontend_tests() {
  run_cmd "Frontend tests" "$FRONTEND_TEST_CMD" "$FRONTEND_ROOT"
}

run_design_tokens_check() {
  if [ -f "$ROOT_DIR/scripts/check-design-tokens.sh" ]; then
    log "Design tokens check..."
    CLAUDE_PROJECT_DIR="$PROJECT_ROOT" bash "$ROOT_DIR/scripts/check-design-tokens.sh"
  fi
}

run_api_contract_check() {
  if [ -f "$ROOT_DIR/scripts/generate-api-contracts.sh" ]; then
    log "API contract freshness check..."
    CLAUDE_PROJECT_DIR="$PROJECT_ROOT" bash "$ROOT_DIR/scripts/generate-api-contracts.sh" --validate-only
  fi
}

run_agent_static_audits() {
  if [ -f "$ROOT_DIR/scripts/audit-agent-trailer-vocabulary.py" ]; then
    log "Agent trailer vocabulary audit..."
    ( cd "$PROJECT_ROOT" && python3 -B -S scripts/audit-agent-trailer-vocabulary.py >/tmp/agent-trailer-audit.$$ )
    rm -f /tmp/agent-trailer-audit.$$
  fi
  if [ -f "$ROOT_DIR/scripts/audit-agent-reality.py" ]; then
    log "Agent reality audit..."
    ( cd "$PROJECT_ROOT" && python3 -B -S scripts/audit-agent-reality.py >/tmp/agent-reality-audit.$$ )
    rm -f /tmp/agent-reality-audit.$$
  fi
  if [ -f "$ROOT_DIR/scripts/audit-template-screen-journey-redactor.py" ]; then
    log "Template screen/journey redactor audit..."
    ( cd "$PROJECT_ROOT" && python3 -B -S scripts/audit-template-screen-journey-redactor.py >/tmp/template-screen-journey-audit.$$ )
    rm -f /tmp/template-screen-journey-audit.$$
  fi
  if [ -f "$ROOT_DIR/scripts/audit-orchestrator-refactor-consistency.py" ]; then
    log "Orchestrator refactor consistency audit..."
    ( cd "$PROJECT_ROOT" && python3 -B -S scripts/audit-orchestrator-refactor-consistency.py >/tmp/orchestrator-refactor-audit.$$ )
    rm -f /tmp/orchestrator-refactor-audit.$$
  fi

}

case "$MODE" in
  all)
    run_agent_static_audits
    run_backend_tests
    run_design_tokens_check
    run_api_contract_check
    run_frontend_tests
    ;;
  backend)
    run_backend_tests
    ;;
  frontend)
    run_design_tokens_check
    run_frontend_tests
    ;;
  lint)
    run_agent_static_audits
    run_design_tokens_check
    run_api_contract_check
    ;;
  *)
    fail "Modo desconocido: $MODE. Usa: all | backend | frontend | lint"
    ;;
esac

echo ""
log "✓ Checks completados."
