# Tester Agent Memory
# Last updated: 2026-05-11

## Environment notes

### Docker / Compose runtime
- Rancher Desktop installed at /Applications/Rancher Desktop.app/
- docker binary at: /Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin/docker
- Docker version: 29.1.4-rd
- Compose version: v5.0.1
- docker is NOT in the default PATH — must be invoked with full path or PATH export:
  export PATH="/Applications/Rancher Desktop.app/Contents/Resources/resources/darwin/bin:$PATH"
- nerdctl: not found in PATH
- hadolint: not installed

### Python / pytest
- python3 at /usr/local/bin/python3 (Python 3.11.5)
- pytest 9.0.2
- Backend tests run from worktree root: `python3 -m pytest backend/tests/ -v`

## Per-task cache

### P00-S02-T001 — Docker compose services (2026-05-11)
- OUTCOME: pass
- T1 PASS: exit 0 on config --quiet; 8 services parsed cleanly
- T2 SKIP: hadolint not available (non-blocking)
- T3 DEFERRED: T003=needs_debug at tester run time; deferred per task pack §I R1
- T4 PASS: minio-bootstrap.sh has 3 BEFORE/AFTER/SUCCESS pairs; no PII in logs
- T5 PASS: all 6 env keys present with dev placeholders
- T6 PASS: nginx:stable-alpine, NERDCTL CAVEAT present, no UNRESOLVED flags
- T7 PASS: 4/4 backend tests green (no regressions)
- T8 PASS: minio-bootstrap.sh syntax valid in both verbose modes
- Handoff: .claude/worktrees/agent-a59eeab464e82ef96/orchestrator-state/tasks/handoffs/P00-S02-T001.md
- Evidence: orchestrator-state/tasks/evidence/P00-S02-T001/
