#!/usr/bin/env bash
# Housekeeping silencioso post-closer. NO interactivo. Operaciones SEGURAS:
#   - Rota ledger.jsonl y bash-ledger.jsonl si >200KB (los comprime y deja vacio).
#   - Borra caches regenerables (__pycache__, .pytest_cache, htmlcov, .DS_Store).
#   - NO archiva/mueve handoffs/evidence/reports por defecto. Eso ensuciaba
#     worktrees justo despues del push y hacia fallar cleanup-worktrees.
#     El archivado historico queda disponible solo con --archive-done.
# NO toca PROGRESS.md (eso es /slice-maintain compact, gate humano).
# NO toca codigo de la app, configs, source-of-truth, registry, runtime-state.
# Si algo falla, sigue (best-effort). Pensado para invocar desde el closer
# antes de cleanup-worktrees.
#
# Uso: bash scripts/slice-clean.sh [--apply] [--keep N] [--archive-done]
#   --apply         ejecuta de verdad (default: dry-run, solo reporta).
#   --keep N        preserva las ultimas N slices "done" si --archive-done (default: 5).
#   --archive-done  mueve handoffs/evidence/reports antiguos; NO usar en closer.
set -uo pipefail
APPLY=0
KEEP=5
ARCHIVE_DONE=0
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --keep)  shift; KEEP="$1" ;;
    --archive-done) ARCHIVE_DONE=1 ;;
    *)       echo "uso: $0 [--apply] [--keep N] [--archive-done]"; exit 2 ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
LEDGER="orchestrator-state/tasks/ledger.jsonl"
BASH_LEDGER="orchestrator-state/tasks/bash-ledger.jsonl"
ARCHIVE_DIR="orchestrator-state/memory/archive/$(date +%Y-%m-%d)"

log() { printf "[slice-clean] %s\n" "$1"; }
maybe()  { if [ "$APPLY" -eq 1 ]; then "$@"; else log "DRY-RUN: $*"; fi; }
hr_count=0; hr_size=0
sd_count=0; sd_size=0
ar_count=0
rotated=0

size_bytes() {
  if du -sb "$1" >/dev/null 2>&1; then
    du -sb "$1" 2>/dev/null | awk '{print $1}'
  else
    du -sk "$1" 2>/dev/null | awk '{print $1 * 1024}'
  fi
}

mtime_epoch() {
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

reverse_lines() {
  if command -v tac >/dev/null 2>&1; then tac; else tail -r; fi
}

rotate_ledger_file() {
  file="$1"
  prefix="$2"
  if [ -f "$file" ]; then
    size=$(wc -c < "$file" 2>/dev/null || echo 0)
    if [ "$size" -gt $((200 * 1024)) ]; then
      target="orchestrator-state/tasks/${prefix}-$(date +%Y-%m-%d-%H%M%S).jsonl.gz"
      log "$(basename "$file") = ${size} bytes - rota a $target"
      if [ "$APPLY" -eq 1 ]; then
        gzip -c "$file" > "$target" && : > "$file" && rotated=1
        old_ledgers=$(ls -1t orchestrator-state/tasks/${prefix}-*.jsonl.gz 2>/dev/null | tail -n +6 || true)
        if [ -n "$old_ledgers" ]; then printf '%s\n' "$old_ledgers" | xargs rm -f; fi
      fi
    fi
  fi
}
rotate_ledger_file "$LEDGER" "ledger"
rotate_ledger_file "$BASH_LEDGER" "bash-ledger"

# Avoid Bash arrays here: slice-clean runs during closer cleanup, and macOS
# Bash 3.2 + set -u can fail on empty array expansions. Keep the prune list as
# literal find predicates.
find_pruned() {
  find .     \( -path "./.git"     -o -path "./.claude"     -o -path "./orchestrator-state/tasks"     -o -path "./orchestrator-state/memory"     -o -path "./docs"     -o -path "./flutter_template"     -o -path "./.venv"     -o -path "./venv"     -o -path "./node_modules" \) -prune     -o "$@" -print 2>/dev/null
}

while IFS= read -r d; do
  [ -z "$d" ] && continue
  sz=$(size_bytes "$d"); sz=${sz:-0}
  hr_count=$((hr_count+1)); hr_size=$((hr_size+sz))
  maybe rm -rf "$d"
done < <(find_pruned -type d \( -name __pycache__ -o -name .pytest_cache -o -name htmlcov -o -name .ruff_cache -o -name .mypy_cache \))

while IFS= read -r f; do
  [ -z "$f" ] && continue
  sz=$(wc -c < "$f" 2>/dev/null); sz=${sz:-0}
  sd_count=$((sd_count+1)); sd_size=$((sd_size+sz))
  maybe rm -f "$f"
done < <(find_pruned -type f \( -name '.DS_Store' -o -name 'Thumbs.db' -o -name '*.tmp' -o -name '*.bak' -o -name '*.swp' \))

if [ "$ARCHIVE_DONE" -eq 1 ] && command -v jq >/dev/null 2>&1 && [ -f orchestrator-state/tasks/registry.json ]; then
  done_ids=$(jq -r '.tasks[] | select(.status == "done") | .id' orchestrator-state/tasks/registry.json 2>/dev/null | reverse_lines | tail -n "+$((KEEP+1))" | reverse_lines)
  if [ -n "$done_ids" ]; then
    if [ "$APPLY" -eq 1 ]; then mkdir -p "$ARCHIVE_DIR/handoffs" "$ARCHIVE_DIR/evidence" "$ARCHIVE_DIR/reports" 2>/dev/null; fi
    while IFS= read -r tid; do
      [ -z "$tid" ] && continue
      hf="orchestrator-state/tasks/handoffs/$tid.md"
      if [ -f "$hf" ]; then
        age_days=$(( ( $(date +%s) - $(mtime_epoch "$hf") ) / 86400 ))
        if [ "$age_days" -gt 2 ]; then
          maybe mv "$hf" "$ARCHIVE_DIR/handoffs/" 2>/dev/null
          [ -d "orchestrator-state/tasks/evidence/$tid" ] && maybe mv "orchestrator-state/tasks/evidence/$tid" "$ARCHIVE_DIR/evidence/" 2>/dev/null
          [ -f "orchestrator-state/tasks/reports/$tid.md" ] && maybe mv "orchestrator-state/tasks/reports/$tid.md" "$ARCHIVE_DIR/reports/" 2>/dev/null
          ar_count=$((ar_count+1))
        fi
      fi
    done <<< "$done_ids"
  fi
fi

log "Caches dirs:    $hr_count (${hr_size} bytes)"
log "Ficheros sueltos: $sd_count (${sd_size} bytes)"
if [ "$ARCHIVE_DONE" -eq 1 ]; then log "Slices archivadas: $ar_count"; else log "Slices archivadas: skipped (--archive-done no usado)"; fi
[ "$rotated" -eq 1 ] && log "ledger(s) rotado(s)"
[ "$APPLY" -eq 0 ] && log "DRY-RUN - relanza con --apply para ejecutar"
exit 0
