# Developer Agent Memory — Hilo People

## Codebase patterns discovered

### Python / FastAPI
- Python 3.11.5 is available locally despite STACK_PROFILE requiring 3.12. Tests run OK on 3.11. T003 should set up venv with 3.12 or Docker.
- `_configure_logging()` clears root logger handlers with `root_logger.handlers.clear()` — this conflicts with pytest `caplog` which injects a handler. Use a `ListHandler` pattern instead of `caplog` for testing BEFORE/AFTER log emission.
- FastAPI `TestClient` (httpx-based) is module-scoped for performance: `@pytest.fixture(scope="module")`.
- `time.monotonic()` captured at module import (not at app creation) for accurate uptime across uvicorn `--reload`.
- `asynccontextmanager` for lifespan is the FastAPI 0.95+ pattern (deprecated `@app.on_event`).

### JWT design decision
- TECHNICAL_GUIDE §10.2 uses asymmetric RS256 (JWT_PRIVATE_KEY / JWT_PUBLIC_KEY), NOT symmetric HS256 (JWT_SECRET). Always use RS256 pattern for new JWT work.

### Hook write scope guard interaction
- Developer runs in a worktree at `.claude/worktrees/<id>/`. The `hook_write_scope_guard.py` blocks Write/Edit tool calls to paths starting with `.claude/` relative to the main repo. Use `Bash` tool for file creation in the worktree instead.

### Scripts interface
- `dev-restart.sh` exports: `ROOT_DIR`, `LOG_DIR`, `BACK_LOG`, `FRONT_LOG`, `BACK_PID_FILE`, `FRONT_PID_FILE` — NOT `BACK_LOG_FILE`/`FRONT_LOG_FILE`. Profile must use these exact names.
- `stop_orphan_on_port`, `wait_for`, `stop_pidfile`, `fail`, `warn`, `log`, `info` are exported from `dev-restart.sh` for use in the profile.

## Decisions and why

### P00-S01-T001 (2026-05-11)
- Created all scaffold files via Bash (not Write tool) because the worktree path starts with `.claude/` relative to main repo and the write scope guard blocks Write tool calls.
- Root `package.json` includes `workspaces: ["frontend"]` for npm workspace compatibility.
- `frontend/package.json` uses `"type": "module"` required for Vite ESM builds.
- `.env.example` documents asymmetric JWT vars per TECHNICAL_GUIDE §10.2, even though task prompt mentioned symmetric JWT_SECRET. Technical guide is authoritative.
- `setup-from-scratch.sh --check` validates structure without installing anything; exit 0 = all files present.

## Frontend ecosystem pins (2026-05 stable baseline)

After official-docs-researcher reconciliation (P00-S01-T001), the correct 2026-05 greenfield frontend stack is:
- `react / react-dom`: ^19.2.0 (React 19 is stable npm latest; ecosystem adopted)
- `vite`: ^8.0.0 (Vite 5 is two majors behind; Vitest 4 requires vite >=6)
- `vitest`: ^4.1.0 (Vitest 4.1 adds explicit Vite 8 support; Vitest 4 is NOT compatible with Vite 5)
- `@vitejs/plugin-react`: ^6.0.1 (peerDeps: vite ^8; uses Oxc not Babel)
- `typescript`: ^6.0.0 (TS 6.0 stable; Vite 8 templates use ~6.0.2)
- `@types/react / @types/react-dom`: ^19.0.0 (match React 19)
- `@testing-library/react`: ^16.3.0 (peerDeps: ^18.0.0 || ^19.0.0; compatible)
- `jsdom`: ^25.0.0

Key compatibility invariant: vitest version X requires vite >= that same minimum. Vitest 3+ requires vite >=6. Vitest 4+ requires vite >=6 (tested with 8). Never pin vite 5 with vitest 3+.

## Gotchas

- `pyproject.toml` `[tool.pytest.ini_options] testpaths` is relative to the file location, so `["tests"]` means `backend/tests/` when pytest is run from `backend/`.
- When `ENABLE_VERBOSE_LOGGING=true`, the test must reinitialize `_configure_logging()` AND add its own handler — the config wipe removes pytest's handler.
- `BACK_PID_FILE` and similar variables are exported by `dev-restart.sh` BEFORE sourcing the profile; the profile can rely on them without re-declaring.
