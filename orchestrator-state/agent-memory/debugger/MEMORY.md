# Debugger memory — bugs, root causes, solutions, gotchas

## P00-S01-T001 (2026-05-08) — Stale dependency pins on bootstrap manifests

- **Symptom**: `/verify-slice` flagged 13 of 14 declared dependency pins (PyPI + npm) as significantly behind current stable. `01-non-negotiables.md#dependencies` requires actually-current pins.
- **Root cause**: developer pinned to "current stable at bootstrap time" using stale memory; the official-docs-researcher safety-net pass at developer-time only flagged FastAPI and did not catch the rest. By the time the slice reached verify-slice, pins were 1–2 majors behind across the board.
- **Fix applied**: text-only diff in `backend/pyproject.toml` and `frontend/package.json` — same write set ("package manifests") declared by the TASK_ID. No installs, no other files touched. Bumped: fastapi 0.115.12→0.136.1, uvicorn 0.34.2→0.46.0, ruff 0.11.10→0.15.12, mypy 1.16.0→2.0.0, pytest 8.3.5→9.0.3, pytest-asyncio 0.25.3→1.3.0, react 18.3.1→19.2.6, vite 6→8, vitest 3→4, typescript 5.8.3→6.0.3, etc.
- **Pattern**: at scaffolding phase, deps are DECLARED but NOT installed. Pin-bump fix is low-risk because real install/compat verification happens 2 slices later (T002 = npm install, T003 = pip install + dependency_smoke). Major-version compat (pytest 9, pytest-asyncio 1.x, mypy 2.x, vite 8, react 19, ts 6) is the install-slice's problem.
- **Recurring gotcha**: `01-non-negotiables.md#dependencies` says "Pin exact versions" — it does NOT say "pin to whatever you remember was stable last quarter". Trust ONLY a registry query at the moment of writing the manifest, never training-data memory for AI/ML or fast-moving JS ecosystems.
- **Anti-pattern**: re-querying registries inside debugger when verify-slice already provided verified values. Apply the verified diff verbatim — re-querying wastes a debug cycle and risks drift between debug pass and the verify report.
- **Acceptance commands at this slice (T001 scope)**:
  1. `python3 -c "import tomllib; tomllib.loads(open('backend/pyproject.toml','rb').read().decode())"` → exit 0.
  2. `python3 -c "import json; json.load(open('frontend/package.json'))"` → exit 0.
  3. `bash scripts/setup-from-scratch.sh --check` → exit 0 (only `.env no existe` warn is expected).
  4. `python3 -m py_compile backend/app/__init__.py backend/app/main.py` → exit 0.
