"""0002 — AI/Chat/RAG/MCP/Agents tables.

Slice:  P02-S01-T001 — DB AI/chat/RAG/MCP/agents schema
Phase:  P02 Core Features (the motor)
Purpose: Creates the full AI+Chat+RAG+MCP+Agents schema needed by Phase 2.
         24 tables in FK-safe dependency order. Adds pgvector extension and
         HNSW index for semantic search on document_embeddings.

Tables created in upgrade() order (FK-safe, parents before children):

  Chat domain:
    1.  conversations         (FK -> users CASCADE)
    2.  messages              (FK -> conversations CASCADE)
    3.  message_citations     (FK -> messages CASCADE; document_id/chunk_id NO FK — D-LATE)

  Admin AI domain:
    4.  ai_providers          (FK -> users for created_by — no CASCADE)
    5.  ai_provider_credentials (FK -> ai_providers CASCADE)
    6.  ai_models             (FK -> ai_providers CASCADE)
    7.  ai_model_tests        (FK -> ai_models CASCADE, FK -> users SET NULL)
    8.  llm_usage_logs        (FK -> users SET NULL, ai_models SET NULL, conversations SET NULL)

  RAG domain:
    9.  rag_collections       (no FK)
    10. documents             (FK -> rag_collections SET NULL, FK -> users no-CASCADE)
    11. document_versions     (FK -> documents CASCADE)
    12. document_chunks       (FK -> documents CASCADE, FK -> document_versions CASCADE)
    13. document_embeddings   (FK -> document_chunks CASCADE, FK -> ai_models SET NULL)
        + HNSW index          document_embeddings_vector_idx (D1: hnsw over ivfflat)
    14. vectorization_jobs    (FK -> documents CASCADE)
        + perf indexes        conversations_user_updated_idx, messages_conversation_created_idx

  MCP+Agents domain:
    15. mcp_servers           (FK -> users for created_by — no CASCADE)
    16. mcp_credentials       (FK -> mcp_servers CASCADE)
    17. mcp_tools             (FK -> mcp_servers CASCADE)
    18. mcp_resources         (FK -> mcp_servers CASCADE)
    19. mcp_prompts           (FK -> mcp_servers CASCADE)
    20. agents                (no FK)
    21. mcp_agent_bindings    (FK -> agents CASCADE, FK -> mcp_tools CASCADE; composite PK)
    22. agent_runs            (FK -> agents SET NULL, FK -> users SET NULL)
    23. mcp_tool_invocations  (FK -> mcp_tools SET NULL, FK -> agent_runs CASCADE)
    24. mcp_approvals         (FK -> mcp_tool_invocations CASCADE, FK -> users no-CASCADE)

Tables dropped in downgrade() order (reverse FK-safe, children before parents).
Extension `vector` NOT dropped in downgrade (D-VECTOR: idempotent, shared).

Revises: 0001
Create Date: 2026-05-13

Decisions implemented:
  D1-HNSW:  HNSW index used instead of ivfflat (§10.3 override — researcher D1,
            2026-05-13). Official pgvector 0.8.2 docs explicitly discourage ivfflat
            on empty tables; HNSW is production-safe without training step.
            See: orchestrator-state/memory/official-doc-notes/P02-S01-T001-pgvector-2026-05-13.md
  D-LATE:   message_citations.document_id + chunk_id stored WITHOUT FK. Citations
            survive document versioning/deletion (historical trace must not break).
            Referential consistency enforced at application layer.
  D-VECTOR: NO DROP EXTENSION vector in downgrade (same rationale as D2-PGCRYPTO in 0001).
  D-IDX:    CHECK constraints on conversations.language + documents.language
            IN ('es','en','fr') — aligned with users_language_chk from 0001.
  D-YAGNI:  Only 3 indexes explicitly declared in §10.3 are created here.
            6 additional performance indexes deferred to feature-specific migrations.
"""

from __future__ import annotations

