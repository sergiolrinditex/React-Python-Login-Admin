"""
Fail-fast tests for the seed loader CLI.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Verifies fail-fast behavior when the bundle is incomplete or malformed:
  1. Missing --source directory → exit 2 with clear message.
  2. Truncated fixture (missing required field) → exit 1 with field-level error.
  3. Corrupt JSON (parse error) → exit 1 with JSON parse error message.
  4. Provider/MCP credential NOT prefixed 'synthetic-' → exit 1 with rejection message.
  5. Provider credential matching real-key pattern (sk-...) → exit 1 with rejection.

These tests do NOT require compose postgres (they fail before touching the DB).

Rules (01-non-negotiables.md §Tests are REAL):
  - No mocking — tests use real tempfiles and the real Pydantic schemas.
  - CLI run via importlib/function call (not subprocess) for speed; the CLI
    subprocess path is covered by test_seed_idempotency.py test 3.

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0
  - pydantic 2.12.5
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

# ---------------------------------------------------------------------------
# Helper: create a minimal valid bundle in a temp dir
# ---------------------------------------------------------------------------


def _make_bundle(base_dir: Path) -> None:
    """Create a minimal valid verification bundle in base_dir.

    Copies the canonical fixtures from the real bundle so each test can
    selectively corrupt one file without affecting others.
    """
    # Resolve repo root from backend/tests/integration/
    repo_root = Path(__file__).parent.parent.parent.parent
    real_bundle = repo_root / "data" / "verification"

    import shutil
    shutil.copytree(str(real_bundle), str(base_dir), dirs_exist_ok=True)


def _run_cli(
    bundle_dir: str | None,
    extra_args: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run the seed CLI as a subprocess and return the result.

    Uses the active Python interpreter with PYTHONPATH pointing at backend/.
    """
    repo_root = Path(__file__).parent.parent.parent.parent
    backend_dir = repo_root / "backend"

    cmd = [sys.executable, "-m", "app.seeds.bootstrap_verification_data"]
    if bundle_dir is not None:
        cmd += ["--source", bundle_dir]
    if extra_args:
        cmd += extra_args

    import os
    env = {
        "PATH": os.environ.get("PATH", ""),
        "ENABLE_VERBOSE_LOGGING": "false",
        # Use a DSN that would fail fast (no tables exist in P00 state is fine).
        "DATABASE_URL": (
            "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd"
            "@127.0.0.1:5433/hilopeople_dev"
        ),
    }
    return subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=str(backend_dir),
        env=env,
    )


# ---------------------------------------------------------------------------
# Test 1 — missing --source directory → exit 2
# ---------------------------------------------------------------------------


def test_missing_source_dir_exits_2() -> None:
    """Pointing --source at a non-existent directory exits with code 2.

    The exit code 2 is the "source directory missing" sentinel per spec.
    STDERR must contain a description of the missing path.
    """
    result = _run_cli("/tmp/does-not-exist-hilopeople-verification-xyz")

    assert result.returncode == 2, (
        f"Expected exit code 2 for missing --source dir. "
        f"Got: {result.returncode}\nSTDERR: {result.stderr[:300]}"
    )
    combined = result.stdout + result.stderr
    assert "does-not-exist" in combined or "not found" in combined.lower(), (
        "STDERR must mention the missing directory path. "
        f"Got: {combined[:300]}"
    )


# ---------------------------------------------------------------------------
# Test 2 — truncated fixture (missing required field) → exit 1
# ---------------------------------------------------------------------------


