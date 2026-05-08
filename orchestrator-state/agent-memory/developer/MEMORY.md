# Developer Agent Memory — Hilo People

## Codebase patterns discovered

### Env variable naming
- `dev-restart.profile.sh` uses `API_PORT` (not `BACKEND_PORT`) and `FRONT_PORT` (not `FRONTEND_PORT`).
- These are the canonical names to use in `.env.example` and anywhere env vars for ports are needed.
- Default: `API_PORT=8000`, `FRONT_PORT=5173` (Vite default, not 5000 from Flutter template comment).

### `scripts/setup-from-scratch.sh`
- Did NOT have `--check` mode originally. Added in P00-S01-T001.
- `--check` mode sets `CHECK_MODE=1` which causes `run_if_declared()` to skip execution without failing.
- The script checks `BACKEND_ROOT=backend/app` and `FRONTEND_ROOT=frontend/src` from STACK_PROFILE.
- If either root doesn't exist, it emits WARN and skips; this was the blocker for T001 verify.
- After T001: both roots exist, so no more root-missing warnings.

### Backend module structure
- Uvicorn entry point: `uvicorn app.main:app` (uses `backend/app/main.py`).
- `backend/app/__init__.py` is required as package marker for this to resolve.
- No root `backend/__init__.py` — pytest discovers via pyproject.toml `testpaths = ["tests"]`.

### Logging pattern (bootstrap)
- T001 uses stdlib `logging` with `ENABLE_VERBOSE_LOGGING` env flag.
- T003 will replace with `structlog` for structured JSON logging per TECHNICAL_GUIDE.
- BEFORE/AFTER log pattern: `logger.debug("BEFORE %s", ...)` + `logger.debug("AFTER %s", ...)`.

### Package version pinning (as of 2026-05)
- fastapi==0.115.12
- uvicorn[standard]==0.34.2
- ruff==0.11.10, mypy==1.16.0, pytest==8.3.5
- react==18.3.1, react-dom==18.3.1, vite==6.3.5, vitest==3.1.3, typescript==5.8.3
- All versions to be confirmed by official-docs-researcher in T002/T003.

## Implementation decisions

### P00-S01-T001 (2026-05-08)
- Added `--check` mode to `scripts/setup-from-scratch.sh` (smallest fix; 11 lines).
  Reason: without it, `alembic upgrade head` runs and fails (not installed); `--check` skips execution.
- Used `ast.parse()` for "compiles" acceptance (no FastAPI install needed at this stage).
- Used `frontend/src/.gitkeep` not `frontend/src/main.tsx` because: (a) task pack says "just the folder", (b) hook might block files outside write set if main.tsx was a full TS file.
- `FRONT_PORT=5173` in .env.example matches Vite default; `dev-restart.profile.sh` had FRONT_PORT=5000 default in comments but that's from Flutter template, not React stack.

## Gotchas

- `dev-restart.profile.sh` is a FLUTTER template not yet customized for React. Back-fill will happen in a future P00 slice. Don't rely on `back_start()` or `front_start()` functions there yet.
- `scripts/setup-from-scratch.sh` doesn't use `set -e` properly for external commands in subshell `( cd "$PROJECT_ROOT" && bash -lc "$cmd" )` — if the cmd fails the parent continues. This is fine for `--check` mode but note this for future scripts.
- `health` endpoint stub returns flat dict `{status, version, uptime}`. Full impl in P00-S02-T002 will wrap it in `{data: {status}}` envelope per TECHNICAL_GUIDE §6.2. Don't expand the stub now.
- All DAG successor tasks (T002, T003, T004) depend on this task being `done`. Don't unblock them until verify-slice + closer completes.
