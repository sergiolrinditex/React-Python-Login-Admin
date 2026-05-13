"""
Hilo People — Celery task: embed chunks and persist to pgvector.

Slice:  P02-S04-T002 — Celery vectorization worker
Phase:  P02 Core Features (the motor)
Purpose: Implements the `embed_chunks` Celery task, which:
           1. Receives the chained dict from extract_and_chunk.
           2. Resolves the default embeddings model from ai_models.
           3. Fetches all document_chunks for (document_id, version_id).
           4. Calls LiteLLM proxy POST /embeddings in batches of 32.
           5. Validates that each embedding vector is exactly 1536-dimensional.
           6. Persists document_embeddings rows (chunk_id, embedding, model_id).
           7. Updates vectorization_jobs.progress from 50→100, status='done'.

         On unrecoverable failure: persists status='failed', error=<msg>.
         On httpx.HTTPError: Celery autoretry fires (exp backoff, max 3).

Key deps:
  - celery==5.6.3       (app.task, bind=True, autoretry_for)
  - httpx==0.28.1       (POST to LiteLLM /embeddings — D-LLM-DIRECT)
  - sqlalchemy==2.0.49  (sync Session for all DB ops)
  - pgvector==0.4.2     (VECTOR type; binding via pgvector.sqlalchemy)
  - app.workers._helpers (shared session factory, logging, DB helpers)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.4#rag-ingestion
  - task pack P02-S04-T002 §2.1 A4-A5 A7-A8 A13-A15, §3.5-3.6, §7, §9

Decisions:
  - D-LLM-DIRECT: httpx direct call; no app/llm_gateway/ yet (P02-S05-T002).
  - D-DIM: reject batch if any embedding dim ≠ 1536 (A15).
  - D-BATCH: embed in batches of 32.
  - D-RETRY: autoretry_for=(httpx.HTTPError,), exp backoff, max_retries=3.
  - SECURITY: LITELLM_MASTER_KEY NEVER logged.
"""

from __future__ import annotations

import logging
import math
import os
import time
import uuid
from typing import Any

import httpx
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.admin_ai import AiModel
from app.db.models.rag import DocumentChunk, DocumentEmbedding, VectorizationJob
from app.worker import app
from app.workers._helpers import (
    _SessionLocal,
    log_after_err,
    log_after_ok,
    log_before,
    mark_done,
    mark_failed,
    update_progress,
)

_LOG = logging.getLogger("hilo.workers.tasks_embeddings")

# LiteLLM client config (D-LLM-DIRECT). SECURITY: _LITELLM_KEY never logged.
_LITELLM_URL: str = os.getenv("LITELLM_BASE_URL", "http://litellm:4000")
_LITELLM_KEY: str = os.getenv("LITELLM_MASTER_KEY", "")

_EXPECTED_DIM = 1536
_EMBED_BATCH_SIZE = 32


# ---------------------------------------------------------------------------
# LiteLLM embeddings client
# ---------------------------------------------------------------------------


def call_embeddings(model_id_string: str, inputs: list[str]) -> list[list[float]]:
    """POST to LiteLLM /embeddings; return list of 1536-d vectors (D-LLM-DIRECT).

    SECURITY: Authorization header value is never included in any log.

    Args:
        model_id_string: LiteLLM model string (e.g. 'openai/text-embedding-3-small').
        inputs:          Batch of text strings to embed.

    Returns:
        List of embedding vectors ordered by input position.

    Raises:
        httpx.HTTPError: On non-2xx response (triggers Celery autoretry).
        ValueError:      On unexpected response shape.
    """
    resp = httpx.post(
        f"{_LITELLM_URL.rstrip('/')}/embeddings",
        headers={"Authorization": f"Bearer {_LITELLM_KEY}"},
        json={"model": model_id_string, "input": inputs},
        timeout=httpx.Timeout(60.0, connect=10.0),
    )
    resp.raise_for_status()
    body = resp.json()
    if "data" not in body or not isinstance(body["data"], list):
        raise ValueError(f"LiteLLM response missing 'data' list: {list(body.keys())}")
    items = sorted(body["data"], key=lambda x: x.get("index", 0))
    return [item["embedding"] for item in items]


