"""
Hilo People — Admin AI providers Pydantic schemas.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Pydantic v2 request/response models for /api/v1/admin/ai/providers.
         Encryption, persistence and audit logic live in service/repository/audit;
         this module only declares wire-level contracts.

Key deps:
  - pydantic v2 (BaseModel, Field, field_validator)

Source refs:
  - task pack P02-S05-T001 §Front→Back→DB contract
  - instrucciones.md §3.1#admin-ai (credentials never echoed)

Decisions:
  - secret_plain is `min_length=1`, marked "NEVER logged or returned" — the
    docstring is part of the contract; consumers must respect it.
  - name is trimmed via field_validator to reject whitespace-only names.
  - Literal whitelists match TECHNICAL_GUIDE §6.2.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator


class ProviderCredentialsInput(BaseModel):
    """Credentials payload for POST /providers — NEVER echoed back.

    Attributes:
        auth_type:            Credential kind.
        secret_plain:         Raw API key or bearer token — encrypted before
                              persistence; never logged.
        refresh_token_plain:  OAuth2 refresh token (optional).
        expires_at:           Token expiry for OAuth2 flows.
    """

    auth_type: Literal["api_key", "oauth2", "bearer"]
    secret_plain: str = Field(..., min_length=1, description="NEVER logged or returned")
    refresh_token_plain: str | None = None
    expires_at: datetime | None = None


class CreateProviderRequest(BaseModel):
    """Request body for POST /api/v1/admin/ai/providers.

    Attributes:
        provider_type: Provider type key (openai|anthropic|azure|litellm|ollama|google|custom).
        name:          Human-readable name (1-200 chars; whitespace-only rejected).
        base_url:      Optional base URL override for self-hosted or Azure endpoints.
        credentials:   Required credential block — encrypted at write time.
    """

    provider_type: Literal[
        "openai", "anthropic", "azure", "litellm", "ollama", "google", "custom"
    ]
    name: str = Field(..., min_length=1, max_length=200)
    base_url: str | None = None
    credentials: ProviderCredentialsInput

    @field_validator("name")
    @classmethod
    def name_not_blank(cls, v: str) -> str:
        """Reject names that are only whitespace."""
        if not v.strip():
            raise ValueError("name must not be blank")
        return v.strip()


class ProviderOut(BaseModel):
    """Response schema for a single provider (credentials NEVER included).

    Attributes:
        id:                   Provider UUID.
        name:                 Human-readable name.
        provider_type:        Provider type key.
        base_url:             Optional base URL override.
        status:               Lifecycle status (draft|active|inactive).
        created_by:           UUID of admin who created it (nullable).
        has_credentials:      True if a credential row exists.
        credential_auth_type: auth_type from credential row (nullable).
        expires_at:           Token expiry from credential row (nullable).
    """

    id: uuid.UUID
    name: str
    provider_type: str
    base_url: str | None
    status: str
    created_by: uuid.UUID | None
    has_credentials: bool
    credential_auth_type: str | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}
