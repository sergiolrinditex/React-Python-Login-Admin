"""
Hilo People — SQLAlchemy 2.x ORM models: Admin AI and LLM gateway.

Slice:  P02-S01-T001 — 0002_ai_chat_rag_mcp_agents migration
Phase:  P02 Core Features (the motor)
Purpose: Defines ORM models for the Admin AI / LiteLLM Gateway feature:
         AiProvider, AiProviderCredential, AiModel, AiModelTest, LlmUsageLog.

Bounded context: admin-ai — LLM provider configuration, credential management
(Fernet-encrypted), model catalog and test results, and per-request usage
accounting across all AI operations (chat, RAG embeddings, agents).

Mapped tables (all created by migration 0002_ai_chat_rag_mcp_agents.py):
  - ai_providers            (FK -> users ON DELETE no-action for created_by)
  - ai_provider_credentials (FK -> ai_providers ON DELETE CASCADE)
  - ai_models               (FK -> ai_providers ON DELETE CASCADE)
  - ai_model_tests          (FK -> ai_models + users ON DELETE CASCADE / SET NULL)
  - llm_usage_logs          (FK -> users + ai_models + conversations ON DELETE SET NULL)

Key deps:
  - app.db.base           — Base (DeclarativeBase with naming_convention)
  - sqlalchemy==2.0.49    (Mapped, mapped_column, JSONB)
  - sqlalchemy.dialects.postgresql — UUID, JSONB

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3#admin-ai
  - docs/source-of-truth/instrucciones.md §3.1#admin-ai
  - 01-non-negotiables.md §Security (Fernet encryption, no API key in logs or frontend)
  - P02-S01-T001 task pack §C.2, §I.1

Decisions implemented:
  - encrypted_secret / encrypted_refresh_token columns: NEVER log values (§10.5).
  - model_type kept as TEXT (no CHECK constraint) until P02-S05 Admin AI defines
    the canonical enum — YAGNI (task pack §I.3 decision: TEXT open).
  - ai_model_tests.created_by ON DELETE SET NULL (audit trace preserved if admin
    account is deleted; differs from CASCADE pattern for identity-attached entities).
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


# ---------------------------------------------------------------------------
# AiProvider — LLM provider configuration
# ---------------------------------------------------------------------------
class AiProvider(Base):
    """ORM model for the `ai_providers` table.

    Represents a configured LLM provider (e.g. OpenAI, Anthropic, Azure, local
    Ollama). status lifecycle: 'draft' → 'active' → 'inactive'. Only admins
    may activate providers (enforced at application layer, P02-S05).

    Table: ai_providers
    PK: id UUID (gen_random_uuid())
    FK: created_by -> users.id (nullable; no ON DELETE — admin ref is informational)

    Refs: §10.3#admin-ai, instrucciones.md §3.1#admin-ai
    """

    __tablename__ = "ai_providers"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    name: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Human-readable provider name (e.g. 'OpenAI Production')",
    )
    provider_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Provider type key (e.g. 'openai', 'anthropic', 'azure', 'litellm')",
    )
    base_url: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Base URL override for self-hosted or Azure endpoints; NULL = provider default",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        server_default=sa.text("'draft'"),
        comment="Lifecycle status: 'draft' | 'active' | 'inactive'",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey("users.id", name="ai_providers_created_by_fkey"),
        nullable=True,
        comment="FK -> users.id (nullable; no CASCADE — informational reference to admin)",
    )


# ---------------------------------------------------------------------------
# AiProviderCredential — encrypted API credentials for a provider
# ---------------------------------------------------------------------------
class AiProviderCredential(Base):
    """ORM model for the `ai_provider_credentials` table.

    Stores Fernet-encrypted API secrets for a provider. auth_type identifies
    the credential kind ('api_key', 'oauth2', 'bearer').
    encrypted_secret and encrypted_refresh_token MUST NEVER be logged.

    Table: ai_provider_credentials
    PK: id UUID (gen_random_uuid())
    FK: provider_id -> ai_providers.id ON DELETE CASCADE

    Refs: §10.3#admin-ai, 01-non-negotiables.md §Security (Fernet AEAD)
    """

    __tablename__ = "ai_provider_credentials"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "ai_providers.id",
            ondelete="CASCADE",
            name="ai_provider_credentials_provider_id_fkey",
        ),
        nullable=False,
        comment="FK -> ai_providers.id ON DELETE CASCADE",
    )
    auth_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Credential kind: 'api_key' | 'oauth2' | 'bearer'",
    )
    encrypted_secret: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Fernet-encrypted API secret — NEVER log this value (§10.5, non-negotiables §Security)",
    )
    encrypted_refresh_token: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Fernet-encrypted OAuth2 refresh token — NEVER log (§10.5)",
    )
    expires_at: Mapped[sa.DateTime | None] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=True,
        comment="OAuth2 token expiry; NULL for non-expiring API keys",
    )


# ---------------------------------------------------------------------------
# AiModel — individual model within a provider
# ---------------------------------------------------------------------------
class AiModel(Base):
    """ORM model for the `ai_models` table.

    Represents a specific model offered by an AiProvider (e.g. gpt-4o,
    claude-3-5-sonnet). model_type is TEXT (open enum until P02-S05 defines
    canonical values). is_default=True means this model is selected when no
    explicit model is requested; enforced to at-most-one per type at app layer.

    Table: ai_models
    PK: id UUID (gen_random_uuid())
    FK: provider_id -> ai_providers.id ON DELETE CASCADE

    Refs: §10.3#admin-ai, instrucciones.md §3.1#admin-ai
    """

    __tablename__ = "ai_models"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    provider_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "ai_providers.id",
            ondelete="CASCADE",
            name="ai_models_provider_id_fkey",
        ),
        nullable=False,
        comment="FK -> ai_providers.id ON DELETE CASCADE",
    )
    model_id: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Provider model identifier (e.g. 'gpt-4o', 'claude-3-5-sonnet-20241022')",
    )
    model_type: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Model category (e.g. 'chat', 'embeddings'); TEXT open until P02-S05 enum",
    )
    capabilities: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'[]'::jsonb"),
        comment="List of capability tags (e.g. ['function_calling', 'vision'])",
    )
    enabled: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="False = model not available to users; must be explicitly enabled by admin",
    )
    is_default: Mapped[bool] = mapped_column(
        sa.Boolean,
        nullable=False,
        server_default=sa.text("false"),
        comment="True = default model for its type; at-most-one per type enforced at app layer",
    )
    pricing: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default=sa.text("'{}'::jsonb"),
        comment="Cost info e.g. {input_cost_per_token, output_cost_per_token}",
    )
    latency_ms_avg: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="Observed average latency in ms; updated by monitoring (P02-S05)",
    )


# ---------------------------------------------------------------------------
# AiModelTest — manual or automated model test result
# ---------------------------------------------------------------------------
class AiModelTest(Base):
    """ORM model for the `ai_model_tests` table.

    Records the result of an admin-triggered test invocation against an AI model.
    Used to verify credentials and latency before enabling a model for users.

    Table: ai_model_tests
    PK: id UUID (gen_random_uuid())
    FK: model_id -> ai_models.id ON DELETE CASCADE
    FK: created_by -> users.id ON DELETE SET NULL (audit trace preserved)

    Refs: §10.3#admin-ai
    """

    __tablename__ = "ai_model_tests"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    model_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "ai_models.id",
            ondelete="CASCADE",
            name="ai_model_tests_model_id_fkey",
        ),
        nullable=False,
        comment="FK -> ai_models.id ON DELETE CASCADE",
    )
    prompt: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Test prompt sent to the model — NEVER log in non-verbose mode",
    )
    output: Mapped[str | None] = mapped_column(
        sa.Text,
        nullable=True,
        comment="Model response; NULL if test failed before response",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="Round-trip latency in ms",
    )
    estimated_cost: Mapped[float | None] = mapped_column(
        sa.Numeric,
        nullable=True,
        comment="Estimated USD cost of the test invocation",
    )
    status: Mapped[str] = mapped_column(
        sa.Text,
        nullable=False,
        comment="Test result status: 'success' | 'failure' | 'timeout'",
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="ai_model_tests_created_by_fkey",
        ),
        nullable=True,
        comment="FK -> users.id ON DELETE SET NULL (audit trace preserved when admin deleted)",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )


# ---------------------------------------------------------------------------
# LlmUsageLog — per-request LLM token and cost accounting
# ---------------------------------------------------------------------------
class LlmUsageLog(Base):
    """ORM model for the `llm_usage_logs` table.

    Records token counts and estimated cost for every LLM invocation across all
    features (chat, RAG vectorization, agent runs). user_id, model_id, and
    conversation_id use ON DELETE SET NULL to preserve aggregate cost history
    even after the user/model/conversation is deleted.

    Table: llm_usage_logs
    PK: id UUID (gen_random_uuid())
    FK: user_id          -> users.id ON DELETE SET NULL
    FK: model_id         -> ai_models.id ON DELETE SET NULL
    FK: conversation_id  -> conversations.id ON DELETE SET NULL

    Refs: §10.3#admin-ai, instrucciones.md §3.1#admin-ai (tokens y coste registrados)
    """

    __tablename__ = "llm_usage_logs"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        server_default=sa.text("gen_random_uuid()"),
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "users.id",
            ondelete="SET NULL",
            name="llm_usage_logs_user_id_fkey",
        ),
        nullable=True,
        comment="FK -> users.id ON DELETE SET NULL (preserve cost history)",
    )
    model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "ai_models.id",
            ondelete="SET NULL",
            name="llm_usage_logs_model_id_fkey",
        ),
        nullable=True,
        comment="FK -> ai_models.id ON DELETE SET NULL (preserve cost history)",
    )
    conversation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        sa.ForeignKey(
            "conversations.id",
            ondelete="SET NULL",
            name="llm_usage_logs_conversation_id_fkey",
        ),
        nullable=True,
        comment="FK -> conversations.id ON DELETE SET NULL; NULL for non-chat invocations",
    )
    tokens_in: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        server_default=sa.text("0"),
        comment="Input (prompt) token count",
    )
    tokens_out: Mapped[int] = mapped_column(
        sa.Integer,
        nullable=False,
        server_default=sa.text("0"),
        comment="Output (completion) token count",
    )
    estimated_cost: Mapped[float] = mapped_column(
        sa.Numeric,
        nullable=False,
        server_default=sa.text("0"),
        comment="Estimated USD cost for this invocation",
    )
    latency_ms: Mapped[int | None] = mapped_column(
        sa.Integer,
        nullable=True,
        comment="Total request latency in ms (network + inference)",
    )
    created_at: Mapped[sa.DateTime] = mapped_column(
        sa.TIMESTAMP(timezone=True),
        nullable=False,
        server_default=sa.text("now()"),
    )
