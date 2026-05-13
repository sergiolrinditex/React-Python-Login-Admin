"""
Hilo People — Unit tests for app.auth.tokens lazy JWT key getter.

Slice:  P02-S02-T002 — Fix module-level _JWT_KEY (lazy getter, import-order-resilient)
Phase:  P02 Core Features
Purpose: Regression tests that pin the import-order-resilience invariant for
         the JWT key getter introduced in P02-S02-T002. These tests document
         and enforce the cache semantics and error contract so the bug
         (module-level _JWT_KEY captured as "" when env is unset at import time)
         cannot silently regress.

         Five tests:
           T1 — Roundtrip: env set, encode → decode → claims equal.
           T2 — Reproducer: env absent at "import" (cache cleared), then set →
                first call succeeds (lazy, not pinned to "").
           T3 — Empty env raises RuntimeError (loud-fail in prod).
           T4 — Cache semantics: second call does NOT re-read os.getenv.
           T5 — _clear_jwt_key_cache allows env rotation.

Key deps:
  - pytest (monkeypatch fixture)
  - app.auth.tokens (encode_access_token, decode_token, _get_jwt_key,
    _clear_jwt_key_cache)
  - unittest.mock (patch for cache-semantics test)

Source refs:
  - task pack P02-S02-T002 §F.6 (test inventory T1..T5)
  - 01-non-negotiables.md §Tests are REAL (no mocks of own services)
  - 01-non-negotiables.md §Security (no key/token values in logs)

Decisions:
  - D-AT1: Each test calls _clear_jwt_key_cache() in setup to guarantee
    isolation — avoids cached value from a prior test leaking into the next.
  - D-AT2: Tests do NOT depend on DB or backend server; they are pure-Python
    unit tests against the tokens module.
  - D-AT3: T3 clears cache AND removes env var so the getter sees no key.
  - D-AT4: T4 patches os.getenv to a sentinel AFTER first successful call;
    second call must return original cached value (not the sentinel).
  - D-AT5: A minimal fake user object is used for encode_access_token to
    avoid SQLAlchemy imports (no ORM needed for token unit tests).
"""

from __future__ import annotations

import uuid
from typing import Any

import pytest

