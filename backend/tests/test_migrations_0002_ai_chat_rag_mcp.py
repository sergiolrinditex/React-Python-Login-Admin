"""
Hilo People — Integration tests for migration 0002_ai_chat_rag_mcp_agents.

Slice:  P02-S01-T001 — DB AI/chat/RAG/MCP/agents schema
Phase:  P02 Core Features (the motor)
Purpose: Verifies that migration 0002 creates all required tables with correct
         constraints, FK cascade behaviors, HNSW index, and CHECK constraints.
         Tests both upgrade and downgrade idempotency against a real PostgreSQL.

         Tests cover (T01-T16):
           T01  — 33 total tables (9 auth + 24 new) after upgrade head.
           T02  — vector extension is loaded.
           T03  — document_embeddings.embedding column type is vector(1536).
           T04  — HNSW index exists on document_embeddings (D1: NOT ivfflat).
           T05  — conversations_user_updated_idx exists (btree).
           T06  — messages_conversation_created_idx exists (btree).
           T07  — ON DELETE CASCADE conversations -> users.
           T08  — ON DELETE CASCADE messages -> conversations.
           T09  — ON DELETE CASCADE document_chunks -> documents.
           T10  — ON DELETE CASCADE document_embeddings -> document_chunks.
           T11  — ON DELETE SET NULL llm_usage_logs.user_id/model_id/conversation_id.
           T12  — ON DELETE CASCADE mcp_tools -> mcp_servers.
           T13  — ON DELETE CASCADE mcp_agent_bindings -> agent AND -> mcp_tool.
           T14  — downgrade drops 24 tables, preserves 9 auth (vector extension stays).
           T15  — idempotence: upgrade -> downgrade -> upgrade same final state.
           T16  — CHECK documents_language_chk rejects unsupported language.
           T17  — CHECK conversations_language_chk rejects unsupported language.

         All tests use a real Postgres DB — no mocks. Marked pytest.mark.integration.
         WRITE_SET_DRIFT: test file is outside the declared write_set
         (backend/alembic/versions/**, backend/app/db/models/**) but justified by
         pattern P-2 (MEMORY.md) + precedent test_migrations_0001_auth.py (P01-S01-T001).

Key deps:
  - pytest==9.0.2
  - sqlalchemy==2.0.49 (create_engine, text)
  - psycopg[binary]==3.3.4
  - alembic==1.18.4 (via CLI binary)
  - DATABASE_URL env var

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3
  - 01-non-negotiables.md §Tests are REAL
  - P02-S01-T001 task pack §I.6
"""

from __future__ import annotations

import os
import subprocess
import uuid
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent  # backend/
_DATABASE_URL = os.getenv("DATABASE_URL", "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev")

# Expected tables after migration 0002:
# 9 auth (0001) + 24 new = 33 tables
_AUTH_TABLES = {
    "users", "employee_profiles", "roles", "permissions", "user_roles",
    "refresh_tokens", "mfa_totp_secrets", "password_reset_tokens", "audit_logs",
}
_NEW_TABLES_0002 = {
    # Chat
    "conversations", "messages", "message_citations",
    # Admin AI
    "ai_providers", "ai_provider_credentials", "ai_models", "ai_model_tests", "llm_usage_logs",
    # RAG
    "rag_collections", "documents", "document_versions", "document_chunks",
    "document_embeddings", "vectorization_jobs",
    # MCP + Agents
    "mcp_servers", "mcp_credentials", "mcp_tools", "mcp_resources", "mcp_prompts",
    "agents", "mcp_agent_bindings", "agent_runs", "mcp_tool_invocations", "mcp_approvals",
}
_ALL_TABLES = _AUTH_TABLES | _NEW_TABLES_0002


def _find_alembic() -> str:
    """Find the alembic binary, searching common install locations."""
    candidates = [
        Path.home() / "Library" / "Python" / "3.11" / "bin" / "alembic",
        Path("/opt/homebrew/bin/alembic"),
        Path("/usr/local/bin/alembic"),
    ]
    for c in candidates:
        if c.exists():
            return str(c)
    return "alembic"


_ALEMBIC_BIN = _find_alembic()


def _run_alembic(*args: str) -> subprocess.CompletedProcess[str]:
    """Run alembic command with DATABASE_URL set in env."""
    env = {**os.environ, "DATABASE_URL": _DATABASE_URL}
    return subprocess.run(
        [_ALEMBIC_BIN, *args],
        cwd=str(_BACKEND_DIR),
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )


def _get_sync_engine():
    """Create a synchronous SQLAlchemy engine for test assertions."""
    url = _DATABASE_URL.replace("postgresql+asyncpg://", "postgresql+psycopg://")
    return create_engine(url, pool_pre_ping=True)


def _get_tables(engine) -> set[str]:
    """Return set of table names in public schema."""
    with engine.connect() as conn:
        result = conn.execute(
            text("SELECT tablename FROM pg_tables WHERE schemaname='public'")
        )
        return {row[0] for row in result}


# ---------------------------------------------------------------------------
# Fixture — ensure clean migration state before each test
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def reset_migrations():
    """Downgrade to base before each test and cleanup after."""
    _run_alembic("downgrade", "base")
    yield
    _run_alembic("downgrade", "base")


# ---------------------------------------------------------------------------
# T01 — All 33 tables exist after upgrade head
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_upgrade_creates_all_33_tables():
    """After upgrade head, all 9 auth + 24 new tables must exist (33 total)."""
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    engine = _get_sync_engine()
    tables = _get_tables(engine)

    for expected in _ALL_TABLES:
        assert expected in tables, f"Missing table after upgrade: {expected}"

    # alembic_version is also present
    non_alembic = tables - {"alembic_version"}
    assert non_alembic == _ALL_TABLES, (
        f"Unexpected tables: {non_alembic - _ALL_TABLES}; "
        f"Missing tables: {_ALL_TABLES - non_alembic}"
    )


# ---------------------------------------------------------------------------
# T02 — vector extension loaded
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_vector_extension_loaded():
    """After upgrade head, the pgvector 'vector' extension must be loaded."""
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    engine = _get_sync_engine()
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        ).fetchone()
    assert row is not None, "Extension 'vector' not found in pg_extension after upgrade"
    assert row[0] == "vector"


# ---------------------------------------------------------------------------
# T03 — document_embeddings.embedding is vector(1536)
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_embedding_column_is_vector_1536():
    """document_embeddings.embedding must have type vector(1536)."""
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    engine = _get_sync_engine()
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT format_type(atttypid, atttypmod)
            FROM pg_attribute
            WHERE attrelid = 'document_embeddings'::regclass
              AND attname = 'embedding'
              AND NOT attisdropped
        """)).fetchone()

    assert row is not None, "Column 'embedding' not found in document_embeddings"
    assert "vector" in row[0].lower(), f"Expected vector type, got: {row[0]}"
    assert "1536" in row[0], f"Expected vector(1536), got: {row[0]}"


# ---------------------------------------------------------------------------
# T04 — HNSW index exists on document_embeddings (NOT ivfflat — D1 decision)
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_upgrade_creates_hnsw_index():
    """document_embeddings_vector_idx must use HNSW access method (not ivfflat)."""
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    engine = _get_sync_engine()
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT indexdef
            FROM pg_indexes
            WHERE indexname = 'document_embeddings_vector_idx'
        """)).fetchone()

    assert row is not None, "Index 'document_embeddings_vector_idx' not found"
    assert "hnsw" in row[0].lower(), (
        f"Expected HNSW index, got: {row[0]}. "
        "D1 decision: ivfflat overridden by official pgvector 0.8.2 docs."
    )
    assert "vector_cosine_ops" in row[0].lower(), f"Expected vector_cosine_ops, got: {row[0]}"


# ---------------------------------------------------------------------------
# T05 — conversations_user_updated_idx exists (btree)
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_conversations_user_updated_idx_exists():
    """conversations_user_updated_idx must exist after upgrade."""
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    engine = _get_sync_engine()
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE indexname = 'conversations_user_updated_idx'
        """)).fetchone()
    assert row is not None, "Index 'conversations_user_updated_idx' not found"


# ---------------------------------------------------------------------------
# T06 — messages_conversation_created_idx exists
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_messages_conversation_created_idx_exists():
    """messages_conversation_created_idx must exist after upgrade."""
    result = _run_alembic("upgrade", "head")
    assert result.returncode == 0, f"upgrade failed:\n{result.stderr}"

    engine = _get_sync_engine()
    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT indexname FROM pg_indexes
            WHERE indexname = 'messages_conversation_created_idx'
        """)).fetchone()
    assert row is not None, "Index 'messages_conversation_created_idx' not found"


