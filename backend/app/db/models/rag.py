"""
Hilo People — SQLAlchemy 2.x ORM models: RAG Admin and vectorization.

Slice:  P02-S01-T001 — 0002_ai_chat_rag_mcp_agents migration
Phase:  P02 Core Features (the motor)
Purpose: Defines ORM models for the RAG (Retrieval-Augmented Generation)
         subsystem: RagCollection, Document, DocumentVersion, DocumentChunk,
         DocumentEmbedding, VectorizationJob.

Bounded context: rag-admin — document ingestion pipeline, chunk management,
pgvector embeddings storage, and asynchronous vectorization job tracking.
Used by the RAG retriever (P02-S04) and admin document upload endpoints (P02-S06).

Mapped tables (all created by migration 0002_ai_chat_rag_mcp_agents.py):
  - rag_collections    (no FK)
  - documents          (FK -> rag_collections ON DELETE SET NULL, FK -> users)
  - document_versions  (FK -> documents ON DELETE CASCADE)
  - document_chunks    (FK -> documents + document_versions ON DELETE CASCADE)
  - document_embeddings (FK -> document_chunks + ai_models; vector(1536) column)
  - vectorization_jobs (FK -> documents ON DELETE CASCADE)

Key deps:
  - app.db.base             — Base (DeclarativeBase with naming_convention)
  - sqlalchemy==2.0.49      (Mapped, mapped_column, JSONB)
  - pgvector==0.4.2         — VECTOR type (ALL CAPS per D3 researcher note)
  - sqlalchemy.dialects.postgresql — UUID, JSONB

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3#rag
  - docs/source-of-truth/instrucciones.md §3.1#rag-admin
  - P02-S01-T001 task pack §C.3, §I.1, §I.4
  - official-doc-notes/P02-S01-T001-pgvector-2026-05-13.md D3

Decisions implemented:
  - D3: import VECTOR (all caps) from pgvector.sqlalchemy per official pgvector 0.4.2 docs.
    The researcher confirmed VECTOR is the correct class name, not Vector.
  - D-IDX: language CHECK applied on documents.language IN ('es','en','fr') to align
    with users.preferred_language and conversations.language constraints.
  - DocumentEmbedding.embedding maps to vector(1536); pgvector HNSW index created
    in migration 0002 (not here in ORM); consistent with migration-first approach.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from pgvector.sqlalchemy import VECTOR  # D3: all-caps per researcher note P02-S01-T001-pgvector-2026-05-13.md
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ---------------------------------------------------------------------------
# RagCollection — top-level grouping of documents
# ---------------------------------------------------------------------------
class RagCollection(Base):
    """ORM model for the `rag_collections` table.

    Groups documents by vertical and optional language for scoped RAG retrieval.
    metadata stores arbitrary collection-level configuration (e.g. chunking
    strategy, embedding model override). The Python attribute is named
    'extra_metadata' to avoid SQLAlchemy's reserved class-level 'metadata'.

    Table: rag_collections
    PK: id UUID (gen_random_uuid())
    No FK constraints (root entity).

    Refs: §10.3#rag, instrucciones.md §3.1#rag-admin
    """

    __tablename__ = "rag_collections"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Human-readable collection name",
    )
    vertical: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Business vertical/domain (e.g. 'legal', 'hr', 'finance')",
    )
    language: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Primary language of documents in collection; NULL = multilingual",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("true"),
        comment="False = collection hidden from retrieval queries",
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="Collection config JSON; DB col: 'metadata' (Python: extra_metadata)",
    )


# ---------------------------------------------------------------------------
# Document — an ingested source document
# ---------------------------------------------------------------------------
class Document(Base):
    """ORM model for the `documents` table.

    Represents a source document uploaded to a RAG collection. Documents are
    versioned (DocumentVersion); embeddings are computed per version (DocumentChunk
    → DocumentEmbedding). language is enforced by CHECK constraint in migration
    (D-IDX: aligned with users.preferred_language and conversations.language).

    status lifecycle: 'uploaded' → 'processing' → 'indexed' | 'failed'.

    Table: documents
    PK: id UUID (gen_random_uuid())
    FK: collection_id -> rag_collections.id ON DELETE SET NULL
    FK: uploaded_by   -> users.id (nullable; no CASCADE — informational)

    Refs: §10.3#rag, instrucciones.md §3.1#rag-admin (solo admins suben documentos)
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    collection_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "rag_collections.id",
            ondelete="SET NULL",
            name="documents_collection_id_fkey",
        ),
        nullable=True,
        comment="FK -> rag_collections.id ON DELETE SET NULL; NULL = orphaned document",
    )
    title: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Document title",
    )
    language: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Document language; CHECK IN ('es','en','fr') enforced in migration 0002 (D-IDX)",
    )
    source_uri: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Storage URI of the original file (e.g. minio://hilo-docs-dev/path.pdf)",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default=sa.text("'uploaded'"),
        comment="Processing status: 'uploaded' | 'processing' | 'indexed' | 'failed'",
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            name="documents_uploaded_by_fkey",
        ),
        nullable=True,
        comment="FK -> users.id (no CASCADE — informational reference to uploader)",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


