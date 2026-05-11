# Official Doc Note: T003 Backend Dependency Pack — Pinned Versions

DATE: 2026-05-11
TASK_ID: P00-S01-T003
TOPIC: All 20 backend packages for T003 — exact stable versions verified via PyPI live JSON + Context7
VERIFIED_BY: official-docs-researcher

---

## Canonical Version Table

All versions verified live from PyPI JSON API on 2026-05-11. No pre-releases, no rc, no dev, no nightly included.

| # | Paquete (PyPI name) | Versión estable | URL oficial PyPI | Fuente verificada | Compat Python 3.11+ | Compat T001 pins | Notas / breaking changes |
|---|---|---|---|---|---|---|---|
| 1 | `sqlalchemy` | **2.0.49** | https://pypi.org/project/sqlalchemy/ | PyPI live JSON | ✅ requires-python >=3.9 | ✅ no conflict | 2.x async confirmed (extras: asyncio, asyncpg, aiosqlite). Use `asyncpg` driver for async Postgres. Import: `from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine`. |
| 2 | `alembic` | **1.18.4** | https://pypi.org/project/alembic/ | PyPI live JSON | ✅ | ✅ no conflict | Companion to SQLAlchemy. Async migrations via `run_sync`. No breaking change vs 1.x stable series. |
| 3 | `celery` | **5.6.3** | https://pypi.org/project/celery/ | PyPI live JSON | ✅ py3.9–3.13 listed | ✅ no conflict | Python 3.11 supported. Named "recovery" release. Stable 5.x series. Requires broker; pair with `redis://` URL via env. |
| 4 | `redis` | **7.4.0** | https://pypi.org/project/redis/ | PyPI live JSON | ✅ | ✅ no conflict | Python Redis client. Async support via `redis.asyncio`. Import: `import redis` or `import redis.asyncio as aioredis`. |
| 5 | `pypdf` | **6.11.0** | https://pypi.org/project/pypdf/ | PyPI live JSON | ✅ | ✅ no conflict | Actively maintained. Import: `from pypdf import PdfReader`. Successor to PyPDF2 (do NOT install PyPDF2). |
| 6 | `python-docx` | **1.2.0** | https://pypi.org/project/python-docx/ | PyPI live JSON | ✅ | ✅ no conflict | Import alias: `from docx import Document` (import name is `docx`, NOT `python_docx`). PyPI dist: `python-docx`. |
| 7 | `resend` | **2.30.0** | https://pypi.org/project/resend/ | PyPI live JSON | ✅ | ✅ no conflict | Official Resend SDK (resendlabs/resend-python, MIT license). Actively maintained as of May 2026. NOT abandoned. |
| 8 | `structlog` | **25.5.0** | https://pypi.org/project/structlog/ | PyPI live JSON | ✅ | ✅ no conflict | Stable. Import: `import structlog`. JSON renderer + request_id context pattern is standard. |
| 9 | `prometheus-client` | **0.25.0** | https://pypi.org/project/prometheus-client/ | PyPI live JSON | ✅ | ✅ no conflict | PyPI dist: `prometheus-client` (hyphen). Python import: `import prometheus_client` (underscore). Expose `/metrics` via ASGI middleware or separate port. |
| 10 | `boto3` | **1.43.6** | https://pypi.org/project/boto3/ | PyPI live JSON | ✅ | ✅ no conflict | AWS SDK. S3/MinIO compat via `endpoint_url`. Import: `import boto3`. |
| 11 | `pgvector` | **0.4.2** | https://pypi.org/project/pgvector/ | PyPI live JSON | ✅ | ✅ no conflict | **Canonical package**: Andrew Kane (andrew@ankane.org), github.com/pgvector/pgvector-python. PyPI dist: `pgvector` (no extras needed — SQLAlchemy adapter bundled). Import: `from pgvector.sqlalchemy import VECTOR`. No separate `pgvector[sqlalchemy]` extras required. Smoke test import: `from pgvector.sqlalchemy import VECTOR`. |
| 12 | `litellm` | **1.83.14** | https://pypi.org/project/litellm/ | PyPI live JSON + Context7 /berriai/litellm | ✅ | ✅ no conflict | ⚠️ AI/ML volatile — re-verify always. Latest stable as of 2026-05-11: 1.83.14. Import: `import litellm`. Context7 confirms stable branch at v1.81.13 / v1.83.3-stable; PyPI live shows 1.83.14 as current. |
| 13 | `langchain` | **1.2.18** | https://pypi.org/project/langchain/ | PyPI live JSON + Context7 /websites/langchain_oss_python_langchain | ✅ | ✅ no conflict | ⚠️ AI/ML volatile. Split package ecosystem: `langchain` (meta), `langchain-core` (1.3.3), `langchain-community` (0.4.1), `langchain-text-splitters` (1.1.2). For RAG: declare `langchain==1.2.18` + `langchain-community==0.4.1` + `langchain-text-splitters==1.1.2`. `langchain-openai` (1.2.1) only if using OpenAI embeddings directly. Import: `from langchain_community.document_loaders import ...` for loaders; `from langchain_text_splitters import RecursiveCharacterTextSplitter` for splitters. |
| 14 | `langgraph` | **1.1.10** | https://pypi.org/project/langgraph/ | PyPI live JSON + Context7 /websites/langchain_oss_python_langgraph | ✅ py3.11+ required | ✅ no conflict | ⚠️ AI/ML volatile. Requires Python >=3.11 (confirmed by docs). Import: `import langgraph`. Install: `pip install langgraph`. CLI (dev only): `pip install "langgraph-cli[inmem]"`. |
| 15 | `deepagents` | **0.5.9** | https://pypi.org/project/deepagents/ | PyPI live JSON | ✅ py3.11–3.14 | ⚠️ SEE NOTES | ⚠️ Beta status (Development Status :: 4 - Beta). Maintained by LangChain org. MIT license. Peer deps: `langchain>=1.2.17,<2.0.0`, `langchain-core>=1.3.2,<2.0.0`, `langchain-anthropic>=1.4.3,<2.0.0`, `langchain-google-genai>=4.2.2,<5.0.0`, `langsmith>=0.8.0`. No explicit `langgraph` pin in requires_dist. Installs `langchain-anthropic` and `langchain-google-genai` as mandatory deps — these are provider SDKs; install order must place deepagents AFTER langchain/langgraph to avoid version downgrades. ⚠️ DISCREPANCY: see separate note. |
| 16 | `mcp` | **1.27.1** | https://pypi.org/project/mcp/ | PyPI live JSON | ✅ | ✅ no conflict | **Canonical MCP Python SDK**: maintained by Anthropic PBC (David Soria Parra, Justin Spahr-Summers). PyPI dist name: `mcp`. Import: `import mcp`. This resolves §2.0 row 14 placeholder `<SDK MCP Python candidato>` — confirmed canonical name is `mcp`. |
| 17 | `tiktoken` | **0.12.0** | https://pypi.org/project/tiktoken/ | PyPI live JSON + Context7 /openai/tiktoken | ✅ | ✅ no conflict | OpenAI tokenizer. Import: `import tiktoken`. Encoding: `tiktoken.encoding_for_model("gpt-4o")` uses `o200k_base`. No breaking changes in 0.12.x. |
| 18 | `ruff` | **0.15.12** | https://pypi.org/project/ruff/ | PyPI live JSON | ✅ | ✅ no conflict | Linter/formatter. Dev extra only. `ruff check backend`. Extremely fast. |
| 19 | `mypy` | **2.0.0** | https://pypi.org/project/mypy/ | PyPI live JSON | ✅ py3.10–3.14 | ✅ no conflict | ⚠️ Major version bump (1.x → 2.0.0). Verify changelog before use. `requires_python>=3.10`. New dep: `ast-serialize>=0.3.0,<1.0.0`, `librt>=0.10.0`. Supports Python 3.11 explicitly. Recommend pinning `mypy==2.0.0` and testing with `mypy backend/app`. |
| 20 | `pytest-asyncio` | **1.3.0** | https://pypi.org/project/pytest-asyncio/ | PyPI live JSON (re-verified 2026-05-11 by debugger) | ✅ requires_python >=3.10 | ✅ pytest>=8.2,<10 (pytest==9.0.2 satisfies) | Updated 2026-05-11 — PyPI confirms 1.3.0 is the latest stable; 1.4.0a* are alphas; requires `pytest<10,>=8.2` → compatible with `pytest==9.0.2`. Initial researcher note pin (1.1.0) was stale. `asyncio_mode = "auto"` in pyproject.toml from T001 — declaring `pytest-asyncio==1.3.0` closes the incongruence. Import: no direct import; configure via pytest.ini / pyproject.toml. |

