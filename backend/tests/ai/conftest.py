"""
Hilo People — pytest fixtures for RAG retriever smoke tests.

Slice:  P02-S04-T001 — RAG retriever + citation smoke
Phase:  P02 Core Features (the motor)
Purpose: Provides the rag_smoke_fixture that creates synthetic test data
         (collections, documents, versions, chunks, embeddings) directly in
         the real test Postgres DB using deterministic 1536-dim vectors.

         These vectors are constructed with numpy so cosine distances are
         provable in test assertions without any LiteLLM / embedding model call.
         This satisfies 'real DB, real pgvector ops, no business logic mocks'
         per .claude/rules/01-non-negotiables.md §Tests are REAL.

         The fixture is function-scoped and uses the pg_session transactional
         rollback strategy from backend/tests/conftest.py — all inserted rows
         disappear on rollback; no teardown DELETE needed.

Key deps:
  - pytest, sqlalchemy.orm.Session
  - numpy (synthetic deterministic 1536-dim vectors)
  - app.db.models.rag (ORM models)
  - backend/tests/conftest.py (pg_session)

Source refs:
  - task pack P02-S04-T001 §Test plan (test data setup section)
  - .claude/rules/01-non-negotiables.md §Tests are REAL

WRITE_SET_DRIFT: This file and tests/ai/__init__.py are outside the declared
  write_set (backend/tests/ai/test_rag_retriever.py only). They are intra-test
  helpers required for test discovery and fixture isolation — same drift pattern
  approved for T002/T004/T007. Declared in handoff P02-S04-T001.md.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Generator

import numpy as np
import pytest
from sqlalchemy.orm import Session

from app.db.models.rag import (
    Document,
    DocumentChunk,
    DocumentEmbedding,
    DocumentVersion,
    RagCollection,
)


# ---------------------------------------------------------------------------
# Helpers for deterministic synthetic embedding vectors
# ---------------------------------------------------------------------------


def _unit_vec(seed: int) -> list[float]:
    """Create a deterministic unit-normalised 1536-dim vector from a seed.

    Args:
        seed: Integer seed for numpy RNG.

    Returns:
        List of 1536 floats representing a unit-normalised embedding vector.
    """
    rng = np.random.default_rng(seed)
    v = rng.standard_normal(1536).astype(np.float32)
    v = v / np.linalg.norm(v)
    return v.tolist()


def _make_query_like(vec: list[float], noise: float = 0.01) -> list[float]:
    """Create a query vector close to vec (high cosine similarity).

    Adds small Gaussian noise then renormalises, so the result is
    similar to vec with cosine similarity < 1.0 but close.

    Args:
        vec:   Base 1536-dim unit vector.
        noise: Standard deviation of additive noise.

    Returns:
        Normalised list of 1536 floats similar to vec.
    """
    arr = np.array(vec, dtype=np.float32)
    arr = arr + np.random.default_rng(42).standard_normal(1536).astype(np.float32) * noise
    arr = arr / np.linalg.norm(arr)
    return arr.tolist()


# ---------------------------------------------------------------------------
# Smoke fixture result container
# ---------------------------------------------------------------------------


@dataclass
class RagSmokeData:
    """Container for all entities created by rag_smoke_fixture.

    Fields named to mirror acceptance criteria labels (A1–A9).

    Attributes:
        c_es:         Enabled collection with language="es".
        c_en:         Enabled collection with language="en".
        c_off:        Disabled collection (enabled=False, language="es").
        doc_es:       Document in c_es with language="es".
        doc_en:       Document in c_en with language="en".
        doc_es_c_off: Document in c_off with language="es".
        chunk_es:     DocumentChunk for doc_es (embedding=vec_es).
        chunk_en:     DocumentChunk for doc_en (embedding=vec_en).
        chunk_off:    DocumentChunk for doc_es_c_off (embedding=vec_off).
        vec_es:       1536-dim unit vector for the ES chunk.
        vec_en:       1536-dim unit vector for the EN chunk.
        vec_off:      1536-dim unit vector for the disabled-collection chunk.
        query_near_es: Query vector highly similar to vec_es.
    """

    c_es: RagCollection
    c_en: RagCollection
    c_off: RagCollection
    doc_es: Document
    doc_en: Document
    doc_es_c_off: Document
    chunk_es: DocumentChunk
    chunk_en: DocumentChunk
    chunk_off: DocumentChunk
    vec_es: list[float]
    vec_en: list[float]
    vec_off: list[float]
    query_near_es: list[float]


# ---------------------------------------------------------------------------
# Core smoke fixture — function-scoped; rolls back via pg_session
# ---------------------------------------------------------------------------


@pytest.fixture()
def rag_smoke_fixture(pg_session: Session) -> Generator[RagSmokeData, None, None]:
    """Insert synthetic RAG entities and yield RagSmokeData.

    Creates:
      - 3 collections: c_es (enabled), c_en (enabled), c_off (disabled)
      - 3 documents: one per collection
      - 3 document_versions (one per document)
      - 3 document_chunks (one per version)
      - 3 document_embeddings with deterministic unit vectors

    All rows are rolled back by the transactional pg_session fixture after
    the test ends — no explicit teardown needed.

    Args:
        pg_session: Transactional SQLAlchemy Session from conftest.py.

    Yields:
        RagSmokeData with references to all created entities + vectors.
    """
    # --- Collections ---
    c_es = RagCollection(
        id=uuid.uuid4(),
        name="t_es_coll",
        vertical="hr",
        language="es",
        enabled=True,
        extra_metadata={},
    )
    c_en = RagCollection(
        id=uuid.uuid4(),
        name="t_en_coll",
        vertical="hr",
        language="en",
        enabled=True,
        extra_metadata={},
    )
    c_off = RagCollection(
        id=uuid.uuid4(),
        name="t_off_coll",
        vertical="hr",
        language="es",
        enabled=False,
        extra_metadata={},
    )
    pg_session.add_all([c_es, c_en, c_off])
    pg_session.flush()

    # --- Documents ---
    doc_es = Document(
        id=uuid.uuid4(),
        collection_id=c_es.id,
        title="Política de Vacaciones ES",
        language="es",
        source_uri="minio://hilo-docs-dev/test/politica_vacaciones_es.pdf",
        status="indexed",
        uploaded_by=None,
    )
    doc_en = Document(
        id=uuid.uuid4(),
        collection_id=c_en.id,
        title="Holiday Policy EN",
        language="en",
        source_uri="minio://hilo-docs-dev/test/holiday_policy_en.pdf",
        status="indexed",
        uploaded_by=None,
    )
    doc_es_c_off = Document(
        id=uuid.uuid4(),
        collection_id=c_off.id,
        title="Doc in Disabled Collection",
        language="es",
        source_uri="minio://hilo-docs-dev/test/disabled_doc.pdf",
        status="indexed",
        uploaded_by=None,
    )
    pg_session.add_all([doc_es, doc_en, doc_es_c_off])
    pg_session.flush()

    # --- Versions ---
    ver_es = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_es.id,
        version=1,
        storage_key="test/politica_vacaciones_es_v1.pdf",
        checksum="aabbcc0001",
    )
    ver_en = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_en.id,
        version=1,
        storage_key="test/holiday_policy_en_v1.pdf",
        checksum="aabbcc0002",
    )
    ver_off = DocumentVersion(
        id=uuid.uuid4(),
        document_id=doc_es_c_off.id,
        version=1,
        storage_key="test/disabled_doc_v1.pdf",
        checksum="aabbcc0003",
    )
    pg_session.add_all([ver_es, ver_en, ver_off])
    pg_session.flush()

    # --- Chunks ---
    chunk_es = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_es.id,
        version_id=ver_es.id,
        chunk_index=0,
        content="Contenido de prueba sobre vacaciones en español.",
        extra_metadata={"page": 1, "section": "intro"},
    )
    chunk_en = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_en.id,
        version_id=ver_en.id,
        chunk_index=0,
        content="Test content about holidays in English.",
        extra_metadata={"page": 1, "section": "intro"},
    )
    chunk_off = DocumentChunk(
        id=uuid.uuid4(),
        document_id=doc_es_c_off.id,
        version_id=ver_off.id,
        chunk_index=0,
        content="Contenido de colección desactivada.",
        extra_metadata={"page": 1},
    )
    pg_session.add_all([chunk_es, chunk_en, chunk_off])
    pg_session.flush()

    # --- Embeddings (deterministic unit vectors, no LiteLLM call) ---
    vec_es = _unit_vec(seed=101)
    vec_en = _unit_vec(seed=202)
    vec_off = _unit_vec(seed=303)

    emb_es = DocumentEmbedding(
        chunk_id=chunk_es.id,
        embedding=vec_es,
        model_id=None,
    )
    emb_en = DocumentEmbedding(
        chunk_id=chunk_en.id,
        embedding=vec_en,
        model_id=None,
    )
    emb_off = DocumentEmbedding(
        chunk_id=chunk_off.id,
        embedding=vec_off,
        model_id=None,
    )
    pg_session.add_all([emb_es, emb_en, emb_off])
    pg_session.flush()

    query_near_es = _make_query_like(vec_es)

    yield RagSmokeData(
        c_es=c_es,
        c_en=c_en,
        c_off=c_off,
        doc_es=doc_es,
        doc_en=doc_en,
        doc_es_c_off=doc_es_c_off,
        chunk_es=chunk_es,
        chunk_en=chunk_en,
        chunk_off=chunk_off,
        vec_es=vec_es,
        vec_en=vec_en,
        vec_off=vec_off,
        query_near_es=query_near_es,
    )
