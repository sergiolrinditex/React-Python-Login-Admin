"""
Hilo People — RAG cosine-similarity retriever.

Slice:  P02-S04-T001 — RAG retriever + citation smoke
Phase:  P02 Core Features (the motor)
Purpose: Implements the retrieve() use case — cosine-similarity search over
         document_embeddings filtered by document.language, rag_collections.enabled,
         and optionally restricted to specific collection UUIDs.

         This is a READ-ONLY module. It never writes to the DB. The caller
         is responsible for providing a pre-computed query_embedding (length=1536);
         embedding generation is deferred to P02-S04-T002 (llm_gateway).

         Returns a list of RetrievedChunk DTOs ordered by descending similarity
         (closest first), capped at filters.k entries.

Key deps:
  - sqlalchemy==2.0.49 (select, Session)
  - pgvector==0.4.2 (VECTOR, cosine_distance via ORM column method)
  - app.db.models.rag (RagCollection, Document, DocumentChunk, DocumentEmbedding)
  - app.rag.schemas (RetrievedChunk, RetrieverFilters)
  - app.rag.errors (InvalidEmbeddingDimensionError, EXPECTED_EMBEDDING_DIM)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.4#rag
  - task pack P02-S04-T001 §SQL contract, §Architecture sketch
  - P02-S01-T001-pgvector-2026-05-13.md (D1=HNSW, D3=VECTOR all-caps)
  - .claude/rules/01-non-negotiables.md §Logging, §Tests are REAL

Decisions:
  - D-RET1: Retriever returns raw chunk content; label formatting for
    message_citations is the caller's responsibility.
  - R5: marca/country filters NOT implemented — documents schema has no
    brand/country columns in this slice. Future follow-up required.
  - R6: score = 1.0 - cosine_distance. For normalised unit-vectors the
    practical range is [0.0, 1.0]; test asserts 0 <= score <= 1.001.
  - R7: WHERE de.embedding IS NOT NULL — skips chunks with no embedding yet.
  - Uses sync SQLAlchemy Session (matching project pattern from db/session.py).
    Caller acquires the session; retrieve() is stateless w.r.t. sessions.
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.rag import Document, DocumentChunk, DocumentEmbedding, RagCollection
from app.rag.errors import EXPECTED_EMBEDDING_DIM, InvalidEmbeddingDimensionError
from app.rag.schemas import RetrievedChunk, RetrieverFilters

logger = logging.getLogger("hilo.rag.retriever")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


# ---------------------------------------------------------------------------
# Private query builder helpers (each ≤50 LOC)
# ---------------------------------------------------------------------------


def _validate_embedding(query_embedding: Sequence[float]) -> None:
    """Validate that query_embedding has exactly 1536 dimensions.

    Args:
        query_embedding: The embedding vector to validate.

    Raises:
        InvalidEmbeddingDimensionError: If len(query_embedding) != 1536.
    """
    dim = len(query_embedding)
    if dim != EXPECTED_EMBEDDING_DIM:
        raise InvalidEmbeddingDimensionError(actual_dim=dim)


def _build_select(
    query_embedding: Sequence[float],
    filters: RetrieverFilters,
) -> Any:
    """Build the SQLAlchemy SELECT statement for cosine similarity search.

    Uses pgvector.sqlalchemy cosine_distance() which pushes down to the
    <=> operator and is eligible for the HNSW index (vector_cosine_ops).
    score = 1.0 - cosine_distance to convert distance to similarity.

    Args:
        query_embedding: Validated 1536-dim embedding vector.
        filters:         Validated retrieval filters (language, collection_ids, k).

    Returns:
        A SQLAlchemy Select object ready for execution.
    """
    distance = DocumentEmbedding.embedding.cosine_distance(query_embedding)
    score_col = (1.0 - distance).label("score")

    stmt = (
        select(
            DocumentChunk.id.label("chunk_id"),
            DocumentChunk.document_id,
            Document.collection_id,
            Document.language,
            DocumentChunk.chunk_index,
            DocumentChunk.content,
            DocumentChunk.extra_metadata.label("metadata"),
            score_col,
        )
        .join(DocumentChunk, DocumentChunk.id == DocumentEmbedding.chunk_id)
        .join(Document, Document.id == DocumentChunk.document_id)
        .join(RagCollection, RagCollection.id == Document.collection_id)
        .where(Document.language == filters.language)
        .where(RagCollection.enabled.is_(True))
        .where(DocumentEmbedding.embedding.isnot(None))
        .order_by(distance.asc())
        .limit(filters.k)
    )

    if filters.collection_ids:
        stmt = stmt.where(
            Document.collection_id.in_(filters.collection_ids)
        )

    return stmt


def _rows_to_dtos(rows: list[Any]) -> list[RetrievedChunk]:
    """Convert SQLAlchemy Row objects to RetrievedChunk DTOs.

    Args:
        rows: List of SQLAlchemy result rows with named columns.

    Returns:
        List of frozen RetrievedChunk dataclass instances.
    """
    return [
        RetrievedChunk(
            chunk_id=row.chunk_id,
            document_id=row.document_id,
            collection_id=row.collection_id,
            language=row.language,
            score=float(row.score),
            content=row.content,
            chunk_index=row.chunk_index,
            metadata=dict(row.metadata) if row.metadata else {},
        )
        for row in rows
    ]


# ---------------------------------------------------------------------------
# Public retrieve() use case
# ---------------------------------------------------------------------------


def retrieve(
    *,
    session: Session,
    query_embedding: Sequence[float],
    filters: RetrieverFilters,
    request_id: str | None = None,
) -> list[RetrievedChunk]:
    """Cosine-similarity search over document_embeddings.

    Executes a pgvector HNSW cosine search filtered by document.language,
    rag_collections.enabled=true, and (optionally) collection_id membership.
    Returns at most filters.k chunks ordered by descending similarity score.

    This function is READ-ONLY — no INSERT/UPDATE/DELETE is performed.

    Args:
        session:         Active SQLAlchemy sync Session (caller owns lifecycle).
        query_embedding: Pre-computed embedding vector; must have exactly 1536
                         dimensions. Raise InvalidEmbeddingDimensionError otherwise.
        filters:         Validated RetrieverFilters (language, collection_ids, k).
        request_id:      Optional X-Request-ID for structured log correlation.

    Returns:
        List of RetrievedChunk DTOs ordered by score descending (closest first).
        Empty list if no matches, unknown collection, or empty embeddings table.

    Raises:
        InvalidEmbeddingDimensionError: If len(query_embedding) != 1536.
        sqlalchemy.exc.SQLAlchemyError: On DB connectivity / query execution failure.
    """
    rid = request_id or str(uuid.uuid4())

    # BEFORE log — no embedding floats, no chunk content
    if _VERBOSE:
        logger.info(
            "rag.retriever.search.start",
            extra={
                "request_id": rid,
                "language": filters.language,
                "collection_ids_count": len(filters.collection_ids),
                "k": filters.k,
                "embedding_dim": len(query_embedding),
            },
        )

    try:
        _validate_embedding(query_embedding)
        stmt = _build_select(query_embedding, filters)
        t0 = time.monotonic()
        result = session.execute(stmt)
        rows = result.fetchall()
        elapsed_ms = round((time.monotonic() - t0) * 1000, 1)
        chunks = _rows_to_dtos(rows)
    except InvalidEmbeddingDimensionError:
        logger.error(
            "rag.retriever.search.invalid_dim",
            extra={
                "request_id": rid,
                "embedding_dim": len(query_embedding),
                "expected_dim": EXPECTED_EMBEDDING_DIM,
            },
        )
        raise
    except Exception as exc:
        logger.error(
            "rag.retriever.search.error",
            extra={
                "request_id": rid,
                "language": filters.language,
                "error_kind": type(exc).__name__,
            },
            exc_info=True,
        )
        raise

    # AFTER log — result count + timing; no content/scores in non-verbose mode
    if _VERBOSE:
        logger.info(
            "rag.retriever.search.ok",
            extra={
                "request_id": rid,
                "result_count": len(chunks),
                "duration_ms": elapsed_ms,
                "top_score": chunks[0].score if chunks else None,
            },
        )
    else:
        if not chunks:
            logger.debug(
                "rag.retriever.search.empty",
                extra={"request_id": rid, "language": filters.language},
            )

    return chunks
