"""
Dependency smoke tests for the full backend dependency set.

Slice: P00-S01-T003 — Backend dependency pack
Phase: P00 — Scaffold + Design System

Purpose:
  Verify that every declared production and dev dependency can be imported
  and that the most critical symbols are present. No live services are used:
  no DB connections, no Redis, no Celery workers, no LLM API calls.

Rules:
  - Celery smoke: instantiate with in-memory broker — no .start(), no .send_task().
  - No asyncpg.connect(), no sqlalchemy engine.connect() at test time.
  - All structlog/config smoke uses only in-process state.
  - LiteLLM and LangChain: import-only; no completion() calls.
  - MCP: import package only; no server bind.

Dependencies (all installed in this slice via pip install -e ".[dev]"):
  Runtime: fastapi, uvicorn, sqlalchemy, alembic, asyncpg, pydantic, pydantic-settings,
           argon2-cffi, pyjwt, cryptography, python-multipart, itsdangerous, httpx,
           pypdf, python-docx, celery, redis, resend, structlog, prometheus-client,
           boto3, pgvector, litellm, langchain, langchain-core, langchain-community,
           langchain-text-splitters, langgraph, deepagents, mcp, tiktoken.
  Dev: ruff, mypy, pytest, pytest-asyncio, pytest-cov.
"""
from __future__ import annotations

import importlib

import pytest


# ---------------------------------------------------------------------------
# Category 1 — Web framework
# ---------------------------------------------------------------------------


def test_fastapi_importable() -> None:
    """FastAPI and its core components can be imported."""
    import fastapi

    assert hasattr(fastapi, "FastAPI"), "FastAPI class missing from fastapi"
    assert hasattr(fastapi, "__version__"), "fastapi has no __version__"
    from fastapi import FastAPI

    app = FastAPI(title="smoke", version="0.0.0")
    assert app.title == "smoke"


def test_uvicorn_importable() -> None:
    """uvicorn can be imported with its main and config modules."""
    import uvicorn

    assert hasattr(uvicorn, "run"), "uvicorn.run missing"


# ---------------------------------------------------------------------------
# Category 2 — ORM / migrations / DB driver
# ---------------------------------------------------------------------------


def test_sqlalchemy_importable() -> None:
    """SQLAlchemy 2.x async symbols are present."""
    import sqlalchemy
    from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

    assert sqlalchemy.__version__.startswith("2."), (
        f"Expected SQLAlchemy 2.x, got {sqlalchemy.__version__}"
    )
    assert AsyncSession is not None
    assert async_sessionmaker is not None
    assert create_async_engine is not None


def test_alembic_importable() -> None:
    """Alembic can be imported."""
    import alembic

    assert hasattr(alembic, "__version__"), "alembic has no __version__"


def test_asyncpg_importable() -> None:
    """asyncpg can be imported (no connection attempted)."""
    import asyncpg

    assert hasattr(asyncpg, "__version__"), "asyncpg has no __version__"
    assert hasattr(asyncpg, "connect"), "asyncpg.connect missing"


# ---------------------------------------------------------------------------
# Category 3 — Pydantic stack
# ---------------------------------------------------------------------------


def test_pydantic_importable() -> None:
    """Pydantic v2 is present and functional."""
    import pydantic
    from pydantic import BaseModel, Field

    assert pydantic.__version__.startswith("2."), (
        f"Expected Pydantic v2, got {pydantic.__version__}"
    )

    class _Smoke(BaseModel):
        x: int = Field(default=1)

    assert _Smoke().x == 1


def test_pydantic_settings_importable() -> None:
    """pydantic-settings can be imported and Settings can be instantiated."""
    from app.core.config import Settings

    # Use an empty env to avoid needing a .env file in tests
    settings = Settings.model_construct()
    assert settings is not None


# ---------------------------------------------------------------------------
# Category 4 — Auth / security
# ---------------------------------------------------------------------------


