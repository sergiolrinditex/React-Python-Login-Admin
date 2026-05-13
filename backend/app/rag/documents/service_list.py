"""
Hilo People — ListDocuments use case for RAG document admin.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Business logic for GET /api/v1/admin/rag/documents.
         Validates query parameters, decodes cursor, delegates to repository.
         No PII in logs (A.2.5) — only counts, filters, and request_id.

Key deps:
  - app.rag.documents.repository (list_documents_paginated)
  - app.rag.documents.cursor (decode_cursor)
  - app.rag.documents.errors (DocumentInvalidError for bad cursor)
  - app.db.models.rag.Document

Source refs:
  - task pack P02-S06-T001 §A.2 (list contract)
  - 01-non-negotiables.md §Logging (no PII in logs)
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from sqlalchemy.orm import Session

from app.db.models.rag import Document
from app.rag.documents import repository
from app.rag.documents.cursor import decode_cursor
from app.rag.documents.errors import DocumentInvalidError

logger = logging.getLogger("hilo.rag.documents.service_list")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_DEFAULT_LIMIT = 50
_MAX_LIMIT = 100
_VALID_STATUSES = frozenset({"uploaded", "processing", "indexed", "failed"})


def list_documents(
    session: Session,
    collection_id: uuid.UUID | None,
    status_filter: str | None,
    cursor: str | None,
    limit: int,
    request_id: str,
) -> tuple[list[Document], str | None]:
    """Execute the list-documents use case.

    Args:
        session:       SQLAlchemy session.
        collection_id: Optional filter by collection.
        status_filter: Optional filter by status ('uploaded','processing','indexed','failed').
        cursor:        Opaque pagination cursor (None = first page).
        limit:         Page size (default 50, max 100).
        request_id:    X-Request-ID correlation.

    Returns:
        Tuple of (Document list, next_cursor string or None).

    Raises:
        DocumentInvalidError: Invalid cursor (→ 400) or invalid status.
    """
    t_start = time.monotonic()

    if _VERBOSE:
        logger.debug(
            "rag.documents.list.start collection_id=%s status=%s "
            "has_cursor=%s limit=%d request_id=%s",
            str(collection_id) if collection_id else "none",
            status_filter or "none",
            cursor is not None,
            limit,
            request_id,
        )  # BEFORE

    # Validate status filter
    if status_filter is not None and status_filter not in _VALID_STATUSES:
        raise DocumentInvalidError(
            "status",
            f"Status '{status_filter}' is not valid. "
            "Use one of: uploaded, processing, indexed, failed.",
        )

    # Clamp limit
    capped_limit = min(max(1, limit), _MAX_LIMIT)

    # Decode cursor
    cursor_created_at = None
    cursor_id = None
    if cursor:
        cursor_created_at, cursor_id = decode_cursor(cursor)

    rows, next_cursor = repository.list_documents_paginated(
        session=session,
        collection_id=collection_id,
        status_filter=status_filter,
        cursor_created_at=cursor_created_at,
        cursor_id=cursor_id,
        limit=capped_limit,
    )

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    if _VERBOSE:
        logger.debug(
            "rag.documents.list.ok count=%d has_next=%s latency_ms=%s request_id=%s",
            len(rows),
            next_cursor is not None,
            latency_ms,
            request_id,
        )  # AFTER — no PII, just counts

    return rows, next_cursor
