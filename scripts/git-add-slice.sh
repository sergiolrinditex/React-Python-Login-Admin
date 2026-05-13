#!/usr/bin/env bash
# git-add-slice.sh — stage only files inside the slice's scope.
#
# Why this exists: 'git add -A' arrastra estado runtime compartido
# (PROGRESS.md, agent-memory/*/MEMORY.md, ledgers, evidence de OTRAS slices)
# que cambia constantemente entre slices paralelas. Esos paths chocan en
# merge time aunque las slices sean DAG-disjuntas. Este script stagea
# ÚNICAMENTE:
#
#   - El write_set declarado de la task en registry.json (paths/globs reales)
#   - Metadata específica de ESTA slice:
#       orchestrator-state/tasks/handoffs/<TASK_ID>.md
#       orchestrator-state/tasks/evidence/<TASK_ID>/
#       orchestrator-state/tasks/reports/<TASK_ID>.md
#       orchestrator-state/tasks/task-packs/<TASK_ID>.md
#       orchestrator-state/tasks/work-items/<TASK_ID>.yaml
#       orchestrator-state/memory/official-doc-notes/<TASK_ID>-*.md
#   - docs/product-baseline/ (lo sincroniza el closer aparte)
#
# Y NUNCA stagea:
#   - PROGRESS.md, agent-memory/, registry.json, runtime-state.json,
#     ledger*.jsonl, task-dag.*, execution-graph.json
#   - Evidence/handoff/report/task-pack de OTRAS slices
#
# Uso: scripts/git-add-slice.sh <TASK_ID>
#      scripts/git-add-slice.sh --dry-run <TASK_ID>

set -euo pipefail

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1; shift
fi
TASK_ID="${1:-}"
if [ -z "$TASK_ID" ] || ! printf '%s' "$TASK_ID" | grep -Eq '^P[0-9]+-S[0-9]+-T[0-9]+$'; then
  echo "ERROR: invalid or missing TASK_ID (expected Pxx-Sxx-Txxx)" >&2
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"
REG="$ROOT/orchestrator-state/tasks/registry.json"
if [ ! -f "$REG" ]; then
  echo "ERROR: registry.json not found at $REG" >&2
  exit 2
fi

# Extraer write_set de la task desde registry.json (jq si está, python3 fallback)
WRITE_SET=$(
  if command -v jq >/dev/null 2>&1; then
    jq -r --arg tid "$TASK_ID" '.tasks[]? | select(.id==$tid) | .write_set[]?' "$REG" 2>/dev/null
  else
    python3 - "$REG" "$TASK_ID" <<'PY'
import json, sys
reg = json.load(open(sys.argv[1])); tid = sys.argv[2]
for t in reg.get('tasks', []):
    if t.get('id') == tid:
        for w in (t.get('write_set') or []):
            print(w)
        break
PY
  fi
)

if [ -z "$WRITE_SET" ]; then
  echo "WARN: no write_set declared for $TASK_ID in registry.json" >&2
fi

# Paths slice-specific (siempre incluidos si existen)
SLICE_PATHS=(
  "orchestrator-state/tasks/handoffs/${TASK_ID}.md"
  "orchestrator-state/tasks/evidence/${TASK_ID}"
  "orchestrator-state/tasks/reports/${TASK_ID}.md"
  "orchestrator-state/tasks/task-packs/${TASK_ID}.md"
  "orchestrator-state/tasks/work-items/${TASK_ID}.yaml"
)
# official-doc-notes son por TASK_ID con sufijo de tema
DOC_NOTES_GLOB="orchestrator-state/memory/official-doc-notes/${TASK_ID}-*.md"

# Baseline (lo añade el sync, pero por si quedó algo del orquestador-meta)
BASELINE="docs/product-baseline"

ADDED=0
add_if_exists() {
  local p="$1"
  if [ -e "$p" ] || compgen -G "$p" >/dev/null 2>&1; then
    if [ "$DRY_RUN" -eq 1 ]; then
      echo "  would: git add '$p'"
    else
      git add "$p" 2>/dev/null && ADDED=$((ADDED+1)) || true
    fi
  fi
}

# 1) write_set declarado (cada glob). git entiende ** y otros patterns
# nativamente; le dejamos a él decidir si hay match. Errores silenciosos
# (no match, no permitido) no rompen el cierre.
while IFS= read -r glob; do
  [ -z "$glob" ] && continue
  if [ "$DRY_RUN" -eq 1 ]; then
    # En dry-run verificamos si git encontraría algo (--dry-run de git add)
    if git add --dry-run -- "$glob" >/dev/null 2>&1; then
      echo "  would: git add -- '$glob' (write_set)"
    fi
  else
    git add -- "$glob" 2>/dev/null && ADDED=$((ADDED+1)) || true
  fi
done <<< "$WRITE_SET"

# 2) slice metadata
for p in "${SLICE_PATHS[@]}"; do
  add_if_exists "$p"
done

# 3) doc-notes con glob
for f in $DOC_NOTES_GLOB; do
  [ -e "$f" ] && add_if_exists "$f"
done

# 4) baseline (si fue tocado por sync-product-baseline.sh)
add_if_exists "$BASELINE"

# Resumen
if [ "$DRY_RUN" -eq 1 ]; then
  echo "git-add-slice DRY-RUN: TASK_ID=$TASK_ID (use sin --dry-run para aplicar)"
else
  STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
  UNSTAGED=$(git status --short | grep -E "^[ ?][MAD?]" | wc -l | tr -d ' ')
  echo "git-add-slice: TASK_ID=$TASK_ID staged_files=$STAGED unstaged_remaining=$UNSTAGED"
fi
