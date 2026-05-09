"""
Pydantic models for the 'admin_ai' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Covers:
  - data/verification/admin_ai/providers.json
  - data/verification/admin_ai/models.json

SECURITY: all credential strings MUST be prefixed 'synthetic-'.
  The loader validates this at schema parse time (defense-in-depth).
  When P02-S02-T001 adds encryption-at-rest, this loader will need a
  follow-up to encrypt-on-write; see docstring in the admin_ai loader.

Dependencies:
  - pydantic 2.12.5
"""
from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field, field_validator

# Regex patterns that match real provider API keys.
# A credential matching any of these is REJECTED — real keys cannot live
# in the synthetic bundle (defense-in-depth per task pack §Security).
_REAL_KEY_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^sk-[A-Za-z0-9]{20,}$"),        # OpenAI-style keys
    re.compile(r"^sk-ant-[A-Za-z0-9\-]{30,}$"),  # Anthropic-style keys
    re.compile(r"^AIza[A-Za-z0-9\-_]{35,}$"),    # Google AI keys
    re.compile(r"^Bearer [A-Za-z0-9\-_]{40,}$"), # Bearer tokens
]


def _is_real_key(value: str) -> bool:
    """Return True if the value looks like a real provider API key."""
    return any(pattern.match(value) for pattern in _REAL_KEY_PATTERNS)


def _require_synthetic_prefix(field_name: str, value: str) -> str:
    """Validate that a credential value starts with 'synthetic-'.

    Purpose: reject real credentials copy-pasted into the synthetic bundle.
    Params:
      field_name — field label for error messages.
      value      — credential string to validate.
    Returns: value if valid.
    Errors: ValueError if value does not start with 'synthetic-' or matches a real key pattern.
    """
    if not value.startswith("synthetic-"):
        raise ValueError(
            f"Field '{field_name}' must start with 'synthetic-' in the verification bundle. "
            f"Got: {value[:12]}... — real credentials are not allowed here."
        )
    if _is_real_key(value):
        raise ValueError(
            f"Field '{field_name}' matches a real provider key pattern. "
            "Real credentials must not appear in the synthetic verification bundle."
        )
    return value


class AiProviderSeed(BaseModel):
    """Seed record for an AI provider (LiteLLM proxy provider).

    Purpose: pre-create the verification provider for J103 admin AI journey.
    Params:
      name          — unique provider name (upsert key).
      provider_type — provider category (e.g., 'litellm').
      api_key       — MUST start with 'synthetic-' (guard).
      base_url      — gateway URL (placeholder for sandbox).
      is_active     — whether this provider is the active one.
    Errors: ValidationError if api_key is missing or does not start with 'synthetic-'.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200, description="Provider name (upsert key).")
    provider_type: str = Field("litellm", description="Provider category.")
    api_key: str = Field(..., description="Must start with 'synthetic-'.")
    base_url: str = Field(..., description="Gateway endpoint URL.")
    is_active: bool = Field(True)
    description: str | None = Field(None, max_length=500)

    @field_validator("api_key")
    @classmethod
    def validate_synthetic_api_key(cls, v: str) -> str:
        """Enforce synthetic- prefix for api_key."""
        return _require_synthetic_prefix("api_key", v)


class AiProviderListSeed(BaseModel):
    """Wrapper for a list of AI provider seeds."""

    model_config = ConfigDict(extra="forbid")

    providers: list[AiProviderSeed]


class AiModelSeed(BaseModel):
    """Seed record for an AI model entry.

    Purpose: pre-register verification models for J103 admin AI journey.
    Params:
      model_id      — model identifier used in LiteLLM calls (upsert key).
      provider_name — references an AiProviderSeed.name.
      display_name  — human-readable label.
      enabled       — whether this model is selectable.
    Errors: ValidationError if required fields are missing.
    """

    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(..., description="LiteLLM model string (upsert key).")
    provider_name: str = Field(..., description="Parent provider name.")
    display_name: str = Field(..., min_length=1, max_length=200)
    enabled: bool = Field(True)
    context_window: int | None = Field(None, ge=1024)


class AiModelListSeed(BaseModel):
    """Wrapper for a list of AI model seeds."""

    model_config = ConfigDict(extra="forbid")

    models: list[AiModelSeed]
