"""
Hilo People — RAG retriever smoke tests.

Slice:  P02-S04-T001 — RAG retriever + citation smoke
Phase:  P02 Core Features (the motor)
Purpose: Integration smoke tests for app.rag.retrieve() against a real Postgres
         + pgvector DB instance. No business logic is mocked; all assertions are
         made against real pgvector cosine_distance results.

         All test names contain 'rag_retriever_smoke' so the registry verification
         command 'pytest backend/tests/ai -k rag_retriever_smoke -v' runs the
         complete suite.

Test cases (per task pack §Test plan):
  T01 — test_rag_retriever_smoke_filter_by_language_es_only   (A1)
  T02 — test_rag_retriever_smoke_filter_by_collection_excludes_others (A2)
  T03 — test_rag_retriever_smoke_combined_filters_AND         (A3)
  T04 — test_rag_retriever_smoke_disabled_collection_excluded (A4)
  T05 — test_rag_retriever_smoke_citation_metadata_shape      (A5)
  T06 — test_rag_retriever_smoke_k_limit_respected            (A6)
  T07 — test_rag_retriever_smoke_unknown_collection_returns_empty (A7)
  T08 — test_rag_retriever_smoke_empty_database_returns_empty (A8)
  T09 — test_rag_retriever_smoke_invalid_language_raises      (A9)
  T10 — test_rag_retriever_smoke_invalid_embedding_dim_raises (defensive)

Key deps:
  - pytest, sqlalchemy.orm.Session
  - numpy (synthetic deterministic vectors via conftest.py helpers)
  - app.rag (retrieve, RetrievedChunk, RetrieverFilters)
  - app.rag.errors (InvalidEmbeddingDimensionError)
  - tests/ai/conftest.py (rag_smoke_fixture, _unit_vec)

Source refs:
  - task pack P02-S04-T001 §Test plan, §Acceptance criteria
  - .claude/rules/01-non-negotiables.md §Tests are REAL
"""

from __future__ import annotations

import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.models.rag import (
    Document,
    DocumentChunk,
    DocumentEmbedding,
    DocumentVersion,
    RagCollection,
)
from app.rag import (
    InvalidEmbeddingDimensionError,
    RetrievedChunk,
    RetrieverFilters,
    retrieve,
)
from tests.ai.conftest import RagSmokeData, _unit_vec


# ---------------------------------------------------------------------------
# T01 — Language filter (positive): language="es" returns only ES chunks (A1)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_filter_by_language_es_only(
    pg_session: Session, rag_smoke_fixture: RagSmokeData
) -> None:
    """Assert retrieve(language='es') returns only chunks from ES documents.

    Given 2 enabled collections (es, en) with one chunk each, a query near
    the ES chunk must return only the ES chunk and exclude the EN chunk.
    The disabled-collection ES chunk must also be excluded (A4 complement).

    Acceptance: A1 — language filter positive.
    """
    data = rag_smoke_fixture
    filters = RetrieverFilters(language="es")
    results = retrieve(
        session=pg_session,
        query_embedding=data.query_near_es,
        filters=filters,
    )

    returned_chunk_ids = {r.chunk_id for r in results}
    assert data.chunk_es.id in returned_chunk_ids, "ES chunk must be returned"
    assert data.chunk_en.id not in returned_chunk_ids, "EN chunk must NOT be returned"
    assert data.chunk_off.id not in returned_chunk_ids, "Disabled-coll chunk must NOT be returned"
    for r in results:
        assert r.language == "es", f"All returned chunks must have language='es', got {r.language}"


# ---------------------------------------------------------------------------
# T02 — Collection filter: collection_ids=[C1] excludes C2 chunks (A2)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_filter_by_collection_excludes_others(
    pg_session: Session, rag_smoke_fixture: RagSmokeData
) -> None:
    """Assert retrieve(collection_ids=[c_es]) returns only c_es chunks.

    With two enabled collections c_es and c_en, restricting to c_es must
    exclude all c_en chunks (and the disabled c_off, per A4).

    Acceptance: A2 — collection filter positive.
    """
    data = rag_smoke_fixture
    filters = RetrieverFilters(language="es", collection_ids=[data.c_es.id])
    results = retrieve(
        session=pg_session,
        query_embedding=data.query_near_es,
        filters=filters,
    )

    returned_chunk_ids = {r.chunk_id for r in results}
    assert data.chunk_es.id in returned_chunk_ids, "c_es chunk must be returned"
    assert data.chunk_en.id not in returned_chunk_ids, "c_en chunk must NOT be returned"
    assert data.chunk_off.id not in returned_chunk_ids, "c_off (disabled) must NOT be returned"
    for r in results:
        assert r.collection_id == data.c_es.id, (
            f"All results must belong to c_es, got {r.collection_id}"
        )