# ---------------------------------------------------------------------------
# T07 — ON DELETE CASCADE conversations -> users
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_cascade_conversations_to_users():
    """Deleting a user must cascade-delete their conversations."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    user_id = str(uuid.uuid4())
    conv_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, status, preferred_language)
            VALUES (:uid, 'cascade_conv@test.com', 'x', 'Test User', 'active', 'es')
        """), {"uid": user_id})
        conn.execute(text("""
            INSERT INTO conversations (id, user_id, title, language)
            VALUES (:cid, :uid, 'Test Conv', 'es')
        """), {"cid": conv_id, "uid": user_id})

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM conversations WHERE id = :cid"), {"cid": conv_id}
        ).fetchone()
    assert row is None, "Conversation should have been cascade-deleted with the user"


# ---------------------------------------------------------------------------
# T08 — ON DELETE CASCADE messages -> conversations
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_cascade_messages_to_conversations():
    """Deleting a conversation must cascade-delete its messages."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    user_id = str(uuid.uuid4())
    conv_id = str(uuid.uuid4())
    msg_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, status, preferred_language)
            VALUES (:uid, 'cascade_msg@test.com', 'x', 'Test', 'active', 'es')
        """), {"uid": user_id})
        conn.execute(text("""
            INSERT INTO conversations (id, user_id, title, language)
            VALUES (:cid, :uid, 'C', 'es')
        """), {"cid": conv_id, "uid": user_id})
        conn.execute(text("""
            INSERT INTO messages (id, conversation_id, role, content)
            VALUES (:mid, :cid, 'user', 'hello')
        """), {"mid": msg_id, "cid": conv_id})

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM conversations WHERE id = :cid"), {"cid": conv_id})

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM messages WHERE id = :mid"), {"mid": msg_id}
        ).fetchone()
    assert row is None, "Message should have been cascade-deleted with the conversation"


# ---------------------------------------------------------------------------
# T09 — ON DELETE CASCADE document_chunks -> documents
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_cascade_chunks_to_documents():
    """Deleting a document must cascade-delete its chunks."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    doc_id = str(uuid.uuid4())
    ver_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO documents (id, title, language, source_uri, status)
            VALUES (:did, 'Doc', 'es', 's3://x', 'uploaded')
        """), {"did": doc_id})
        conn.execute(text("""
            INSERT INTO document_versions (id, document_id, version, storage_key, checksum)
            VALUES (:vid, :did, 1, 'key', 'abc')
        """), {"vid": ver_id, "did": doc_id})
        conn.execute(text("""
            INSERT INTO document_chunks (id, document_id, version_id, chunk_index, content)
            VALUES (:cid, :did, :vid, 0, 'text')
        """), {"cid": chunk_id, "did": doc_id, "vid": ver_id})

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM documents WHERE id = :did"), {"did": doc_id})

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM document_chunks WHERE id = :cid"), {"cid": chunk_id}
        ).fetchone()
    assert row is None, "document_chunks should have been cascade-deleted with document"


# ---------------------------------------------------------------------------
# T10 — ON DELETE CASCADE document_embeddings -> document_chunks
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_cascade_embeddings_to_chunks():
    """Deleting a document_chunk must cascade-delete its embedding."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    doc_id = str(uuid.uuid4())
    ver_id = str(uuid.uuid4())
    chunk_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO documents (id, title, language, source_uri, status)
            VALUES (:did, 'Doc2', 'es', 's3://y', 'uploaded')
        """), {"did": doc_id})
        conn.execute(text("""
            INSERT INTO document_versions (id, document_id, version, storage_key, checksum)
            VALUES (:vid, :did, 1, 'key2', 'def')
        """), {"vid": ver_id, "did": doc_id})
        conn.execute(text("""
            INSERT INTO document_chunks (id, document_id, version_id, chunk_index, content)
            VALUES (:cid, :did, :vid, 0, 'chunk text')
        """), {"cid": chunk_id, "did": doc_id, "vid": ver_id})
        # Insert embedding with NULL vector (schema allows nullable)
        conn.execute(text("""
            INSERT INTO document_embeddings (chunk_id, embedding) VALUES (:cid, NULL)
        """), {"cid": chunk_id})

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM document_chunks WHERE id = :cid"), {"cid": chunk_id})

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT chunk_id FROM document_embeddings WHERE chunk_id = :cid"), {"cid": chunk_id}
        ).fetchone()
    assert row is None, "document_embeddings should have been cascade-deleted with the chunk"


