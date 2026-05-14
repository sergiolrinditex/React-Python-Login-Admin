"""
Hilo People — Typed domain errors for RAG collection admin endpoints.

Slice:  P02-S06-T002 — RAG collection endpoints (§D-RAGCOLL-SPLIT)
Phase:  P02 Core Features (the motor)
Purpose: Defines all typed exceptions raised by the RAG collection update flow.
         Callers catch typed errors and map them to HTTP error envelopes.
         This module has NO external dependencies (importable from domain layer).

Key deps: none (domain layer — no FastAPI, no DB)

Source refs:
  - task pack P02-S06-T002 §I.2 (§D-RAGCOLL-SPLIT)
  - 01-non-negotiables.md §Error handling (typed domain errors, never catch generic)
"""

from __future__ import annotations

import uuid


class CollectionNotFoundError(Exception):
    """Raised when the requested collection UUID is not in rag_collections.

    Attributes:
        collection_id: The UUID that was not found.
    """

    def __init__(self, collection_id: uuid.UUID) -> None:
        self.collection_id = collection_id
        super().__init__(f"Collection {collection_id} not found.")


class CollectionInvalidError(Exception):
    """Raised for field-level validation failures in the service layer.

    Attributes:
        field:  The offending field name (e.g. 'name', 'vertical', 'body').
        reason: Human-readable explanation.
    """

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"Invalid collection field '{field}': {reason}")