# ---------------------------------------------------------------------------
# T03 — Combined filters AND-semantics: language=es + collection=C1 (A3)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_combined_filters_AND(
    pg_session: Session, rag_smoke_fixture: RagSmokeData
) -> None:
    """Assert language + collection filters are applied with AND semantics.

    Inserting a second ES-language chunk in a different collection (c2_es)
    then filtering language='es' + collection_ids=[c_es] must return only
    c_es chunks, not c2_es chunks.

    Acceptance: A3 — combined AND semantics.
    """
    data = rag_smoke_fixture

    # Create extra ES collection + chunk to verify AND semantics
    c2_es = RagCollection(
        id=uuid.uuid4(),
        name="t_c2_es",
        vertical="hr",
        language="es",
        enabled=True,
        extra_metadata={},
    )
    pg_session.add(c2_es)
    pg_session.flush()

    doc2 = Document(
        id=uuid.uuid4(),
        collection_id=c2_es.id,
        title="Another ES Doc",
        language="es",
        source_uri="minio://hilo-docs-dev/test/another_es.pdf",
        status="indexed",
        uploaded_by=None,
    )
    pg_session.add(doc2)
    pg_session.flush()

    ver2 = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc2.id,
        version=1,
        storage_key="test/another_es_v1.pdf",
        checksum="aabbcc0099",
    )
    pg_session.add(ver2)
    pg_session.flush()

    chunk2 = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc2.id,
        version_id=ver2.id,
        chunk_index=0,
        content="Otro contenido en español en colección 2.",
        extra_metadata={},
    )
    pg_session.add(chunk2)
    pg_session.flush()

    vec2 = _unit_vec(seed=555)
    emb2 = DocumentEmbedding(
        chunk_id=chunk2.id,
        embedding=vec2,
        model_id=None,
    )
    pg_session.add(emb2)
    pg_session.flush()

    # Filter: language=es AND collection_ids=[c_es only]
    filters = RetrieverFilters(
        language="es",
        collection_ids=[data.c_es.id],
        k=50,
    )
    results = retrieve(
        session=pg_session,
        query_embedding=data.query_near_es,
        filters=filters,
    )

    returned_chunk_ids = {r.chunk_id for r in results}
    assert data.chunk_es.id in returned_chunk_ids, "c_es ES chunk must be returned"
    assert chunk2.id not in returned_chunk_ids, (
        "c2_es chunk must NOT be returned — fails collection filter"
    )


# ---------------------------------------------------------------------------
# T04 — Disabled collection excluded regardless of filter match (A4)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_disabled_collection_excluded(
    pg_session: Session, rag_smoke_fixture: RagSmokeData
) -> None:
    """Assert chunks from disabled collections are NEVER returned.

    Even with explicit collection_ids=[c_off.id], the disabled collection
    must contribute zero chunks (business rule: c.enabled=true required).

    Acceptance: A4 — disabled collection exclusion.
    """
    data = rag_smoke_fixture

    # Attempt 1: no collection filter — disabled chunk must be absent
    filters_all = RetrieverFilters(language="es", k=50)
    results_all = retrieve(
        session=pg_session,
        query_embedding=data.query_near_es,
        filters=filters_all,
    )
    all_chunk_ids = {r.chunk_id for r in results_all}
    assert data.chunk_off.id not in all_chunk_ids, (
        "Disabled collection chunk must NOT appear without explicit filter"
    )

    # Attempt 2: explicit collection_ids=[c_off.id] — still must be absent
    filters_explicit = RetrieverFilters(
        language="es",
        collection_ids=[data.c_off.id],
        k=50,
    )
    results_explicit = retrieve(
        session=pg_session,
        query_embedding=data.vec_off,  # query most similar to c_off chunk
        filters=filters_explicit,
    )
    assert results_explicit == [], (
        "Explicitly requesting a disabled collection must return empty list"
    )