def test_argon2_cffi_importable() -> None:
    """argon2-cffi can be imported and hash/verify works."""
    from argon2 import PasswordHasher

    ph = PasswordHasher()
    h = ph.hash("smoke-password")
    assert ph.verify(h, "smoke-password")


def test_pyjwt_importable() -> None:
    """PyJWT can be imported and encode/decode round-trips."""
    import jwt

    token = jwt.encode({"sub": "smoke"}, "secret", algorithm="HS256")
    decoded = jwt.decode(token, "secret", algorithms=["HS256"])
    assert decoded["sub"] == "smoke"


def test_cryptography_importable() -> None:
    """cryptography Fernet can be imported and encrypt/decrypt works."""
    from cryptography.fernet import Fernet

    key = Fernet.generate_key()
    f = Fernet(key)
    token = f.encrypt(b"smoke-data")
    assert f.decrypt(token) == b"smoke-data"


# ---------------------------------------------------------------------------
# Category 5 — HTTP / forms / cookies
# ---------------------------------------------------------------------------


def test_python_multipart_importable() -> None:
    """python-multipart can be imported."""
    importlib.import_module("multipart")


def test_itsdangerous_importable() -> None:
    """itsdangerous can be imported and signing works."""
    from itsdangerous import URLSafeSerializer

    s = URLSafeSerializer("secret")
    signed = s.dumps({"smoke": True})
    assert s.loads(signed) == {"smoke": True}


def test_httpx_importable() -> None:
    """httpx can be imported with async client available."""
    import httpx

    assert hasattr(httpx, "AsyncClient"), "httpx.AsyncClient missing"
    assert hasattr(httpx, "__version__"), "httpx has no __version__"


# ---------------------------------------------------------------------------
# Category 6 — Document parsing
# ---------------------------------------------------------------------------


def test_pypdf_importable() -> None:
    """pypdf can be imported."""
    import pypdf

    assert hasattr(pypdf, "__version__"), "pypdf has no __version__"
    assert hasattr(pypdf, "PdfReader"), "pypdf.PdfReader missing"


def test_python_docx_importable() -> None:
    """python-docx can be imported."""
    import docx

    assert hasattr(docx, "Document"), "docx.Document missing"


# ---------------------------------------------------------------------------
# Category 7 — Queue / cache
# ---------------------------------------------------------------------------


def test_celery_importable() -> None:
    """Celery can be imported and instantiated with in-memory broker.

    NOTE: no worker is started, no task is sent. In-memory broker only.
    """
    from celery import Celery

    app = Celery("smoke", broker="memory://")
    assert app.main == "smoke"


def test_redis_importable() -> None:
    """redis-py can be imported (no connection attempted)."""
    import redis

    assert hasattr(redis, "Redis"), "redis.Redis missing"
    assert hasattr(redis, "__version__"), "redis has no __version__"


# ---------------------------------------------------------------------------
# Category 8 — Email
# ---------------------------------------------------------------------------


def test_resend_importable() -> None:
    """resend can be imported."""
    import resend

    assert hasattr(resend, "Emails") or hasattr(resend, "emails"), (
        "resend.Emails or resend.emails missing"
    )


# ---------------------------------------------------------------------------
# Category 9 — Observability
# ---------------------------------------------------------------------------


def test_structlog_importable() -> None:
    """structlog can be imported and a logger can be obtained."""
    import structlog

    log = structlog.get_logger("smoke")
    assert log is not None


def test_prometheus_client_importable() -> None:
    """prometheus-client can be imported and a Counter can be created."""
    import prometheus_client

    c = prometheus_client.Counter("smoke_total", "Smoke counter")
    assert c is not None


# ---------------------------------------------------------------------------
# Category 10 — Storage
# ---------------------------------------------------------------------------


def test_boto3_importable() -> None:
    """boto3 can be imported (no AWS credentials needed for import)."""
    import boto3

    assert hasattr(boto3, "client"), "boto3.client missing"
    assert hasattr(boto3, "__version__"), "boto3 has no __version__"