# ---------------------------------------------------------------------------
# DocumentVersion — immutable snapshot of a document's content
# ---------------------------------------------------------------------------
class DocumentVersion(Base):
    """ORM model for the `document_versions` table.

    Each re-upload or content update creates a new version. Embeddings are
    recomputed per version. checksum enables deduplication detection.

    Table: document_versions
    PK: id UUID (gen_random_uuid())
    FK: document_id -> documents.id ON DELETE CASCADE

    Refs: §10.3#rag, instrucciones.md §3.1#rag-admin (embeddings recalculados por versión)
    """

    __tablename__ = "document_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "documents.id",
            ondelete="CASCADE",
            name="document_versions_document_id_fkey",
        ),
        nullable=False,
        comment="FK -> documents.id ON DELETE CASCADE",
    )
    version: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        comment="Monotonically increasing version number within a document",
    )
    storage_key: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="MinIO object key for this version's raw file",
    )
    checksum: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="SHA-256 checksum of the file content for deduplication",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


# ---------------------------------------------------------------------------
# DocumentChunk — a text segment within a DocumentVersion
# ---------------------------------------------------------------------------
class DocumentChunk(Base):
    """ORM model for the `document_chunks` table.

    A document version is split into fixed-size overlapping text chunks for
    embedding. chunk_index is the 0-based position within the version.
    metadata stores chunking metadata (e.g. page number, section title).

    Table: document_chunks
    PK: id UUID (gen_random_uuid())
    FK: document_id -> documents.id ON DELETE CASCADE
    FK: version_id  -> document_versions.id ON DELETE CASCADE

    Refs: §10.3#rag
    """

    __tablename__ = "document_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "documents.id",
            ondelete="CASCADE",
            name="document_chunks_document_id_fkey",
        ),
        nullable=False,
        comment="FK -> documents.id ON DELETE CASCADE",
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "document_versions.id",
            ondelete="CASCADE",
            name="document_chunks_version_id_fkey",
        ),
        nullable=False,
        comment="FK -> document_versions.id ON DELETE CASCADE",
    )
    chunk_index: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        comment="0-based position of this chunk within the version",
    )
    content: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Raw text content of this chunk",
    )
    extra_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata",
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="Chunk metadata (page, section, etc.); DB col: 'metadata'",
    )


# ---------------------------------------------------------------------------
# DocumentEmbedding — pgvector embedding for a DocumentChunk
# ---------------------------------------------------------------------------
class DocumentEmbedding(Base):
    """ORM model for the `document_embeddings` table.

    Stores the pgvector embedding for a document chunk. chunk_id is both PK
    and FK (1:1 relationship — one embedding per chunk). embedding is a 1536-
    dimensional vector (text-embedding-3-small / ada-002 compatible).

    The VECTOR type is imported from pgvector.sqlalchemy — ALL CAPS per
    official pgvector-python 0.4.2 docs (researcher D3, 2026-05-13).
    The HNSW index on embedding is created by migration 0002 via raw SQL:
      CREATE INDEX document_embeddings_vector_idx ON document_embeddings
        USING hnsw (embedding vector_cosine_ops) WITH (m=16, ef_construction=64);
    This overrides the ivfflat directive in §10.3 (researcher D1, handoff §risks).

    Table: document_embeddings
    PK: chunk_id UUID (FK -> document_chunks ON DELETE CASCADE — 1:1)
    FK: model_id -> ai_models.id ON DELETE SET NULL

    Refs: §10.3#rag, P02-S01-T001 task pack §I.4 (vector ORM mapping)
    """

    __tablename__ = "document_embeddings"

    chunk_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "document_chunks.id",
            ondelete="CASCADE",
            name="document_embeddings_chunk_id_fkey",
        ),
        primary_key=True,
        comment="PK + FK -> document_chunks.id ON DELETE CASCADE (1:1)",
    )
    embedding: Mapped[list[float] | None] = mapped_column(
        VECTOR(1536),
        nullable=True,
        comment=(
            "1536-dim pgvector embedding (text-embedding-3-small compatible). "
            "HNSW index document_embeddings_vector_idx created in migration 0002."
        ),
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "ai_models.id",
            ondelete="SET NULL",
            name="document_embeddings_model_id_fkey",
        ),
        nullable=True,
        comment="FK -> ai_models.id ON DELETE SET NULL (preserve embedding even if model deleted)",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


# ---------------------------------------------------------------------------
# VectorizationJob — async job tracking for document embedding runs
# ---------------------------------------------------------------------------
class VectorizationJob(Base):
    """ORM model for the `vectorization_jobs` table.

    Tracks Celery worker jobs that embed a document's chunks. progress is
    0-100 (percent). error stores the exception message if status='failed'.
    finished_at is set when status transitions to 'done' or 'failed'.

    Table: vectorization_jobs
    PK: id UUID (gen_random_uuid())
    FK: document_id -> documents.id ON DELETE CASCADE

    Refs: §10.3#rag, instrucciones.md §3.1#rag-admin (vectorización en Celery)
    """

    __tablename__ = "vectorization_jobs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "documents.id",
            ondelete="CASCADE",
            name="vectorization_jobs_document_id_fkey",
        ),
        nullable=False,
        comment="FK -> documents.id ON DELETE CASCADE",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Job status: 'pending' | 'running' | 'done' | 'failed'",
    )
    progress: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        server_default=sa.text("0"),
        comment="Completion percentage 0-100",
    )
    error: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Error message if status='failed'; NULL otherwise",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
    finished_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="Timestamp when job completed (success or failure)",
    )
