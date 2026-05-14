#!/usr/bin/env bash
# check-progress-updated.sh
#
# Comprueba si orchestrator-state/memory/PROGRESS.md fue tocado en la slice activa.
# Lo invoca el validator como gate bloqueante (sección 6 de validator.md):
# si el developer modificó código pero no actualizó PROGRESS.md, los siguientes
# agentes pierden contexto. Esto enforce el contrato sin depender solo del prompt.
#
# Resolución del worktree (en orden):
#   1. --worktree <path>        explícito.
#   2. --auto                   busca worktree cuyo path contenga el active TASK_ID
#                               (leído de orchestrator-state/tasks/runtime-state.json).
#   3. (sin args)               usa el repo en CWD.
#
# Exit codes:
#   0  → PROGRESS.md aparece como modificado/untracked    → gate PASS
#   1  → PROGRESS.md NO aparece y la slice toca código    → gate FAIL (changes_requested)
#   2  → PROGRESS.md NO aparece y la slice es solo docs/  → gate SKIP (permitido)
#        tests/scripts (refactor sin código de producto)
#   3  → no se pudo determinar el worktree                → gate INCONCLUSIVE
#   4  → uso incorrecto                                   → error de invocación
#
# Stdout (clave=valor, una por línea):
#   PROGRESS_MD_TOUCHED=yes|no
#   SLICE_TYPE=code|docs|tests|mixed|empty|unknown
#   WORKTREE=<path>
#   CHANGED_FILES_COUNT=<n>
#   GATE=pass|fail|skip|inconclusive

set -uo pipefail

RUNTIME_STATE="orchestrator-state/tasks/runtime-state.json"

usage() {
  cat <<'EOF' >&2
Usage:
  scripts/check-progress-updated.sh [--worktree <path>] [--auto]

Sin flags: usa el repo en CWD.
EOF
  exit 4
}

WORKTREE=""
AUTO=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --worktree)
      WORKTREE="${2:-}"
      [[ -z "$WORKTREE" ]] && usage
      shift 2
      ;;
    --auto)
      AUTO=1
      shift
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      ;;
  esac
done

# --- 1. Resolver worktree ---------------------------------------------------

if [[ -z "$WORKTREE" && "$AUTO" == "1" ]]; then
  if [[ ! -f "$RUNTIME_STATE" ]]; then
    echo "PROGRESS_MD_TOUCHED=no"
    echo "SLICE_TYPE=unknown"
    echo "WORKTREE="
    echo "CHANGED_FILES_COUNT=0"
    echo "GATE=inconclusive"
    echo "REASON=no_runtime_state" >&2
    exit 3
  fi
  TASK_ID="${CLAUDE_ACTIVE_TASK_ID:-${CLAUDE_TASK_ID:-}}"

  if [[ -n "$TASK_ID" ]]; then
    # git worktree list --porcelain emite líneas:
    #   worktree /path/to/worktree
    #   HEAD <sha>
    #   branch refs/heads/<branch>
    # Buscamos el worktree path que contenga el TASK_ID.
    WORKTREE=$(git worktree list --porcelain 2>/dev/null \
      | awk -v tid="$TASK_ID" '/^worktree / { p=substr($0, 10) } p && (p ~ tid) { print p; exit }')
  fi

  if [[ -z "$WORKTREE" ]]; then
    # Fallback: usa CWD (push-to-main or manual task terminal without a separate worktree).
    WORKTREE="$(pwd)"
  fi
fi

if [[ -z "$WORKTREE" ]]; then
  WORKTREE="$(pwd)"
fi

if [[ ! -d "$WORKTREE/.git" && ! -f "$WORKTREE/.git" ]]; then
  echo "PROGRESS_MD_TOUCHED=no"
  echo "SLICE_TYPE=unknown"
  echo "WORKTREE=$WORKTREE"
  echo "CHANGED_FILES_COUNT=0"
  echo "GATE=inconclusive"
  echo "REASON=not_a_git_repo" >&2
  exit 3
fi

# --- 2. Recolectar archivos modificados ------------------------------------

# Modificados (staged + unstaged) + untracked.
# Formato porcelain: "XY path"  (XY = códigos de status, path puede llevar comillas).
PORCELAIN=$(git -C "$WORKTREE" status --porcelain --untracked-files=all 2>/dev/null || true)

# Si el developer ya commiteó dentro del worktree, los cambios no aparecen
# en status. Comparamos también contra la rama base del worktree (origin/main
# o main si existe) para no perderlos.
DIFF_VS_BASE=""
for ref in origin/main main origin/master master; do
  if git -C "$WORKTREE" rev-parse --verify "$ref" >/dev/null 2>&1; then
    DIFF_VS_BASE=$(git -C "$WORKTREE" diff --name-only "$ref"...HEAD 2>/dev/null || true)
    break
  fi
