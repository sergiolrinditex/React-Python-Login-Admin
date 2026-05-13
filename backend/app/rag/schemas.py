"""
Hilo People — RAG retriever public DTOs and input validation.

Slice:  P02-S04-T001 — RAG retriever + citation smoke
Phase:  P02 Core Features (the motor)
Purpose: Defines the public data shapes for the RAG retrieval API:
           - RetrievedChunk: immutable frozen dataclass returned by retrieve().
           - RetrieverFilters: Pydantic v2 model for validated input.

         RetrievedChunk carries all fields needed for downstream
         message_citations persistence (chunk_id, document_id, score)
         without extra DB hops — per decision D-RET1.

Key deps:
  - pydantic==2.x (BaseModel, Field, Literal)
  - dataclasses (frozen=True for immutability)
  - uuid, typing (Any)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.4#rag
  - task pack P02-S04-T001 §Data contract
  - .claude/rules/01-non-negotiables.md §File size (~200 LOC target)

Decisions:
  - D-RET1: Retriever returns raw chunk content; label formatting for
    message_citations.label is the caller's responsibility (P02-S03-T002).
  - RetrievedChunk is a frozen dataclass (not Pydantic) to keep it a
    lightweight domain DTO with no serialization dependencies. Callers
    that need JSON can use dataclasses.asdict().
  - RetrieverFilters uses Pydantic v2 for early validation and clear
    error messages before any DB operation occurs.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Domain DTO — returned by retrieve(); carry-through for message_citations
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class RetrievedChunk:
    """Immutable domain DTO for a single retrieved document chunk.

    Carries all fields needed by the caller to:
      1. Display context to the LLM (content).
      2. Persist message_citations without extra DB hops (chunk_id,
         document_id, score — per D-RET1).

    score is cosine similarity in [0.0, 1.0] for unit-normalised vectors
    (1.0 = identical vectors). The ordering guarantee is non-increasing
    score across a retrieve() result list.

    Fields:
        chunk_id:     UUID of the document_chunks row.
        document_id:  UUID of the parent document.
        collection_id: UUID of the parent rag_collections row.
        language:     Document language ("es" | "en" | "fr").
        score:        Cosine similarity [0.0, 1.0]; highest = most similar.
        content:      Raw text of the chunk (do NOT log — may contain policy text).
        chunk_index:  0-based position within the document version.
        metadata:     Passthrough of document_chunks.metadata JSONB.
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    collection_id: uuid.UUID
    language: str
    score: float
    content: str
    chunk_index: int
    metadata: dict[str, Any]


# ---------------------------------------------------------------------------
# Input validation — Pydantic model used by retrieve() caller interface
# ---------------------------------------------------------------------------
class RetrieverFilters(BaseModel):
    """Validated input for the RAG retriever.

    Validated by Pydantic v2 before any DB operation. Invalid language raises
    pydantic.ValidationError; invalid k raises pydantic.ValidationError.

    Fields:
        language:        Required document language filter. One of {es, en, fr}.
        collection_ids:  Optional list of collection UUIDs to restrict search.
                         Empty list (default) = no collection filter (all enabled
                         collections contribute results).
        k:               Maximum number of chunks to return (1–50); default=5.

    Source refs:
        - task pack P02-S04-T001 §Data contract
        - instrucciones.md §3.1#rag-admin (language + collection scoping)
    """

    language: Literal["es", "en", "fr"]
    collection_ids: list[uuid.UUID] = Field(
        default_factory=list,
        description="Restrict to specific collection UUIDs. Empty = all enabled collections.",
    )
    k: int = Field(
        default=5,
        ge=1,
        le=50,
        description="Maximum number of chunks returned (1–50).",
    )

    model_config = {"frozen": True}  # Pydantic v2: immutable after creation