from app.auth.tokens import (
    _clear_jwt_key_cache,
    _get_jwt_key,
    decode_token,
    encode_access_token,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

# A real key ≥32 bytes used across tests (not secret; for tests only)
_TEST_KEY = "test-dev-jwt-secret-key-for-unit-tests-only-32b+"
_TEST_KEY_B = "another-test-jwt-key-for-rotation-test-32b!!"


class _FakeUser:
    """Minimal user-like object for encode_access_token calls.

    encode_access_token accepts any object with the required attributes;
    it does not require an ORM instance. Using a fake avoids DB dependency
    in unit tests (D-AT2).
    """

    def __init__(self) -> None:
        self.id: uuid.UUID = uuid.uuid4()
        self.email: str = f"unit-test-{self.id.hex[:8]}@example.com"
        self.preferred_language: str = "es"
        self.employee_profile_id: str | None = None
        self.user_roles: list[Any] = []


@pytest.fixture(autouse=True)
def _reset_jwt_key_cache() -> None:
    """Auto-use fixture: clear the lru_cache before every test (D-AT1).

    Guarantees that cached values from previous tests do not leak into the
    current test. Also restores env after test.
    """
    _clear_jwt_key_cache()
    yield
    _clear_jwt_key_cache()


# ---------------------------------------------------------------------------
# T1 — Roundtrip: encode → decode → claims equal
# ---------------------------------------------------------------------------


def test_encode_then_decode_roundtrip_with_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """T1: Basic roundtrip — encode_access_token then decode_token returns matching claims.

    Pins the baseline behavior: when JWT_PRIVATE_KEY is present at call time,
    encode/decode round-trips cleanly.
    """
    monkeypatch.setenv("JWT_PRIVATE_KEY", _TEST_KEY)

    user = _FakeUser()
    token = encode_access_token(user)
    assert isinstance(token, str)
    assert len(token) > 0

    claims = decode_token(token)
    assert claims["sub"] == str(user.id)
    assert claims["email"] == user.email
    assert "exp" in claims
    assert "jti" in claims
    assert claims["preferred_language"] == "es"
    assert claims["roles"] == ["employee"]


# ---------------------------------------------------------------------------
# T2 — Reproducer: env absent at "import time", then set → first call succeeds
# ---------------------------------------------------------------------------


def test_decode_works_after_module_import_with_empty_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T2: Reproduce the bug — simulates import with env absent, then env set.

    Sequence:
      1. Cache is already cleared by autouse fixture (simulates "import-time" state).
      2. Remove JWT_PRIVATE_KEY from env (env absent, as when module is imported
         before conftest loads .env).
      3. Set JWT_PRIVATE_KEY to a real key (simulates conftest/profile loading .env).
      4. Call encode_access_token → should succeed (lazy getter reads env at call time).
      5. Call decode_token → should succeed and return correct claims.

    Pre-fix behaviour: if _JWT_KEY was captured at import with "", step 4 and 5
    would produce tokens signed with "" — and decoding with the real key would fail.
    Post-fix: lazy getter reads env at step 3's value, not the "" seen at import.
    """
    # Step 2: simulate import-time env absence
    monkeypatch.delenv("JWT_PRIVATE_KEY", raising=False)

    # Step 3: fixture / conftest sets env (happens after collection in real pytest)
    monkeypatch.setenv("JWT_PRIVATE_KEY", _TEST_KEY)

    # Step 4+5: encode and decode must both succeed and agree on the key
    user = _FakeUser()
    token = encode_access_token(user)
    claims = decode_token(token)
    assert claims["sub"] == str(user.id)


# ---------------------------------------------------------------------------
# T3 — Empty env raises RuntimeError (loud-fail in prod)
# ---------------------------------------------------------------------------


def test_encode_raises_runtime_error_when_jwt_key_missing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T3: When JWT_PRIVATE_KEY is absent/empty at call time, raises RuntimeError.

    Pins the loud-fail-in-prod posture: missing key → hard RuntimeError,
    not a silent empty-string encode that produces an unusable token.
    The RuntimeError is raised BEFORE PyJWT is called (D-TK6).
    """
    monkeypatch.delenv("JWT_PRIVATE_KEY", raising=False)

    user = _FakeUser()
    with pytest.raises(RuntimeError, match="JWT_PRIVATE_KEY"):
        encode_access_token(user)


def test_get_jwt_key_raises_runtime_error_on_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """T3b: _get_jwt_key() itself raises RuntimeError when env is empty string.

    Explicit contract: even if JWT_PRIVATE_KEY is set to "" (not absent),
    the getter raises. Cache never stores the empty value.
    """
    monkeypatch.setenv("JWT_PRIVATE_KEY", "")

    with pytest.raises(RuntimeError, match="JWT_PRIVATE_KEY"):
        _get_jwt_key()


# ---------------------------------------------------------------------------
# T4 — Cache semantics: second call does NOT re-read os.getenv
# ---------------------------------------------------------------------------


def test_jwt_key_getter_is_cached(monkeypatch: pytest.MonkeyPatch) -> None:
    """T4: After first successful call, _get_jwt_key() uses lru_cache.

    Verifies that the second call returns the cached value even if os.getenv
    would now return a different sentinel. Documents the cache contract:
    the key is stable for the lifetime of the process (or until
    _clear_jwt_key_cache() is called).
    """
    monkeypatch.setenv("JWT_PRIVATE_KEY", _TEST_KEY)

    # First call — populates cache
    key_first = _get_jwt_key()
    assert key_first == _TEST_KEY

    # Mutate env to a sentinel (cache should shield from this change)
    sentinel = "SENTINEL_SHOULD_NOT_BE_RETURNED"
    monkeypatch.setenv("JWT_PRIVATE_KEY", sentinel)

    # Second call — must return cached value, not sentinel
    key_second = _get_jwt_key()
    assert key_second == _TEST_KEY, (
        "Expected cached value from first call; got sentinel — "
        "lru_cache is not working as expected"
    )
    assert key_second != sentinel


# ---------------------------------------------------------------------------
# T5 — _clear_jwt_key_cache allows env rotation
# ---------------------------------------------------------------------------


def test_clear_jwt_key_cache_allows_env_rotation(monkeypatch: pytest.MonkeyPatch) -> None:
    """T5: _clear_jwt_key_cache() forces the next call to re-read os.environ.

    Pins the test-only rotation contract: after clearing the cache and changing
    the env var, _get_jwt_key() returns the new value. This is how
    gen-dev-secrets.sh rotation works in test scenarios.
    """
    monkeypatch.setenv("JWT_PRIVATE_KEY", _TEST_KEY)
    key_a = _get_jwt_key()
    assert key_a == _TEST_KEY

    # Rotate env and clear cache
    monkeypatch.setenv("JWT_PRIVATE_KEY", _TEST_KEY_B)
    _clear_jwt_key_cache()

    key_b = _get_jwt_key()
    assert key_b == _TEST_KEY_B
    assert key_b != key_a
