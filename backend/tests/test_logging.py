"""
Logging security tests — CWE-532 frame-locals leak prevention.

Slice: P00-S02-T004 — Disable structlog Rich-traceback show_locals globally
Phase: P00 — Scaffold + Design System

Tests covered (4 total):
  1. test_exc_info_does_not_leak_frame_locals_verbose
       exc_info=True in verbose mode (ConsoleRenderer path) must NOT leak
       sentinel secrets bound as frame locals in the exception frame.
  2. test_exc_info_does_not_leak_frame_locals_json
       Same under ENABLE_VERBOSE_LOGGING=false (JSONRenderer path).
  3. test_enable_verbose_logging_env_var_false
       With ENABLE_VERBOSE_LOGGING=false env var, frame-local secrets must
       not appear in log output.
  4. test_redaction_processor_still_scrubs_event_dict_keys
       Regression: the existing top-level dict-level redaction still fires
       for keys like password=, dsn=, etc. (acceptance criteria #6 for T002
       + non-regression for T004's extended _REDACTED_KEYS).

Architecture note (CWE-532):
  structlog's ConsoleRenderer uses RichTracebackFormatter which by default
  sets show_locals=True.  This means any exc_info=True log call renders the
  full stack frame locals to stdout — including asyncpg's cparams dict that
  holds host, user, password, port, database in plaintext.
  P00-S02-T004 fixes this by passing show_locals=False to the formatter
  constructor.  These tests assert the fix holds under both rendering modes.

Real tests (01-non-negotiables.md §Tests are REAL):
  - No mocking of structlog itself.
  - configure_logging() is called directly — it is the production function.
  - _configured guard is reset before each test and restored after (same
    pattern as test_health.py tests 7 and 9 which already manage this).
  - Tests use real structlog loggers via get_logger(), not logging.getLogger().
  - capsys fixture captures real stdout/stderr output.

Test isolation note:
  configure_logging() adds a StreamHandler(sys.stdout) to the root logger
  AND calls structlog.configure() which both become global singletons.
  Each test uses _restore_logging_state() in its finally block to reset
  the root logger handlers back to a clean stub, preventing the
  "I/O operation on closed file" error that would otherwise bleed into
  subsequent tests when pytest closes the capsys capture buffer.

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0 (asyncio_mode=auto in pyproject.toml)
  - structlog 25.5.0
"""
from __future__ import annotations

import contextlib
import logging

import pytest

from app.core.logging import (
    _REDACTED_SENTINEL,
    configure_logging,
    get_logger,
)

# Sentinel values chosen so they cannot collide with any other log text
# (uvicorn banners, structlog meta, test framework output, etc.).
# Using the exact same sentinel the task pack mandates for reproduction.
_SENTINEL_PASSWORD = "S3CRET-PASSWORD-DO-NOT-LEAK"
_SENTINEL_HOST = "127.0.0.1:1"
_SENTINEL_USER = "baduser"
_SENTINEL_DB = "baddb"
_SENTINEL_DSN = (
    f"postgresql+asyncpg://{_SENTINEL_USER}:{_SENTINEL_PASSWORD}"
    f"@{_SENTINEL_HOST}/{_SENTINEL_DB}"
)


def _save_logging_state() -> tuple[bool, list[logging.Handler]]:
    """Capture current logging state so it can be restored after a test.

    Returns:
      (prev_configured, prev_handlers) tuple for use in _restore_logging_state().
    """
    import app.core.logging as core_logging

    prev_configured = core_logging._configured
    root = logging.getLogger()
    prev_handlers = list(root.handlers)
    return prev_configured, prev_handlers


def _restore_logging_state(
    prev_configured: bool,
    prev_handlers: list[logging.Handler],
) -> None:
    """Restore root logger and _configured flag to pre-test state.

    This prevents the "I/O operation on closed file" error that occurs when
    a StreamHandler added by configure_logging(verbose=True) still points to
    the capsys-captured stdout after pytest closes the capture buffer.

    Params:
      prev_configured — value of core_logging._configured before the test.
      prev_handlers   — root logger handlers before the test.
    """
    import app.core.logging as core_logging

    core_logging._configured = prev_configured
    root = logging.getLogger()
    # Remove any handlers added during the test.
    for handler in list(root.handlers):
        if handler not in prev_handlers:
            with contextlib.suppress(Exception):
                handler.close()
            root.removeHandler(handler)
    # Re-attach the original handlers.
    for handler in prev_handlers:
        if handler not in root.handlers:
            root.addHandler(handler)