done

# Lista combinada de archivos cambiados (staged/unstaged/untracked + commits del worktree).
ALL_CHANGED=$(
  {
    echo "$PORCELAIN" | awk 'NF{ sub(/^.. /, ""); print }'
    echo "$DIFF_VS_BASE"
  } | grep -v '^$' | sort -u
)

CHANGED_COUNT=$(echo "$ALL_CHANGED" | grep -c . || true)

# --- 3. ¿Está PROGRESS.md tocado? -------------------------------------------

PROGRESS_TOUCHED="no"
if echo "$ALL_CHANGED" | grep -qE "(^|/)orchestrator-state/memory/PROGRESS\.md$"; then
  PROGRESS_TOUCHED="yes"
fi

# --- 4. Clasificar tipo de slice -------------------------------------------
#
# code   → al menos un archivo de producto:
#          .dart, .py, .ts, .tsx, .js, .jsx, .go, .rs, .java, .kt, .swift
#          o backend/api/* fuera de tests, o lib/* fuera de tests/
# tests  → solo archivos en test/, tests/, *_test.*, *.test.*, spec/, __tests__/
# docs   → solo .md, .txt, README, docs/, orchestrator-state/memory/*.md
# mixed  → code + (tests/docs)
# empty  → 0 archivos cambiados

CODE_COUNT=0
TESTS_COUNT=0
DOCS_COUNT=0

while IFS= read -r f; do
  [[ -z "$f" ]] && continue
  # Ignora archivos de framework derivados.
  case "$f" in
    orchestrator-state/tasks/ledger.jsonl|orchestrator-state/tasks/bash-ledger.jsonl|orchestrator-state/tasks/ledger.jsonl.lock|orchestrator-state/tasks/bash-ledger.jsonl.lock|orchestrator-state/hook-errors.log)
      continue
      ;;
  esac

  is_test=0
  case "$f" in
    */test/*|*/tests/*|*/spec/*|*/__tests__/*) is_test=1 ;;
    *_test.dart|*_test.py|*_test.go|*.test.ts|*.test.tsx|*.test.js|*.spec.ts|*.spec.tsx|*.spec.js) is_test=1 ;;
  esac

  if (( is_test == 1 )); then
    TESTS_COUNT=$((TESTS_COUNT + 1))
    continue
  fi

  case "$f" in
    *.dart|*.py|*.ts|*.tsx|*.js|*.jsx|*.go|*.rs|*.java|*.kt|*.swift|*.sql)
      CODE_COUNT=$((CODE_COUNT + 1))
      ;;
    # Docs / config / scripts. The generic patterns (*.yaml, *.toml, *.json,
    # *.txt, *.lock) already subsume pubspec.*, pyproject.toml, package.json,
    # tsconfig*.json and requirements*.txt — listing them again would only
    # produce shellcheck SC2221/SC2222 (dead patterns).
    *.md|*.txt|*.yaml|*.yml|*.toml|*.json|*.env*|*.sh|Dockerfile*|Makefile|*.gradle|*.lock)
      DOCS_COUNT=$((DOCS_COUNT + 1))
      ;;
    *)
      # Desconocido cuenta como "docs" para no falsear el gate.
      DOCS_COUNT=$((DOCS_COUNT + 1))
      ;;
  esac
done <<< "$ALL_CHANGED"

if (( CHANGED_COUNT == 0 )); then
  SLICE_TYPE="empty"
elif (( CODE_COUNT > 0 )) && (( TESTS_COUNT + DOCS_COUNT > 0 )); then
  SLICE_TYPE="mixed"
elif (( CODE_COUNT > 0 )); then
  SLICE_TYPE="code"
elif (( TESTS_COUNT > 0 )) && (( DOCS_COUNT == 0 )); then
  SLICE_TYPE="tests"
else
  SLICE_TYPE="docs"
fi

# --- 5. Decidir gate --------------------------------------------------------

GATE="fail"
EXIT_CODE=1

if [[ "$PROGRESS_TOUCHED" == "yes" ]]; then
  GATE="pass"
  EXIT_CODE=0
elif [[ "$SLICE_TYPE" == "docs" || "$SLICE_TYPE" == "tests" || "$SLICE_TYPE" == "empty" ]]; then
  GATE="skip"
  EXIT_CODE=2
else
  GATE="fail"
  EXIT_CODE=1
fi

# --- 6. Output -------------------------------------------------------------

echo "PROGRESS_MD_TOUCHED=$PROGRESS_TOUCHED"
echo "SLICE_TYPE=$SLICE_TYPE"
echo "WORKTREE=$WORKTREE"
echo "CHANGED_FILES_COUNT=$CHANGED_COUNT"
echo "GATE=$GATE"

exit "$EXIT_CODE"
