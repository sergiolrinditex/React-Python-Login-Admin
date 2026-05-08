# Backend dependency pin table — P00-S01-T003

VERIFIED_AT: 2026-05-08
SOURCE: PyPI JSON API (pypi.org/pypi/<name>/json) — full parallel deep pass
RESOLVED: Applied with deviations documented below. All 39 smoke tests GREEN. ruff+mypy clean. uvicorn /health=200.
Deviations from researcher recommendation:
  1. pydantic: pinned to ==2.12.5 instead of range (achieves same resolved version; litellm forces 2.12.5).
  2. redis: pinned to ==6.4.0 (not 7.4.0) because celery 5.6.3 → kombu 5.6.x requires redis<6.5.
  3. itsdangerous: kept in runtime deps (consistent with researcher's table row "add").
  All other pins applied verbatim from researcher's pin table.

---

## Pin table (PyPI latest stable as of 2026-05-08)

| Category | Package | Pinned (T001 baseline) | Latest stable today | Action | Canonical import | Notes / breaking changes |
|---|---|---|---|---|---|---|
| web | fastapi | 0.136.1 | **0.136.1** | keep | `from fastapi import FastAPI` | No change. Already at latest. |
| web | uvicorn[standard] | 0.46.0 | **0.46.0** | keep | `import uvicorn` | No change. Already at latest. |
| web | httpx | 0.28.1 (dev) | **0.28.1** | promote to runtime | `import httpx` | Promote from dev to runtime deps (LiteLLM client, Resend HTTP). LiteLLM pins `httpx==0.28.1` exactly — do NOT bump. |
| web | python-multipart | — | **0.0.27** | add | `from multipart import ...` | Required by FastAPI for `Form(...)` and `UploadFile`. Declare in runtime deps. |
| persistence | sqlalchemy[asyncio] | — | **2.0.49** | add | `from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker` | asyncio extra enables AsyncEngine + AsyncSession. Requires asyncpg driver for PostgreSQL. |
| persistence | asyncpg | — | **0.31.0** | add | `import asyncpg` | PostgreSQL async driver. Covers both SQLAlchemy async AND Alembic async migrations (via `async_engine_from_config`). No psycopg2 needed. See §Alembic decision below. |
| persistence | alembic | — | **1.18.4** | add | `from alembic import command` | Supports async migrations via `run_sync` + asyncpg since 1.11.0. Use `alembic init -t async`. |
| persistence | pgvector | — | **0.4.2** | add | `from pgvector.sqlalchemy import Vector` | Python binding only. PG extension (`CREATE EXTENSION vector`) is P01-S01-T001. Requires Python >=3.9 → compatible with 3.11. |
| persistence | psycopg2-binary | — | **2.9.12** | OPTIONAL — see note | `import psycopg2` | **NOT required**: asyncpg covers Alembic async. Only add if sync tooling (e.g. pgAdmin introspect, alembic sync-mode fallback) is needed. Default: omit. |
| validation | pydantic | — | **2.13.4** | add — but see CRITICAL DISCREPANCY #1 | `from pydantic import BaseModel` | Latest is 2.13.4 but litellm==1.83.14 pins `pydantic==2.12.5` exactly. Resolution: declare `pydantic>=2.12.5,<3.0.0` in pyproject and let pip resolve to 2.12.5 (litellm wins). Do NOT pin 2.13.4 explicitly. |
| validation | pydantic-settings | — | **2.14.1** | add | `from pydantic_settings import BaseSettings` | Works with pydantic 2.x. No breaking changes in 2.14.x relative to 2.13.x. |
| logging | structlog | — | **25.5.0** | add | `import structlog` | Stable. `structlog.configure()` + `structlog.get_logger()` pattern unchanged. |
| observability | prometheus-client | — | **0.25.0** | add | `from prometheus_client import Counter, Gauge` | Stable. No breaking changes. |
| async/tasks | celery[redis] | — | **5.6.3** | add | `from celery import Celery` | redis extra required for Redis broker. Smoke test: `Celery("smoke", broker="memory://")` — no `.start()`. |
| async/tasks | redis | — | **7.4.0** | add | `import redis.asyncio as aioredis` | Version 7.x is the current stable. Async client via `redis.asyncio`. |
| auth | argon2-cffi | — | **25.1.0** | add | `from argon2 import PasswordHasher` | Stable. `PasswordHasher()` API unchanged. |
| auth | pyjwt[crypto] | — | **2.12.1** | add — CHOSEN over python-jose | `import jwt` | See §JWT decision below. `[crypto]` extra requires `cryptography>=3.4.0`. |
| auth | cryptography | — | **48.0.0** | add | `from cryptography.fernet import Fernet` | Major version 48. Fernet API unchanged. Used for provider-key encryption per §10.2. |
| auth | python-jose | — | **3.5.0** | DO NOT ADD | — | Actively maintained (May 2025 release) but NOT chosen. PyJWT is the recommended modern library for FastAPI 2026. python-jose has known CVE history and slower maintenance cadence. Use PyJWT[crypto] only. |
| forms | itsdangerous | — | **2.2.0** | add | `from itsdangerous import URLSafeTimedSerializer` | Stable. Used for signed cookies / tokens. |
| files | pypdf | — | **6.10.2** | add | `from pypdf import PdfReader` | Major version 6. No breaking changes from 4.x → 6.x in basic read API. |
| files | python-docx | — | **1.2.0** | add | `from docx import Document` | Stable. |
| email | resend | — | **2.30.0** | add | `import resend` | Official Resend Python SDK. HTTP-based, uses httpx. |
| storage | boto3 | — | **1.43.6** | add | `import boto3` | AWS SDK. Stable. |
| AI/gateway | litellm | — | **1.83.14** | add | `from litellm import acompletion` | HIGH VOLATILITY. Requires Python >=3.10. Pins `httpx==0.28.1` and `pydantic==2.12.5` exactly — see CRITICAL DISCREPANCY #1. Weekly releases. |
| AI/RAG | langchain | — | **1.2.18** | add | `from langchain.chains import ...` | Requires Python >=3.10. Requires `langchain-core>=1.3.3,<2.0.0` and `langgraph>=1.1.10,<1.2.0`. These constraints are satisfied by the other pinned versions. |
| AI/RAG | langchain-core | — | **1.3.3** | add | `from langchain_core.messages import HumanMessage` | Required by langchain, langgraph, deepagents. Pin to 1.3.3 exactly or `>=1.3.3,<2.0.0`. |
| AI/RAG | langchain-community | — | **0.4.1** | add | `from langchain_community.vectorstores import ...` | Requires `langchain-core>=1.0.1,<2.0.0` — compatible. NOT a 1.x package; community track stays at 0.x while core moved to 1.x. |
| AI/RAG | langchain-text-splitters | — | **1.1.2** | add | `from langchain_text_splitters import RecursiveCharacterTextSplitter` | Requires `langchain-core>=1.2.31,<2.0.0` — compatible. |
| AI/graph | langgraph | — | **1.1.10** | add | `from langgraph.graph import StateGraph` | Requires Python >=3.10. Requires `langchain-core>=1.3.0,<2` — compatible. Also pulls `langgraph-checkpoint`, `langgraph-prebuilt`, `langgraph-sdk`. |
| AI/agents | deepagents | — | **0.5.7** | add | `from deepagents import ...` | Stable (not pre-release). Requires Python >=3.11 — matches project constraint. Requires `langchain>=1.2.17,<2.0.0` (compatible), `langchain-anthropic>=1.4.3` (transitive — must be installed). |
| AI/MCP | mcp | — | **1.27.1** | add | `from mcp import ClientSession` | OFFICIAL Anthropic SDK. Author: Anthropic, PBC. Homepage: modelcontextprotocol.io. This IS the correct canonical package. |
| AI/tokens | tiktoken | — | **0.12.0** | add | `import tiktoken` | LiteLLM pulls tiktoken==0.12.0 as a direct dep — versions match. |
| dev | ruff | 0.15.12 | **0.15.12** | keep | CLI only | Already at latest. |
| dev | mypy | 2.0.0 | **2.0.0** | keep | CLI only | Already at latest. |
| dev | pytest | 9.0.3 | **9.0.3** | keep | `import pytest` | Already at latest. |
| dev | pytest-asyncio | 1.3.0 | **1.3.0** | keep | `import pytest_asyncio` | Requires Python >=3.10. `asyncio_mode = "auto"` is recommended config. |
| dev | pytest-cov | — | **7.1.0** | add | CLI only (`--cov`) | New in dev deps. |
| dev | pip-audit | — | **2.10.0** | add | CLI only | Required by non-negotiables §Dependencies. |

---

## CRITICAL DISCREPANCIES

### DISCREPANCY #1 — pydantic exact-pin conflict from litellm (HIGH RISK)

**Issue**: `litellm==1.83.14` declares `pydantic==2.12.5` as an **exact** pin in its `requires_dist`. The latest standalone pydantic stable is `2.13.4`. If you declare `pydantic==2.13.4` in `[project].dependencies`, pip install will fail with a dependency conflict because litellm constrains pydantic to exactly 2.12.5.

**Resolution**: Do NOT pin pydantic to a specific version in pyproject.toml directly. Use a range:
```toml
"pydantic>=2.7.4,<3.0.0",
```
This lets pip resolve to `pydantic==2.12.5` (dictated by litellm's exact pin), which is still a stable, production-quality version. pydantic-settings 2.14.1 is compatible with pydantic 2.12.5.

**Developer action**: After `pip install -e ".[dev]"`, run `pip show pydantic` to confirm the resolved version. Document in handoff.

---

### DISCREPANCY #2 — langchain now requires Python >=3.10 (planner said >=3.9)

**Issue**: Task pack §Risk 6 says "langchain 1.x requires 3.9+". Verified today: `langchain==1.2.18` requires `>=3.10.0,<4.0.0`. Same for langgraph (>=3.10), litellm (>=3.10), deepagents (>=3.11).

**Resolution**: NOT a blocker. Project `pyproject.toml` already declares `requires-python = ">=3.11"`, which satisfies all these constraints. No action needed in pyproject. Just correct the source-of-truth comment (do this in a future slice, not T003 which cannot edit source-of-truth during active task).

**Developer action**: None — the stack is compatible. Note in handoff for future ADR update.

---

### DISCREPANCY #3 — deepagents pulls langchain-anthropic as a direct dep

**Issue**: `deepagents==0.5.7` requires `langchain-anthropic>=1.4.3,<2.0.0`. This will be transitively installed. The project does not explicitly declare langchain-anthropic in pyproject, but it will be present in the resolved lock.

**Resolution**: This is acceptable — transitive deps are normal. No need to declare langchain-anthropic explicitly in pyproject.toml unless the app code directly imports it. Document in handoff.

**Developer action**: After install, run `pip show langchain-anthropic` and document the resolved version in the smoke test evidence. Do NOT add to pyproject.toml directly (it's a transitive dep of deepagents).

---

### DISCREPANCY #4 — litellm pins tiktoken==0.12.0 exactly

**Status**: ALIGNED. Latest tiktoken on PyPI is also 0.12.0. No conflict.

---

### DISCREPANCY #5 — mcp[proxy] from litellm vs standalone mcp

**Status**: ALIGNED. LiteLLM's proxy extra pins `mcp==1.26.0`, but we install litellm WITHOUT the proxy extra. The standalone `mcp==1.27.1` we declare is independent. No conflict.

---

## Key architectural decisions (researcher findings for developer)

### JWT library decision

**CHOSEN**: `pyjwt[crypto]==2.12.1`

**Rationale**: PyJWT is the modern, actively maintained JWT library recommended for FastAPI in 2026. It has a clean API (`jwt.encode()` / `jwt.decode()`), the `[crypto]` extra adds RSA/EC support via `cryptography>=3.4.0` which we already declare. python-jose (3.5.0, May 2025) is still maintained but has a CVE history and is not the FastAPI-recommended default. Single library for JWT eliminates redundancy.

**Import**: `import jwt` (from `PyJWT` package)

### Alembic + asyncpg decision (no psycopg2 needed)

**CONFIRMED**: asyncpg alone is sufficient for both:
1. SQLAlchemy async ORM (via `create_async_engine("postgresql+asyncpg://...")`)
2. Alembic async migrations (via `async_engine_from_config` + `run_sync`, available since Alembic 1.11.0)

`psycopg2-binary` is NOT required. Only add it if sync tooling is explicitly needed in a future slice. Omit from T003.

### langchain-community 0.x vs 1.x numbering

`langchain-community` stays at 0.x versioning while `langchain-core` moved to 1.x. This is intentional upstream design — they are separate release tracks. `langchain-community==0.4.1` is the current stable and is fully compatible with `langchain-core==1.3.3`.

### pgvector: Python binding vs DB extension

`pgvector==0.4.2` (Python package) installs only the SQLAlchemy/psycopg integration. The PostgreSQL extension is enabled by `CREATE EXTENSION vector;` in P01-S01-T001 migration. Do NOT confuse the two.

---

## Recommended pyproject.toml block

```toml
[project]
name = "hilo-people-backend"
version = "0.1.0"
description = "Hilo People — FastAPI backend"
requires-python = ">=3.11"
dependencies = [
    # Web / HTTP
    "fastapi==0.136.1",
    "uvicorn[standard]==0.46.0",
    "httpx==0.28.1",
    "python-multipart==0.0.27",

    # Persistence
    "sqlalchemy[asyncio]==2.0.49",
    "asyncpg==0.31.0",
    "alembic==1.18.4",
    "pgvector==0.4.2",

    # Validation / config
    "pydantic>=2.7.4,<3.0.0",          # litellm pins pydantic==2.12.5 exactly — let pip resolve
    "pydantic-settings==2.14.1",

    # Auth / security
    "argon2-cffi==25.1.0",
    "PyJWT[crypto]==2.12.1",
    "cryptography==48.0.0",
    "itsdangerous==2.2.0",

    # Forms
    "python-multipart==0.0.27",        # duplicate-safe — FastAPI/pip deduplicates

    # Files
    "pypdf==6.10.2",
    "python-docx==1.2.0",

    # Async tasks / cache
    "celery[redis]==5.6.3",
    "redis==7.4.0",

    # Email
    "resend==2.30.0",

    # Storage
    "boto3==1.43.6",

    # Observability
    "structlog==25.5.0",
    "prometheus-client==0.25.0",

    # AI / ML (HIGH VOLATILITY — re-verify before any version bump)
    "litellm==1.83.14",
    "langchain==1.2.18",
    "langchain-core==1.3.3",
    "langchain-community==0.4.1",
    "langchain-text-splitters==1.1.2",
    "langgraph==1.1.10",
    "deepagents==0.5.7",
    "mcp==1.27.1",
    "tiktoken==0.12.0",
]

[project.optional-dependencies]
dev = [
    "ruff==0.15.12",
    "mypy==2.0.0",
    "pytest==9.0.3",
    "pytest-asyncio==1.3.0",
    "pytest-cov==7.1.0",
    "pip-audit==2.10.0",
]
```

**Note on python-multipart duplication**: remove the duplicate line (only one `python-multipart` entry needed). Listed twice above only to show it belongs in runtime deps.

**Note on pydantic**: Declare with range `>=2.7.4,<3.0.0` and let pip resolve to `2.12.5` (driven by litellm). After install, verify with `pip show pydantic`.

---

## Python 3.11 compatibility matrix

| Package | requires_python | 3.11 compatible? |
|---|---|---|
| fastapi | >=3.8 | YES |
| uvicorn | >=3.8 | YES |
| httpx | >=3.8 | YES |
| sqlalchemy | >=3.9 | YES |
| asyncpg | >=3.8 | YES |
| alembic | >=3.9 | YES |
| pgvector | >=3.9 | YES |
| pydantic | >=3.8 | YES |
| pydantic-settings | >=3.8 | YES |
| structlog | >=3.9 | YES |
| prometheus-client | >=3.8 | YES |
| celery | >=3.8 | YES |
| redis | >=3.8 | YES |
| argon2-cffi | >=3.7 | YES |
| pyjwt | >=3.9 | YES |
| cryptography | >=3.7 | YES |
| itsdangerous | >=3.8 | YES |
| pypdf | >=3.9 | YES |
| python-docx | >=3.9 | YES |
| resend | >=3.8 | YES |
| boto3 | >=3.8 | YES |
| litellm | >=3.10 | YES |
| langchain | >=3.10 | YES |
| langchain-core | >=3.9 | YES |
| langchain-community | >=3.9 | YES |
| langchain-text-splitters | >=3.9 | YES |
| langgraph | >=3.10 | YES |
| deepagents | >=3.11 | YES (requires exactly 3.11+) |
| mcp | >=3.10 | YES |
| tiktoken | >=3.9 | YES |
| ruff | >=3.7 | YES |
| mypy | >=3.9 | YES |
| pytest | >=3.9 | YES |
| pytest-asyncio | >=3.10 | YES |
| pytest-cov | >=3.9 | YES |
| pip-audit | >=3.8 | YES |

All packages are Python 3.11 compatible. deepagents is the most constrained at >=3.11, which aligns with the project's `requires-python = ">=3.11"`.

---

## LiteLLM peer-constraint resolution (full)

litellm==1.83.14 pins these deps exactly (will override any top-level declaration):
- `httpx==0.28.1` — matches our pin. NO CONFLICT.
- `pydantic==2.12.5` — conflicts if we pin `pydantic==2.13.4`. RESOLUTION: use range (see Discrepancy #1).
- `tiktoken==0.12.0` — matches our pin. NO CONFLICT.
- `openai==2.24.0` — transitive, not declared by us directly.
- `aiohttp==3.13.4` — transitive.

---

## AI ecosystem summary (volatile — re-verify at every major dep bump)

| Package | Version today | Volatility | Re-verify threshold |
|---|---|---|---|
| litellm | 1.83.14 | VERY HIGH (weekly) | Before any bump |
| langchain | 1.2.18 | HIGH (monthly) | Before any bump |
| langchain-core | 1.3.3 | HIGH | Before any bump |
| langchain-community | 0.4.1 | HIGH | Before any bump |
| langchain-text-splitters | 1.1.2 | MEDIUM | Before any bump |
| langgraph | 1.1.10 | HIGH | Before any bump |
| deepagents | 0.5.7 | MEDIUM-HIGH | Before any bump |
| mcp | 1.27.1 | MEDIUM (Anthropic-maintained) | Before any bump |
| tiktoken | 0.12.0 | LOW | 7 days |

---

## RESOLVED tracker

The developer must append `RESOLVED: applied verbatim` (or `RESOLVED: <reason for deviation>`) at the top of this file once they update `backend/pyproject.toml`. Until then, the docs-discrepancy hook will warn on every Write/Edit.
