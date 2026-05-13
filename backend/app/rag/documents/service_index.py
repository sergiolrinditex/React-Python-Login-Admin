"""
Hilo People — IndexDocument use case for RAG document admin.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Business logic for POST /api/v1/admin/rag/documents/{id}/index.
         Responsibilities:
           1. Fetch document by id (→ 404 if not found).
           2. Validate collection_id is not NULL (→ 422 if missing, F.8).
           3. Check for in-flight job (→ 409 on pending/running).
           4. INSERT vectorization_jobs(status='pending') + UPDATE documents.status='processing'.
           5. Dispatch chain(extract_and_chunk, embed_chunks).apply_async() (§F).
           6. On dispatch failure: ROLLBACK job row + doc status; return 500.
           7. Emit audit_log (A.3.7).

Key deps:
  - celery (chain — F.1)
  - app.workers.tasks_documents.extract_and_chunk (F.2)
  - app.workers.tasks_embeddings.embed_chunks (F.2)
  - app.rag.documents.{repository, audit, errors}

Source refs:
  - task pack P02-S06-T001 §A.3, §F (worker dispatch contract, verified)
  - 01-non-negotiables.md §Error handling (typed, rollback on failure)
"""

from __future__ import annotations

import logging
import os
import time
import uuid

from sqlalchemy.orm import Session

from app.db.models.rag import Document, VectorizationJob
from app.rag.documents import audit, repository
from app.rag.documents.errors import (
    DocumentInvalidError,
    IndexDispatchError,
    IndexInProgressError,
)

logger = logging.getLogger("hilo.rag.documents.service_index")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# Module-level import of Celery chain for patchability in tests (§F.6).
# Guard against ImportError when Celery is not installed in test environments.
try:
    from celery import chain  # type: ignore[import-untyped]  # noqa: F401
    from app.workers.tasks_documents import extract_and_chunk  # noqa: F401
    from app.workers.tasks_embeddings import embed_chunks  # noqa: F401
except ImportError:
    chain = None  # type: ignore[assignment]
    extract_and_chunk = None  # type: ignore[assignment]
    embed_chunks = None  # type: ignore[assignment]


def index_document(
    session: Session,
    document_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    request_id: str,
    client_ip: str,
) -> VectorizationJob:
    """Execute the index-document use case.

    Args:
        session:       SQLAlchemy session (caller manages lifecycle).
        document_id:   UUID of the document to index.
        admin_user_id: Authenticated admin UUID.
        request_id:    X-Request-ID correlation string.
        client_ip:     Client IP for audit.

    Returns:
        The created (or existing in-flight) VectorizationJob ORM instance.

    Raises:
        DocumentInvalidError: Document not found (404) or no collection_id (422).
        IndexInProgressError: Existing pending/running job (409).
        IndexDispatchError:   Celery/Redis dispatch failed (500).
    """
    t_start = time.monotonic()

    if _VERBOSE:
        logger.debug(
            "rag.documents.index.start document_id=%s admin_id=%s request_id=%s",
            str(document_id),
            str(admin_user_id),
            request_id,
        )  # BEFORE

    # A.3.1 Document must exist
    doc: Document | None = repository.get_document_by_id(session, document_id)
    if doc is None:
        raise DocumentInvalidError("id", f"Document {document_id} not found.")

    # A.3.2 Document must have a collection_id
    if doc.collection_id is None:
        raise DocumentInvalidError(
            "collection_id",
            "Document has no collection_id; cannot be indexed.",
        )

    # A.3.3 In-flight dedup
    inflight = repository.find_inflight_job(session, document_id)
    if inflight is not None:
        raise IndexInProgressError(str(inflight.id), inflight.status)

    # A.3.4/A.3.5 INSERT job + UPDATE document.status atomically
    job = repository.create_job_and_set_processing(session, document_id)

    # A.3.4 Celery dispatch (§F.2 — apply_async with chain)
    # Use the module-level `chain` import (imported at top of this module to
    # allow patch("app.rag.documents.service_index.chain") in tests per §F.6).
    # A local `from celery import chain` inside the function body would shadow
    # the module attribute and make the test patch ineffective.
    try:
        chain(
            extract_and_chunk.s(str(document_id), request_id=request_id),
            embed_chunks.s(),
        ).apply_async()
    except Exception as exc:
        # F.8 Rollback job row + document status on dispatch failure
        logger.error(
            "rag.documents.index.dispatch.error document_id=%s error=%s request_id=%s",
            str(document_id),
            type(exc).__name__,
            request_id,
            exc_info=True,
        )
        try:
            session.rollback()
        except Exception:
            pass
        raise IndexDispatchError(exc) from exc

    session.commit()

    # A.3.7 Audit
    audit.audit_document_index(
        actor_user_id=admin_user_id,
        document_id=document_id,
        metadata={
            "request_id": request_id,
            "ip": client_ip,
            "document_id": str(document_id),
            "job_id": str(job.id),
        },
    )

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    if _VERBOSE:
        logger.debug(
            "rag.documents.index.ok job_id=%s document_id=%s latency_ms=%s request_id=%s",
            str(job.id),
            str(document_id),
            latency_ms,
            request_id,
        )  # AFTER
    else:
        logger.warning(
            "rag.documents.index.ok job_id=%s document_id=%s latency_ms=%s request_id=%s",
            str(job.id),
            str(document_id),
            latency_ms,
            request_id,
        )

    return job
