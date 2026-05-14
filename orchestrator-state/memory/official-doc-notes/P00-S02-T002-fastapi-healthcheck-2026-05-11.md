# P00-S02-T002 fastapi-healthcheck — Official Docs Verification
- DATE: 2026-05-11
- TASK_ID: P00-S02-T002

RESOLVED: 2026-05-11 — all 3 items verified OK against official FastAPI docs with no discrepancy vs task pack: (a) dependency_overrides pattern matches https://fastapi.tiangolo.com/advanced/testing-dependencies/, (b) module-level sync engine for health-ping is acceptable per FastAPI lifespan guidance (lifespan preferred for async resources but not required for a plain sync engine with pool_pre_ping), (c) HTTP 200 healthy / 503 degraded matches fastapi.status.HTTP_503_SERVICE_UNAVAILABLE. No source-of-truth amendment needed.

---

## FastAPI dependency_overrides pattern — VERIFIED OK

- OFFICIAL: `app.dependency_overrides[original_dep_fn] = override_fn`. Clear with `app.dependency_overrides = {}` or `app.dependency_overrides.clear()`. Works for any `Depends(fn)` used in path operations, including router-level dependencies.
- INTERNAL (task pack §Test pattern): uses `app.dependency_overrides[get_db_engine] = lambda: fake_engine` and `app.dependency_overrides.clear()` in `finally`. Pattern is correct.
- SOURCE: https://fastapi.tiangolo.com/advanced/testing-dependencies/
- DISCREPANCY: none — the task pack pattern matches the official pattern exactly.
- RESOLVED: 2026-05-11 — verified OK, no action needed.

---

## FastAPI lifespan vs module-level engine — VERIFIED OK

- OFFICIAL: FastAPI recommends the `@asynccontextmanager async def lifespan(app)` pattern for startup/shutdown resource init (replaces deprecated `@app.on_event`). However, for a sync `create_engine` used only for simple health pings, module-level initialization is acceptable and common in official FastAPI examples (no lifecycle requirement for a plain sync engine with pool_pre_ping).
- INTERNAL (task pack §Contracts): recommends module-level `engine = create_engine(url, pool_pre_ping=True)` inline in `api/router.py`. This is acceptable. If the developer wants to be fully idiomatic for FastAPI >= 0.93, they can wrap in `lifespan`, but for a health-check scaffold engine it is not required.
- SOURCE: https://fastapi.tiangolo.com/zh-hant/reference/fastapi (lifespan parameter docs)
- DISCREPANCY: none — module-level sync engine is acceptable; lifespan is preferred for async resources.
- RESOLVED: 2026-05-11 — verified OK. Task pack recommendation is sound.

---

## FastAPI liveness/readiness — HTTP codes — VERIFIED OK

- OFFICIAL: FastAPI exports `status.HTTP_503_SERVICE_UNAVAILABLE = 503` from `fastapi.status`. There is no built-in liveness/readiness endpoint. Hand-rolled probes are the standard pattern (FastAPI has no Spring Boot Actuator equivalent).
- INTERNAL (task pack §Acceptance): HTTP 200 healthy, HTTP 503 degraded — matches official status code constants.
- SOURCE: https://fastapi.tiangolo.com/reference/status (HTTP_503_SERVICE_UNAVAILABLE confirmed)
- DISCREPANCY: none.
- RESOLVED: 2026-05-11 — verified OK.
