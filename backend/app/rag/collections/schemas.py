"""
Hilo People — Pydantic v2 schemas for RAG collection admin endpoints.

Slice:  P02-S06-T002 — RAG collection endpoints (§D-RAGCOLL-SPLIT)
Phase:  P02 Core Features (the motor)
Purpose: Request/response schemas for GET /collections and PATCH /collections/{id}.
         Follows the {data, meta, errors} envelope contract (TECHNICAL_GUIDE §6.2).

Key deps:
  - pydantic v2 (BaseModel, Field, model_validator)

Source refs:
  - task pack P02-S06-T002 §H (frozen endpoint contracts)
  - TECHNICAL_GUIDE §6.2 envelope contract
  - 01-non-negotiables.md §API contract
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator
from pydantic_core import PydanticCustomError


class CollectionOut(BaseModel):
    """Output schema for a RAG collection row.

    Maps RagCollection ORM columns to JSON-serialisable shape.
    `extra_metadata` Python attr → serialised as `metadata` in JSON output
    to align with the DB column name and TECHNICAL_GUIDE §6.2 contract.

    Attributes:
        id:       Collection UUID.
        name:     Human-readable collection name.
        vertical: Business vertical / domain.
        language: Primary language code (es/en/fr); null = multilingual.
        enabled:  True if collection is active in retrieval queries.
        metadata: Arbitrary collection configuration JSON.
    """

    model_config = {"from_attributes": True, "populate_by_name": True}

    id: uuid.UUID
    name: str
    vertical: str
    language: str | None = None
    enabled: bool
    metadata: dict[str, Any] = Field(alias="extra_metadata", default_factory=dict)


class ResponseMeta(BaseModel):
    """Top-level response meta block (§6.2 envelope).

    Attributes:
        request_id: X-Request-ID correlation string.
    """

    request_id: str | None = None


class CollectionListResponse(BaseModel):
    """Response envelope for GET /api/v1/admin/rag/collections.

    No pagination in V1 (collections are O(10) — §H.1 decision).

    Attributes:
        data: List of collection records ordered by name ASC.
        meta: Request meta with request_id.
    """

    data: list[CollectionOut]
    meta: ResponseMeta


class CollectionPatchIn(BaseModel):
    """Request body for PATCH /api/v1/admin/rag/collections/{id}.

    All fields are optional; at least one must be provided (model_validator).
    `language` must be in whitelist es|en|fr (pattern validator).
    `metadata` and `id` are NOT editable.

    DRIFT §D-RAGCOLL-LANG-IN-PATCH: `language` included despite §6.2 listing
    only {name?,vertical?,enabled?}. Justified by Coverage Registry acceptance
    ("toggles vertical/language settings") and UX_CONTRACT §3.2.

    Attributes:
        name:     New name (1–255 chars); None = no change.
        vertical: New vertical (1–64 chars); None = no change.
        language: New language code (es|en|fr); None = no change.
        enabled:  New enabled bool; None = no change.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    vertical: str | None = Field(None, min_length=1, max_length=64)
    language: str | None = Field(None, pattern=r"^(es|en|fr)$")
    enabled: bool | None = None

    @model_validator(mode="after")
    def at_least_one_field(self) -> "CollectionPatchIn":
        """Reject empty patch body (all fields None).

        Uses pydantic_core.PydanticCustomError instead of plain ValueError so
        Pydantic v2 stores str arguments in ctx (not an Exception instance).
        Plain ValueError would leak an un-serialisable Exception via
        ctx["error"] into Starlette's JSONResponse on the 422 passthrough
        branch in app.main; PydanticCustomError keeps the error envelope
        JSON-serialisable without requiring any change to the global
        validation handler.

        Raises:
            PydanticCustomError: If all four editable fields are None.
        """
        if (
            self.name is None
            and self.vertical is None
            and self.language is None
            and self.enabled is None
        ):
            raise PydanticCustomError(
                "rag_invalid_payload",
                "at_least_one_field_required",
            )
        return self


class CollectionPatchResponse(BaseModel):
    """Response envelope for PATCH /api/v1/admin/rag/collections/{id}.

    Attributes:
        data: Updated collection record.
        meta: Request meta with request_id.
    """

    data: CollectionOut
    meta: ResponseMeta