def _raise_with_sensitive_locals() -> None:
    """Function whose frame holds sentinel secrets as locals when it raises.

    Designed to mirror the asyncpg cparams pattern: secrets are bound as
    frame locals only — they are NEVER included in the exception message.
    This means the only leak vector is the traceback frame-locals renderer.

    If show_locals=True, RichTracebackFormatter will print every local in
    this frame (password, host, port, user, database, dsn) to stdout.
    If show_locals=False, none of them appear.
    """
    # Frame locals — NEVER passed to the exception message.
    password = _SENTINEL_PASSWORD  # noqa: F841 bound as local on purpose
    host = _SENTINEL_HOST  # noqa: F841
    user = _SENTINEL_USER  # noqa: F841
    database = _SENTINEL_DB  # noqa: F841
    dsn = _SENTINEL_DSN  # noqa: F841
    # Generic error message — contains no secrets.
    raise RuntimeError("connection refused")


def _assert_no_leaks(captured_text: str) -> None:
    """Assert none of the sentinel secrets appear in the captured log output.

    Params:
      captured_text — combined stdout + stderr from capsys.
    Errors: AssertionError with diagnostic detail on first failed check.
    """
    leaks: list[str] = []
    for needle, label in (
        (_SENTINEL_PASSWORD, "password"),
        (_SENTINEL_USER, "user"),
        (_SENTINEL_DB, "database"),
        (_SENTINEL_DSN, "full DSN"),
        # host+port combined (the host sentinel already contains :1)
        ("127.0.0.1:1", "host:port"),
        # DSN scheme — should not appear either
        ("postgresql+asyncpg://", "DSN scheme"),
    ):
        if needle in captured_text:
            leaks.append(f"{label}={needle!r}")

    assert not leaks, (
        "Log output leaked sensitive frame-local values — CWE-532 regression.\n"
        f"Leaked: {', '.join(leaks)}\n"
        f"Full output (first 2000 chars):\n{captured_text[:2000]}"
    )


# ---------------------------------------------------------------------------
# Test 1 — exc_info=True in verbose mode must NOT leak frame locals
# ---------------------------------------------------------------------------


