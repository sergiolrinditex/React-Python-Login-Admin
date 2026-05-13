"""
Hilo People — Celery task: extract text and chunk document.

Slice:  P02-S04-T002 — Celery vectorization worker
Phase:  P02 Core Features (the motor)
Purpose: Implements the `extract_and_chunk` Celery task, which:
           1. Looks up the vectorization job for a document.
           2. Downloads the document binary via _storage.read_bytes().
           3. Extracts plain text via _storage.extract_text().
           4. Creates or reuses a DocumentVersion by SHA-256 checksum.
           5. Splits text into overlapping chunks (RecursiveCharacterTextSplitter).
           6. Persists document_chunks via session.add_all().
           7. Updates vectorization_jobs.progress at each stage.

         Returns a dict consumed by embed_chunks in the Celery chain.
         On unrecoverable failure: persists status='failed' and returns cleanly.
         On IOError/ConnectionError: re-raises so Celery autoretry fires.

Key deps:
  - celery==5.6.3              (app.task, autoretry_for)
  - langchain-text-splitters==1.1.2 (RecursiveCharacterTextSplitter)
  - sqlalchemy==2.0.49         (sync Session)
  - app.workers._helpers       (session factory, logging, DB helpers)
  - app.workers._storage       (read_bytes, detect_mime, extract_text, get_or_create_version)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.4#rag-ingestion
  - task pack P02-S04-T002 §2.1 A1-A3 A5 A7-A12, §3.5, §5.1-5.4, §7, §9

Decisions:
  - D-SYNC-SESSION: sync SQLAlchemy Session (no asyncio/eventlet complexity).
  - D-PROGRESS-TX: each progress UPDATE is its own committed tx.
  - D-NOCOL: fail immediately if documents.collection_id IS NULL.
  - D-IDX-REUSE: reuse version if SHA-256 checksum matches latest version.
  - D-CHUNK-DEFAULT: chunk_size=1000, overlap=150; overridable via
      rag_collections.metadata->>'chunk_size' / 'chunk_overlap'.
  - D-RETRY: autoretry_for=(IOError, ConnectionError), exp backoff, max 3.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import sqlalchemy as sa
from langchain_text_splitters import RecursiveCharacterTextSplitter
from sqlalchemy.orm import Session

from app.db.models.rag import Document, DocumentChunk, RagCollection, VectorizationJob
from app.worker import app
from app.workers._helpers import (
    _SessionLocal,
    log_after_err,
    log_after_ok,
    log_before,
    mark_failed,
    update_progress,
)
from app.workers._storage import detect_mime, extract_text, get_or_create_version, read_bytes

_LOG = logging.getLogger("hilo.workers.tasks_documents")


@app.task(
    bind=True,
    name="hilo.vectorization.extract_and_chunk",
    autoretry_for=(IOError, ConnectionError),
    retry_backoff=True,
    retry_backoff_max=30,
    max_retries=3,
)
def extract_and_chunk(
    self: Any,
    document_id: str,
    version_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Extract text, create/reuse document version, chunk, persist document_chunks.

    First stage of the vectorization chain. Downloads document bytes, extracts
    text, splits into overlapping chunks, and persists to document_chunks.
    Returns a dict consumed by embed_chunks.

    On IOError/ConnectionError: Celery autoretry fires (exp backoff, max 3).
    On any other exception: status='failed' persisted; returns failure dict.

    Args:
        document_id: UUID string of the document to process.
        version_id:  Optional existing version UUID (ignored if checksum matches).
        request_id:  Optional correlation ID from the HTTP caller.

    Returns:
        dict: {job_id, document_id, version_id, chunks_created, status}.
    """
    rid = request_id or uuid.uuid4().hex
    session: Session = _SessionLocal()
    job_id: uuid.UUID | None = None
    t_start = time.monotonic()

    try:
        # ── Fetch job ────────────────────────────────────────────────────
        job = session.execute(
            sa.select(VectorizationJob)
            .where(VectorizationJob.document_id == uuid.UUID(document_id))
            .order_by(VectorizationJob.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()

        if job is None:
            _LOG.warning("vectorization.start.after.error",
                         extra={"document_id": document_id, "error_type": "JobNotFound",
                                "request_id": rid})
            return {"status": "failed", "error": "JobNotFound", "document_id": document_id}

        job_id = job.id

        # Idempotency: skip if already done (A10)
        if job.status == "done":
            _LOG.info("vectorization.skip.already_done",
                      extra={"job_id": str(job_id), "document_id": document_id})
            return {"job_id": str(job_id), "document_id": document_id,
                    "version_id": version_id, "chunks_created": 0, "status": "done"}

        log_before(_LOG, "start", job_id, document_id, request_id=rid)
        session.execute(
            sa.update(VectorizationJob)
            .where(VectorizationJob.id == job_id)
            .values(status="running", progress=5)
        )
        session.commit()

        # ── Load document ────────────────────────────────────────────────
        doc = session.execute(
            sa.select(Document).where(Document.id == uuid.UUID(document_id))
        ).scalar_one_or_none()

        if doc is None:
            mark_failed(session, job_id, "DocumentNotFound")
            return {"job_id": str(job_id), "status": "failed", "error": "DocumentNotFound"}

        if doc.collection_id is None:
            mark_failed(session, job_id, "NoCollection")
            return {"job_id": str(job_id), "status": "failed", "error": "NoCollection"}

        # ── STAGE: read_storage ──────────────────────────────────────────
        log_before(_LOG, "read_storage", job_id, document_id, source_uri=doc.source_uri)
        t0 = time.monotonic()
        raw_bytes = read_bytes(doc.source_uri)
        log_after_ok(_LOG, "read_storage", job_id,
                     round((time.monotonic() - t0) * 1000, 1), bytes_read=len(raw_bytes))
        update_progress(session, job_id, 10)

        # ── STAGE: extract_text ──────────────────────────────────────────
        try:
            mime = detect_mime(doc.source_uri)
        except ValueError as exc:
            mark_failed(session, job_id, str(exc))
            log_after_err(_LOG, "extract_text", job_id, "UnsupportedMimeType",
                          round((time.monotonic() - t_start) * 1000, 1))
            return {"job_id": str(job_id), "status": "failed", "error": str(exc)}

        log_before(_LOG, "extract_text", job_id, document_id, mime=mime)
        t0 = time.monotonic()
        try:
            text = extract_text(raw_bytes, mime)
        except ValueError as exc:
            mark_failed(session, job_id, str(exc))
            log_after_err(_LOG, "extract_text", job_id, type(exc).__name__,
                          round((time.monotonic() - t0) * 1000, 1))
            return {"job_id": str(job_id), "status": "failed", "error": str(exc)}

        log_after_ok(_LOG, "extract_text", job_id,
                     round((time.monotonic() - t0) * 1000, 1), chars_extracted=len(text))
        update_progress(session, job_id, 25)

        # ── STAGE: version_create ────────────────────────────────────────
        log_before(_LOG, "version_create", job_id, document_id)
        t0 = time.monotonic()
        doc_uuid = uuid.UUID(document_id)
        ver, ver_new = get_or_create_version(session, doc_uuid, raw_bytes, doc.source_uri)
        session.commit()
        resolved_version_id = str(ver.id)
        log_after_ok(_LOG, "version_create", job_id,
                     round((time.monotonic() - t0) * 1000, 1),
                     version=ver.version, version_created=ver_new)

        # ── STAGE: chunk_text ────────────────────────────────────────────
        chunk_size, chunk_overlap = 1000, 150
        coll = session.execute(
            sa.select(RagCollection).where(RagCollection.id == doc.collection_id)
        ).scalar_one_or_none()
        if coll and coll.extra_metadata:
            chunk_size = int(coll.extra_metadata.get("chunk_size", chunk_size))
            chunk_overlap = int(coll.extra_metadata.get("chunk_overlap", chunk_overlap))

        log_before(_LOG, "chunk_text", job_id, document_id,
                   chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        t0 = time.monotonic()
        chunk_texts = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size, chunk_overlap=chunk_overlap
        ).split_text(text)
        log_after_ok(_LOG, "chunk_text", job_id,
                     round((time.monotonic() - t0) * 1000, 1),
                     chunks_created=len(chunk_texts))

        # ── STAGE: chunks_persist ────────────────────────────────────────
        log_before(_LOG, "chunks_persist", job_id, document_id,
                   chunk_count=len(chunk_texts))
        t0 = time.monotonic()
        ver_uuid = ver.id
        chunk_objects = [
            DocumentChunk(
                document_id=doc_uuid,
                version_id=ver_uuid,
                chunk_index=idx,
                content=content,
                extra_metadata={},
            )
            for idx, content in enumerate(chunk_texts)
        ]
        session.add_all(chunk_objects)
        session.commit()
        log_after_ok(_LOG, "chunks_persist", job_id,
                     round((time.monotonic() - t0) * 1000, 1),
                     chunks_persisted=len(chunk_objects))
        update_progress(session, job_id, 50)

        log_after_ok(_LOG, "start", job_id,
                     round((time.monotonic() - t_start) * 1000, 1),
                     chunks_created=len(chunk_objects), version_id=resolved_version_id)

        return {
            "job_id": str(job_id),
            "document_id": document_id,
            "version_id": resolved_version_id,
            "chunks_created": len(chunk_objects),
            "status": "chunked",
        }

    except (IOError, ConnectionError):
        raise  # Celery autoretry handles these

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        if job_id is not None:
            try:
                mark_failed(session, job_id, err_msg)
            except Exception:
                pass
        _LOG.error(
            "vectorization.start.after.error",
            extra={"job_id": str(job_id) if job_id else "unknown",
                   "document_id": document_id, "error_type": type(exc).__name__,
                   "latency_ms": round((time.monotonic() - t_start) * 1000, 1)},
            exc_info=True,
        )
        return {"job_id": str(job_id) if job_id else None, "document_id": document_id,
                "status": "failed", "error": err_msg[:1024]}

    finally:
        session.close()