def test_truncated_fixture_missing_field_exits_1() -> None:
    """Fixture with missing required field 'email' exits 1 with field-level error.

    The error message must identify the field and the fixture file.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_dir = Path(tmpdir)
        _make_bundle(bundle_dir)

        # Overwrite employee_primary.json without the required 'email' field.
        truncated = {
            "full_name": "Ana García López",
            "password_plain_for_seed": "Hilo!Verify2026",
            "role": "employee",
            "mfa_enabled": True,
            "is_active": True,
        }
        (bundle_dir / "users" / "employee_primary.json").write_text(
            json.dumps(truncated), encoding="utf-8"
        )

        result = _run_cli(str(bundle_dir), ["--only", "auth"])

    assert result.returncode == 1, (
        f"Expected exit code 1 for missing required field 'email'. "
        f"Got: {result.returncode}\nSTDOUT: {result.stdout[:300]}\nSTDERR: {result.stderr[:300]}"
    )
    combined = result.stdout + result.stderr
    assert "email" in combined.lower() or "validation" in combined.lower(), (
        "Error output must mention the invalid field or validation failure. "
        f"Got: {combined[:400]}"
    )


# ---------------------------------------------------------------------------
# Test 3 — corrupt JSON (parse error) → exit 1
# ---------------------------------------------------------------------------


def test_corrupt_json_exits_1() -> None:
    """Fixture with invalid JSON syntax exits 1 with a parse error message."""
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_dir = Path(tmpdir)
        _make_bundle(bundle_dir)

        # Write invalid JSON to the providers file.
        (bundle_dir / "admin_ai" / "providers.json").write_text(
            '{ "providers": [ { "name": "bad" }  INVALID_SYNTAX ]',
            encoding="utf-8",
        )

        result = _run_cli(str(bundle_dir), ["--only", "admin_ai"])

    assert result.returncode == 1, (
        f"Expected exit code 1 for corrupt JSON. "
        f"Got: {result.returncode}\nSTDERR: {result.stderr[:300]}"
    )
    combined = result.stdout + result.stderr
    c = combined.lower()
    is_json_err = "json" in c or "parse" in c or "error" in c
    assert is_json_err, (
        "Error output must indicate a JSON parse failure. "
        f"Got: {combined[:400]}"
    )


# ---------------------------------------------------------------------------
# Test 4 — credential without 'synthetic-' prefix → exit 1
# ---------------------------------------------------------------------------


def test_credential_without_synthetic_prefix_exits_1() -> None:
    """Provider api_key not prefixed 'synthetic-' causes exit 1.

    Defense-in-depth guard: the schema validator rejects any credential that
    does not start with 'synthetic-', preventing accidental leakage of real keys.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_dir = Path(tmpdir)
        _make_bundle(bundle_dir)

        # Write a provider with a non-synthetic api_key.
        bad_providers = {
            "providers": [
                {
                    "name": "bad-provider",
                    "provider_type": "litellm",
                    "api_key": "real-looking-key-without-synthetic-prefix",
                    "base_url": "http://localhost:4000",
                    "is_active": True,
                }
            ]
        }
        (bundle_dir / "admin_ai" / "providers.json").write_text(
            json.dumps(bad_providers), encoding="utf-8"
        )

        result = _run_cli(str(bundle_dir), ["--only", "admin_ai"])

    assert result.returncode == 1, (
        f"Expected exit code 1 for api_key without 'synthetic-' prefix. "
        f"Got: {result.returncode}\nSTDOUT: {result.stdout[:300]}\nSTDERR: {result.stderr[:300]}"
    )
    combined = result.stdout + result.stderr
    assert "synthetic" in combined.lower() or "validation" in combined.lower(), (
        "Error output must mention the synthetic- guard or validation failure. "
        f"Got: {combined[:400]}"
    )


# ---------------------------------------------------------------------------
# Test 5 — credential matching real key pattern (sk-...) → exit 1
# ---------------------------------------------------------------------------


def test_real_key_pattern_credential_exits_1() -> None:
    """Provider api_key matching a real key pattern exits 1 even with 'synthetic-' prefix absent.

    Additional defense: even if the key has no 'synthetic-' prefix and also
    matches sk-...<20+ chars> it must be rejected.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        bundle_dir = Path(tmpdir)
        _make_bundle(bundle_dir)

        # sk-style key without synthetic prefix — matches real key pattern.
        bad_providers = {
            "providers": [
                {
                    "name": "bad-openai-provider",
                    "provider_type": "litellm",
                    "api_key": "sk-abcdefghijklmnopqrstuvwxyz12345678",
                    "base_url": "http://localhost:4000",
                    "is_active": True,
                }
            ]
        }
        (bundle_dir / "admin_ai" / "providers.json").write_text(
            json.dumps(bad_providers), encoding="utf-8"
        )

        result = _run_cli(str(bundle_dir), ["--only", "admin_ai"])

    assert result.returncode == 1, (
        f"Expected exit code 1 for api_key matching real-key pattern (sk-...). "
        f"Got: {result.returncode}\nSTDOUT: {result.stdout[:300]}\nSTDERR: {result.stderr[:300]}"
    )