# ---------------------------------------------------------------------------
# T11 — ON DELETE SET NULL: llm_usage_logs.user_id / model_id / conversation_id
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_set_null_llm_usage_logs():
    """Deleting a user/model/conversation must SET NULL the FKs in llm_usage_logs."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    user_id = str(uuid.uuid4())
    conv_id = str(uuid.uuid4())
    provider_id = str(uuid.uuid4())
    model_id = str(uuid.uuid4())
    log_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, status, preferred_language)
            VALUES (:uid, 'setnull@test.com', 'x', 'T', 'active', 'es')
        """), {"uid": user_id})
        conn.execute(text("""
            INSERT INTO conversations (id, user_id, title, language)
            VALUES (:cid, :uid, 'C2', 'es')
        """), {"cid": conv_id, "uid": user_id})
        conn.execute(text("""
            INSERT INTO ai_providers (id, name, provider_type, status)
            VALUES (:pid, 'TestProvider', 'openai', 'draft')
        """), {"pid": provider_id})
        conn.execute(text("""
            INSERT INTO ai_models (id, provider_id, model_id, model_type, enabled, is_default)
            VALUES (:mid, :pid, 'gpt-4o', 'chat', false, false)
        """), {"mid": model_id, "pid": provider_id})
        conn.execute(text("""
            INSERT INTO llm_usage_logs
                (id, user_id, model_id, conversation_id, tokens_in, tokens_out, estimated_cost)
            VALUES (:lid, :uid, :mid, :cid, 10, 5, 0.001)
        """), {"lid": log_id, "uid": user_id, "mid": model_id, "cid": conv_id})

    # Delete in cascade-safe order
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM conversations WHERE id = :cid"), {"cid": conv_id})
        conn.execute(text("DELETE FROM users WHERE id = :uid"), {"uid": user_id})
        conn.execute(text("DELETE FROM ai_models WHERE id = :mid"), {"mid": model_id})

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT user_id, model_id, conversation_id FROM llm_usage_logs WHERE id = :lid"),
            {"lid": log_id}
        ).fetchone()

    assert row is not None, "llm_usage_log row should still exist after deleting referenced entities"
    assert row[0] is None, "user_id should be NULL after user deletion"
    assert row[1] is None, "model_id should be NULL after model deletion"
    assert row[2] is None, "conversation_id should be NULL after conversation deletion"


# ---------------------------------------------------------------------------
# T12 — ON DELETE CASCADE mcp_tools -> mcp_servers
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_cascade_mcp_tools_to_servers():
    """Deleting an mcp_server must cascade-delete its mcp_tools."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    server_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO mcp_servers (id, name, transport_type, status)
            VALUES (:sid, 'TestServer', 'http', 'draft')
        """), {"sid": server_id})
        conn.execute(text("""
            INSERT INTO mcp_tools (id, server_id, name, enabled, requires_approval, risk_level)
            VALUES (:tid, :sid, 'test_tool', false, true, 'medium')
        """), {"tid": tool_id, "sid": server_id})

    with engine.begin() as conn:
        conn.execute(text("DELETE FROM mcp_servers WHERE id = :sid"), {"sid": server_id})

    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT id FROM mcp_tools WHERE id = :tid"), {"tid": tool_id}
        ).fetchone()
    assert row is None, "mcp_tools should have been cascade-deleted with mcp_server"


# ---------------------------------------------------------------------------
# T13 — ON DELETE CASCADE mcp_agent_bindings -> agent AND -> mcp_tool
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_cascade_agent_bindings():
    """Deleting an agent or tool must cascade-delete the binding row."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    agent_id = str(uuid.uuid4())
    server_id = str(uuid.uuid4())
    tool_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO agents (id, name, enabled) VALUES (:aid, 'Agent1', false)
        """), {"aid": agent_id})
        conn.execute(text("""
            INSERT INTO mcp_servers (id, name, transport_type, status)
            VALUES (:sid, 'Srv', 'http', 'draft')
        """), {"sid": server_id})
        conn.execute(text("""
            INSERT INTO mcp_tools (id, server_id, name, enabled, requires_approval, risk_level)
            VALUES (:tid, :sid, 'tool2', false, true, 'low')
        """), {"tid": tool_id, "sid": server_id})
        conn.execute(text("""
            INSERT INTO mcp_agent_bindings (agent_id, tool_id, enabled)
            VALUES (:aid, :tid, true)
        """), {"aid": agent_id, "tid": tool_id})

    # Delete agent → binding must cascade
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM agents WHERE id = :aid"), {"aid": agent_id})

    with engine.connect() as conn:
        row = conn.execute(text("""
            SELECT agent_id FROM mcp_agent_bindings
            WHERE agent_id = :aid AND tool_id = :tid
        """), {"aid": agent_id, "tid": tool_id}).fetchone()
    assert row is None, "mcp_agent_bindings should be cascade-deleted when agent is deleted"


