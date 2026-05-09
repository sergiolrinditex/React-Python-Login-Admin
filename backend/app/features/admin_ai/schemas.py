"""
Pydantic schemas for admin_ai feature — discover-models endpoint.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Schemas defined here:
  - AiModelOut        — single model row in the response (maps AiModel ORM row)
  - SkippedModel      — model that was seen but not upserted (with reason)
  - DiscoverModelsData — inner data object for the discover-models response
  - DiscoverModelsResponse — §6.2 envelope: { data: DiscoverModelsData }

Envelope convention (TECHNICAL_GUIDE §6.2):
  Consistent envelope: `{data, meta?, errors?}`.
  The discover-models response only contains `data` (no pagination meta needed).

Dependencies:
  - pydantic 2.12.5

Note: no logging here — pure Pydantic schema module.
Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §6.2 + task-pack P00-S02-T006 §5 (schemas plan)
"""
from __future__ import annotations

import uuid
from typing import Literal

from pydantic import BaseModel, Field


class AiModelOut(BaseModel):
    """Response schema for a single AI model row.

    Maps directly to the AiModel ORM row. Used in both `added` and `existing`
    lists of the DiscoverModelsData response so the caller gets a consistent shape
    regardless of whether the model was just inserted or already existed.

    Fields match TECHNICAL_GUIDE §10.3 ai_models columns (+ auto_discovered D1).
    """

    id: uuid.UUID = Field(description="Primary key of the ai_models row.")
    provider_id: uuid.UUID = Field(description="FK to ai_providers.")
    model_id: str = Field(description="Provider-scoped model identifier.")
    model_type: str = Field(description="'chat' | 'embedding' | 'unknown'.")
    capabilities: list = Field(description="JSONB capability array.")
    enabled: bool = Field(description="Whether the model is enabled for use.")
    is_default: bool = Field(description="Whether this is the default model.")
    auto_discovered: bool = Field(
        description="True when inserted by the discover-models endpoint."
    )

    model_config = {"from_attributes": True}


class SkippedModel(BaseModel):
    """A model seen from the provider but not inserted (with reason).

    Used in the `skipped` list of DiscoverModelsData. Reasons include
    unsupported model types, parse errors in the provider response, etc.

    Fields:
      model_id — the raw model identifier from the provider response.
      reason   — human-readable why it was skipped (not a user-facing error).
    """

    model_id: str = Field(description="Raw model identifier from the provider.")
    reason: Literal[
        "unsupported_model_type",
        "parse_error",
        "empty_model_id",
    ] = Field(description="Why this model was not upserted.")


class DiscoverModelsData(BaseModel):
    """Inner data object for the discover-models response (§6.2 envelope).

    Fields:
      added       — newly inserted rows (auto_discovered=True).
      existing    — rows that already existed (left unchanged).
      skipped     — models seen but not inserted.
      total_seen  — len(added) + len(existing) + len(skipped).
    """

    added: list[AiModelOut] = Field(
        default_factory=list,
        description="Models inserted in this call (auto_discovered=True).",
    )
    existing: list[AiModelOut] = Field(
        default_factory=list,
        description="Models that already existed in the catalog (unchanged).",
    )
    skipped: list[SkippedModel] = Field(
        default_factory=list,
        description="Models seen from provider but not inserted (with reason).",
    )
    total_seen: int = Field(
        description="Total models returned by the provider (added + existing + skipped)."
    )


class DiscoverModelsResponse(BaseModel):
    """§6.2 envelope for POST /providers/{provider_id}/discover-models.

    Shape: { data: DiscoverModelsData }

    Per TECHNICAL_GUIDE §6.2 consistent envelope convention:
    'Consistent envelope: {data, meta, errors}'. Only `data` is included here
    (no pagination meta needed for a reconciliation diff endpoint).
    """

    data: DiscoverModelsData
