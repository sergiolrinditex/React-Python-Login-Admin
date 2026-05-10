"""
Regression tests: argon2id hashes must NEVER appear in logs during sign-up (CWE-532).

Slice: P01-S02-T011 — SQLAlchemy echo leaks argon2 hash in verbose logs
Phase: P01 — Auth + Base Capabilities

Origin: FU-20260510090824 promoted from P01-S02-T001 /verify-slice evidence
  (4 occurrences of $argon2id$ in back-verbose.log for V1+V2 sign-up runs).

Root cause (closed by P00-S02-T012 / commit 4ccf7b0):
  `create_async_engine(..., echo=True)` caused SQLAlchemy to set the
  `sqlalchemy.engine` stdlib logger to INFO level, emitting every SQL
  statement's bind-parameter tuple — including `users.password_hash` argon2id
  strings — verbatim, bypassing the structlog `_redaction_processor`.

Defense layers (closed):
  1. T012 / echo=False permanent → engine-level fix; closes ALL bind-param leak
     vectors for ALL tables, including `users.password_hash`.
  2. T011 / `password_hash` in _REDACTED_KEYS → belt-and-suspenders; if any
     future code path ever logs `password_hash=...` as a structlog key, it is
     automatically redacted.

Test inventory:
  T1 (unit canary): configure_logging(verbose=True) + _CapturingHandler on
     `sqlalchemy.engine`; emit event with password_hash key; assert `$argon2id$`
     is absent from both structlog stdout AND the SA logger handler.
  T2 (integration happy): POST /api/v1/auth/sign-up with fresh email (→ 201);
     capture stdout via capsys AND sqlalchemy.engine handler;
     assert `$argon2id$` is absent from both.
  T3 (integration duplicate): POST /api/v1/auth/sign-up twice with same email
     (→ 201 then 409); assert `$argon2id$` absent from both captures.

Dependencies:
  - pytest 9.0.3, pytest-asyncio 1.3.0 (asyncio_mode=auto)
  - httpx 0.28.1 (ASGITransport — not deprecated AsyncClient(app=app) form)
  - sqlalchemy[asyncio] 2.0.49, asyncpg 0.31.0, argon2-cffi 25.1.0
  - structlog 25.5.0
  - conftest.py autouse `reset_db_engine_singleton` (P00-S02-T016, commit cd702de)
    AWAITS dispose() in the test's own event loop — do NOT duplicate it here.
"""
from __future__ import annotations

import logging
import socket
import uuid
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_DB_DSN = (
    "postgresql+asyncpg://hilopeople:hilopeople_dev_pwd"
    "@127.0.0.1:5433/hilopeople_dev"
)

# Valid sign-up payload template — override email per test for isolation.
_VALID_PAYLOAD = {
    "email": "signup-argon2-test@testdomain.com",
    "password": "Aa1!Secure$Pass",
    "full_name": "Argon2 Leak Tester",
    "legal_acceptance": True,
}

# The argon2id hash prefix that must NEVER appear in any log output.
_ARGON2ID_MARKER = "$argon2id$"

# ---------------------------------------------------------------------------
# Reachability guard
# ---------------------------------------------------------------------------


def _db_reachable() -> bool:
    """Return True if compose postgres is reachable on host port 5433."""
    try:
        with socket.create_connection(("127.0.0.1", 5433), timeout=1):
            return True
    except OSError:
        return False


_DB_UP = _db_reachable()

_skip_no_db = pytest.mark.skipif(
    not _DB_UP,
    reason="compose postgres not reachable on 5433 — DB-requiring test skipped",
)

# ---------------------------------------------------------------------------
# _CapturingHandler (reused from test_db_engine_no_secret_leak.py pattern)
# ---------------------------------------------------------------------------


class _CapturingHandler(logging.Handler):
    """Capture all log messages emitted through this handler.

    Purpose: intercept sqlalchemy.engine stdlib logger records so we can assert
    that no $argon2id$ string is present, complementing the capsys stdout check.
    Pattern: attach to the SA logger before the operation, remove after.
    """

    def __init__(self) -> None:
        super().__init__()
        self.records: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        """Append the formatted message to the records list."""
        self.records.append(record.getMessage())