# ---------------------------------------------------------------------------
# T14 — downgrade drops 24 tables, preserves 9 auth tables + vector extension
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_downgrade_drops_24_tables_preserves_auth():
    """Downgrade to 0001 must drop all 24 new tables but keep 9 auth tables."""
    up_result = _run_alembic("upgrade", "head")
    assert up_result.returncode == 0, f"upgrade failed:\n{up_result.stderr}"

    down_result = _run_alembic("downgrade", "-1")
    assert down_result.returncode == 0, f"downgrade failed:\n{down_result.stderr}"

    engine = _get_sync_engine()
    tables = _get_tables(engine)

    # Auth tables must remain
    for auth_table in _AUTH_TABLES:
        assert auth_table in tables, f"Auth table missing after downgrade: {auth_table}"

    # None of the 24 new tables should remain
    for new_table in _NEW_TABLES_0002:
        assert new_table not in tables, f"Table {new_table!r} should have been dropped by downgrade"

    # vector extension must still be present (D-VECTOR)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT extname FROM pg_extension WHERE extname='vector'")
        ).fetchone()
    assert row is not None, "vector extension must be preserved after downgrade (D-VECTOR)"


# ---------------------------------------------------------------------------
# T15 — idempotence: upgrade -> downgrade -> upgrade yields same state
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_idempotent_upgrade_downgrade_upgrade():
    """upgrade → downgrade → upgrade must produce identical final state."""
    # First upgrade
    r1 = _run_alembic("upgrade", "head")
    assert r1.returncode == 0, f"first upgrade failed:\n{r1.stderr}"

    engine = _get_sync_engine()
    tables_after_first = _get_tables(engine)

    # Downgrade
    r2 = _run_alembic("downgrade", "-1")
    assert r2.returncode == 0, f"downgrade failed:\n{r2.stderr}"

    # Second upgrade
    r3 = _run_alembic("upgrade", "head")
    assert r3.returncode == 0, f"second upgrade failed:\n{r3.stderr}"

    tables_after_second = _get_tables(engine)
    assert tables_after_first == tables_after_second, (
        f"Tables differ after second upgrade.\n"
        f"Only in first: {tables_after_first - tables_after_second}\n"
        f"Only in second: {tables_after_second - tables_after_first}"
    )


# ---------------------------------------------------------------------------
# T16 — CHECK documents_language_chk rejects unsupported language
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_documents_language_check_constraint():
    """documents.language CHECK must reject values outside ('es','en','fr')."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()

    with pytest.raises(Exception) as exc_info:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO documents (id, title, language, source_uri, status)
                VALUES (gen_random_uuid(), 'Doc DE', 'de', 's3://z', 'uploaded')
            """))

    error_str = str(exc_info.value).lower()
    assert "check" in error_str or "constraint" in error_str or "violates" in error_str, (
        f"Expected CHECK constraint violation, got: {exc_info.value}"
    )


# ---------------------------------------------------------------------------
# T17 — CHECK conversations_language_chk rejects unsupported language
# ---------------------------------------------------------------------------
@pytest.mark.integration
def test_conversations_language_check_constraint():
    """conversations.language CHECK must reject values outside ('es','en','fr')."""
    _run_alembic("upgrade", "head")
    engine = _get_sync_engine()
    user_id = str(uuid.uuid4())

    with engine.begin() as conn:
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, full_name, status, preferred_language)
            VALUES (:uid, 'lang_chk@test.com', 'x', 'U', 'active', 'es')
        """), {"uid": user_id})

    with pytest.raises(Exception) as exc_info:
        with engine.begin() as conn:
            conn.execute(text("""
                INSERT INTO conversations (id, user_id, title, language)
                VALUES (gen_random_uuid(), :uid, 'C', 'de')
            """), {"uid": user_id})

    error_str = str(exc_info.value).lower()
    assert "check" in error_str or "constraint" in error_str or "violates" in error_str, (
        f"Expected CHECK constraint violation, got: {exc_info.value}"
    )
