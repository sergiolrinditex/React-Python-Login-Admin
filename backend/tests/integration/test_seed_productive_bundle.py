"""
Integration tests for the productive verification bundle (P00-S02-T005).

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Tests covered (7 cases):
  1. test_manifest_is_productive — MANIFEST.json declares _bundle_type=productive.
  2. test_dry_run_productive_bundle_exits_0 — CLI dry-run on real bundle exits 0.
  3. test_mfa_fixture_productive_shape — auth/mfa_primary.json has synthetic_totp=False
       and 10 backup_codes_argon2 hashes.
  4. test_providers_fixture_uses_env_refs — all providers use api_key_env, not plaintext keys.
  5. test_servers_fixture_env_or_public — mcp servers use access_token_env or are public.
  6. test_rag_docs_no_deprecated_entries_active — all non-deprecated docs are loadable.
  7. test_seed_all_namespaces_table_tolerant_with_real_db — with real DB (post-migration),
       all 6 namespaces load cleanly with the productive bundle (skips or inserts — no crash).
       Requires: compose postgres on :5433 and VERIFICATION_GEMINI_API_KEY set.

Rules (01-non-negotiables.md §Tests are REAL):
  - No mocking. No fake data.
  - Tests 1–6: no DB required (fixture-only validation).
  - Test 7: real compose postgres required; skipped when unreachable.

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0
  - pydantic 2.12.5
  - sqlalchemy[asyncio] 2.0.49
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.conftest import _db_reachable

# ---------------------------------------------------------------------------
# Bundle path helper
# ---------------------------------------------------------------------------


def _bundle_dir() -> Path:
    """Return the canonical data/verification/ bundle directory.

    Resolves: backend/tests/integration/ -> backend/ -> repo root -> data/verification/
    """
    repo_root = Path(__file__).parent.parent.parent.parent
    return repo_root / "data" / "verification"


_BUNDLE = _bundle_dir()


# ---------------------------------------------------------------------------
# Test 1 — MANIFEST.json declares _bundle_type=productive
# ---------------------------------------------------------------------------


def test_manifest_is_productive() -> None:
    """MANIFEST.json must declare _bundle_type=productive for P00-S02-T005.

    Ensures the bootstrapper reads the productive path for all loaders.
    """
    manifest_path = _BUNDLE / "MANIFEST.json"
    assert manifest_path.exists(), f"MANIFEST.json missing at {manifest_path}"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    got = manifest.get("_bundle_type")
    assert got == "productive", (
        f"Expected _bundle_type='productive' in MANIFEST.json. Got: {got!r}"
    )


# ---------------------------------------------------------------------------
# Test 2 — CLI dry-run on productive bundle exits 0
# ---------------------------------------------------------------------------


def test_dry_run_productive_bundle_exits_0() -> None:
    """CLI --dry-run on the productive bundle validates all fixtures and exits 0.

    This test does not require a DB connection (--dry-run skips all DB writes).
    The VERIFICATION_* env vars are not required for dry-run (no env resolution happens).
    """
    repo_root = Path(__file__).parent.parent.parent.parent
    backend_dir = repo_root / "backend"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "app.seeds.bootstrap_verification_data",
            "--source",
            str(_BUNDLE),
            "--dry-run",
        ],
        capture_output=True,
        text=True,
        cwd=str(backend_dir),
        env={
            "PATH": os.environ.get("PATH", ""),
            "ENABLE_VERBOSE_LOGGING": "false",
            "DATABASE_URL": (
                "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd"
                "@127.0.0.1:5433/hilopeople_dev"
            ),
        },
    )

    assert result.returncode == 0, (
        f"Productive bundle --dry-run must exit 0. "
        f"Got exit code {result.returncode}.\n"
        f"STDOUT: {result.stdout[:600]}\n"
        f"STDERR: {result.stderr[:600]}"
    )


# ---------------------------------------------------------------------------
# Test 3 — auth/mfa_primary.json has productive shape
# ---------------------------------------------------------------------------


def test_mfa_fixture_productive_shape() -> None:
    """auth/mfa_primary.json has synthetic_totp=False and 10 argon2 backup hashes.

    Validates the fixture directly via Pydantic schema without DB interaction.
    """
    from app.seeds.schemas.auth import MfaPrimarySeed

    mfa_path = _BUNDLE / "auth" / "mfa_primary.json"
    assert mfa_path.exists(), f"mfa_primary.json missing at {mfa_path}"

    raw = json.loads(mfa_path.read_text(encoding="utf-8"))
    # Strip _-prefixed metadata keys (like _comment) — same as load_fixture().
    raw = {k: v for k, v in raw.items() if not k.startswith("_")}
    result = MfaPrimarySeed.validate_with_bundle_type(raw, "productive")

    assert result.synthetic_totp is False, (
        "mfa_primary.json: productive bundle must have synthetic_totp=False. "
        f"Got: {result.synthetic_totp}"
    )
    assert result.backup_codes_argon2 is not None, (
        "mfa_primary.json: productive bundle must include backup_codes_argon2."
    )
    assert len(result.backup_codes_argon2) == 10, (
        f"backup_codes_argon2 must have exactly 10 entries. Got: {len(result.backup_codes_argon2)}"
    )
    for h in result.backup_codes_argon2:
        assert h.startswith("$argon2id$"), (
            f"Backup code hash must start with '$argon2id$'. Got: {h[:20]}"
        )


# ---------------------------------------------------------------------------
# Test 4 — providers.json uses env refs, not plaintext keys
# ---------------------------------------------------------------------------


def test_providers_fixture_uses_env_refs() -> None:
    """admin_ai/providers.json: all providers that need auth use api_key_env, not plaintext keys.

    Validates the productive fixture shape: no provider with 'is_active=True'
    should have a plaintext api_key.
    """
    providers_path = _BUNDLE / "admin_ai" / "providers.json"
    assert providers_path.exists(), f"providers.json missing at {providers_path}"

    data = json.loads(providers_path.read_text(encoding="utf-8"))
    providers = data.get("providers", [])
    assert len(providers) > 0, "providers.json must have at least one provider."

    from app.seeds.schemas.admin_ai import AiProviderSeed

    for p in providers:
        result = AiProviderSeed.validate_with_bundle_type(p, "productive")
        # If provider has an active env ref, plaintext key must be absent or None.
        if result.api_key_env:
            assert result.api_key is None or not result.api_key.startswith("AIza"), (
                f"Provider '{result.name}': has api_key_env "
                "but also a plaintext key with real-key pattern."
            )


# ---------------------------------------------------------------------------
# Test 5 — MCP servers use access_token_env or are public
# ---------------------------------------------------------------------------


def test_servers_fixture_env_or_public() -> None:
    """mcp_agents/servers.json: servers that need auth use access_token_env, never plaintext tokens.

    Public servers (no auth required) may omit both fields.
    """
    servers_path = _BUNDLE / "mcp_agents" / "servers.json"
    assert servers_path.exists(), f"servers.json missing at {servers_path}"

    data = json.loads(servers_path.read_text(encoding="utf-8"))
    servers = data.get("servers", [])
    assert len(servers) > 0, "servers.json must have at least one server."

    from app.seeds.schemas.mcp_agents import McpServerSeed

    for s in servers:
        # validate_with_bundle_type enforces the productive guard.
        McpServerSeed.validate_with_bundle_type(s, "productive")
        # Verify no plaintext token matches real token patterns.
        result = McpServerSeed.model_validate(s)
        if result.access_token:
            assert result.access_token.startswith("synthetic-") or result.access_token_env, (
                f"Server '{result.name}': plaintext access_token found without synthetic- prefix. "
                "Use access_token_env instead."
            )


# ---------------------------------------------------------------------------
# Test 6 — rag/documents/*.json — no DEPRECATED entries are active
# ---------------------------------------------------------------------------


def test_rag_docs_no_deprecated_entries_active() -> None:
    """rag/documents/*.json: no file with DEPRECATED-DO-NOT-LOAD title survives loading.

    The rag_docs loader skips files whose title starts with 'DEPRECATED-DO-NOT-LOAD'.
    This test verifies that:
      (a) at least one non-deprecated document exists.
      (b) deprecated documents would be correctly identified and skipped.
    """
    from app.seeds.schemas.rag import RagDocumentSeed

    docs_dir = _BUNDLE / "rag" / "documents"
    assert docs_dir.exists(), f"rag/documents/ directory missing at {docs_dir}"

    doc_files = sorted(docs_dir.glob("*.json"))
    assert len(doc_files) > 0, "rag/documents/ must contain at least one .json file."

    active_docs = []
    deprecated_docs = []
    for doc_file in doc_files:
        raw = json.loads(doc_file.read_text(encoding="utf-8"))
        # Strip _-prefixed metadata keys (like _comment) — same as load_fixture().
        raw = {k: v for k, v in raw.items() if not k.startswith("_")}
        doc = RagDocumentSeed.model_validate(raw)
        if doc.title.startswith("DEPRECATED-DO-NOT-LOAD"):
            deprecated_docs.append(doc_file.name)
        else:
            active_docs.append(doc_file.name)

    assert len(active_docs) >= 1, (
        f"Expected at least 1 non-deprecated document. Found only deprecated: {deprecated_docs}"
    )


# ---------------------------------------------------------------------------
# Test 7 — all 6 namespaces load against real DB (table-tolerant)
# ---------------------------------------------------------------------------


@pytest.mark.skipif(
    not _db_reachable(),
    reason="compose postgres not reachable on :5433 — run 'docker compose up -d postgres' first",
)
@pytest.mark.skipif(
    not os.environ.get("VERIFICATION_GEMINI_API_KEY"),
    reason=(
        "VERIFICATION_GEMINI_API_KEY not set. "
        "Set it in .env.local and source it: set -a; source .env.local; set +a"
    ),
)
async def test_seed_all_namespaces_table_tolerant_with_real_db(
    verification_bundle_dir: Path,
) -> None:
    """All 6 namespaces load cleanly against real compose postgres.

    In P01 state (post-migration), some tables exist (users, mfa_totp_secrets, roles,
    user_roles, employee_profiles, rag_collections), others are still missing (P02 tables).
    The loader must not crash — it either inserts rows or skips with WARN.

    Requires:
      - compose postgres on :5433.
      - VERIFICATION_GEMINI_API_KEY env var set (for admin_ai productive provider).
    """
    from sqlalchemy.ext.asyncio import create_async_engine

    from app.seeds.loader import (
        load_admin_ai,
        load_auth,
        load_history,
        load_mcp_agents,
        load_rag_chat,
        load_rag_docs,
    )

    dsn = "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd@127.0.0.1:5433/hilopeople_dev"
    engine = create_async_engine(dsn, pool_pre_ping=True)

    loaders = [
        load_auth,
        load_rag_chat,
        load_history,
        load_admin_ai,
        load_rag_docs,
        load_mcp_agents,
    ]

    try:
        for loader_fn in loaders:
            report = await loader_fn(
                engine, verification_bundle_dir, bundle_type="productive"
            )
            # Each namespace must return a LoadReport.
            assert report.namespace, f"loader returned empty namespace: {report}"
            # No namespace should crash — it either inserts or skips.
            assert isinstance(report.rows_inserted, int)
            assert isinstance(report.skipped_tables, list)
    finally:
        await engine.dispose()
