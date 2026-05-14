"""
Hilo People — Unit tests for scripts/gen-dev-secrets.sh.

Slice:  P02-S03-T004 — Rotate ENCRYPTION_KEY in dev .env + seed active AI provider
Phase:  P02 Core Features
Purpose: 5 tests for the bash provisioner script (T01..T05 from task pack):
           T01 — Placeholder ENCRYPTION_KEY → rotated to valid 44-char Fernet key
           T02 — Already-valid Fernet key → preserved (changed=0)
           T03 — Captured stdout+stderr NEVER contains the actual key bytes
           T04 — After rotation .env has chmod 600 (owner read/write only)
           T05 — Missing .env → exit non-zero with clear error on stderr

         Tests run the REAL bash script via subprocess in an isolated tmp_path .env.
         No mocking of the script internals — purely black-box.

Key deps:
  - pytest==9.0.2
  - subprocess (stdlib)
  - cryptography==48.0.0 (Fernet — validate generated key)

Source refs:
  - task pack P02-S03-T004 §Test plan T01..T05
  - D-T004-A1 (Fernet.generate_key pattern)
  - D-T004-A2 (placeholder-only rotation)
  - D-T004-A3 (never print key values)
  - D-T004-A7 (constructor-only validity smoke)
  - 01-non-negotiables.md §Tests are REAL, §Logging
"""

from __future__ import annotations

import stat
import subprocess
import sys
from pathlib import Path

import pytest
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Resolve script path (worktree-safe)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve()
# backend/tests/unit/test_gen_dev_secrets.py → walk up 3 levels → repo root
_REPO_ROOT = _HERE.parents[3]
_SCRIPT = _REPO_ROOT / "scripts" / "gen-dev-secrets.sh"

# Minimal .env template with placeholder keys
_ENV_TEMPLATE = """\
# Test .env for gen-dev-secrets.sh unit tests
JWT_PRIVATE_KEY=replace-with-dev-key
JWT_PUBLIC_KEY=replace-with-dev-key
ENCRYPTION_KEY=replace-with-dev-key
MFA_ENCRYPTION_KEY=replace-with-fernet-key-from-generate_key
ENABLE_VERBOSE_LOGGING=false
DATABASE_URL=postgresql+asyncpg://hilo:hilo@localhost:5432/hilo_dev
"""


def _run_script(env_path: Path) -> subprocess.CompletedProcess[str]:
    """Run gen-dev-secrets.sh against the given .env path.

    Args:
        env_path: Path to the .env file to operate on.

    Returns:
        CompletedProcess with stdout/stderr captured.
    """
    return subprocess.run(
        ["bash", str(_SCRIPT), "--env", str(env_path)],
        capture_output=True,
        text=True,
    )


def _read_env_value(env_path: Path, key: str) -> str:
    """Parse a key=value line from .env without loading into os.environ.

    Args:
        env_path: Path to the .env file.
        key:      Variable name to look up.

    Returns:
        The raw value string, or empty string if not found.
    """
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        if k.strip() == key:
            return v.strip()
    return ""


def _is_valid_fernet_key(key: str) -> bool:
    """Return True if key is a valid Fernet key (constructor smoke test).

    Args:
        key: String to validate.

    Returns:
        True if Fernet(key.encode()) succeeds without raising.
    """
    try:
        Fernet(key.encode())
        return True
    except Exception:
        return False


# ===========================================================================
# T01 — Placeholder ENCRYPTION_KEY → rotated to valid 44-char Fernet key
# ===========================================================================
def test_placeholder_encryption_key_is_rotated(tmp_path: Path) -> None:
    """T01: placeholder ENCRYPTION_KEY → script rotates to valid Fernet key (44 chars, exit 0)."""
    env_file = tmp_path / ".env"
    env_file.write_text(_ENV_TEMPLATE, encoding="utf-8")

    result = _run_script(env_file)

    assert result.returncode == 0, (
        f"Script exited {result.returncode}. stderr={result.stderr}"
    )

    new_key = _read_env_value(env_file, "ENCRYPTION_KEY")
    assert new_key != "replace-with-dev-key", "ENCRYPTION_KEY was not rotated"
    assert len(new_key) == 44, (
        f"Expected 44-char Fernet key, got len={len(new_key)}"
    )
    assert new_key.endswith("="), (
        f"Fernet key should end with '=', got: last char={new_key[-1]!r}"
    )
    assert _is_valid_fernet_key(new_key), (
        "Generated key is not accepted by Fernet constructor"
    )
    # stdout machine-readable summary
    assert "changed=" in result.stdout, (
        f"Expected 'changed=N' in stdout. stdout={result.stdout!r}"
    )


