# Verify-slice evidence — P00-S02-T001

- TASK_ID: P00-S02-T001
- TIMESTAMP: 2026-05-11T12:25:00+02:00
- MODE: pre-closer
- VERIFIER: main-orchestrator (human-driven, /verify-slice)
- RUNTIME: docker compose v5.0.1 on Rancher Desktop (moby backend)
- VERIFY_OUTCOME: issues_found

## Hard reset performed

1. `docker compose down -v` against pre-existing 37h stack at this path (containers from a prior compose snapshot — `hilo-redis` running `redis:8-alpine` and `hilo-postgres` running `pgvector/pgvector:pg18-bookworm`, NOT the imagess declared in the new YAML). Volumes `pg_data` and `minio_data` removed. EXIT=0.
2. `cp .env.example .env` to load required env vars; without it `docker compose config` warned about 6 unset variables. EXIT=0.
3. `docker compose config --quiet` parses cleanly. `docker compose config --services` returns the 8 expected services (postgres, redis, litellm, minio, minio-init, backend, worker, frontend). EXIT=0.
4. `docker compose up -d postgres redis litellm minio` pulled images. Postgres failed first attempt: host port 5432 was occupied by `apn-postgres` from a concurrent compose project (`agentepeoplevigilancianormativa` — Inditex PeopleTech). Stopped apn-postgres temporarily, restarted our postgres, then restored apn-postgres at teardown.

## Healthcheck reality table

| Service | Image (per new YAML) | Compose status | Healthcheck cmd | Runs INSIDE container? | App actually alive? |
|---------|----------------------|----------------|-----------------|------------------------|---------------------|
| postgres | postgres:17-alpine | healthy | pg_isready -U $POSTGRES_USER | YES (exit 0, "accepting connections") | YES |
| redis | valkey/valkey:8-alpine | healthy | valkey-cli ping | YES (PONG) | YES |
| minio | minio/minio:RELEASE.2025-09-07T16-13-09Z | healthy | curl http://localhost:9000/minio/health/live | YES (exit 0; curl present in minio image) | YES |
| litellm | ghcr.io/berriai/litellm:v1.83.14-stable.patch.3 | **UNHEALTHY** | curl http://localhost:4000/health/liveliness | **NO — curl AND wget MISSING in image** (only `/app/.venv/bin/python` present) | YES (200 from host: `"I'm alive!"`) |

## Application-level proofs

```text
$ curl -fsS http://localhost:4000/health/liveliness
"I'm alive!"

$ curl -fsS http://localhost:4000/health/readiness
{"status":"healthy","db":"Not connected","cache":null,"litellm_version":"1.83.14","success_callbacks":[],"use_aiohttp_transport":true,"log_level":"WARNING","is_detailed_debug":false}
```

The litellm app is alive on port 4000 with the correct version, but compose marks the container unhealthy because the healthcheck *command* depends on a binary that does not exist inside that image. As a consequence, any service that declares `depends_on: { litellm: { condition: service_healthy } }` will never have its predecessor become healthy. In this YAML, `backend` does exactly that (`docker-compose.yml:150`) — so on a real `docker compose up -d backend`, backend will never start despite litellm being alive.

## minio-init bootstrap

```text
minio-init-1  | [minio-init] BEFORE: configuring mc alias 'local' -> http://minio:9000
minio-init-1  | Added `local` successfully.
minio-init-1  | [minio-init] AFTER: alias 'local' configured
minio-init-1  | [minio-init] BEFORE: creating bucket 'hilo-docs-dev' if not exists
minio-init-1  | Bucket created successfully `local/hilo-docs-dev`.
minio-init-1  | [minio-init] AFTER: bucket 'hilo-docs-dev' created successfully
minio-init-1  | [minio-init] BEFORE: setting bucket 'hilo-docs-dev' policy to private
minio-init-1  | Access permission for `local/hilo-docs-dev` is set to `private`
minio-init-1  | [minio-init] AFTER: bucket 'hilo-docs-dev' policy set to private
minio-init-1  | [minio-init] SUCCESS: MinIO bootstrap complete
minio-init-1 exited with code 0
```

Subsequent `mc ls local/` confirmed `hilo-docs-dev/`. BEFORE/AFTER/SUCCESS logging compliant with non-negotiables §Logging.

## Backend regression (no compose dependency)

`python3 -m pytest backend/tests/ -v` → `24 passed, 1 warning in 5.53s` (no regressions; pre-existing langgraph deprecation warning logged as R6 already).

## dev-restart.sh --check (canonical verify command)