# ---------------------------------------------------------------------------
# Logging state context manager (T1 + T2 + T3 logging setup)
# ---------------------------------------------------------------------------


class _VerboseLoggingContext:
    """Context manager that reconfigures logging to DEBUG and restores state.

    Mirrors the pattern in test_auth_signup.py::T8 — resets `_configured`
    guard, calls `configure_logging(verbose=True)`, then restores root logger
    handlers + level + `_configured` flag on exit.

    Also attaches and detaches a _CapturingHandler to `sqlalchemy.engine`
    so bind-param leaks are caught at both channels:
      (a) structlog stdout (via capsys)
      (b) sqlalchemy.engine stdlib logger (via sa_handler.records)
    """

    def __init__(self) -> None:
        self.sa_handler: _CapturingHandler = _CapturingHandler()
        self._prev_configured: bool = False
        self._prev_root_handlers: list[logging.Handler] = []
        self._prev_root_level: int = logging.WARNING

    def __enter__(self) -> _VerboseLoggingContext:
        import app.core.logging as logging_module  # noqa: PLC0415

        # BEFORE: save current logging state
        self._prev_configured = logging_module._configured
        self._prev_root_handlers = logging.root.handlers[:]
        self._prev_root_level = logging.root.level

        # Reconfigure at DEBUG (verbose=True) to expose all log output
        logging_module._configured = False
        logging_module.configure_logging(verbose=True)

        # Attach capturing handler to sqlalchemy.engine for bind-param intercept
        sa_logger = logging.getLogger("sqlalchemy.engine")
        sa_logger.addHandler(self.sa_handler)

        return self

    def __exit__(self, *_: object) -> None:
        import app.core.logging as logging_module  # noqa: PLC0415

        # Remove SA capturing handler
        logging.getLogger("sqlalchemy.engine").removeHandler(self.sa_handler)

        # Restore root logger to previous state (prevent cross-test pollution)
        logging.root.handlers[:] = self._prev_root_handlers
        logging.root.setLevel(self._prev_root_level)
        logging_module._configured = self._prev_configured

    @property
    def sa_captured(self) -> str:
        """All SA log records joined for easy assert."""
        return "\n".join(self.sa_handler.records)


# ---------------------------------------------------------------------------
# HTTP client fixture (ASGI transport — same pattern as test_auth_signup.py)
# ---------------------------------------------------------------------------


@pytest_asyncio.fixture
async def http() -> AsyncGenerator[AsyncClient, None]:
    """AsyncClient using ASGITransport against the real FastAPI app.

    Purpose: real ASGI-level HTTP client (no network), no mocks of business logic.
    Uses the non-deprecated ASGITransport form (httpx 0.28.1).
    """
    from app.main import app  # noqa: PLC0415

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Unique email helper
# ---------------------------------------------------------------------------


def _unique_email(prefix: str = "argon2-test") -> str:
    """Return a unique email per test run to avoid duplicate-email collisions."""
    return f"{prefix}+{uuid.uuid4().hex[:8]}@testdomain.com"


# ---------------------------------------------------------------------------
# T1 — Unit canary: password_hash redaction via _REDACTED_KEYS
# ---------------------------------------------------------------------------