# ---------------------------------------------------------------------------
# Celery task
# ---------------------------------------------------------------------------


@app.task(
    bind=True,
    name="hilo.vectorization.embed_chunks",
    autoretry_for=(httpx.HTTPError,),
    retry_backoff=True,
    retry_backoff_max=30,
    max_retries=3,
)
def embed_chunks(
    self: Any,
    prev: dict | None = None,
    document_id: str | None = None,
    version_id: str | None = None,
    request_id: str | None = None,
) -> dict:
    """Read document_chunks, call LiteLLM /embeddings, persist document_embeddings.

    When called via Celery chain, `prev` is the dict returned by extract_and_chunk.
    document_id and version_id may also be passed directly for standalone invocation.

    On httpx.HTTPError: Celery autoretry fires (exp backoff, max 3).
    On any other exception: status='failed' persisted; returns failure dict.

    Args:
        prev:        Chained input dict from extract_and_chunk (may be None).
        document_id: Document UUID string (overrides prev if provided).
        version_id:  Version UUID string (overrides prev if provided).
        request_id:  Optional correlation ID.

    Returns:
        dict: {job_id, document_id, version_id, embeddings_created, status}.
    """
    if prev is not None:
        document_id = document_id or prev.get("document_id")
        version_id = version_id or prev.get("version_id")
        job_id_str = prev.get("job_id")
        if prev.get("status") == "failed":
            return prev  # propagate upstream failure
    else:
        job_id_str = None

    rid = request_id or uuid.uuid4().hex
    session: Session = _SessionLocal()
    t_start = time.monotonic()
    job_id: uuid.UUID | None = None

    try:
        # ── Resolve job ──────────────────────────────────────────────────
        if job_id_str:
            try:
                job_id = uuid.UUID(job_id_str)
            except ValueError:
                job_id = None

        if job_id is None and document_id:
            row = session.execute(
                sa.select(VectorizationJob)
                .where(VectorizationJob.document_id == uuid.UUID(document_id))
                .order_by(VectorizationJob.created_at.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row:
                job_id = row.id

        if job_id is None:
            return {"status": "failed", "error": "JobNotFound", "document_id": document_id}

        # ── STAGE: model_resolve ─────────────────────────────────────────
        log_before(_LOG, "model_resolve", job_id, document_id, request_id=rid)
        t0 = time.monotonic()
        ai_model = session.execute(
            sa.select(AiModel)
            .where(AiModel.model_type == "embeddings")
            .where(AiModel.enabled.is_(True))
            .where(AiModel.is_default.is_(True))
            .limit(1)
        ).scalar_one_or_none()

        if ai_model is None:
            mark_failed(session, job_id, "NoDefaultEmbeddingsModel")
            log_after_err(_LOG, "model_resolve", job_id, "NoDefaultEmbeddingsModel",
                          round((time.monotonic() - t0) * 1000, 1))
            return {"job_id": str(job_id), "status": "failed",
                    "error": "NoDefaultEmbeddingsModel"}

        log_after_ok(_LOG, "model_resolve", job_id,
                     round((time.monotonic() - t0) * 1000, 1),
                     model_type=ai_model.model_type)

        # ── STAGE: fetch chunks ──────────────────────────────────────────
        log_before(_LOG, "embed_batch", job_id, document_id, version_id=version_id)
        chunks = session.execute(
            sa.select(DocumentChunk)
            .where(DocumentChunk.document_id == uuid.UUID(document_id))
            .where(DocumentChunk.version_id == uuid.UUID(version_id))
            .order_by(DocumentChunk.chunk_index)
        ).scalars().all()

        total = len(chunks)
        if total == 0:
            mark_done(session, job_id)
            return {"job_id": str(job_id), "document_id": document_id,
                    "version_id": version_id, "embeddings_created": 0, "status": "done"}

        # ── STAGE: embed_batch (batches of 32) ───────────────────────────
        embeddings_created = 0
        num_batches = math.ceil(total / _EMBED_BATCH_SIZE)

        for batch_idx in range(num_batches):
            start_i = batch_idx * _EMBED_BATCH_SIZE
            batch = chunks[start_i: start_i + _EMBED_BATCH_SIZE]

            t0 = time.monotonic()
            log_before(_LOG, "embed_batch", job_id, document_id,
                       batch_idx=batch_idx, batch_size=len(batch))

            try:
                vectors = call_embeddings(ai_model.model_id,
                                          [c.content for c in batch])
            except httpx.HTTPStatusError as exc:
                status_code = exc.response.status_code
                err = "LiteLLMAuth" if status_code in (401, 403) else f"LiteLLM5xx:{status_code}"
                mark_failed(session, job_id, err)
                log_after_err(_LOG, "embed_batch", job_id, err,
                              round((time.monotonic() - t0) * 1000, 1))
                raise  # httpx.HTTPStatusError is a subclass of httpx.HTTPError → autoretry

            latency_ms = round((time.monotonic() - t0) * 1000, 1)

            # Validate embedding dimensions (D-DIM, A15)
            for vec in vectors:
                if len(vec) != _EXPECTED_DIM:
                    err = f"EmbeddingDimMismatch: got={len(vec)} expected={_EXPECTED_DIM}"
                    mark_failed(session, job_id, err)
                    log_after_err(_LOG, "embed_batch", job_id, "EmbeddingDimMismatch",
                                  latency_ms)
                    return {"job_id": str(job_id), "status": "failed", "error": err}

            # Persist batch in its own transaction (A9)
            try:
                session.add_all([
                    DocumentEmbedding(chunk_id=chunk.id, embedding=vec, model_id=ai_model.id)
                    for chunk, vec in zip(batch, vectors)
                ])
                session.commit()
            except Exception as exc:
                session.rollback()
                err = f"{type(exc).__name__}: {exc}"
                mark_failed(session, job_id, err)
                log_after_err(_LOG, "embeddings_persist", job_id, type(exc).__name__,
                              latency_ms)
                return {"job_id": str(job_id), "status": "failed", "error": err[:1024]}

            embeddings_created += len(batch)
            progress = max(50, min(99, 50 + int(50 * embeddings_created / total)))
            update_progress(session, job_id, progress)
            log_after_ok(_LOG, "embed_batch", job_id, latency_ms,
                         batch_idx=batch_idx, embeddings_in_batch=len(batch))

        # ── STAGE: finalize ──────────────────────────────────────────────
        log_before(_LOG, "finalize", job_id, document_id,
                   embeddings_created=embeddings_created)
        mark_done(session, job_id)
        log_after_ok(_LOG, "finalize", job_id,
                     round((time.monotonic() - t_start) * 1000, 1),
                     embeddings_created=embeddings_created)

        return {"job_id": str(job_id), "document_id": document_id,
                "version_id": version_id, "embeddings_created": embeddings_created,
                "status": "done"}

    except httpx.HTTPError:
        raise  # Celery autoretry

    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        if job_id is not None:
            try:
                mark_failed(session, job_id, err_msg)
            except Exception:
                pass
        _LOG.error(
            "vectorization.embed_chunks.after.error",
            extra={"job_id": str(job_id) if job_id else "unknown",
                   "document_id": document_id, "error_type": type(exc).__name__,
                   "latency_ms": round((time.monotonic() - t_start) * 1000, 1)},
            exc_info=True,
        )
        return {"job_id": str(job_id) if job_id else None, "document_id": document_id,
                "status": "failed", "error": err_msg[:1024]}

    finally:
        session.close()
