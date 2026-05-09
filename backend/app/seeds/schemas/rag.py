"""
Pydantic models for the 'rag_docs' and 'rag_chat' namespaces.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Covers:
  - data/verification/rag/collections.json  (rag_chat namespace)
  - data/verification/rag/documents/politica_vacaciones_es.json  (rag_docs namespace)

NOTE: No embeddings or vector data here. Vectorization is P02-S04-T002 territory.
      The rag_docs loader registers document METADATA only.

Dependencies:
  - pydantic 2.12.5
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RagCollectionSeed(BaseModel):
    """Seed record for a RAG document collection.

    Purpose: define the 'politicas_tienda' collection for J101/J104 journeys.
    Params:
      name       — unique collection identifier (natural key for upsert).
      language   — primary content language code.
      vertical   — business vertical label.
      enabled    — whether the collection is queryable.
      description — optional human-readable description.
    Errors: ValidationError if required fields are missing.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(
        ..., min_length=1, max_length=200, description="Collection name (upsert key)."
    )
    language: str = Field(..., min_length=2, max_length=10)
    vertical: str = Field(..., min_length=1, max_length=100)
    enabled: bool = Field(True)
    description: str | None = Field(None, max_length=500)


class RagCollectionListSeed(BaseModel):
    """Wrapper for a list of RAG collection seeds.

    Purpose: top-level shape for data/verification/rag/collections.json.
    """

    model_config = ConfigDict(extra="forbid")

    collections: list[RagCollectionSeed]


class RagDocumentSeed(BaseModel):
    """Seed record for RAG document metadata (no binary, no embeddings).

    Purpose: pre-register the policy document for J104/J101 verification.
    The actual PDF content is a placeholder; vectorization happens in P02-S04-T002.

    Params:
      title       — document title (part of upsert key with language).
      language    — content language code (part of upsert key).
      source_path — placeholder path or URL for the original file.
      mime_type   — MIME type hint.
      checksum_sha256 — synthetic SHA256 (64 hex chars) for idempotency.
      collection_name — references a RagCollectionSeed.name.
    Errors: ValidationError if required fields are missing or checksum is malformed.
    """

    model_config = ConfigDict(extra="forbid")

    title: str = Field(..., min_length=1, max_length=500)
    language: Literal["es", "en", "fr"] = Field("es")
    source_path: str = Field(..., description="Placeholder path until real file is delivered.")
    mime_type: str = Field("application/pdf")
    checksum_sha256: str = Field(..., min_length=64, max_length=64)
    collection_name: str = Field(..., description="Parent collection name.")
    description: str | None = Field(None, max_length=500)