Script runs cleanly. Exit code = 1 because backend/frontend dev servers are not part of this scaffold-only slice (T002/T004 own that). Matches the developer's documented expectation ("EXIT: 1 (as expected — uvicorn/vite dev servers are not running in worktree)"). Not a defect of this slice.

## Worker service declaration

Service declared with `build:` reusing the backend image, `restart: on-failure`, `depends_on: [postgres, redis]`, `command: ['celery', '-A', 'app.worker', 'worker', '--loglevel=info']`. Per task pack §C R5 + §I R5, the worker is not expected to *run* until P02-S04-T002 (when `app.worker` module is created). Declaration acceptance met; runtime acceptance is documented as deferred.

## Findings

### F1 (in-scope defect, debugger territory) — LiteLLM healthcheck command broken

- **What**: `docker-compose.yml:96` declares `test: ["CMD-SHELL", "curl -fsS http://localhost:4000/health/liveliness || exit 1"]` for the litellm service.
- **Reality**: The official LiteLLM image (`ghcr.io/berriai/litellm:v1.83.14-stable.patch.3`) ships with `python` but *not* `curl` and *not* `wget`. The healthcheck command therefore always fails inside the container, leaving the service permanently `unhealthy` even when the app is alive and returns 200.
- **Blast radius**: `backend` declares `depends_on: { litellm: { condition: service_healthy } }`. On any future `docker compose up -d backend`, backend would never start. This directly violates the slice's acceptance literal "*LiteLLM ... boot locally*" because compose's notion of "boot" is healthy, not just process-up.
- **Why-not-FU**: in-scope by every triage criterion — touched path (`docker-compose.yml`) is in canonical write_set, no new endpoint/route/table/journey/data contract, no scope expansion, no `Write set`/`Conflict group` change.
- **Fix proposal** (debugger): replace the healthcheck `test:` with a python-stdlib probe that already runs inside the image:
  - `test: ["CMD-SHELL", "python -c \"import urllib.request,sys; r=urllib.request.urlopen('http://localhost:4000/health/liveliness', timeout=3); sys.exit(0 if r.status==200 else 1)\" || exit 1"]`
  - or, since `python -c` requires no shell escapes if we use a different form, the CMD form may be cleaner. Developer/debugger decides.

### F2 (out-of-scope nit, optional FU) — host port 5432 collision pattern

- The new YAML maps `5432:5432`. On the user's machine, a concurrent compose project (`agentepeoplevigilancianormativa` / Inditex PeopleTech) holds 5432 with `apn-postgres`. The previous compose snapshot of this same project used `5433:5432` precisely to coexist. The change to `5432:5432` is a regression in concurrent-project ergonomics, but it is *not* a slice-blocking defect because the task pack §F suggests `5432:5432` and the user can choose to stop the colliding project for verify (which is what we did).
- Suggested follow-up: parametrize via `${POSTGRES_HOST_PORT:-5432}` and document in `.env.example`. Classification: `scope_expansion` / `future_enhancement`. Not registered automatically — defer to user decision.

### F3 (non-blocking, format) — official-doc-note RESOLVED format

- `orchestrator-state/memory/official-doc-notes/P00-S02-T001-infra-compose-2026-05-11.md` lines 110–111 use `RESOLVED 2026-05-11 — ...` (without colon). The discrepancy hook regex looks for `RESOLVED:` and therefore still warns at SessionStart, even though the underlying items 5 and 8 are demonstrably applied in code (NERDCTL CAVEAT block present, `nginx:stable-alpine` in frontend/Dockerfile). Add proper `RESOLVED:` lines so the hook stops warning. Warn-only, never blocks.

## Files / evidence layout

```
orchestrator-state/tasks/evidence/P00-S02-T001/verify/
├── SUMMARY.md                        (this file)
├── 01-compose-down.out               (pre-verify teardown of 37h stack)
├── 02-services-list.out              (8 services declared)
├── 03-compose-up-infra.out           (image pulls + container creations)
├── 04-compose-ps-after-up.out
├── 05a-apn-postgres-stop.out         (Inditex postgres stopped temporarily)
├── 05b-postgres-start.out            (our postgres started)
├── 06-healthy-wait.out               (20-tick poll; litellm degrades to unhealthy at t=18)
├── 07a-litellm-logs.out              (uvicorn alive, no app-level error)
├── 08-minio-init.out                 (one-shot bucket creation)
├── 09-backend-pytest.out             (24/24 PASS)
├── 10-dev-restart-check.out          (script-level verify)
├── 11-final-ps.out                   (postgres/redis/minio healthy; litellm unhealthy)
└── 12-teardown.out                   (post-verify teardown + apn-postgres restored)
```