---

## Additional langchain ecosystem packages (for full smoke test coverage)

| Paquete | Versión | Notas |
|---|---|---|
| `langchain-core` | 1.3.3 | Required by langchain 1.2.18 |
| `langchain-community` | 0.4.1 | Document loaders, vector stores |
| `langchain-text-splitters` | 1.1.2 | Text chunking for RAG |
| `langchain-anthropic` | pulled by deepagents (>=1.4.3) | Anthropic model integration |
| `langchain-google-genai` | pulled by deepagents (>=4.2.2) | Google model integration |
| `langsmith` | pulled by deepagents (>=0.8.0) | Tracing/observability |

---

## Import alias quick reference (for smoke test)

| PyPI dist name | Python import | Notes |
|---|---|---|
| `python-docx` | `import docx` | NOT `import python_docx` |
| `prometheus-client` | `import prometheus_client` | underscore, not hyphen |
| `pgvector` | `from pgvector.sqlalchemy import VECTOR` | No extras needed |
| `celery` | `import celery` | Standard |
| `redis` | `import redis` | Async: `import redis.asyncio` |
| `structlog` | `import structlog` | Standard |
| `litellm` | `import litellm` | Standard |
| `langchain` | `from langchain_core.messages import HumanMessage` | Use langchain_core, langchain_community |
| `langgraph` | `import langgraph` | Standard |
| `deepagents` | `import deepagents` | Beta |
| `mcp` | `import mcp` | Official Anthropic SDK |
| `tiktoken` | `import tiktoken` | Standard |
| `sqlalchemy` | `from sqlalchemy.ext.asyncio import AsyncSession` | 2.x async |
| `alembic` | `import alembic` | Standard |
| `boto3` | `import boto3` | Standard |
| `pypdf` | `from pypdf import PdfReader` | NOT pypdf2 |
| `resend` | `import resend` | Standard |

