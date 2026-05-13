"""
Hilo People — RAG retriever typed errors.

Slice:  P02-S04-T001 — RAG retriever + citation smoke
Phase:  P02 Core Features (the motor)
Purpose: Defines domain-level typed errors raised by the RAG retriever.
         Each error signals a distinct failure mode so callers can handle
         them without catching generic Exception.

Errors:
  - InvalidEmbeddingDimensionError: query_embedding length != 1536.
  - InvalidLanguageError: language not in {es, en, fr}.

Key deps:
  - None (leaf module; no external deps)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.4#rag
  - task pack P02-S04-T001 §Data contract (A9, A10)
  - .claude/rules/01-non-negotiables.md §Error handling (typed domain errors)
"""

from __future__ import annotations

EXPECTED_EMBEDDING_DIM = 1536
VALID_LANGUAGES = frozenset({"es", "en", "fr"})


class RagRetrieverError(Exception):
    """Base class for all RAG retriever domain errors.

    Callers should catch specific sub-classes; catch this base class only
    when unified handling of all retriever errors is needed.
    """


class InvalidEmbeddingDimensionError(RagRetrieverError):
    """Raised when query_embedding length is not exactly 1536.

    The embedding dimension is fixed by the model contract (text-embedding-3-small /
    ada-002 compatible). Mismatched dimensions cause pgvector to raise a DB-level
    error; we validate early to provide a clear message with actual vs expected.

    Args:
        actual_dim: The dimension of the supplied embedding vector.

    Example:
        raise InvalidEmbeddingDimensionError(actual_dim=512)
    """

    def __init__(self, actual_dim: int) -> None:
        self.actual_dim = actual_dim
        super().__init__(
            f"query_embedding must have exactly {EXPECTED_EMBEDDING_DIM} dimensions, "
            f"got {actual_dim}"
        )


class InvalidLanguageError(RagRetrieverError):
    """Raised when the requested language is not in the allowed set {es, en, fr}.

    The documents table has a CHECK constraint for language IN ('es','en','fr').
    Pydantic catches this first via Literal["es","en","fr"] in RetrieverFilters;
    this error exists as a fallback for programmatic callers that bypass Pydantic.

    Args:
        language: The invalid language code that was supplied.

    Example:
        raise InvalidLanguageError(language="de")
    """

    def __init__(self, language: str) -> None:
        self.language = language
        super().__init__(
            f"language must be one of {sorted(VALID_LANGUAGES)}, got '{language}'"
        )