import logging

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID, JSONB

logger = logging.getLogger("alembic.runtime.migration")

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    """Create all AI/Chat/RAG/MCP/Agent tables in FK-safe order.

    Creates vector extension first (IF NOT EXISTS — idempotent), then
    24 tables in topological order. HNSW index and language CHECK constraints
    applied per D1-HNSW and D-IDX decisions above.
    CAUTION: downgrading with data will trigger cascades — never downgrade
    in production without a backup.
    """
    logger.info("0002.upgrade.start: creating vector extension and 24 AI/Chat/RAG/MCP tables")

    # ------------------------------------------------------------------
    # 0. PostgreSQL extension — pgvector for vector(1536) type
    # ------------------------------------------------------------------
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    logger.info("0002.upgrade: vector extension ensured")

    # ==================================================================
    # CHAT DOMAIN
    # ==================================================================

    # ------------------------------------------------------------------
    # 1. conversations
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table conversations")
    op.create_table(
        "conversations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE", name="conversations_user_id_fkey"), nullable=False),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("language", sa.Text, nullable=False, server_default=sa.text("'es'")),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("language IN ('es','en','fr')", name="conversations_language_chk"),
    )
    logger.info("0002.upgrade: table conversations created")

    # ------------------------------------------------------------------
    # 2. messages
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table messages")
    op.create_table(
        "messages",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="CASCADE", name="messages_conversation_id_fkey"), nullable=False),
        sa.Column("role", sa.Text, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("token_count", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    logger.info("0002.upgrade: table messages created")

    # ------------------------------------------------------------------
    # 3. message_citations — NO FK on document_id / chunk_id (D-LATE)
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table message_citations")
    op.create_table(
        "message_citations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("message_id", UUID(as_uuid=True), sa.ForeignKey("messages.id", ondelete="CASCADE", name="message_citations_message_id_fkey"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), nullable=True),
        sa.Column("chunk_id", UUID(as_uuid=True), nullable=True),
        sa.Column("label", sa.Text, nullable=False),
        sa.Column("score", sa.Float, nullable=False),
    )
    logger.info("0002.upgrade: table message_citations created (D-LATE: document_id/chunk_id without FK)")

    # ==================================================================
    # ADMIN AI DOMAIN (before RAG — ai_models referenced by document_embeddings)
    # ==================================================================

    # ------------------------------------------------------------------
    # 4. ai_providers
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table ai_providers")
    op.create_table(
        "ai_providers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("provider_type", sa.Text, nullable=False),
        sa.Column("base_url", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", name="ai_providers_created_by_fkey"), nullable=True),
    )
    logger.info("0002.upgrade: table ai_providers created")

    # ------------------------------------------------------------------
    # 5. ai_provider_credentials
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table ai_provider_credentials")
    op.create_table(
        "ai_provider_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("ai_providers.id", ondelete="CASCADE", name="ai_provider_credentials_provider_id_fkey"), nullable=False),
        sa.Column("auth_type", sa.Text, nullable=False),
        sa.Column("encrypted_secret", sa.Text, nullable=False),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    logger.info("0002.upgrade: table ai_provider_credentials created")

    # ------------------------------------------------------------------
    # 6. ai_models
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table ai_models")
    op.create_table(
        "ai_models",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("provider_id", UUID(as_uuid=True), sa.ForeignKey("ai_providers.id", ondelete="CASCADE", name="ai_models_provider_id_fkey"), nullable=False),
        sa.Column("model_id", sa.Text, nullable=False),
        sa.Column("model_type", sa.Text, nullable=False),
        sa.Column("capabilities", JSONB, nullable=False, server_default=sa.text("'[]'::jsonb")),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("pricing", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("latency_ms_avg", sa.Integer, nullable=True),
    )
    logger.info("0002.upgrade: table ai_models created")

    # ------------------------------------------------------------------
    # 7. ai_model_tests
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table ai_model_tests")
    op.create_table(
        "ai_model_tests",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("model_id", UUID(as_uuid=True), sa.ForeignKey("ai_models.id", ondelete="CASCADE", name="ai_model_tests_model_id_fkey"), nullable=False),
        sa.Column("prompt", sa.Text, nullable=False),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("estimated_cost", sa.Numeric, nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL", name="ai_model_tests_created_by_fkey"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    logger.info("0002.upgrade: table ai_model_tests created")

    # ------------------------------------------------------------------
    # 8. llm_usage_logs — ON DELETE SET NULL for all FKs (preserve history)
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table llm_usage_logs")
    op.create_table(
        "llm_usage_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL", name="llm_usage_logs_user_id_fkey"), nullable=True),
        sa.Column("model_id", UUID(as_uuid=True), sa.ForeignKey("ai_models.id", ondelete="SET NULL", name="llm_usage_logs_model_id_fkey"), nullable=True),
        sa.Column("conversation_id", UUID(as_uuid=True), sa.ForeignKey("conversations.id", ondelete="SET NULL", name="llm_usage_logs_conversation_id_fkey"), nullable=True),
        sa.Column("tokens_in", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("tokens_out", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("estimated_cost", sa.Numeric, nullable=False, server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    logger.info("0002.upgrade: table llm_usage_logs created")

    # ==================================================================
    # RAG DOMAIN
    # ==================================================================

    # ------------------------------------------------------------------
    # 9. rag_collections
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table rag_collections")
    op.create_table(
        "rag_collections",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("vertical", sa.Text, nullable=False),
        sa.Column("language", sa.Text, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    logger.info("0002.upgrade: table rag_collections created")

    # ------------------------------------------------------------------
    # 10. documents
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table documents")
    op.create_table(
        "documents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("collection_id", UUID(as_uuid=True), sa.ForeignKey("rag_collections.id", ondelete="SET NULL", name="documents_collection_id_fkey"), nullable=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("language", sa.Text, nullable=False),
        sa.Column("source_uri", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'uploaded'")),
        sa.Column("uploaded_by", UUID(as_uuid=True), sa.ForeignKey("users.id", name="documents_uploaded_by_fkey"), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("language IN ('es','en','fr')", name="documents_language_chk"),
    )
    logger.info("0002.upgrade: table documents created")

    # ------------------------------------------------------------------
    # 11. document_versions
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table document_versions")
    op.create_table(
        "document_versions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE", name="document_versions_document_id_fkey"), nullable=False),
        sa.Column("version", sa.Integer, nullable=False),
        sa.Column("storage_key", sa.Text, nullable=False),
        sa.Column("checksum", sa.Text, nullable=False),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    logger.info("0002.upgrade: table document_versions created")

    # ------------------------------------------------------------------
    # 12. document_chunks
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table document_chunks")
    op.create_table(
        "document_chunks",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE", name="document_chunks_document_id_fkey"), nullable=False),
        sa.Column("version_id", UUID(as_uuid=True), sa.ForeignKey("document_versions.id", ondelete="CASCADE", name="document_chunks_version_id_fkey"), nullable=False),
        sa.Column("chunk_index", sa.Integer, nullable=False),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("metadata", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    logger.info("0002.upgrade: table document_chunks created")

    # ------------------------------------------------------------------
    # 13. document_embeddings — vector(1536) via raw SQL (D3: avoids Alembic dialect)
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table document_embeddings (vector column via raw SQL)")
    op.execute("""
        CREATE TABLE document_embeddings (
            chunk_id UUID PRIMARY KEY
                REFERENCES document_chunks(id) ON DELETE CASCADE
                DEFERRABLE INITIALLY DEFERRED,
            embedding vector(1536),
            model_id UUID REFERENCES ai_models(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    logger.info("0002.upgrade: table document_embeddings created")

    # HNSW index — D1: hnsw instead of ivfflat (researcher note P02-S01-T001-pgvector-2026-05-13.md)
    # Official pgvector 0.8.2 docs: HNSW is safe on empty table (no training step).
    # ivfflat on empty table explicitly discouraged (degenerate lists clustering).
    logger.info("0002.upgrade: creating HNSW index document_embeddings_vector_idx (D1 override of §10.3 ivfflat)")
    op.execute("""
        CREATE INDEX document_embeddings_vector_idx
            ON document_embeddings
            USING hnsw (embedding vector_cosine_ops)
            WITH (m = 16, ef_construction = 64)
    """)
    logger.info("0002.upgrade: HNSW index document_embeddings_vector_idx created")

    # ------------------------------------------------------------------
    # 14. vectorization_jobs
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table vectorization_jobs")
    op.create_table(
        "vectorization_jobs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("document_id", UUID(as_uuid=True), sa.ForeignKey("documents.id", ondelete="CASCADE", name="vectorization_jobs_document_id_fkey"), nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("progress", sa.Integer, nullable=False, server_default=sa.text("0")),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    logger.info("0002.upgrade: table vectorization_jobs created")

    # Performance indexes declared in §10.3 (D-YAGNI: only these 2 btree indexes now)
    logger.info("0002.upgrade: creating perf indexes (conversations_user_updated_idx, messages_conversation_created_idx)")
    op.create_index(
        "conversations_user_updated_idx",
        "conversations",
        [sa.text("user_id"), sa.text("updated_at DESC")],
        postgresql_using="btree",
    )
    op.create_index(
        "messages_conversation_created_idx",
        "messages",
        ["conversation_id", "created_at"],
        postgresql_using="btree",
    )
    logger.info("0002.upgrade: performance indexes created")

    # ==================================================================
    # MCP + AGENTS DOMAIN
    # ==================================================================

    # ------------------------------------------------------------------
    # 15. mcp_servers
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table mcp_servers")
    op.create_table(
        "mcp_servers",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("transport_type", sa.Text, nullable=False),
        sa.Column("endpoint_url", sa.Text, nullable=True),
        sa.Column("command", sa.Text, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default=sa.text("'draft'")),
        sa.Column("last_sync_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_by", UUID(as_uuid=True), sa.ForeignKey("users.id", name="mcp_servers_created_by_fkey"), nullable=True),
    )
    logger.info("0002.upgrade: table mcp_servers created")

    # ------------------------------------------------------------------
    # 16. mcp_credentials
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table mcp_credentials")
    op.create_table(
        "mcp_credentials",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("server_id", UUID(as_uuid=True), sa.ForeignKey("mcp_servers.id", ondelete="CASCADE", name="mcp_credentials_server_id_fkey"), nullable=False),
        sa.Column("auth_type", sa.Text, nullable=False),
        sa.Column("encrypted_secret", sa.Text, nullable=True),
        sa.Column("encrypted_refresh_token", sa.Text, nullable=True),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    logger.info("0002.upgrade: table mcp_credentials created")

    # ------------------------------------------------------------------
    # 17. mcp_tools
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table mcp_tools")
    op.create_table(
        "mcp_tools",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("server_id", UUID(as_uuid=True), sa.ForeignKey("mcp_servers.id", ondelete="CASCADE", name="mcp_tools_server_id_fkey"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("input_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("output_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("requires_approval", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.Column("risk_level", sa.Text, nullable=False, server_default=sa.text("'medium'")),
    )
    logger.info("0002.upgrade: table mcp_tools created")

    # ------------------------------------------------------------------
    # 18. mcp_resources
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table mcp_resources")
    op.create_table(
        "mcp_resources",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("server_id", UUID(as_uuid=True), sa.ForeignKey("mcp_servers.id", ondelete="CASCADE", name="mcp_resources_server_id_fkey"), nullable=False),
        sa.Column("uri", sa.Text, nullable=False),
        sa.Column("name", sa.Text, nullable=True),
        sa.Column("mime_type", sa.Text, nullable=True),
        sa.Column("description", sa.Text, nullable=True),
    )
    logger.info("0002.upgrade: table mcp_resources created")

    # ------------------------------------------------------------------
    # 19. mcp_prompts
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table mcp_prompts")
    op.create_table(
        "mcp_prompts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("server_id", UUID(as_uuid=True), sa.ForeignKey("mcp_servers.id", ondelete="CASCADE", name="mcp_prompts_server_id_fkey"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("arguments_schema", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    logger.info("0002.upgrade: table mcp_prompts created")

    # ------------------------------------------------------------------
    # 20. agents
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table agents")
    op.create_table(
        "agents",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("config", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
    )
    logger.info("0002.upgrade: table agents created")

    # ------------------------------------------------------------------
    # 21. mcp_agent_bindings — composite PK (agent_id, tool_id)
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table mcp_agent_bindings")
    op.create_table(
        "mcp_agent_bindings",
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="CASCADE", name="mcp_agent_bindings_agent_id_fkey"), nullable=False),
        sa.Column("tool_id", UUID(as_uuid=True), sa.ForeignKey("mcp_tools.id", ondelete="CASCADE", name="mcp_agent_bindings_tool_id_fkey"), nullable=False),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default=sa.text("true")),
        sa.PrimaryKeyConstraint("agent_id", "tool_id", name="pk_mcp_agent_bindings"),
    )
    logger.info("0002.upgrade: table mcp_agent_bindings created")

    # ------------------------------------------------------------------
    # 22. agent_runs
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table agent_runs")
    op.create_table(
        "agent_runs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("agent_id", UUID(as_uuid=True), sa.ForeignKey("agents.id", ondelete="SET NULL", name="agent_runs_agent_id_fkey"), nullable=True),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL", name="agent_runs_user_id_fkey"), nullable=True),
        sa.Column("input", sa.Text, nullable=False),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("output", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("finished_at", sa.TIMESTAMP(timezone=True), nullable=True),
    )
    logger.info("0002.upgrade: table agent_runs created")

    # ------------------------------------------------------------------
    # 23. mcp_tool_invocations
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table mcp_tool_invocations")
    op.create_table(
        "mcp_tool_invocations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("tool_id", UUID(as_uuid=True), sa.ForeignKey("mcp_tools.id", ondelete="SET NULL", name="mcp_tool_invocations_tool_id_fkey"), nullable=True),
        sa.Column("agent_run_id", UUID(as_uuid=True), sa.ForeignKey("agent_runs.id", ondelete="CASCADE", name="mcp_tool_invocations_agent_run_id_fkey"), nullable=False),
        sa.Column("arguments_json", JSONB, nullable=False, server_default=sa.text("'{}'::jsonb")),
        sa.Column("result_json", JSONB, nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("latency_ms", sa.Integer, nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    logger.info("0002.upgrade: table mcp_tool_invocations created")

    # ------------------------------------------------------------------
    # 24. mcp_approvals
    # ------------------------------------------------------------------
    logger.info("0002.upgrade: creating table mcp_approvals")
    op.create_table(
        "mcp_approvals",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()"), nullable=False),
        sa.Column("invocation_id", UUID(as_uuid=True), sa.ForeignKey("mcp_tool_invocations.id", ondelete="CASCADE", name="mcp_approvals_invocation_id_fkey"), nullable=False),
        sa.Column("requested_by", UUID(as_uuid=True), sa.ForeignKey("users.id", name="mcp_approvals_requested_by_fkey"), nullable=True),
        sa.Column("approved_by", UUID(as_uuid=True), sa.ForeignKey("users.id", name="mcp_approvals_approved_by_fkey"), nullable=True),
        sa.Column("status", sa.Text, nullable=False),
        sa.Column("reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    logger.info("0002.upgrade: table mcp_approvals created")

    logger.info("0002.upgrade.done: 24 tables + vector extension + HNSW index + 2 btree indexes + 2 CHECK constraints created")


def downgrade() -> None:
    """Drop all 24 AI/Chat/RAG/MCP/Agent tables in reverse FK-safe order.

    Drops tables 24 → 1 (children before parents) to satisfy FK constraints.
    Extension `vector` is NOT dropped (D-VECTOR: idempotent, shared with future
    migrations; same rationale as D2-PGCRYPTO in migration 0001).

    CAUTION: This downgrade will CASCADE-delete all data in these 24 tables.
    NEVER run in production without a backup. Auth tables (0001) are preserved.
    """
    logger.info("0002.downgrade.start: dropping 24 AI/Chat/RAG/MCP/Agent tables in reverse FK-safe order")

    # MCP+Agents domain — reverse order (24 → 15)
    op.drop_table("mcp_approvals")
    logger.info("0002.downgrade: dropped mcp_approvals")
    op.drop_table("mcp_tool_invocations")
    logger.info("0002.downgrade: dropped mcp_tool_invocations")
    op.drop_table("agent_runs")
    logger.info("0002.downgrade: dropped agent_runs")
    op.drop_table("mcp_agent_bindings")
    logger.info("0002.downgrade: dropped mcp_agent_bindings")
    op.drop_table("agents")
    logger.info("0002.downgrade: dropped agents")
    op.drop_table("mcp_prompts")
    logger.info("0002.downgrade: dropped mcp_prompts")
    op.drop_table("mcp_resources")
    logger.info("0002.downgrade: dropped mcp_resources")
    op.drop_table("mcp_tools")
    logger.info("0002.downgrade: dropped mcp_tools")
    op.drop_table("mcp_credentials")
    logger.info("0002.downgrade: dropped mcp_credentials")
    op.drop_table("mcp_servers")
    logger.info("0002.downgrade: dropped mcp_servers")

    # RAG domain — reverse order (14 → 9)
    op.drop_table("vectorization_jobs")
    logger.info("0002.downgrade: dropped vectorization_jobs")
    op.drop_index("messages_conversation_created_idx", table_name="messages")
    op.drop_index("conversations_user_updated_idx", table_name="conversations")
    logger.info("0002.downgrade: dropped performance indexes")
    # HNSW index dropped with the table via raw SQL
    op.execute("DROP TABLE IF EXISTS document_embeddings")
    logger.info("0002.downgrade: dropped document_embeddings (HNSW index cascade-dropped)")
    op.drop_table("document_chunks")
    logger.info("0002.downgrade: dropped document_chunks")
    op.drop_table("document_versions")
    logger.info("0002.downgrade: dropped document_versions")
    op.drop_table("documents")
    logger.info("0002.downgrade: dropped documents")
    op.drop_table("rag_collections")
    logger.info("0002.downgrade: dropped rag_collections")

    # Admin AI domain — reverse order (8 → 4)
    op.drop_table("llm_usage_logs")
    logger.info("0002.downgrade: dropped llm_usage_logs")
    op.drop_table("ai_model_tests")
    logger.info("0002.downgrade: dropped ai_model_tests")
    op.drop_table("ai_models")
    logger.info("0002.downgrade: dropped ai_models")
    op.drop_table("ai_provider_credentials")
    logger.info("0002.downgrade: dropped ai_provider_credentials")
    op.drop_table("ai_providers")
    logger.info("0002.downgrade: dropped ai_providers")

    # Chat domain — reverse order (3 → 1)
    op.drop_table("message_citations")
    logger.info("0002.downgrade: dropped message_citations")
    op.drop_table("messages")
    logger.info("0002.downgrade: dropped messages")
    op.drop_table("conversations")
    logger.info("0002.downgrade: dropped conversations")

    # D-VECTOR: NOT dropping `vector` extension (idempotent, shared with future migrations)
    logger.info("0002.downgrade.done: 24 tables dropped; vector extension preserved (D-VECTOR)")