# ---------------------------------------------------------------------------
# Category 11 — PostgreSQL vector binding
# ---------------------------------------------------------------------------


def test_pgvector_importable() -> None:
    """pgvector Python binding can be imported (no DB connection)."""
    import pgvector

    assert hasattr(pgvector, "__version__") or importlib.import_module("pgvector") is not None


# ---------------------------------------------------------------------------
# Category 12 — AI gateway
# ---------------------------------------------------------------------------


def test_litellm_importable() -> None:
    """litellm can be imported (no LLM call attempted).

    Note: litellm exposes version as `_version` (private), not `__version__`.
    We verify the completion symbol is present and that the package imported.
    """
    import litellm

    assert hasattr(litellm, "completion"), "litellm.completion missing"
    # litellm uses _version (not __version__); either is acceptable
    assert hasattr(litellm, "_version") or hasattr(litellm, "__version__"), (
        "litellm has no version attribute"
    )


# ---------------------------------------------------------------------------
# Category 13 — RAG / LangChain
# ---------------------------------------------------------------------------


def test_langchain_core_importable() -> None:
    """langchain-core can be imported."""
    from langchain_core.documents import Document

    doc = Document(page_content="smoke", metadata={})
    assert doc.page_content == "smoke"


def test_langchain_importable() -> None:
    """langchain can be imported."""
    import langchain

    assert hasattr(langchain, "__version__"), "langchain has no __version__"


def test_langchain_community_importable() -> None:
    """langchain-community can be imported."""
    importlib.import_module("langchain_community")


def test_langchain_text_splitters_importable() -> None:
    """langchain-text-splitters can be imported."""
    from langchain_text_splitters import CharacterTextSplitter

    assert CharacterTextSplitter is not None


# ---------------------------------------------------------------------------
# Category 14 — LangGraph
# ---------------------------------------------------------------------------


def test_langgraph_importable() -> None:
    """langgraph can be imported."""
    import langgraph

    assert hasattr(langgraph, "__version__") or importlib.import_module("langgraph") is not None


# ---------------------------------------------------------------------------
# Category 15 — DeepAgents
# ---------------------------------------------------------------------------


def test_deepagents_importable() -> None:
    """deepagents can be imported (no API call attempted)."""
    importlib.import_module("deepagents")


# ---------------------------------------------------------------------------
# Category 16 — MCP Python SDK
# ---------------------------------------------------------------------------


def test_mcp_importable() -> None:
    """mcp (modelcontextprotocol/python-sdk) can be imported (no server bind)."""
    import mcp

    assert importlib.import_module("mcp") is not None


# ---------------------------------------------------------------------------
# Category 17 — Token counting
# ---------------------------------------------------------------------------


def test_tiktoken_importable() -> None:
    """tiktoken can be imported and an encoding can be loaded."""
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode("smoke test")
    assert len(tokens) > 0


# ---------------------------------------------------------------------------
# Category 18 — Core infrastructure (this slice)
# ---------------------------------------------------------------------------


def test_core_config_importable() -> None:
    """app.core.config.Settings can be imported and constructed."""
    from app.core.config import Settings

    settings = Settings.model_construct()
    assert settings is not None


def test_core_logging_importable() -> None:
    """app.core.logging.get_logger returns a bound logger."""
    from app.core.logging import get_logger

    log = get_logger("smoke")
    assert log is not None


def test_core_db_importable() -> None:
    """app.core.db symbols are importable (no connection attempted)."""
    from app.core.db import get_session

    assert get_session is not None


# ---------------------------------------------------------------------------
# Category 19 — Dev tools
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "module",
    [
        "ruff",
        "mypy",
        "pytest",
        "pytest_asyncio",
        "pytest_cov",
    ],
)
def test_dev_tool_importable(module: str) -> None:
    """Each dev tool package can be imported."""
    importlib.import_module(module)
