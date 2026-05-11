# Orchestrator state

This directory is intentionally outside `.claude/`.

Claude Code protects writes to `.claude/` even in autonomous modes, so this engine keeps `.claude/` static and writes all runtime state here:

- `memory/` — PROGRESS, active task/phase, decisions, risks, official-doc notes.
- `tasks/` — registry, runtime-state, work-items, task-packs, follow-up proposals, source-doc patches, handoffs, evidence, reports, ledger.
- `agent-memory/` — manual per-agent memory that survives `/clear` and app resets.
- `dev-logs/` — backend/frontend logs produced by `scripts/dev-restart.sh`.
- `hook-errors.log` — visible hook failures surfaced by SessionStart.

This directory is gitignored except for this README. Do not delete it during an app build. Use `./scripts/reset-for-new-project.sh` only when switching to a new app after replacing the source-of-truth pack.
