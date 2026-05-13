"""
Hilo People — Repository layer for RAG document admin endpoints.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Pure DB layer — no business logic. All operations use parametrized
         SQLAlchemy queries. Provides:
           - find_by_sha_and_collection: SHA-256 dedup check (A.1.7).
           - list_documents_paginated: cursor-based list (A.2.2).
           - get_document_by_id: fetch single document.
           - collection_exists: validate collection_id before FK (A.1.6).
           - find_inflight_job: check pending/running job (A.3.3).
           - create_job_and_set_processing: atomic job INSERT + status UPDATE (A.3.4/A.3.5).

Key deps:
  - sqlalchemy==2.0.49 (sync Session, parametrized queries)
  - app.db.models.rag (Document, RagCollection, VectorizationJob)
  - app.rag.documents.cursor (encode_cursor for pagination)

Source refs:
  - task pack P02-S06-T001 §C (DB tables), §A.1, §A.2, §A.3
  - 01-non-negotiables.md §Database (migrations, parametrized, transactions)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.rag import Document, RagCollection, VectorizationJob
from app.rag.documents.cursor import encode_cursor

logger = logging.getLogger("hilo.rag.documents.repository")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 50


# ---------------------------------------------------------------------------
# Collection validation
# ---------------------------------------------------------------------------

def collection_exists(session: Session, collection_id: uuid.UUID) -> bool:
    """Check whether a rag_collection row exists for the given UUID (A.1.6).

    Args:
        session:       Active SQLAlchemy session.
        collection_id: UUID to validate.

    Returns:
        True if the collection exists; False otherwise.
    """
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.collection_exists.start collection_id=%s",
            str(collection_id),
        )  # BEFORE
    t_start = time.monotonic()
    exists = session.execute(
        sa.select(sa.literal(1)).where(
            RagCollection.id == collection_id
        )
    ).scalar_one_or_none() is not None
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.collection_exists.ok exists=%s latency_ms=%s",
            exists,
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER
    return exists


# ---------------------------------------------------------------------------
# SHA-256 dedup
# ---------------------------------------------------------------------------

def find_by_sha_and_collection(
    session: Session, sha256: str, collection_id: uuid.UUID
) -> Document | None:
    """Find an existing document by SHA-256 and collection_id (A.1.7 dedup).

    Different collection_id → different document even for identical bytes.

    Args:
        session:       Active SQLAlchemy session.
        sha256:        Hex SHA-256 of the file content.
        collection_id: Target collection UUID.

    Returns:
        Existing Document row if found; None otherwise.
    """
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.find_by_sha.start sha256_prefix=%s collection_id=%s",
            sha256[:8],
            str(collection_id),
        )  # BEFORE
    t_start = time.monotonic()
    # source_uri encodes sha256 in the key; filter by sha256 substring is not safe
    # without an index. Instead, we use a dedicated filter approach:
    # source_uri LIKE '%/{sha256}.%' is the canonical dedup check for v1.
    result = session.execute(
        sa.select(Document).where(
            Document.collection_id == collection_id,
            Document.source_uri.like(f"%/{sha256}.%"),
        ).limit(1)
    ).scalar_one_or_none()
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.find_by_sha.ok found=%s latency_ms=%s",
            result is not None,
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER
    return result


# ---------------------------------------------------------------------------
# List with cursor pagination
# ---------------------------------------------------------------------------

def list_documents_paginated(
    session: Session,
    collection_id: uuid.UUID | None,
    status_filter: str | None,
    cursor_created_at: datetime | None,
    cursor_id: uuid.UUID | None,
    limit: int,
) -> tuple[list[Document], str | None]:
    """Fetch a page of documents with cursor pagination (A.2.1–A.2.3).

    Ordering: created_at DESC, id DESC (stable tiebreaker).
    Cursor encodes (created_at, id) of the LAST row returned on the previous page.

    Args:
        session:           Active SQLAlchemy session.
        collection_id:     Optional filter — only return docs in this collection.
        status_filter:     Optional filter — only return docs with this status.
        cursor_created_at: Pagination anchor timestamp (None = first page).
        cursor_id:         Pagination anchor UUID (None = first page).
        limit:             Page size (1–100).

    Returns:
        Tuple of (list of Document rows, next_cursor string or None).
    """
    capped_limit = min(max(1, limit), _MAX_LIMIT)

    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.list.start "
            "collection_id=%s status=%s has_cursor=%s limit=%d",
            str(collection_id) if collection_id else "none",
            status_filter or "none",
            cursor_created_at is not None,
            capped_limit,
        )  # BEFORE

    t_start = time.monotonic()
    stmt = sa.select(Document)

    filters: list[sa.ColumnElement] = []
    if collection_id is not None:
        filters.append(Document.collection_id == collection_id)
    if status_filter is not None:
        filters.append(Document.status == status_filter)
    if cursor_created_at is not None and cursor_id is not None:
        # Cursor pagination: rows WHERE (created_at, id) < (anchor, anchor_id)
        # using composite comparison for stable DESC ordering.
        filters.append(
            sa.or_(
                Document.created_at < cursor_created_at,
                sa.and_(
                    Document.created_at == cursor_created_at,
                    Document.id < cursor_id,
                ),
            )
        )

    if filters:
        stmt = stmt.where(sa.and_(*filters))

    stmt = stmt.order_by(
        Document.created_at.desc(), Document.id.desc()
    ).limit(capped_limit + 1)  # +1 to detect if there's a next page

    rows: list[Document] = list(session.execute(stmt).scalars().all())

    has_next = len(rows) > capped_limit
    if has_next:
        rows = rows[:capped_limit]

    next_cursor: str | None = None
    if has_next and rows:
        last = rows[-1]
        next_cursor = encode_cursor(last.created_at, last.id)

    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.list.ok count=%d has_next=%s latency_ms=%s",
            len(rows),
            has_next,
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER

    return rows, next_cursor


# ---------------------------------------------------------------------------
# Get single document
# ---------------------------------------------------------------------------

def get_document_by_id(
    session: Session, document_id: uuid.UUID
) -> Document | None:
    """Fetch a document by primary key (used by /index endpoint).

    Args:
        session:     Active SQLAlchemy session.
        document_id: Document UUID.

    Returns:
        Document ORM instance or None.
    """
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.get_by_id.start document_id=%s",
            str(document_id),
        )  # BEFORE
    t_start = time.monotonic()
    row = session.execute(
        sa.select(Document).where(Document.id == document_id)
    ).scalar_one_or_none()
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.get_by_id.ok found=%s latency_ms=%s",
            row is not None,
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER
    return row


# ---------------------------------------------------------------------------
# Vectorization job operations
# ---------------------------------------------------------------------------

def find_inflight_job(
    session: Session, document_id: uuid.UUID
) -> VectorizationJob | None:
    """Find a pending or running vectorization job for this document (A.3.3).

    Args:
        session:     Active SQLAlchemy session.
        document_id: Document UUID.

    Returns:
        VectorizationJob if one is pending/running; None otherwise.
    """
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.find_inflight_job.start document_id=%s",
            str(document_id),
        )  # BEFORE
    t_start = time.monotonic()
    job = session.execute(
        sa.select(VectorizationJob).where(
            VectorizationJob.document_id == document_id,
            VectorizationJob.status.in_(["pending", "running"]),
        ).order_by(VectorizationJob.created_at.desc()).limit(1)
    ).scalar_one_or_none()
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.find_inflight_job.ok found=%s latency_ms=%s",
            job is not None,
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER
    return job


def create_job_and_set_processing(
    session: Session, document_id: uuid.UUID
) -> VectorizationJob:
    """INSERT vectorization_jobs(pending) and UPDATE documents.status=processing (A.3.4/A.3.5).

    Atomic: both the job INSERT and the document status UPDATE happen in the
    same session. The caller must commit() to persist both.

    Args:
        session:     Active SQLAlchemy session.
        document_id: Document UUID.

    Returns:
        Newly created VectorizationJob (flushed, not yet committed).
    """
    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.create_job.start document_id=%s",
            str(document_id),
        )  # BEFORE
    t_start = time.monotonic()

    job = VectorizationJob(
        document_id=document_id,
        status="pending",
        progress=0,
    )
    session.add(job)
    session.flush()  # Materialise UUID

    session.execute(
        sa.update(Document)
        .where(Document.id == document_id)
        .values(status="processing")
    )

    if _VERBOSE:
        logger.debug(
            "rag.documents.repository.create_job.ok job_id=%s latency_ms=%s",
            str(job.id),
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER
    return job