# ===========================================================================
# T02 — Already-valid Fernet key → preserved (changed=0)
# ===========================================================================
def test_valid_fernet_key_is_preserved(tmp_path: Path) -> None:
    """T02: already-valid ENCRYPTION_KEY → script reports changed=0, key unchanged."""
    real_key = Fernet.generate_key().decode()
    env_content = _ENV_TEMPLATE.replace(
        "ENCRYPTION_KEY=replace-with-dev-key",
        f"ENCRYPTION_KEY={real_key}",
    )
    env_file = tmp_path / ".env"
    env_file.write_text(env_content, encoding="utf-8")

    result = _run_script(env_file)

    assert result.returncode == 0, (
        f"Script exited {result.returncode}. stderr={result.stderr}"
    )

    preserved_key = _read_env_value(env_file, "ENCRYPTION_KEY")
    assert preserved_key == real_key, (
        "ENCRYPTION_KEY was changed even though it was already a valid Fernet key"
    )
    # changed count for ENCRYPTION_KEY specifically should be 0 (key kept)
    assert "kept" in result.stderr, (
        f"Expected 'kept' status in stderr for non-placeholder key. stderr={result.stderr!r}"
    )


# ===========================================================================
# T03 — Script NEVER prints the actual key bytes in stdout or stderr
# ===========================================================================
def test_script_never_prints_key_value(tmp_path: Path) -> None:
    """T03: stdout+stderr NEVER contains the actual generated key bytes."""
    env_file = tmp_path / ".env"
    env_file.write_text(_ENV_TEMPLATE, encoding="utf-8")

    result = _run_script(env_file)
    assert result.returncode == 0, f"Script failed. stderr={result.stderr}"

    new_key = _read_env_value(env_file, "ENCRYPTION_KEY")
    assert new_key and new_key != "replace-with-dev-key", "Key was not rotated"

    combined_output = result.stdout + result.stderr
    assert new_key not in combined_output, (
        "SECURITY: the generated ENCRYPTION_KEY value was found in script output. "
        "D-T004-A3 requires keys are NEVER printed."
    )

    # Also check JWT keys are not printed
    jwt_key = _read_env_value(env_file, "JWT_PRIVATE_KEY")
    if jwt_key and jwt_key != "replace-with-dev-key":
        assert jwt_key not in combined_output, (
            "SECURITY: JWT_PRIVATE_KEY value was found in script output."
        )


# ===========================================================================
# T04 — After rotation .env permissions are 0600
# ===========================================================================
@pytest.mark.skipif(sys.platform == "win32", reason="chmod not applicable on Windows")
def test_env_file_has_secure_permissions(tmp_path: Path) -> None:
    """T04: after rotation the .env file has chmod 600 (owner r/w only)."""
    env_file = tmp_path / ".env"
    env_file.write_text(_ENV_TEMPLATE, encoding="utf-8")

    result = _run_script(env_file)
    assert result.returncode == 0, f"Script failed. stderr={result.stderr}"

    mode = oct(stat.S_IMODE(env_file.stat().st_mode))
    assert mode == "0o600", (
        f"Expected .env permissions 0600, got {mode}. "
        "D-T004-A3 / gen-dev-secrets.sh must call chmod 600."
    )


# ===========================================================================
# T05 — Missing .env → exit non-zero with error on stderr
# ===========================================================================
def test_missing_env_file_exits_nonzero(tmp_path: Path) -> None:
    """T05: non-existent .env → script exits with non-zero code and writes error to stderr."""
    nonexistent = tmp_path / "does_not_exist.env"

    result = _run_script(nonexistent)

    assert result.returncode != 0, (
        f"Expected non-zero exit for missing .env, got {result.returncode}"
    )
    assert result.stderr.strip(), "Expected error message on stderr for missing .env"
    # stderr should mention the path or 'not_found'
    assert (
        "not_found" in result.stderr.lower()
        or str(nonexistent.name) in result.stderr
        or "env_file" in result.stderr
    ), f"stderr should describe missing env file. stderr={result.stderr!r}"
