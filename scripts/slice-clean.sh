#!/usr/bin/env bash
# Housekeeping silencioso post-closer. NO interactivo. Operaciones SEGURAS:
#   - Rota orchestrator-state/tasks/ledger.jsonl si >200KB (lo comprime y deja vacío).
#   - Borra caches regenerables (__pycache__, .pytest_cache, htmlcov, .DS_Store).
#   - Archiva handoffs/evidence/reports de slices con status "done" en registry
#     y >2 días desde su mtime, en orchestrator-state/memory/archive/<fecha>/.
# NO toca PROGRESS.md (eso es /slice-maintain compact, gate humano).
# NO toca código de la app, configs, source-of-truth, registry, runtime-state.
# Si algo falla, sigue (best-effort). Pensado para invocar desde /verify-slice
# tras el closer.
#
# Uso: bash scripts/slice-clean.sh [--apply] [--keep N]
#   --apply  ejecuta de verdad (default: dry-run, solo reporta).
#   --keep N preserva las últimas N slices "done" sin archivar (default: 5).
set -uo pipefail
APPLY=0
KEEP=5
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --keep)  shift; KEEP="$1" ;;
    *)       echo "uso: $0 [--apply] [--keep N]"; exit 2 ;;
  esac
  shift
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT" || exit 1
LEDGER="orchestrator-state/tasks/ledger.jsonl"
ARCHIVE_DIR="orchestrator-state/memory/archive/$(date +%Y-%m-%d)"

log() { printf "[slice-clean] %s\n" "$1"; }
maybe()  { if [ "$APPLY" -eq 1 ]; then "$@"; else log "DRY-RUN: $*"; fi; }
hr_count=0; hr_size=0
sd_count=0; sd_size=0
ar_count=0
rotated=0

size_bytes() {
  # GNU: du -sb. macOS/BSD: du -sk. Used only for reporting, so approximate
  # KB->bytes fallback is fine.
  if du -sb "$1" >/dev/null 2>&1; then
    du -sb "$1" 2>/dev/null | awk '{print $1}'
  else
    du -sk "$1" 2>/dev/null | awk '{print $1 * 1024}'
  fi
}

mtime_epoch() {
  # macOS/BSD stat uses -f %m; GNU stat uses -c %Y.
  stat -f %m "$1" 2>/dev/null || stat -c %Y "$1" 2>/dev/null || echo 0
}

reverse_lines() {
  if command -v tac >/dev/null 2>&1; then
    tac
  else
    tail -r
  fi
}

# 1. Rotación del ledger si >200KB
if [ -f "$LEDGER" ]; then
  size=$(wc -c < "$LEDGER" 2>/dev/null || echo 0)
  if [ "$size" -gt $((200 * 1024)) ]; then
    target="orchestrator-state/tasks/ledger-$(date +%Y-%m-%d-%H%M%S).jsonl.gz"
    log "ledger.jsonl = ${size} bytes — rota a $target"
    if [ "$APPLY" -eq 1 ]; then
      gzip -c "$LEDGER" > "$target" && : > "$LEDGER" && rotated=1
      # Mantener máx 5 ledgers comprimidos. macOS xargs no soporta -r.
      old_ledgers=$(ls -1t orchestrator-state/tasks/ledger-*.jsonl.gz 2>/dev/null | tail -n +6 || true)
      if [ -n "$old_ledgers" ]; then
        printf '%s\n' "$old_ledgers" | xargs rm -f
      fi
    fi
  fi
fi

# 2. Caches regenerables — find safe directories
prune_paths=(.git .claude orchestrator-state/tasks orchestrator-state/memory docs flutter_template .venv venv node_modules)
prune_args=()
for p in "${prune_paths[@]}"; do prune_args+=( -path "./$p" -prune -o ); done

# Caches concretos
while IFS= read -r d; do
  [ -z "$d" ] && continue
  sz=$(size_bytes "$d"); sz=${sz:-0}
  hr_count=$((hr_count+1)); hr_size=$((hr_size+sz))
  maybe rm -rf "$d"
done < <(find . "${prune_args[@]}" -type d \( -name __pycache__ -o -name .pytest_cache -o -name htmlcov -o -name .ruff_cache -o -name .mypy_cache \) -print 2>/dev/null)

# Ficheros sueltos
while IFS= read -r f; do
  [ -z "$f" ] && continue
  sz=$(wc -c < "$f" 2>/dev/null); sz=${sz:-0}
  sd_count=$((sd_count+1)); sd_size=$((sd_size+sz))
  maybe rm -f "$f"
done < <(find . "${prune_args[@]}" -type f \( -name '.DS_Store' -o -name 'Thumbs.db' -o -name '*.tmp' -o -name '*.bak' -o -name '*.swp' \) -print 2>/dev/null)

# 3. Archivar handoffs/evidence/reports de slices done con >2 días
# (solo si jq existe — si no, omitir el archivado para no fallar)
if command -v jq >/dev/null 2>&1 && [ -f orchestrator-state/tasks/registry.json ]; then
  # IDs de tareas done, ordenados por orden en registry, descartando las últimas KEEP
  done_ids=$(jq -r '.tasks[] | select(.status == "done") | .id' orchestrator-state/tasks/registry.json 2>/dev/null | reverse_lines | tail -n "+$((KEEP+1))" | reverse_lines)
  if [ -n "$done_ids" ]; then
    if [ "$APPLY" -eq 1 ]; then
      mkdir -p "$ARCHIVE_DIR/handoffs" "$ARCHIVE_DIR/evidence" "$ARCHIVE_DIR/reports" 2>/dev/null
    fi
    while IFS= read -r tid; do
      [ -z "$tid" ] && continue
      # Solo archivar si el handoff existe y tiene >2 días
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

# Resumen
log "Caches dirs:    $hr_count (${hr_size} bytes)"
log "Ficheros sueltos: $sd_count (${sd_size} bytes)"
log "Slices archivadas: $ar_count"
[ "$rotated" -eq 1 ] && log "ledger.jsonl rotado"
[ "$APPLY" -eq 0 ] && log "DRY-RUN — relanza con --apply para ejecutar"
exit 0