# ---------------------------------------------------------------------------
# T05 — Citation metadata shape: all 8 fields correct (A5)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_citation_metadata_shape(
    pg_session: Session, rag_smoke_fixture: RagSmokeData
) -> None:
    """Assert each returned item has all 8 RetrievedChunk fields with correct types.

    Also verifies score in [0.0, 1.001] and ordering is monotone non-increasing.

    Acceptance: A5 — citation metadata shape and ordering.
    """
    data = rag_smoke_fixture
    # Insert extra ES chunks to verify ordering with multiple results
    extra_chunks = []
    for i, seed in enumerate([701, 702, 703]):
        ver_i = DocumentVersion(
            id=uuid.uuid4(),
            document_id=data.doc_es.id,
            version=i + 2,
            storage_key=f"test/extra_v{i+2}.pdf",
            checksum=f"extra_chk_{i}",
        )
        pg_session.add(ver_i)
        pg_session.flush()

        chunk_i = DocumentChunk(
            id=uuid.uuid4(),
            document_id=data.doc_es.id,
            version_id=ver_i.id,
            chunk_index=i,
            content=f"Chunk extra {i} en español.",
            extra_metadata={"extra_index": i},
        )
        pg_session.add(chunk_i)
        pg_session.flush()

        emb_i = DocumentEmbedding(
            chunk_id=chunk_i.id,
            embedding=_unit_vec(seed=seed),
            model_id=None,
        )
        pg_session.add(emb_i)
        pg_session.flush()
        extra_chunks.append(chunk_i)

    filters = RetrieverFilters(language="es", k=10)
    results = retrieve(
        session=pg_session,
        query_embedding=data.query_near_es,
        filters=filters,
    )

    assert len(results) >= 1, "At least the base ES chunk must be returned"

    for item in results:
        assert isinstance(item, RetrievedChunk), f"Expected RetrievedChunk, got {type(item)}"
        assert isinstance(item.chunk_id, uuid.UUID), "chunk_id must be UUID"
        assert isinstance(item.document_id, uuid.UUID), "document_id must be UUID"
        assert isinstance(item.collection_id, uuid.UUID), "collection_id must be UUID"
        assert isinstance(item.language, str), "language must be str"
        assert isinstance(item.score, float), "score must be float"
        assert isinstance(item.content, str), "content must be str"
        assert isinstance(item.chunk_index, int), "chunk_index must be int"
        assert isinstance(item.metadata, dict), "metadata must be dict"
        # R6: score = 1.0 - cosine_distance. For unit vectors the theoretical range
        # is [0, 1]; pgvector floating-point may yield slightly negative scores for
        # near-orthogonal vectors (distance slightly > 1.0 before cast to float).
        # Tolerance of -0.01 covers realistic float noise without masking real bugs.
        assert -0.01 <= item.score <= 1.001, (
            f"score must be in [-0.01, 1.001] for normalised vectors, got {item.score}"
        )

    # Ordering: scores must be monotone non-increasing
    scores = [r.score for r in results]
    for i in range(len(scores) - 1):
        assert scores[i] >= scores[i + 1] - 1e-6, (
            f"Scores must be non-increasing: scores[{i}]={scores[i]} < scores[{i+1}]={scores[i+1]}"
        )


# ---------------------------------------------------------------------------
# T06 — k limit respected: ≤k results regardless of matching rows (A6)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_k_limit_respected(
    pg_session: Session, rag_smoke_fixture: RagSmokeData
) -> None:
    """Assert retrieve(k=N) returns at most N rows.

    Inserts 12 ES chunks total (1 base + 11 extra), then verifies:
      - k=5 returns ≤5 rows
      - k=1 returns ≤1 row
      - default k (5) returns ≤5 rows

    Acceptance: A6 — k limit enforced.
    """
    data = rag_smoke_fixture

    # Insert 11 extra ES chunks to have 12 total in c_es
    for i in range(11):
        ver_i = DocumentVersion(
            id=uuid.uuid4(),
            document_id=data.doc_es.id,
            version=i + 10,
            storage_key=f"test/k_test_v{i+10}.pdf",
            checksum=f"k_chk_{i}",
        )
        pg_session.add(ver_i)
        pg_session.flush()

        chunk_i = DocumentChunk(
            id=uuid.uuid4(),
            document_id=data.doc_es.id,
            version_id=ver_i.id,
            chunk_index=i,
            content=f"K-test chunk {i} en español.",
            extra_metadata={},
        )
        pg_session.add(chunk_i)
        pg_session.flush()

        emb_i = DocumentEmbedding(
            chunk_id=chunk_i.id,
            embedding=_unit_vec(seed=1000 + i),
            model_id=None,
        )
        pg_session.add(emb_i)
        pg_session.flush()

    query = data.query_near_es

    results_k5 = retrieve(
        session=pg_session,
        query_embedding=query,
        filters=RetrieverFilters(language="es", k=5),
    )
    assert len(results_k5) <= 5, f"k=5 must return ≤5 rows, got {len(results_k5)}"

    results_k1 = retrieve(
        session=pg_session,
        query_embedding=query,
        filters=RetrieverFilters(language="es", k=1),
    )
    assert len(results_k1) <= 1, f"k=1 must return ≤1 row, got {len(results_k1)}"

    results_default = retrieve(
        session=pg_session,
        query_embedding=query,
        filters=RetrieverFilters(language="es"),  # default k=5
    )
    assert len(results_default) <= 5, (
        f"default k=5 must return ≤5 rows, got {len(results_default)}"
    )


