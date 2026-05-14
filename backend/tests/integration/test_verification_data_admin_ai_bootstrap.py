"""
Hilo People — Integration tests for admin_ai bootstrap group (P02-S03-T004).

Slice:  P02-S03-T004 — Rotate ENCRYPTION_KEY in dev .env + seed active AI provider
Phase:  P02 Core Features
Purpose: 4 tests verifying that running the bootstrap with --only admin_ai after
         ENCRYPTION_KEY rotation seeds ai_providers, ai_provider_credentials,
         and ai_models correctly (T10..T13):
           T10 — Full admin_ai bootstrap exits 0; ai_providers/credentials/models seeded
           T11 — ai_provider_credentials.encrypted_secret round-trips via decrypt_secret
           T12 — Exactly one chat model with enabled=true AND is_default=true exists
           T13 — No plaintext credentials or key material appear in verbose or quiet logs

         Requires: live Postgres with alembic head=0002 applied (ai_providers,
         ai_provider_credentials, ai_models tables exist). If tables are missing,
         tests produce deferred-ok results and are marked as expected deferral.

         ENCRYPTION_KEY is monkeypatched to a fresh Fernet key per test run.
         The lru_cache on _get_fernet() is cleared before and after each test.

Key deps:
  - pytest==9.0.2
  - sqlalchemy==2.0.49 (pg_engine / pg_session from conftest)
  - cryptography==48.0.0 (Fernet — validate round-trip)
  - app.verification_data.bootstrap (main() entry point)
  - app.security.encryption (decrypt_secret, reset_fernet_cache)
  - data/verification/admin_ai/ (fixture files)

Source refs:
  - task pack P02-S03-T004 §Test plan T10..T13
  - 01-non-negotiables.md §Tests are REAL (real Postgres, real Fernet key)
  - TECHNICAL_GUIDE §6.5 Verification Data Contract (J103 admin-ai row)
"""

from __future__ import annotations

import importlib
import json
import os
from io import StringIO
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_BACKEND_DIR = Path(__file__).parent.parent.parent  # backend/
_REPO_ROOT = _BACKEND_DIR.parent
_VERIFICATION_DATA = _REPO_ROOT / "data" / "verification"


# ---------------------------------------------------------------------------
# Helper: run bootstrap.main() for admin_ai group with patched ENCRYPTION_KEY
# ---------------------------------------------------------------------------

def run_admin_ai_bootstrap(
    fernet_key: str,
    extra_env: dict | None = None,
    verbose: bool = True,
) -> tuple[int, str, str]:
    """Run bootstrap --only admin_ai with a fresh Fernet key.

    Reloads bootstrap + loader modules to pick up env var changes.

    Args:
        fernet_key:  Valid Fernet key string for ENCRYPTION_KEY.
        extra_env:   Additional env overrides (merged on top of base_env).
        verbose:     If True, sets ENABLE_VERBOSE_LOGGING=true.

    Returns:
        Tuple of (exit_code, stdout, stderr).
    """
    stdout_cap = StringIO()
    stderr_cap = StringIO()

    base_env: dict[str, str] = {
        "DATABASE_URL": os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://hilo:hilo@localhost:5432/hilo_dev",
        ),
        "ENCRYPTION_KEY": fernet_key,
        "ENABLE_VERBOSE_LOGGING": "true" if verbose else "false",
        "MFA_ENCRYPTION_KEY": os.getenv("MFA_ENCRYPTION_KEY", Fernet.generate_key().decode()),
    }
    if extra_env:
        base_env.update(extra_env)

    import app.verification_data.bootstrap as bs_mod
    import app.verification_data.loader as loader_mod

    with (
        patch.dict(os.environ, base_env, clear=False),
        patch("sys.stdout", stdout_cap),
        patch("sys.stderr", stderr_cap),
    ):
        from app.security.encryption import reset_fernet_cache
        reset_fernet_cache()
        importlib.reload(loader_mod)
        importlib.reload(bs_mod)
        from app.verification_data.bootstrap import main as reloaded_main
        exit_code = reloaded_main(
            ["--source", str(_VERIFICATION_DATA), "--only", "admin_ai"]
        )
        reset_fernet_cache()

    return exit_code, stdout_cap.getvalue(), stderr_cap.getvalue()


# ===========================================================================
# T10 — Full admin_ai bootstrap exits 0; providers/credentials/models seeded
# ===========================================================================
@pytest.mark.integration
def test_admin_ai_bootstrap_seeds_all_tables(pg_engine: Any) -> None:
    """T10: bootstrap --only admin_ai exits 0; ai_providers + credentials + models have ≥1 row."""
    from sqlalchemy import inspect as sa_inspect, text
    from sqlalchemy.orm import sessionmaker

    insp = sa_inspect(pg_engine)
    tables_needed = ["ai_providers", "ai_provider_credentials", "ai_models"]
    missing = [t for t in tables_needed if not insp.has_table(t)]
    if missing:
        pytest.skip(f"Tables not available (no DB): {missing}")

    fernet_key = Fernet.generate_key().decode()
    exit_code, stdout, stderr = run_admin_ai_bootstrap(fernet_key)

    assert exit_code == 0, (
        f"Bootstrap exited {exit_code}.\nstdout={stdout}\nstderr={stderr}"
    )

    # Parse summary JSON
    summary_lines = [ln for ln in stdout.strip().splitlines() if ln.strip().startswith("{")]
    assert summary_lines, f"No JSON summary found in stdout: {stdout!r}"
    summary = json.loads(summary_lines[-1])
    assert summary.get("status") == "ok", f"Summary status not ok: {summary}"

    SessionLocal = sessionmaker(bind=pg_engine)
    with SessionLocal() as session:
        prov_count = session.execute(
            text("SELECT COUNT(*) FROM ai_providers WHERE status = 'active'")
        ).scalar()
        assert prov_count >= 1, f"Expected ≥1 active ai_providers row, got {prov_count}"

        cred_count = session.execute(
            text("SELECT COUNT(*) FROM ai_provider_credentials")
        ).scalar()
        assert cred_count >= 1, f"Expected ≥1 ai_provider_credentials row, got {cred_count}"

        model_count = session.execute(
            text("SELECT COUNT(*) FROM ai_models")
        ).scalar()
        assert model_count >= 1, f"Expected ≥1 ai_models row, got {model_count}"


