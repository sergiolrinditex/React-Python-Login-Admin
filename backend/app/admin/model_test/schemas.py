"""
Hilo People — Admin model-test Pydantic schemas.

WRITE_SET_DRIFT §D-MT-SCHEMAS (P02-S05-T002): New file in backend/app/admin/model_test/
subpackage. Not in declared write_set but required for the model_test feature module.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: Pydantic v2 schemas for POST /api/v1/admin/ai/models/{id}/test.
         TestModelRequest validates the request body.
         ModelTestOut defines the success response shape.

Key deps:
  - pydantic v2 (BaseModel, model_config, field_validator)
  - uuid, datetime

Source refs:
  - task pack P02-S05-T002 §D.2.A (request/response contract)
  - 01-non-negotiables.md §API contract (Pydantic v2, input validation)
"""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class TestModelRequest(BaseModel):
    """Request body for POST /api/v1/admin/ai/models/{id}/test.

    Attributes:
        prompt:     Test prompt text (1–4000 chars; whitespace stripped).
        max_tokens: Maximum completion tokens (default 256).
    """

    model_config = {"str_strip_whitespace": True}

    prompt: str = Field(
        ...,
        min_length=1,
        max_length=4000,
        description="Test prompt sent to the model (1–4000 chars, stripped).",
    )
    max_tokens: int = Field(
        default=256,
        ge=1,
        le=4096,
        description="Maximum completion tokens (1–4096).",
    )

    @field_validator("prompt")
    @classmethod
    def prompt_not_blank(cls, v: str) -> str:
        """Reject whitespace-only prompts after stripping.

        Args:
            v: Prompt string (already stripped by model_config).

        Returns:
            Validated prompt string.

        Raises:
            ValueError: If prompt is blank after stripping.
        """
        if not v.strip():
            raise ValueError("Prompt must not be blank.")
        return v


class ModelTestOut(BaseModel):
    """Success response data for POST /api/v1/admin/ai/models/{id}/test.

    Reflects the ai_model_tests row created by the test invocation.

    Attributes:
        id:             UUID of the ai_model_tests row.
        model_id:       UUID of the tested AiModel.
        output:         Assistant response text (None if test failed).
        latency_ms:     Round-trip latency in milliseconds.
        estimated_cost: USD cost estimate (None if provider pricing unknown).
        status:         Test result — 'success' | 'failure' | 'timeout'.
        created_at:     Timestamp of the test row insertion.
    """

    id: uuid.UUID
    model_id: uuid.UUID
    output: str | None
    latency_ms: int | None
    estimated_cost: float | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
