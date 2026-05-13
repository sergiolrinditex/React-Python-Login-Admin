"""
Hilo People — Admin AI model catalog Pydantic schemas.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Pydantic v2 request/response models for /api/v1/admin/ai/models.
         The model_type list is intentionally loose (str) to accept any of
         chat/embeddings/other types declared in the DB without forcing a
         schema migration when a new category is added.

Key deps:
  - pydantic v2 (BaseModel)

Source refs:
  - task pack P02-S05-T001 §Front→Back→DB contract (GET, PATCH /models)
  - instrucciones.md §3.1#admin-ai (D-DEF1 invariant)

Decisions:
  - D-PATCH1: UpdateModelRequest has both fields Optional; the handler
    rejects "both None" with 400 AI_MODEL_PAYLOAD_INVALID (not Pydantic
    422, because the source-of-truth contract is field-level semantics).
"""

from __future__ import annotations

import uuid
from typing import Any

from pydantic import BaseModel


class ModelOut(BaseModel):
    """Response schema for a single AI model.

    Attributes:
        id:             Model UUID.
        provider_id:    Parent provider UUID.
        model_id:       Provider-specific model identifier (e.g. 'gpt-4o').
        model_type:     Category: 'chat' | 'embeddings' | other.
        capabilities:   List of capability tags.
        enabled:        True if available to users.
        is_default:     True if this is the default for its model_type.
        pricing:        Pricing metadata dict.
        latency_ms_avg: Average observed latency in ms (null until monitored).
    """

    id: uuid.UUID
    provider_id: uuid.UUID
    model_id: str
    model_type: str
    capabilities: list[Any]
    enabled: bool
    is_default: bool
    pricing: dict[str, Any]
    latency_ms_avg: int | None

    model_config = {"from_attributes": True}


class UpdateModelRequest(BaseModel):
    """Request body for PATCH /api/v1/admin/ai/models/{model_id}.

    At least one field must be non-None (enforced in handler, not Pydantic,
    to return 400 AI_MODEL_PAYLOAD_INVALID per task pack §D-PATCH1).

    Attributes:
        enabled:    New enabled state (optional).
        is_default: New is_default state (optional).
    """

    enabled: bool | None = None
    is_default: bool | None = None
