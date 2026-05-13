"""
Hilo People — RAG retriever public API.

Slice:  P02-S04-T001 — RAG retriever + citation smoke
Phase:  P02 Core Features (the motor)
Purpose: Re-exports the public surface of the rag module so callers can import
         from 'app.rag' without knowing the internal file layout.

         Public API:
           - retrieve()                  — cosine-similarity search use case
           - RetrievedChunk              — domain DTO (frozen dataclass)
           - RetrieverFilters            — Pydantic input validator
           - InvalidEmbeddingDimensionError  — typed error for bad embedding dim
           - InvalidLanguageError        — typed error for bad language code

Key deps:
  - app.rag.retriever (retrieve function)
  - app.rag.schemas   (RetrievedChunk, RetrieverFilters)
  - app.rag.errors    (typed errors)

Source refs:
  - task pack P02-S04-T001 §Architecture sketch
  - .claude/rules/01-non-negotiables.md §Code architecture (Clean Architecture)
"""

from app.rag.errors import InvalidEmbeddingDimensionError, InvalidLanguageError
from app.rag.retriever import retrieve
from app.rag.schemas import RetrievedChunk, RetrieverFilters

__all__ = [
    "retrieve",
    "RetrievedChunk",
    "RetrieverFilters",
    "InvalidEmbeddingDimensionError",
    "InvalidLanguageError",
]
