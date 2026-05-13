"""
Hilo People — Shared helpers for Celery vectorization worker tasks.

Slice:  P02-S04-T002 — Celery vectorization worker
Phase:  P02 Core Features (the motor)
Purpose: Private module shared by tasks_documents and tasks_embeddings.
         Contains:
           - Logging helpers (_log_before, _log_after_ok, _log_after_err)
           - DB helpers (_update_progress, _mark_failed)
           - SQLAlchemy session factory (_engine, _SessionLocal, DB_URL)

WRITE_SET_DRIFT §D-HELPERS: This file is outside the registry write_set.
  Extracted to keep tasks_documents.py and tasks_embeddings.py within the
  ~300 LOC cap (both exceeded cap with all helpers inline). Pre-declared
  in handoff P02-S04-T002.md §D-WORKER1 (same drift group, intrinsic).

Key deps:
  - sqlalchemy==2.0.49 (sync Session, sessionmaker, create_engine)
  - os (env var access)

Source refs:
  - task pack P02-S04-T002 §6.3 (potential helpers drift)
  - .claude/rules/01-non-negotiables.md §File size, §Logging
"""

from __future__ import annotations

import logging
import os
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session, sessionmaker

from app.db.models.rag import VectorizationJob

# ---------------------------------------------------------------------------
# Verbose logging flag — matches app.rag.retriever pattern
# ---------------------------------------------------------------------------
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Shared DB session factory (sync psycopg3)
# ---------------------------------------------------------------------------
_DB_URL: str = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev",
)
if _DB_URL.startswith("postgresql+asyncpg://"):
    _DB_URL = _DB_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)
elif _DB_URL.startswith("postgresql://") and not _DB_URL.startswith("postgresql+"):
    _DB_URL = _DB_URL.replace("postgresql://", "postgresql+psycopg://", 1)

_engine = sa.create_engine(_DB_URL, pool_pre_ping=True, pool_size=3, max_overflow=5)
_SessionLocal = sessionmaker(bind=_engine, autocommit=False, autoflush=False)


# ---------------------------------------------------------------------------
# Logging helpers (BEFORE / AFTER pattern — §7)
# ---------------------------------------------------------------------------


def log_before(logger: logging.Logger, stage: str, job_id: Any,
               document_id: Any, **extra: Any) -> None:
    """Log the BEFORE event for a stage when verbose mode is active.

    Args:
        logger:      Logger instance from calling module.
        stage:       Stage name (e.g. 'read_storage').
        job_id:      VectorizationJob UUID.
        document_id: Document UUID.
        **extra:     Additional structured context (no PII).
    """
    if _VERBOSE:
        logger.info(
            "vectorization.%s.before",
            stage,
            extra={"job_id": str(job_id), "document_id": str(document_id), **extra},
        )


def log_after_ok(logger: logging.Logger, stage: str, job_id: Any,
                 latency_ms: float, **extra: Any) -> None:
    """Log the AFTER-OK event for a stage when verbose mode is active.

    Args:
        logger:     Logger instance.
        stage:      Stage name.
        job_id:     VectorizationJob UUID.
        latency_ms: Stage duration in milliseconds.
        **extra:    Additional structured context (counts, ids — no content).
    """
    if _VERBOSE:
        logger.info(
            "vectorization.%s.after.ok",
            stage,
            extra={"job_id": str(job_id), "latency_ms": latency_ms, **extra},
        )


def log_after_err(logger: logging.Logger, stage: str, job_id: Any,
                  error_type: str, latency_ms: float) -> None:
    """Log the AFTER-ERROR event for a stage (always logged regardless of flag).

    Args:
        logger:     Logger instance.
        stage:      Stage name.
        job_id:     VectorizationJob UUID.
        error_type: Exception class name.
        latency_ms: Stage duration in milliseconds.
    """
    logger.warning(
        "vectorization.%s.after.error",
        stage,
        extra={
            "job_id": str(job_id),
            "error_type": error_type,
            "latency_ms": latency_ms,
        },
    )


# ---------------------------------------------------------------------------
# DB helpers — each update in its own transaction (D-PROGRESS-TX)
# ---------------------------------------------------------------------------


def update_progress(session: Session, job_id: uuid.UUID, progress: int) -> None:
    """Commit a progress UPDATE in its own transaction (D-PROGRESS-TX).

    Args:
        session:  Active SQLAlchemy session (will commit).
        job_id:   VectorizationJob UUID.
        progress: New progress value (0-100).
    """
    session.execute(
        sa.update(VectorizationJob)
        .where(VectorizationJob.id == job_id)
        .values(progress=progress)
    )
    session.commit()


def mark_failed(session: Session, job_id: uuid.UUID, error: str) -> None:
    """Persist failure status in its own transaction.

    Args:
        session: Active SQLAlchemy session (will commit).
        job_id:  VectorizationJob UUID.
        error:   Error message (truncated to 1024 chars).
    """
    session.execute(
        sa.update(VectorizationJob)
        .where(VectorizationJob.id == job_id)
        .values(
            status="failed",
            error=error[:1024],
            finished_at=sa.text("now()"),
        )
    )
    session.commit()


def mark_done(session: Session, job_id: uuid.UUID) -> None:
    """Persist done status with progress=100 in its own transaction.

    Args:
        session: Active SQLAlchemy session (will commit).
        job_id:  VectorizationJob UUID.
    """
    session.execute(
        sa.update(VectorizationJob)
        .where(VectorizationJob.id == job_id)
        .values(status="done", progress=100, finished_at=sa.text("now()"))
    )
    session.commit()