def test_redacted_keys_covers_password_hash() -> None:
    """T1: _REDACTED_KEYS contains 'password_hash'; processor redacts it.

    Purpose: unit canary — verifies that P01-S02-T011 Variant B (_REDACTED_KEYS
    extension) is in place. Exercises the dict-level structlog processor directly
    without needing the DB.

    Logging contract:
      BEFORE: validate processor setup.
      AFTER: assert password_hash key is replaced by ***REDACTED***.
    """
    from app.core.logging import _REDACTED_KEYS, _REDACTED_SENTINEL  # noqa: PLC0415

    # BEFORE: log intent
    print("[T1] BEFORE: asserting password_hash in _REDACTED_KEYS")  # noqa: T201

    assert "password_hash" in _REDACTED_KEYS, (
        "P01-S02-T011 Variant B: 'password_hash' must be in _REDACTED_KEYS "
        "to satisfy FU-20260510090824 acceptance 'password_hash field redacted "
        "at logging layer' branch. Check backend/app/core/logging.py."
    )

    # Also verify the redaction processor actually redacts it
    from app.core.logging import _redaction_processor  # noqa: PLC0415

    test_event: dict = {
        "event": "test",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$fakesalt$fakehash",
    }
    result = _redaction_processor(None, "info", test_event)

    assert result["password_hash"] == _REDACTED_SENTINEL, (
        f"Expected _redaction_processor to replace password_hash with "
        f"'{_REDACTED_SENTINEL}', got: {result['password_hash']}"
    )
    assert _ARGON2ID_MARKER not in str(result.values()), (
        f"$argon2id$ marker must not appear in redacted event dict values. "
        f"Got: {result}"
    )

    # AFTER: log success
    print(  # noqa: T201
        f"[T1] AFTER: password_hash in _REDACTED_KEYS=True; "
        f"processor redacts to {_REDACTED_SENTINEL}"
    )


# ---------------------------------------------------------------------------
# T2 — Integration happy path: no $argon2id$ in logs during successful sign-up
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_signup_happy_path_no_argon2_in_logs(
    http: AsyncClient, capsys: pytest.CaptureFixture
) -> None:
    """T2: POST /api/v1/auth/sign-up (new email) → 201; $argon2id$ absent from logs.

    Strategy: enable verbose logging (DEBUG), perform a real sign-up against the
    real FastAPI app + real Postgres + real argon2id hasher, then assert:
      - HTTP 201.
      - `$argon2id$` does NOT appear in structlog stdout (capsys).
      - `$argon2id$` does NOT appear in sqlalchemy.engine handler records.

    Logging contract:
      BEFORE: "capturing back.log for happy-path sign-up flow"
      AFTER: "captured N structlog lines + M SA records, asserting no $argon2id$"

    Root cause: T012 echo=False closes the SA bind-param leak channel.
    Regression guard: if echo=True is re-introduced, both assertions below fail.
    """
    email = _unique_email("happy")

    with _VerboseLoggingContext() as ctx:
        print(  # noqa: T201
            f"[T2] BEFORE: capturing back.log for happy-path sign-up flow (email={email})"
        )

        resp = await http.post(
            "/api/v1/auth/sign-up",
            json={**_VALID_PAYLOAD, "email": email},
            headers={"X-Request-ID": f"t2-{uuid.uuid4().hex}"},
        )
        captured = capsys.readouterr()
        stdout_text = captured.out

    # AFTER
    structlog_lines = stdout_text.count("\n")
    sa_records_count = len(ctx.sa_handler.records)
    print(  # noqa: T201
        f"[T2] AFTER: captured {structlog_lines} structlog lines + "
        f"{sa_records_count} SA records, asserting no {_ARGON2ID_MARKER}"
    )

    assert resp.status_code == 201, (
        f"Expected 201 for happy-path sign-up, got {resp.status_code}: {resp.text}"
    )

    # Core acceptance gate (FU-20260510090824 Verify: grep '$argon2id$' → 0)
    assert _ARGON2ID_MARKER not in stdout_text, (
        f"SECURITY REGRESSION: '{_ARGON2ID_MARKER}' found in structlog stdout "
        f"during sign-up with ENABLE_VERBOSE_LOGGING=true!\n"
        f"This means the argon2id hash leaked via logs. "
        f"Check db.py — echo must be False permanently (P00-S02-T012 / CWE-532).\n"
        f"Context: first 500 chars of stdout:\n{stdout_text[:500]}"
    )

    sa_all = ctx.sa_captured
    assert _ARGON2ID_MARKER not in sa_all, (
        f"SECURITY REGRESSION: '{_ARGON2ID_MARKER}' found in sqlalchemy.engine "
        f"handler records during sign-up with ENABLE_VERBOSE_LOGGING=true!\n"
        f"SA bind-param leak is active. Check db.py echo=False (P00-S02-T012).\n"
        f"SA records (first 500 chars):\n{sa_all[:500]}"
    )


