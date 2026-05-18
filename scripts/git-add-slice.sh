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
#       orchestrator-state/tasks/lifecycle-events/<TASK_ID>.json
#       orchestrator-state/tasks/follow-ups/<FOLLOWUP_ID>.yaml cuyo origin_task_id sea <TASK_ID>
#       orchestrator-state/memory/official-doc-notes/<TASK_ID>-*.md
#   - docs/product-baseline/ (lo sincroniza el closer aparte)
#
# Y NUNCA stagea:
#   - PROGRESS.md, agent-memory/, registry.json, runtime-state.json,
#     ledger*.jsonl, task-dag.*, execution-graph.json
#   - Evidence/handoff/report/task-pack/follow-up de OTRAS slices
#
# Nota: muchos artefactos del orquestador estan gitignored para que el repo
# canonico no quede dirty tras bootstrap/hook runtime. Este script usa git add -f
# solo para los artefactos auditables de ESTA slice.
#
# Uso: scripts/git-add-slice.sh <TASK_ID>
#      scripts/git-add-slice.sh --dry-run <TASK_ID>

set -euo pipefail
SCRIPT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

DRY_RUN=0
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=1; shift
fi
TASK_ID="${1:-}"
if [ -z "$TASK_ID" ] || ! printf '%s' "$TASK_ID" | grep -Eq '^P[0-9]+-S[0-9]+-T[0-9]+$'; then
  echo "ERROR: invalid or missing TASK_ID (expected Pxx-Sxx-Txxx)" >&2
  exit 2
fi

WORKSPACE_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)"

# In pr-flow/git-flow the closer runs from the per-TASK_ID worktree, while the
# scheduler registry remains in the canonical orchestrator root. Use the
# canonical registry for write_set lookup, but stage paths from the current
# checkout/worktree so the slice artifacts enter the PR/feature branch.
CANONICAL_ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-}"
if [ -z "$CANONICAL_ROOT" ] && [ -x "$WORKSPACE_ROOT/scripts/ensure-task-worktree.sh" ]; then
  CANONICAL_ROOT="$(bash "$WORKSPACE_ROOT/scripts/ensure-task-worktree.sh" --print-root 2>/dev/null || true)"
fi
CANONICAL_ROOT="${CANONICAL_ROOT:-$WORKSPACE_ROOT}"
REG="$CANONICAL_ROOT/orchestrator-state/tasks/registry.json"
cd "$WORKSPACE_ROOT"
if [ ! -f "$REG" ]; then
  echo "ERROR: registry.json not found at $REG" >&2
  echo "Hint: in pr-flow/git-flow, export CLAUDE_ORCHESTRATOR_ROOT=<main repo root> before closing from a task worktree." >&2
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

# Paths slice-specific (siempre incluidos si existen). Keep this as a
# newline list instead of a Bash array so macOS Bash 3.2 + set -u cannot fail on
# empty-array expansion.
SLICE_PATHS=$(cat <<EOF_SLICE_PATHS
orchestrator-state/tasks/handoffs/${TASK_ID}.md
orchestrator-state/tasks/evidence/${TASK_ID}
orchestrator-state/tasks/reports/${TASK_ID}.md
orchestrator-state/tasks/task-packs/${TASK_ID}.md
orchestrator-state/tasks/work-items/${TASK_ID}.yaml
orchestrator-state/tasks/lifecycle-events/${TASK_ID}.json
EOF_SLICE_PATHS
)
# official-doc-notes son por TASK_ID con sufijo de tema
DOC_NOTES_GLOB="orchestrator-state/memory/official-doc-notes/${TASK_ID}-*.md"

# Follow-up proposals are PR artifacts when they originate from this slice.
# In pr-flow/git-flow a validator/tester/verify command may have registered the
# proposal in the canonical root so every terminal sees runtime-state, while the
# PR commit is created from the task worktree. Mirror only this TASK_ID's FU YAML
# into the active checkout before staging; never stage FU files from other slices.
FOLLOWUP_PATHS=$(
  python3 - "$TASK_ID" "$CANONICAL_ROOT" "$WORKSPACE_ROOT" <<'PY_FOLLOWUPS'
import re, shutil, sys
from pathlib import Path

task_id, canonical_root, workspace_root = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])
rel_dir = Path("orchestrator-state/tasks/follow-ups")
seen: set[str] = set()

def yaml_field(text: str, key: str) -> str:
    match = re.search(r"(?m)^\s*" + re.escape(key) + r"\s*:\s*(.*?)\s*(?:#.*)?$", text)
    if not match:
        return ""
    value = match.group(1).strip()
    if (value.startswith("'") and value.endswith("'")) or (value.startswith('"') and value.endswith('"')):
        value = value[1:-1]
    return value.strip()