def test_exc_info_does_not_leak_frame_locals_verbose(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ConsoleRenderer path (verbose=True): exc_info=True must not render locals.

    This is the primary CWE-532 regression test.  Before P00-S02-T004, the
    ConsoleRenderer used RichTracebackFormatter(show_locals=True) and would
    print all frame-local variables when exc_info=True was passed.
    After the fix, show_locals=False means only the traceback lines appear.

    Acceptance: task pack criteria #2 (verbose path).
    """
    prev_configured, prev_handlers = _save_logging_state()
    try:
        import app.core.logging as core_logging

        core_logging._configured = False
        configure_logging(verbose=True)
        _logger = get_logger("test_verbose_exc_info")

        # BEFORE: trigger an exception with sensitive frame locals.
        try:
            _raise_with_sensitive_locals()
        except RuntimeError:
            _logger.error(
                "BEFORE test_exc_info_does_not_leak_frame_locals_verbose: "
                "logging exc_info under verbose=True",
                exc_info=True,
            )

        # AFTER: capture and assert.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        _assert_no_leaks(combined)
    finally:
        _restore_logging_state(prev_configured, prev_handlers)


# ---------------------------------------------------------------------------
# Test 2 — exc_info=True in JSON mode must NOT leak frame locals
# ---------------------------------------------------------------------------


def test_exc_info_does_not_leak_frame_locals_json(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """JSONRenderer path (verbose=False): exc_info=True must not render locals.

    Python's stdlib traceback.format_exception does not include frame locals
    by default, so this path was already safe before T004.  This test provides
    defense-in-depth regression coverage: if the renderer is swapped in a
    future commit, this test catches any new leak.

    Acceptance: task pack criteria #2 + #3 (JSON path).
    """
    prev_configured, prev_handlers = _save_logging_state()
    try:
        import app.core.logging as core_logging

        core_logging._configured = False
        configure_logging(verbose=False)
        _logger = get_logger("test_json_exc_info")

        # BEFORE: trigger exception with sensitive frame locals.
        try:
            _raise_with_sensitive_locals()
        except RuntimeError:
            _logger.error(
                "BEFORE test_exc_info_does_not_leak_frame_locals_json: "
                "logging exc_info under verbose=False",
                exc_info=True,
            )

        # AFTER: capture and assert.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        _assert_no_leaks(combined)
    finally:
        _restore_logging_state(prev_configured, prev_handlers)


# ---------------------------------------------------------------------------
# Test 3 — ENABLE_VERBOSE_LOGGING=false env var path
# ---------------------------------------------------------------------------


def test_enable_verbose_logging_env_var_false(
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """ENABLE_VERBOSE_LOGGING=false: the app reads this env var in main.py.

    This test simulates the production env var path by calling
    configure_logging(verbose=False) — matching the behavior of main.py when
    ENABLE_VERBOSE_LOGGING != 'true'.  Ensures JSON path is also leak-free.

    Acceptance: task pack criteria #3 (ENABLE_VERBOSE_LOGGING toggle works).
    """
    prev_configured, prev_handlers = _save_logging_state()
    try:
        import app.core.logging as core_logging

        monkeypatch.setenv("ENABLE_VERBOSE_LOGGING", "false")
        core_logging._configured = False
        configure_logging(verbose=False)
        _logger = get_logger("test_env_var_false")

        # BEFORE: trigger exception with sensitive frame locals.
        try:
            _raise_with_sensitive_locals()
        except RuntimeError:
            _logger.error(
                "BEFORE test_enable_verbose_logging_env_var_false: "
                "logging exc_info with ENABLE_VERBOSE_LOGGING=false",
                exc_info=True,
            )

        # AFTER: capture and assert.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        _assert_no_leaks(combined)
    finally:
        _restore_logging_state(prev_configured, prev_handlers)


# ---------------------------------------------------------------------------
# Test 4 — dict-level redaction processor regression
# ---------------------------------------------------------------------------


def test_redaction_processor_still_scrubs_event_dict_keys(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Top-level event_dict key redaction must still fire after T004 changes.

    This test is a regression guard for the existing _redaction_processor
    that scrubs event_dict keys.  P00-S02-T004 extended _REDACTED_KEYS but
    must NOT break the existing behavior.

    Tests both new keys (dsn, database_url, connection_string, pwd) added in
    T004 and the original keys (password, token, secret, api_key).

    Acceptance: task pack criteria #6 (existing top-level redaction preserved).
    """
    prev_configured, prev_handlers = _save_logging_state()
    try:
        import app.core.logging as core_logging

        core_logging._configured = False
        configure_logging(verbose=True)
        _logger = get_logger("test_redaction")

        # BEFORE: log with sensitive top-level keys — none should appear in output.
        _logger.warning(
            "BEFORE test_redaction_processor_still_scrubs_event_dict_keys: "
            "logging sensitive top-level kwargs",
            password="leakme_password",
            token="leakme_token",
            secret="leakme_secret",
            api_key="leakme_api_key",
            dsn="leakme_dsn",
            database_url="leakme_database_url",
            connection_string="leakme_connection_string",
            pwd="leakme_pwd",
        )

        # AFTER: capture and assert sentinels are present but raw values absent.
        captured = capsys.readouterr()
        combined = captured.out + captured.err

        for raw_value, label in (
            ("leakme_password", "password"),
            ("leakme_token", "token"),
            ("leakme_secret", "secret"),
            ("leakme_api_key", "api_key"),
            ("leakme_dsn", "dsn"),
            ("leakme_database_url", "database_url"),
            ("leakme_connection_string", "connection_string"),
            ("leakme_pwd", "pwd"),
        ):
            assert raw_value not in combined, (
                f"Redaction processor failed: {label}={raw_value!r} leaked into log output.\n"
                f"Full output (first 2000 chars):\n{combined[:2000]}"
            )

        # The redaction sentinel must appear (confirming the processor ran).
        assert _REDACTED_SENTINEL in combined, (
            f"Redaction sentinel {_REDACTED_SENTINEL!r} not found in output — "
            "processor may not have run at all."
        )
    finally:
        _restore_logging_state(prev_configured, prev_handlers)