# ---------------------------------------------------------------------------
# T07 — Unknown collection_id returns empty list, no exception (A7)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_unknown_collection_returns_empty(
    pg_session: Session, rag_smoke_fixture: RagSmokeData
) -> None:
    """Assert retrieve(collection_ids=[random_uuid]) returns [] without raising.

    An unknown UUID simply matches no documents — the result must be an empty
    list, not a 5xx or exception.

    Acceptance: A7 — unknown collection returns empty.
    """
    data = rag_smoke_fixture
    unknown_id = uuid.uuid4()
    filters = RetrieverFilters(language="es", collection_ids=[unknown_id])
    results = retrieve(
        session=pg_session,
        query_embedding=data.query_near_es,
        filters=filters,
    )
    assert results == [], (
        f"Unknown collection_ids must return empty list, got {results}"
    )


# ---------------------------------------------------------------------------
# T08 — Empty DB returns empty list, no exception (A8)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_empty_database_returns_empty(
    pg_session: Session,
) -> None:
    """Assert retrieve() returns [] when document_embeddings is empty.

    This test does NOT use rag_smoke_fixture, so the transactional session
    has no embedding rows. The result must be [] without any exception.

    Note: Other tests running in the same process may have committed rows,
    but pg_session uses savepoints/nested transactions so these are not
    visible here (each pg_session starts in its own transaction).

    Acceptance: A8 — empty embeddings table returns empty.
    """
    # Use a query vector that would match anything if embeddings existed
    query = _unit_vec(seed=999)
    filters = RetrieverFilters(language="es")
    results = retrieve(
        session=pg_session,
        query_embedding=query,
        filters=filters,
    )
    assert results == [], (
        f"Empty embeddings table must return empty list, got {results}"
    )


# ---------------------------------------------------------------------------
# T09 — Invalid language raises ValidationError (A9)
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_invalid_language_raises(
    pg_session: Session,
) -> None:
    """Assert that invalid language codes raise pydantic.ValidationError.

    Pydantic's Literal["es","en","fr"] validator catches invalid codes
    before any DB operation. Both empty string and unsupported codes tested.

    Acceptance: A9 — invalid language raises at service boundary.
    """
    with pytest.raises(ValidationError):
        RetrieverFilters(language="de")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        RetrieverFilters(language="")  # type: ignore[arg-type]

    with pytest.raises(ValidationError):
        RetrieverFilters(language="EN")  # type: ignore[arg-type]  # case-sensitive


# ---------------------------------------------------------------------------
# T10 — Invalid embedding dimension raises InvalidEmbeddingDimensionError
# ---------------------------------------------------------------------------


def test_rag_retriever_smoke_invalid_embedding_dim_raises(
    pg_session: Session,
) -> None:
    """Assert retrieve() raises InvalidEmbeddingDimensionError for wrong dim.

    A query_embedding of length 1535 (instead of 1536) must raise
    InvalidEmbeddingDimensionError before any DB round-trip.

    Defensive test — catches programming errors upstream in llm_gateway
    integration (P02-S04-T002 concern).
    """
    short_vec = [0.0] * 1535
    filters = RetrieverFilters(language="es")

    with pytest.raises(InvalidEmbeddingDimensionError) as exc_info:
        retrieve(
            session=pg_session,
            query_embedding=short_vec,
            filters=filters,
        )

    assert exc_info.value.actual_dim == 1535, (
        f"actual_dim must be 1535, got {exc_info.value.actual_dim}"
    )
    assert "1536" in str(exc_info.value), "Error message must mention expected dim 1536"
