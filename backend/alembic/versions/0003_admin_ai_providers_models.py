"""Admin AI: ai_providers, ai_provider_credentials, ai_models tables.

Revision ID: 0003
Revises: 0001
Create Date: 2026-05-09

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Tables created (in dependency order):
  1. ai_providers             — configured AI provider accounts
  2. ai_provider_credentials  — encrypted credential per provider (FK CASCADE)
  3. ai_models                — model catalog per provider (FK CASCADE)

Discrepancy D1 resolved here:
  §10.3 DDL block omits `ai_models.auto_discovered`. The seed bundle's
  models.json (T005) declares this field. ADR-001 references it in the
  reconcile logic. → Added as `BOOLEAN NOT NULL DEFAULT false`.

Discrepancy D4 queued for closer §10.3 amendment:
  Closer should amend §10.3 DDL to add `auto_discovered BOOLEAN NOT NULL DEFAULT false`
  and add the discover-models endpoint row to §6.2 inventory.

Migration risk R3 (P02-S01-T001 conflict):
  P02-S01-T001 was originally scoped to create 0002_ai_chat_rag_mcp_agents.py
  including ai_providers/ai_models. This slice creates 0003 (skipping 0002 to leave
  room for the consolidated migration). When P02-S01-T001 lands it MUST be reshaped
  to 0004_chat_rag_mcp_agents.py covering only tables NOT created here. The closer
  queues this source-of-truth amendment.

Indexes per 01-non-negotiables.md §Database:
  - ai_models.provider_id (foreign key join)
  - ai_models UNIQUE (provider_id, model_id) — upsert identity key
  - ai_provider_credentials.provider_id (foreign key join)
  - ai_provider_credentials.expires_at WHERE NOT NULL (expiry janitor sweep)

Downgrade discipline:
  Drop tables in reverse dependency order (children first):
    ai_models → ai_provider_credentials → ai_providers
  Do NOT drop extensions (pgcrypto, vector) — created in 0001.

Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 + ADR-001 §15
Task-pack P00-S02-T006 §6.3 + §7.1
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers
revision: str = "0003"
down_revision: str | None = "0001"
branch_labels: None = None
depends_on: None = None


def upgrade() -> None:
    """Create ai_providers, ai_provider_credentials, ai_models tables.

    Executes DDL from TECHNICAL_GUIDE §10.3 verbatim, with the addition of
    `ai_models.auto_discovered` per ADR-001 + T005 seed schema.

    Creates explicit indexes for foreign-key joins and the UNIQUE identity
    key used by the upsert-or-diff repository pattern.
    """
    # ------------------------------------------------------------------
    # 1. ai_providers
    # ------------------------------------------------------------------
    op.create_table(
        "ai_providers",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("provider_type", sa.Text, nullable=False),
        sa.Column("base_url", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="draft"),
        sa.Column(
            "created_by",
            sa.UUID(as_uuid=True),
            sa.ForeignKey("users.id", name="fk_ai_providers_created_by_users"),
            nullable=True,
        ),
    )

    # ------------------------------------------------------------------
    # 2. ai_provider_credentials
    # ------------------------------------------------------------------
    op.create_table(
        "ai_provider_credentials",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "ai_providers.id",
                ondelete="CASCADE",
                name="fk_ai_provider_credentials_provider_id_ai_providers",
            ),
            nullable=False,
        ),
        sa.Column("auth_type", sa.Text, nullable=False),
        sa.Column("encrypted_secret", sa.Text, nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )

    # Index: FK join (provider_id)
    op.create_index(
        "ix_ai_provider_credentials_provider_id",
        "ai_provider_credentials",
        ["provider_id"],
    )
    # Partial index: expiry sweep (WHERE expires_at IS NOT NULL)
    op.create_index(
        "ix_ai_provider_credentials_expires_at",
        "ai_provider_credentials",
        ["expires_at"],
        postgresql_where=sa.text("expires_at IS NOT NULL"),
    )

    # ------------------------------------------------------------------
    # 3. ai_models
    # ------------------------------------------------------------------
    op.create_table(
        "ai_models",
        sa.Column(
            "id",
            sa.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
            nullable=False,
        ),
        sa.Column(
            "provider_id",
            sa.UUID(as_uuid=True),
            sa.ForeignKey(
                "ai_providers.id",
                ondelete="CASCADE",
                name="fk_ai_models_provider_id_ai_providers",
            ),
            nullable=False,
        ),
        sa.Column("model_id", sa.Text, nullable=False),
        sa.Column("model_type", sa.Text, nullable=False),
        sa.Column(
            "capabilities",
            JSONB,
            nullable=False,
            server_default=sa.text("'[]'::jsonb"),
        ),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="false"),
        sa.Column(
            "pricing",
            JSONB,
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column("latency_ms_avg", sa.Integer, nullable=True),
        # D1 amendment: auto_discovered per ADR-001 + T005 seed schema
        sa.Column(
            "auto_discovered",
            sa.Boolean,
            nullable=False,
            server_default="false",
        ),
    )

    # Index: FK join
    op.create_index("ix_ai_models_provider_id", "ai_models", ["provider_id"])
    # UNIQUE index: upsert identity key (provider_id, model_id)
    op.create_index(
        "uq_ai_models_provider_id_model_id",
        "ai_models",
        ["provider_id", "model_id"],
        unique=True,
    )


def downgrade() -> None:
    """Drop ai_models, ai_provider_credentials, ai_providers in child-first order.

    Drops indexes explicitly before dropping tables to avoid constraint conflicts
    on partial/compound indexes that Alembic may not auto-discover.
    """
    # ai_models
    op.drop_index("uq_ai_models_provider_id_model_id", table_name="ai_models")
    op.drop_index("ix_ai_models_provider_id", table_name="ai_models")
    op.drop_table("ai_models")

    # ai_provider_credentials
    op.drop_index(
        "ix_ai_provider_credentials_expires_at",
        table_name="ai_provider_credentials",
    )
    op.drop_index(
        "ix_ai_provider_credentials_provider_id",
        table_name="ai_provider_credentials",
    )
    op.drop_table("ai_provider_credentials")

    # ai_providers (parent last)
    op.drop_table("ai_providers")
