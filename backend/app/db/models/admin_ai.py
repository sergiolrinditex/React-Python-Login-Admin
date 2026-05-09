"""
SQLAlchemy ORM models: AiProvider, AiProviderCredential, AiModel.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Tables declared here (per HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 + ADR-001 §15):
  - ai_providers            — configured AI provider accounts
  - ai_provider_credentials — encrypted credential row per provider (FK CASCADE)
  - ai_models               — model catalog per provider (FK CASCADE)

Discrepancy D1 resolved: `ai_models.auto_discovered` column added per ADR-001.
§10.3 DDL block did not include it; T005 seed schema + acceptance #2 require it.
The migration 0003 adds it. The closer queues §10.3 amendment.

Dependencies:
  - sqlalchemy 2.0.49
  - app.db.models.base.Base

Note: no logging here — pure SQLAlchemy declarative module (same exemption as
other ORM model files; see task-pack §C3 file-size note).

Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 lines 114-145
Task-pack P00-S02-T006 §6.2 (ORM plan)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.models.base import Base

if TYPE_CHECKING:
    from app.db.models.user import User


class AiProvider(Base):
    """ORM model for the `ai_providers` table.

    Table: ai_providers (TECHNICAL_GUIDE §10.3)
    Slice: P00-S02-T006

    One row per configured AI provider account (Gemini, OpenAI, LiteLLM proxy, …).
    The `status` field follows a draft→active→disabled lifecycle.
    `created_by` is nullable — system-seeded providers have no actor.

    Purpose: central registry of provider accounts consumed by discovery + routing.
    """

    __tablename__ = "ai_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        doc="Primary key (UUID v4, server-generated).",
    )
    name: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="Human-readable provider name (e.g. 'gemini-direct').",
    )
    provider_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="Provider kind: 'gemini' | 'openai' | 'litellm'. Drives dispatch logic.",
    )
    base_url: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        doc="Base URL for direct calls (None = use SDK default).",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default="draft",
        doc="Lifecycle: draft | active | disabled.",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey("users.id", name="fk_ai_providers_created_by_users"),
        nullable=True,
        doc="User who created this provider (NULL for system-seeded rows).",
    )

    # Relationships
    credentials: Mapped[list[AiProviderCredential]] = relationship(
        "AiProviderCredential",
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="select",
    )
    models: Mapped[list[AiModel]] = relationship(
        "AiModel",
        back_populates="provider",
        cascade="all, delete-orphan",
        lazy="select",
    )

    if TYPE_CHECKING:
        creator: Mapped[User | None]


class AiProviderCredential(Base):
    """ORM model for the `ai_provider_credentials` table.

    Table: ai_provider_credentials (TECHNICAL_GUIDE §10.3)
    Slice: P00-S02-T006

    Stores the ENCRYPTED credential for a provider. One active credential per
    provider is the typical pattern; multiple rows are allowed for key rotation.
    `encrypted_secret` is a Fernet-encrypted blob — decrypted on-the-fly by
    `app.core.security.decrypt_secret()`.

    Security: NEVER log `encrypted_secret`. NEVER return it via the API.
    """

    __tablename__ = "ai_provider_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        doc="Primary key.",
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey(
            "ai_providers.id",
            ondelete="CASCADE",
            name="fk_ai_provider_credentials_provider_id_ai_providers",
        ),
        nullable=False,
        doc="Foreign key to ai_providers.",
    )
    auth_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="Credential kind: 'api_key' | 'master_key' | 'bearer_token'.",
    )
    encrypted_secret: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="Fernet-encrypted API key/token. Decrypt via core.security.decrypt_secret().",
    )
    expires_at: Mapped[datetime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        doc="Optional expiry for rotating credentials (NULL = no expiry).",
    )

    provider: Mapped[AiProvider] = relationship(
        "AiProvider",
        back_populates="credentials",
        lazy="select",
    )


class AiModel(Base):
    """ORM model for the `ai_models` table.

    Table: ai_models (TECHNICAL_GUIDE §10.3 + ADR-001 D1 amendment)
    Slice: P00-S02-T006

    One row per model known by the system. Models may be:
    - Manual starter entries (auto_discovered=false, from seed bundle).
    - Dynamically discovered via POST /discover-models (auto_discovered=true).

    The UNIQUE constraint on (provider_id, model_id) is enforced via a database
    index (see migration 0003). The repository layer uses this to do
    SELECT-then-INSERT diff instead of upsert to preserve existing settings.

    Columns:
    - model_type: 'chat' | 'embedding' | 'unknown' (§10.3 enum, mapped in service)
    - capabilities: JSONB array of capability strings (default [])
    - pricing: JSONB object with cost-per-token data (default {})
    - auto_discovered: D1 amendment — true when added by discover-models endpoint
    """

    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
        doc="Primary key.",
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        sa.UUID(as_uuid=True),
        sa.ForeignKey(
            "ai_providers.id",
            ondelete="CASCADE",
            name="fk_ai_models_provider_id_ai_providers",
        ),
        nullable=False,
        doc="Foreign key to ai_providers.",
    )
    model_id: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="Provider-scoped model identifier (e.g. 'models/gemini-2.5-flash').",
    )
    model_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        doc="Model capability class: 'chat' | 'embedding' | 'unknown'.",
    )
    capabilities: Mapped[list] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
        doc="Array of capability strings (e.g. ['generateContent']).",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this model is available for use. Admin activates explicitly.",
    )
    is_default: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default="false",
        doc="Whether this is the default model for its provider.",
    )
    pricing: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        doc="Cost-per-token pricing data (provider format).",
    )
    latency_ms_avg: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        doc="Average observed latency in ms (updated by test-prompt results).",
    )
    # D1 amendment (TECHNICAL_GUIDE §10.3 discrepancy, resolved in migration 0003)
    auto_discovered: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default="false",
        doc="True when this row was inserted by the discover-models endpoint (ADR-001).",
    )

    provider: Mapped[AiProvider] = relationship(
        "AiProvider",
        back_populates="models",
        lazy="select",
    )