def rel_to_workspace(path: Path) -> str:
    try:
        return path.resolve().relative_to(workspace_root.resolve()).as_posix()
    except Exception:
        return ""

def consider(path: Path) -> None:
    if not path.is_file() or path.suffix not in {".yaml", ".yml"}:
        return
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return
    if yaml_field(text, "origin_task_id") != task_id:
        return
    status = (yaml_field(text, "status") or "proposed").lower()
    if status not in {"proposed", "promoted", "waived"}:
        return
    target = workspace_root / rel_dir / path.name
    if path.resolve() != target.resolve():
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists() or target.read_bytes() != path.read_bytes():
            shutil.copy2(path, target)
    rel = rel_to_workspace(target)
    if rel and rel not in seen:
        seen.add(rel)
        print(rel)

for root in (canonical_root, workspace_root):
    directory = root / rel_dir
    if directory.is_dir():
        for item in sorted(directory.glob("*.y*ml")):
            consider(item)
PY_FOLLOWUPS
)

# Close lifecycle event: this is the durable, conflict-free state signal that
# travels with the PR. registry.json itself is local runtime and is not staged.
if [ "$DRY_RUN" -eq 0 ]; then
  EVENT_SCRIPT="$CANONICAL_ROOT/.claude/bin/write_lifecycle_event.py"
  if [ ! -f "$EVENT_SCRIPT" ]; then
    EVENT_SCRIPT="$SCRIPT_ROOT/.claude/bin/write_lifecycle_event.py"
  fi
  CLAUDE_ORCHESTRATOR_ROOT="$CANONICAL_ROOT" \
  CLAUDE_WORKSPACE_ROOT="$WORKSPACE_ROOT" \
  python3 -B -S "$EVENT_SCRIPT" "$TASK_ID" >/dev/null
else
  echo "  would: write orchestrator-state/tasks/lifecycle-events/${TASK_ID}.json"
fi

# Baseline (lo añade el sync, pero por si quedó algo del orquestador-meta)
BASELINE="docs/product-baseline"

ADDED=0
add_if_exists() {
  local p="$1"
  local force="${2:-0}"
  if [ -e "$p" ] || compgen -G "$p" >/dev/null 2>&1; then
    if [ "$DRY_RUN" -eq 1 ]; then
      if [ "$force" = "1" ]; then
        echo "  would: git add -f -- '$p'"
      else
        echo "  would: git add -- '$p'"
      fi
    else
      if [ "$force" = "1" ]; then
        git add -f -- "$p" 2>/dev/null && ADDED=$((ADDED+1)) || true
      else
        git add -- "$p" 2>/dev/null && ADDED=$((ADDED+1)) || true
      fi
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
while IFS= read -r p; do
  [ -z "$p" ] && continue
  add_if_exists "$p" 1
done <<EOF_SLICE_PATHS_LOOP
$SLICE_PATHS
EOF_SLICE_PATHS_LOOP

# 3) follow-up proposals owned by this TASK_ID
while IFS= read -r fu_path; do
  [ -z "$fu_path" ] && continue
  add_if_exists "$fu_path" 1
done <<< "$FOLLOWUP_PATHS"

# 4) doc-notes con glob
for f in $DOC_NOTES_GLOB; do
  [ -e "$f" ] && add_if_exists "$f" 1
done

# 5) baseline (si fue tocado por sync-product-baseline.sh)
add_if_exists "$BASELINE"

# Guardrail: write_set is not permission to delete product files. Any staged
# deletion must be explicitly declared as delete_set/allowed_deletions in the
# task record, otherwise broad globs or stale worktrees can erase unrelated
# modules during closer. Violating deletions are unstaged but the worktree is
# not modified.
if [ "$DRY_RUN" -eq 0 ]; then
  DELETE_GUARD="$SCRIPT_ROOT/scripts/check_staged_deletions.py"
  if [ -f "$DELETE_GUARD" ]; then
    python3 -B -S "$DELETE_GUARD" "$TASK_ID" --registry "$REG" --repo "$WORKSPACE_ROOT" --unstage
  fi
fi

# Resumen
if [ "$DRY_RUN" -eq 1 ]; then
  echo "git-add-slice DRY-RUN: TASK_ID=$TASK_ID (use sin --dry-run para aplicar)"
else
  STAGED=$(git diff --cached --name-only | wc -l | tr -d ' ')
  UNSTAGED=$(git status --short | awk '/^[ ?][MAD?]/ {count += 1} END {print count + 0}')
  echo "git-add-slice: TASK_ID=$TASK_ID staged_files=$STAGED unstaged_remaining=$UNSTAGED"
fi