---

## Compatibility summary against T001 pins

T001 pins:
- `fastapi==0.135.2` — compatible with all packages above (no conflicts found)
- `uvicorn==0.42.0` — no conflicts
- `pydantic==2.12.5` — SQLAlchemy 2.0.49 + LangChain 1.2.18 both support pydantic v2
- `pytest==9.0.2` — pytest-asyncio 1.3.0 requires `pytest>=8.2,<10` ✅
- `httpx==0.28.1` — no conflicts

All 20 packages are compatible with Python 3.11+.

---

## Discrepancy flags

1. **deepagents — Beta status + forced provider SDKs**: `deepagents==0.5.9` is Beta (4-Beta classifier). It mandates `langchain-anthropic>=1.4.3` and `langchain-google-genai>=4.2.2` as hard runtime deps. These are provider-specific SDKs with their own API key requirements. This is a potential install bloat concern for a smoke test (import only). The smoke test can import `deepagents` without instantiating agents — no network calls required. → DISCREPANCY NOTE CREATED: `T003-discrepancy-deepagents.md`.

2. **mypy 2.0.0 — major version bump**: mypy jumped from 1.x to 2.0.0. Breaking changes undocumented in PyPI JSON. Changelog at github.com/python/mypy/blob/master/CHANGELOG.md must be reviewed before configuring strict mode. → Developer must test `mypy backend/app` before declaring mypy config done.

3. **langchain split packages**: `langchain` 1.x is now a meta-package. The actual RAG components are in `langchain-community`, `langchain-core`, `langchain-text-splitters`. Developer must declare the specific sub-packages, not just `langchain` alone, to avoid implicit transitive version drift. → Included in canonical table above.

---

RESOLVED: yes — all 20 packages verified with exact stable versions from PyPI live on 2026-05-11.
TIMESTAMP: 2026-05-11T00:00:00Z
PARTIAL_EXCEPTIONS: deepagents Beta status documented in discrepancy note; developer must await human decision on whether to include it in T003 or defer to follow-up.
UPDATED: 2026-05-11 by debugger (pytest-asyncio aligned to latest stable 1.3.0)
  - PyPI live re-check (https://pypi.org/pypi/pytest-asyncio/json) returned version="1.3.0",
    requires_python=">=3.10", requires_dist contains "pytest<10,>=8.2". 1.4.0a* are alphas.
  - Initial row 20 pin (1.1.0) was stale and would have caused unnecessary drift versus
    PyPI live. Developer's choice of 1.3.0 was correct; this note is now realigned.
  - No source-of-truth doc is affected; this is an official-doc-notes amendment only.
