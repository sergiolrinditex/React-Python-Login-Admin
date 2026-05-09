"""
Pydantic models for the 'admin_ai' namespace.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Covers:
  - data/verification/admin_ai/providers.json
  - data/verification/admin_ai/models.json

CHANGE from T003:
  - AiProviderSeed: api_key now optional; new fields api_key_env + api_key_backup_env.
    Productive bundles use *_env references; synthetic bundles use 'synthetic-' prefix.
  - AiModelSeed: RESHAPED — name, capability, is_active (was 'enabled'), auto_discovered.
    display_name is now optional (derived from name if absent).
    NOTE: this reshape is intentional (T005); synthetic fixture shape also updated.
  - _REAL_KEY_PATTERNS guard remains active for defense-in-depth.
  - Bundle type enforcement via validate_with_bundle_type() class methods.

SECURITY:
  - Productive bundles MUST use api_key_env references; real keys never in JSON.
  - _REAL_KEY_PATTERNS regex remains active to reject accidental plaintext real keys.
  - Synthetic guard: api_key must start with 'synthetic-'.

Dependencies:
  - pydantic 2.12.5
"""
from __future__ import annotations

import re
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

# Regex patterns that match real provider API keys.
# A credential matching any of these is REJECTED as defense-in-depth.
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
    """Seed record for an AI provider (LiteLLM proxy / direct API provider).

    Purpose: pre-create the verification providers for J103 admin AI journey.
    Supports both synthetic (dev) and productive (real) bundles.

    Params:
      name              — unique provider name (upsert key).
      provider_type     — provider category (e.g., 'gemini', 'openai', 'litellm').
      api_key           — plaintext key (synthetic bundles only, must start 'synthetic-').
      api_key_env       — env var name holding the real key (productive bundles).
      api_key_backup_env — env var name for backup key (optional, productive only).
      base_url          — gateway URL.
      is_active         — whether this provider is the active one.
      description       — optional human-readable description.

    Validation rules (enforced via validate_with_bundle_type):
      - synthetic: api_key required, must start 'synthetic-', must not match real patterns.
      - productive: api_key_env required (preferred); api_key plaintext rejected if it
        matches _REAL_KEY_PATTERNS.
      - bundle_type=None: raises ValueError (R7 guard).

    Errors: ValidationError if rules are violated.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200, description="Provider name (upsert key).")
    provider_type: str = Field("litellm", description="Provider category.")
    api_key: str | None = Field(
        None, description="Plaintext key (synthetic only, 'synthetic-' prefix)."
    )
    api_key_env: str | None = Field(
        None, description="Env var name for the real API key (productive)."
    )
    api_key_backup_env: str | None = Field(
        None, description="Env var name for backup key (productive, optional)."
    )
    base_url: str = Field(..., description="Gateway endpoint URL.")
    is_active: bool = Field(True)
    description: str | None = Field(None, max_length=500)

    @classmethod
    def validate_with_bundle_type(
        cls, data: dict[str, Any], bundle_type: str | None
    ) -> AiProviderSeed:
        """Validate AiProviderSeed with explicit bundle_type enforcement.

        Params:
          data        — raw dict from the fixture file.
          bundle_type — 'synthetic' or 'productive'. None raises ValueError.
        Returns: validated instance.
        Errors: ValueError on invariant violations.
        """
        if bundle_type is None:
            raise ValueError(
                "AiProviderSeed: bundle_type must not be None. "
                "Pass bundle_type via validate_with_bundle_type()."
            )

        instance = cls.model_validate(data)

        if bundle_type == "synthetic":
            if not instance.api_key:
                raise ValueError(
                    "synthetic bundle: AiProviderSeed.api_key is required."
                )
            _require_synthetic_prefix("api_key", instance.api_key)

        elif bundle_type == "productive":
            if instance.api_key and _is_real_key(instance.api_key):
                raise ValueError(
                    "productive bundle: AiProviderSeed.api_key contains a plaintext real key. "
                    "Use api_key_env to reference an env var instead."
                )
            # api_key_env or api_key must be present for providers that need auth.
            # Public providers (e.g. docs-langchain) can have neither.
            # We validate this loosely here; loader will fail-fast on resolve_env_var.

        else:
            raise ValueError(
                f"Unknown bundle_type: {bundle_type!r}. Expected 'synthetic' or 'productive'."
            )

        return instance


class AiProviderListSeed(BaseModel):
    """Wrapper for a list of AI provider seeds."""

    model_config = ConfigDict(extra="forbid")

    providers: list[AiProviderSeed]


class AiModelSeed(BaseModel):
    """Seed record for an AI model entry (reshaped in T005).

    Purpose: pre-register verification models for J103 admin AI journey.
    SHAPE CHANGE from T003: name + capability + is_active (was 'enabled') + auto_discovered.
    display_name is now optional (derived from name at loader time if absent).

    Params:
      name          — human-readable model name (upsert key).
      model_id      — model identifier used in LiteLLM calls.
      provider_name — references an AiProviderSeed.name.
      display_name  — optional UI label (defaults to name if absent).
      capability    — model capability type: 'chat', 'embedding', or 'reranker'.
      is_active     — whether this model is selectable (was 'enabled' in T003).
      auto_discovered — False for manual starter entries; True when discovered
                       via FU-X1 dynamic discovery endpoint.
      context_window — optional token context limit.

    Errors: ValidationError if required fields are missing or capability is invalid.
    """

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, max_length=200, description="Model name (upsert key).")
    model_id: str = Field(..., description="LiteLLM model string.")
    provider_name: str = Field(..., description="Parent provider name.")
    display_name: str | None = Field(None, min_length=1, max_length=200)
    capability: Literal["chat", "embedding", "reranker"] = Field(
        ..., description="Model capability type."
    )
    is_active: bool = Field(True)
    auto_discovered: bool = Field(False)
    context_window: int | None = Field(None, ge=1024)


class AiModelListSeed(BaseModel):
    """Wrapper for a list of AI model seeds."""

    model_config = ConfigDict(extra="forbid")

    models: list[AiModelSeed]