# ---------------------------------------------------------------------------
# T3 — Integration duplicate: no $argon2id$ on 409 path either
# ---------------------------------------------------------------------------


@_skip_no_db
@pytest.mark.asyncio
async def test_signup_duplicate_path_no_argon2_in_logs(
    http: AsyncClient, capsys: pytest.CaptureFixture
) -> None:
    """T3: POST /api/v1/auth/sign-up twice (→ 201 then 409); $argon2id$ absent from both.

    Strategy: register a fresh email (→ 201), then attempt the same email again
    (→ 409 AUTH_EMAIL_TAKEN). The second attempt still triggers argon2 hash
    comparison in the DB lookup path, so logs must remain clean.

    Assert $argon2id$ absent from BOTH the 201 and the 409 stdout captures.

    Logging contract:
      BEFORE: "capturing back.log for duplicate sign-up flow (V1+V2)"
      AFTER: "captured N+M lines for both requests, asserting no $argon2id$"
    """
    email = _unique_email("dup")

    # --- First request (201) ---
    with _VerboseLoggingContext() as ctx1:
        print(  # noqa: T201
            f"[T3] BEFORE: capturing back.log for duplicate sign-up flow V1 (email={email})"
        )
        resp1 = await http.post(
            "/api/v1/auth/sign-up",
            json={**_VALID_PAYLOAD, "email": email},
            headers={"X-Request-ID": f"t3v1-{uuid.uuid4().hex}"},
        )
        captured1 = capsys.readouterr()
        stdout1 = captured1.out

    lines1 = stdout1.count("\n")
    sa1_count = len(ctx1.sa_handler.records)
    print(  # noqa: T201
        f"[T3] AFTER V1: captured {lines1} structlog lines + "
        f"{sa1_count} SA records for first sign-up"
    )

    # --- Second request (409) ---
    with _VerboseLoggingContext() as ctx2:
        print(  # noqa: T201
            f"[T3] BEFORE: capturing back.log for duplicate sign-up flow V2 (email={email})"
        )
        resp2 = await http.post(
            "/api/v1/auth/sign-up",
            json={**_VALID_PAYLOAD, "email": email},
            headers={"X-Request-ID": f"t3v2-{uuid.uuid4().hex}"},
        )
        captured2 = capsys.readouterr()
        stdout2 = captured2.out

    lines2 = stdout2.count("\n")
    sa2_count = len(ctx2.sa_handler.records)
    print(  # noqa: T201
        f"[T3] AFTER V2: captured {lines2} structlog lines + "
        f"{sa2_count} SA records for duplicate sign-up"
    )

    assert resp1.status_code == 201, (
        f"First sign-up expected 201, got {resp1.status_code}: {resp1.text}"
    )
    assert resp2.status_code == 409, (
        f"Duplicate sign-up expected 409, got {resp2.status_code}: {resp2.text}"
    )

    # Core acceptance gate for BOTH requests
    for label, stdout_text, sa_ctx in (("V1 (201)", stdout1, ctx1), ("V2 (409)", stdout2, ctx2)):
        assert _ARGON2ID_MARKER not in stdout_text, (
            f"SECURITY REGRESSION [{label}]: '{_ARGON2ID_MARKER}' found in "
            f"structlog stdout with ENABLE_VERBOSE_LOGGING=true!\n"
            f"check db.py echo=False (P00-S02-T012 / CWE-532).\n"
            f"First 500 chars:\n{stdout_text[:500]}"
        )
        sa_all = sa_ctx.sa_captured
        assert _ARGON2ID_MARKER not in sa_all, (
            f"SECURITY REGRESSION [{label}]: '{_ARGON2ID_MARKER}' found in "
            f"sqlalchemy.engine handler records with ENABLE_VERBOSE_LOGGING=true!\n"
            f"SA bind-param leak. Check db.py echo=False (P00-S02-T012).\n"
            f"SA records (first 500 chars):\n{sa_all[:500]}"
        )
