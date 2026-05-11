# Official Doc Note: Backend Stack Versions — FastAPI / uvicorn / Pydantic

DATE: 2026-05-11
TASK_ID: P00-S01-T001
TOPIC: Backend pyproject.toml version pins and patterns for FastAPI + uvicorn + pydantic

---

## SOURCE_URL

- https://pypi.org/pypi/fastapi/json (PyPI, live)
- https://pypi.org/pypi/uvicorn/json (PyPI, live)
- https://pypi.org/pypi/pydantic/json (PyPI, live)
- https://fastapi.tiangolo.com/tutorial/first-steps (Context7 /websites/fastapi_tiangolo)
- https://github.com/fastapi/fastapi/blob/master/docs/en/docs/deployment/docker.md (Context7 /fastapi/fastapi)
- https://github.com/fastapi/fastapi/blob/master/docs/en/docs/release-notes.md (lifespan pattern)
- https://github.com/kludex/uvicorn (Context7 /kludex/uvicorn)

## SOURCE_VERSION (verified live on 2026-05-11)

| Package | Latest stable |
|---|---|
| fastapi | **0.136.1** |
| uvicorn | **0.46.0** |
| pydantic | **2.13.4** |

## INTERNAL_CLAIM

Task pack §4.3 / §6 instructs: "only `fastapi` and `uvicorn` on backend". No explicit version pins given. The planner marks this as an Unknown (§10.4): "pyproject.toml xor requirements.txt is preferred — both paths in write_set; convention in TECHNICAL_GUIDE §2 uses pyproject.toml style". Task pack §3.3 confirms `python -c "from app.main import app"` must succeed.

## DISCREPANCY

None on the core pattern. Observations:

1. **FastAPI entrypoint pattern** — `from fastapi import FastAPI; app = FastAPI(); @app.get('/health')` remains canonical (confirmed via Context7). No breaking change.

2. **Lifespan** — The `@asynccontextmanager async def lifespan(app: FastAPI): ... yield ...` pattern (replacing deprecated `@app.on_event("startup")`) is the current canonical approach. The `/health` STUB in this slice does NOT use lifespan (no DB/Redis), so the stub pattern is simply `app = FastAPI()` — fully aligned with task pack §3.3 and §4.4.

3. **FastAPI version jump** — Latest is 0.136.1 (not 0.113.x from Docker example docs). Recommend pinning `fastapi[standard]>=0.115.0,<0.137.0` or similar. The `fastapi[standard]` extra bundles uvicorn, so using `fastapi[standard]` avoids a separate `uvicorn` line — BUT for explicit control and STACK_PROFILE alignment, declaring both separately is acceptable:
   - `fastapi>=0.115.0,<0.137.0`
   - `uvicorn[standard]>=0.29.0,<0.47.0`

4. **Pydantic v2 confirmed** — pydantic 2.13.4 is stable. Task pack assumes pydantic v2. NO discrepancy.

5. **pyproject.toml format** — PEP 621 `[project]` table remains the modern standard. Hatchling is the recommended build backend for new projects (used by FastAPI's own tooling). `setuptools` remains valid but is the legacy path.

6. **`__init__.py` requirement** — For `uvicorn app.main:app`, the `backend/` directory must be on PYTHONPATH (or cwd), and `app/` must be a package. An empty `backend/app/__init__.py` IS required for the import `from app.main import app` to work when PYTHONPATH=`backend/` or cwd=`backend/`. PEP 420 namespace packages do NOT reliably work with `uvicorn app.main:app` — the explicit `__init__.py` is correct per task pack §13.

## IMPACT_ON_TASK

- Pin versions explicitly per `01-non-negotiables.md`: use `fastapi>=0.115.0,<0.137.0` (or exact pin `==0.136.1`).
- Do NOT use `fastapi[standard]` in pyproject.toml to avoid bundling uvicorn implicitly — or DO use it and remove explicit `uvicorn` line; either is fine but must be consistent.
- Pydantic v2 is the only supported version for new projects — confirmed, no issue.
- `backend/app/__init__.py` (empty) is required — confirmed, no issue.

## RECOMMENDATION

Minimal `backend/pyproject.toml` for this slice (T001 — stub only):

```toml
[project]
name = "hilo-people-backend"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0,<0.137.0",
    "uvicorn[standard]>=0.29.0,<0.47.0",
    "pydantic>=2.7.0,<3.0.0",
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

Full dep pack (SQLAlchemy, Alembic, Celery, LiteLLM, LangChain, LangGraph, pgvector) is deferred to T003 per task pack §5.

RESOLVED: Reviewed 2026-05-11. Current pins (fastapi==0.135.2, uvicorn==0.42.0, pydantic==2.12.5) fall within the researcher's recommended ranges (fastapi>=0.115.0,<0.137.0, uvicorn[standard]>=0.29.0,<0.47.0, pydantic>=2.7.0,<3.0.0). Pydantic v2 + __init__.py decision confirmed. No code change required this slice. T003 will declare the full dependency pack and may bump fastapi/uvicorn to latest exact pins if needed.
