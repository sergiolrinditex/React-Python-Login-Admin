# Tester Agent Memory

> Reflexion-style memory. Append-only. Read at the start of every tester session.

---

## Cycle 1 — P00-S01-T002 (2026-05-11)

### Learnings

1. **npm workspace hoisting shifts lockfile location**: When the workspace root has `workspaces: ["frontend"]`, the lockfile is always at the workspace root (`package-lock.json`), never at `frontend/package-lock.json`. `npm ci --dry-run` must run from the workspace root, not from `frontend/`. Task packs that declare `frontend/package-lock.json` in the write_set are misdeclared; accept the root-level file and document it.

2. **VITE_ prefix for Vitest env vars**: To set `VITE_ENABLE_VERBOSE_LOGGING` during Vitest runs, prepend it to the bash command as an env var: `VITE_ENABLE_VERBOSE_LOGGING=true bash -lc "npm --prefix frontend run test -- --run"`. Vitest picks up `VITE_*` prefixed env vars from the process environment when using `jsdom` environment.

3. **Worktree root vs project root**: The developer ran with `isolation: worktree`. All `npm` commands must run from inside the worktree (e.g. `/Users/sergiolr/Desktop/Productos/React-Python-Login-Admin/.claude/worktrees/agent-add4156565b59d77a/`), not from the main repo root. Always `cd` or use the worktree path as the working directory.

4. **Backend-regression N/A for frontend-only slices**: When a task pack's `Front → Back → DB contract` table shows backend/DB rows as `NO`, backend regression is N/A. Do not spin up uvicorn just to declare it; document the explicit rationale in the handoff instead.

5. **Verbose logging confirmation pattern**: Run tests with `--reporter=verbose` to surface stdout output from components/modules. The `[providers]` prefix makes it easy to grep for BEFORE/AFTER pattern. Always save both verbose-on and verbose-off runs as separate evidence files.

6. **No PII grep**: After collecting verbose logs, run `grep -i -E "(password|token|email|secret|key|pii|credentials)"` on the log file to confirm no sensitive data. If matches are found, classify as critical finding immediately.

7. **Real tests for provider wiring**: Provider-level component tests that use real BrowserRouter, QueryClientProvider, and I18nextProvider are valid real tests per rule 01. They are unit tests for pure wiring logic — not integration tests. They do not require a running backend.

### Evidence paths
- `orchestrator-state/tasks/evidence/P00-S01-T002/tester-vitest-run.log`
- `orchestrator-state/tasks/evidence/P00-S01-T002/tester-vitest-run-verbose.log`
- `orchestrator-state/tasks/evidence/P00-S01-T002/tester-vitest-run-verbose-off.log`
- `orchestrator-state/tasks/evidence/P00-S01-T002/tester-npm-ci-dry-run.log`
- `orchestrator-state/tasks/evidence/P00-S01-T002/tester-resolve-check.log`

### OUTCOME: pass | NEXT_STATUS: ready_for_close