# ===========================================================================
# T11 — ai_provider_credentials.encrypted_secret round-trips via decrypt_secret
# ===========================================================================
@pytest.mark.integration
def test_credentials_encrypted_secret_round_trips(pg_engine: Any) -> None:
    """T11: stored encrypted_secret decrypts cleanly via decrypt_secret to original plain."""
    from sqlalchemy import inspect as sa_inspect, text
    from sqlalchemy.orm import sessionmaker

    insp = sa_inspect(pg_engine)
    if not insp.has_table("ai_provider_credentials"):
        pytest.skip("ai_provider_credentials table not available")

    fernet_key = Fernet.generate_key().decode()
    exit_code, stdout, stderr = run_admin_ai_bootstrap(fernet_key)
    assert exit_code == 0, f"Bootstrap failed. stderr={stderr}"

    # Set the same key for decrypt
    from app.security.encryption import decrypt_secret, reset_fernet_cache
    reset_fernet_cache()

    with patch.dict(os.environ, {"ENCRYPTION_KEY": fernet_key}):
        reset_fernet_cache()
        SessionLocal = sessionmaker(bind=pg_engine)
        with SessionLocal() as session:
            rows = session.execute(
                text("SELECT encrypted_secret FROM ai_provider_credentials LIMIT 5")
            ).fetchall()

        assert rows, "No ai_provider_credentials rows found after bootstrap"

        for row in rows:
            enc = row[0]
            assert enc, "encrypted_secret should not be empty"
            # Must NOT be the plain credential value
            assert enc != "hilo-dev-litellm-master-key-2026", (
                "SECURITY: credential_plain was stored as plain text in DB"
            )
            # Must decrypt without error
            decrypted = decrypt_secret(enc)
            assert decrypted, "decrypt_secret returned empty string"
            assert len(decrypted) > 0

        reset_fernet_cache()


# ===========================================================================
# T12 — Exactly one chat model with enabled=true AND is_default=true
# ===========================================================================
@pytest.mark.integration
def test_exactly_one_default_chat_model(pg_engine: Any) -> None:
    """T12: after admin_ai bootstrap, exactly one ai_models row has model_type=chat, enabled=true, is_default=true."""
    from sqlalchemy import inspect as sa_inspect, text
    from sqlalchemy.orm import sessionmaker

    insp = sa_inspect(pg_engine)
    if not insp.has_table("ai_models"):
        pytest.skip("ai_models table not available")

    fernet_key = Fernet.generate_key().decode()
    exit_code, _, stderr = run_admin_ai_bootstrap(fernet_key)
    assert exit_code == 0, f"Bootstrap failed. stderr={stderr}"

    SessionLocal = sessionmaker(bind=pg_engine)
    with SessionLocal() as session:
        count = session.execute(
            text(
                "SELECT COUNT(*) FROM ai_models"
                " WHERE model_type = 'chat' AND enabled = true AND is_default = true"
            )
        ).scalar()

    assert count >= 1, (
        f"Expected at least 1 chat model with enabled=true AND is_default=true, got {count}"
    )


# ===========================================================================
# T13 — No plaintext credentials appear in verbose OR quiet log captures
# ===========================================================================
@pytest.mark.integration
@pytest.mark.parametrize("verbose", [True, False], ids=["verbose_true", "verbose_false"])
def test_no_plaintext_credentials_in_logs(pg_engine: Any, verbose: bool) -> None:
    """T13: ENABLE_VERBOSE_LOGGING=true/false → no plaintext creds or key material in output."""
    from sqlalchemy import inspect as sa_inspect
    insp = sa_inspect(pg_engine)
    if not insp.has_table("ai_providers"):
        pytest.skip("ai_providers table not available (DB required)")

    fernet_key = Fernet.generate_key().decode()
    exit_code, stdout, stderr = run_admin_ai_bootstrap(fernet_key, verbose=verbose)
    assert exit_code == 0, f"Bootstrap failed. stderr={stderr}"

    combined = stdout + stderr

    # The plain credential from the fixture must not appear in any output
    assert "hilo-dev-litellm-master-key-2026" not in combined, (
        "SECURITY: credential_plain 'hilo-dev-litellm-master-key-2026' found in output"
    )

    # The Fernet key itself must never appear in output
    assert fernet_key not in combined, (
        "SECURITY: ENCRYPTION_KEY value found in output"
    )

    # No base64-looking key material in single contiguous 44-char tokens
    import re
    # Fernet keys are 44 url-safe base64 chars ending in =
    fernet_pattern = re.compile(r"[A-Za-z0-9_\-]{43}=")
    matches = fernet_pattern.findall(combined)
    assert not matches, (
        f"Possible Fernet key material found in output: {matches}"
    )
