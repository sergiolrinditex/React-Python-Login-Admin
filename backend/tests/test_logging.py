"""
Logging security tests — CWE-532 frame-locals leak prevention + httpx api-key suppression.

Slice: P00-S02-T004 — Disable structlog Rich-traceback show_locals globally
       P00-S02-T009 — Suppress httpx logger to prevent Gemini API key leak in verbose logs
Phase: P00 — Scaffold + Design System

Tests covered (9 total):

  T004 tests (4):
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

  T009 tests (5):
  5. test_httpx_logger_suppressed_in_verbose_mode (A1)
       httpx MockTransport request to URL containing ?key=AIza-FAKE-SENTINEL...
       must NOT appear in captured output under verbose=True. Acceptance A1.
  6. test_httpx_logger_warning_still_propagates (A4)
       WARNING-level messages from the httpx logger must still propagate after
       the INFO suppression. Ensures we do not break actionable failure info.
  7. test_httpx_logger_already_silent_in_production_mode (A3)
       Same MockTransport sentinel request under verbose=False must produce no
       AIza substring in captured output. Regression guard.
  8. test_openai_bearer_pattern_not_in_logs (A2, defense-in-depth)
       httpx request with Authorization: Bearer sk-FAKE-... header must not
       leak the bearer prefix. httpx INFO standard line does not include headers,
       but this guards against a future httpx version change.
  9. test_httpx_real_gemini_request_no_key_leak (skipif-gated, T5 from pack)
       Real Gemini HTTP request (requires VERIFICATION_GEMINI_API_KEY env var).
       Confirms no AIza substring in captured output under verbose=True.
       Skipped automatically in CI without the env var.

Architecture note (CWE-532):
  structlog's ConsoleRenderer uses RichTracebackFormatter which by default
  sets show_locals=True.  This means any exc_info=True log call renders the
  full stack frame locals to stdout — including asyncpg's cparams dict that
  holds host, user, password, port, database in plaintext.
  P00-S02-T004 fixes this by passing show_locals=False to the formatter
  constructor.  These tests assert the fix holds under both rendering modes.

  P00-S02-T009 adds the third CWE-532 layer: httpx's INFO logger emits the
  full request URL including query-string api keys.  configure_logging() now
  pins logging.getLogger("httpx").setLevel(WARNING) unconditionally so these
  lines never appear in any log output regardless of verbose mode.

Real tests (01-non-negotiables.md §Tests are REAL):
  - No mocking of structlog itself.
  - configure_logging() is called directly — it is the production function.
  - _configured guard is reset before each test and restored after (same
    pattern as test_health.py tests 7 and 9 which already manage this).
  - Tests use real structlog loggers via get_logger(), not logging.getLogger().
  - capsys fixture captures real stdout/stderr output.
  - httpx.MockTransport is used for T009 tests: Google Gemini is an external
    API we do not control — mocking it is explicitly permitted by the project
    non-negotiables ("Only acceptable mocks: external third-party APIs you
    do not control"). The leak vector (httpx INFO URL logging) IS reproduced
    deterministically regardless of transport.

Test isolation note:
  configure_logging() adds a StreamHandler(sys.stdout) to the root logger
  AND calls structlog.configure() which both become global singletons.
  Each test uses _restore_logging_state() in its finally block to reset
  the root logger handlers back to a clean stub, preventing the
  "I/O operation on closed file" error that would otherwise bleed into
  subsequent tests when pytest closes the capsys capture buffer.
  T009 tests additionally restore the httpx/httpcore logger levels via
  _restore_logging_state_with_httpx() to prevent cross-test pollution.

Dependencies:
  - pytest 9.0.3
  - pytest-asyncio 1.3.0 (asyncio_mode=auto in pyproject.toml)
  - structlog 25.5.0
  - httpx 0.28.1
"""
from __future__ import annotations

import contextlib
import logging
import os

import httpx
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


# ===========================================================================
# T009 — httpx logger suppression (P00-S02-T009 / FU-20260509220224)
# ===========================================================================
# Sentinel api key — deterministic, distinguishable from any real key.
# Must contain "AIza" (Gemini prefix) for the leak-detection regex.
_GEMINI_FAKE_SENTINEL = "AIzaSyFAKE-SENTINEL-DO-NOT-LEAK-T009"
_OPENAI_FAKE_SENTINEL = "sk-FAKE-OPENAI-1234567890ABCDEFGHIJ"
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

# skipif guard: same pattern as test_admin_ai_discover_models.py
_GEMINI_SKIP = pytest.mark.skipif(
    not os.getenv("VERIFICATION_GEMINI_API_KEY"),
    reason="VERIFICATION_GEMINI_API_KEY not set — real Gemini API test skipped",
)


def _save_logging_state_with_httpx() -> (
    tuple[bool, list[logging.Handler], int, int]
):
    """Capture logging state including httpx/httpcore logger levels.

    Returns:
      (prev_configured, prev_handlers, prev_httpx_level, prev_httpcore_level)
    """
    import app.core.logging as core_logging

    prev_configured = core_logging._configured
    root = logging.getLogger()
    prev_handlers = list(root.handlers)
    prev_httpx_level = logging.getLogger("httpx").level
    prev_httpcore_level = logging.getLogger("httpcore").level
    return prev_configured, prev_handlers, prev_httpx_level, prev_httpcore_level


def _restore_logging_state_with_httpx(
    prev_configured: bool,
    prev_handlers: list[logging.Handler],
    prev_httpx_level: int,
    prev_httpcore_level: int,
) -> None:
    """Restore root logger, _configured flag, and httpx/httpcore levels.

    Extends _restore_logging_state() with httpx logger level restoration so
    T009 tests do not bleed httpx WARNING level into subsequent tests that
    might check default logger states.

    Params:
      prev_configured     — core_logging._configured before the test.
      prev_handlers       — root logger handlers before the test.
      prev_httpx_level    — httpx logger level before the test (0 = NOTSET).
      prev_httpcore_level — httpcore logger level before the test.
    """
    _restore_logging_state(prev_configured, prev_handlers)
    logging.getLogger("httpx").setLevel(prev_httpx_level)
    logging.getLogger("httpcore").setLevel(prev_httpcore_level)


def _assert_no_key_leaks(captured_text: str) -> None:
    """Assert no Gemini/OpenAI key signatures appear in captured log output.

    Checks for the acceptance regex from the task pack:
      r'AIza|sk-[A-Za-z0-9]{20}'

    Params:
      captured_text — combined stdout + stderr from capsys.
    Errors: AssertionError with diagnostic detail on first failed check.
    """
    import re

    _KEY_PATTERN = re.compile(r"AIza|sk-[A-Za-z0-9]{20}")
    match = _KEY_PATTERN.search(captured_text)
    assert match is None, (
        "Log output contains api key signature — CWE-532 T009 regression.\n"
        f"Pattern matched: {match.group()!r} at position {match.start()}\n"
        f"Full output (first 2000 chars):\n{captured_text[:2000]}"
    )


# ---------------------------------------------------------------------------
# Test 5 (T1) — httpx INFO suppressed in verbose mode (acceptance A1)
# ---------------------------------------------------------------------------


async def test_httpx_logger_suppressed_in_verbose_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """httpx INFO "HTTP Request" line with ?key=AIza... must not appear in verbose mode.

    Reproduces the exact leak vector: httpx logs the full outbound URL at INFO
    level before the transport runs.  A MockTransport proves this because httpx
    logs the REQUEST (not the response), so the mock just prevents a real network
    call while still exercising the logging path.

    Acceptance: A1 (task pack §3).
    """
    prev_state = _save_logging_state_with_httpx()
    try:
        import app.core.logging as core_logging

        core_logging._configured = False
        configure_logging(verbose=True)

        # BEFORE: make an outbound request via MockTransport.
        # httpx will log "HTTP Request: GET <full URL>" at INFO — the fix should
        # suppress this line so the ?key=AIza... sentinel never reaches stdout.
        def _mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"models": []})

        async with httpx.AsyncClient(
            transport=httpx.MockTransport(_mock_handler)
        ) as client:
            await client.get(
                _GEMINI_BASE_URL,
                params={"key": _GEMINI_FAKE_SENTINEL},
            )

        # AFTER: capture and assert no key leak.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        _assert_no_key_leaks(combined)

        # Also assert the INFO marker itself is suppressed (belt-and-suspenders).
        assert "HTTP Request:" not in combined, (
            "httpx INFO 'HTTP Request:' line appeared in verbose output — "
            "httpx logger suppression not working."
        )
    finally:
        _restore_logging_state_with_httpx(*prev_state)


# ---------------------------------------------------------------------------
# Test 6 (T2) — httpx WARNING still propagates (acceptance A4)
# ---------------------------------------------------------------------------


def test_httpx_logger_warning_still_propagates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """WARNING-level messages from the httpx logger must still propagate.

    Verifies acceptance A4: the fix must NOT silence WARNING/ERROR from httpx
    — those carry actionable failure info (connection refused, 5xx, timeouts)
    and contain no api keys in their message.

    Emits a synthetic warning directly via the stdlib httpx logger (not via
    httpx internals) to test the level boundary without requiring a network call.
    """
    prev_state = _save_logging_state_with_httpx()
    try:
        import app.core.logging as core_logging

        core_logging._configured = False
        configure_logging(verbose=True)

        _WARN_MARKER = "test-warning-passthrough-marker-T009"

        # BEFORE: emit a WARNING directly on the httpx logger.
        logging.getLogger("httpx").warning(_WARN_MARKER)

        # AFTER: capture and assert the warning appeared.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        assert _WARN_MARKER in combined, (
            f"httpx WARNING message {_WARN_MARKER!r} did not appear in output — "
            "setLevel(WARNING) may have over-suppressed beyond INFO."
        )
    finally:
        _restore_logging_state_with_httpx(*prev_state)


# ---------------------------------------------------------------------------
# Test 7 (T3) — httpx already silent in production mode (acceptance A3)
# ---------------------------------------------------------------------------


async def test_httpx_logger_already_silent_in_production_mode(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Regression guard: verbose=False must also produce no AIza in output.

    In production mode the root logger is already at WARNING, so httpx INFO is
    already suppressed.  This test guards against a future commit that raises
    root to DEBUG without pinning httpx explicitly — our explicit setLevel(WARNING)
    on the named logger is the defense-in-depth catch.

    Acceptance: A3 (task pack §3).
    """
    prev_state = _save_logging_state_with_httpx()
    try:
        import app.core.logging as core_logging

        core_logging._configured = False
        configure_logging(verbose=False)

        def _mock_handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"models": []})

        # BEFORE: same mock request as T1, but production mode.
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(_mock_handler)
        ) as client:
            await client.get(
                _GEMINI_BASE_URL,
                params={"key": _GEMINI_FAKE_SENTINEL},
            )

        # AFTER: capture and assert no key leak.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        _assert_no_key_leaks(combined)
        assert "HTTP Request:" not in combined, (
            "httpx INFO 'HTTP Request:' line appeared in production mode output."
        )
    finally:
        _restore_logging_state_with_httpx(*prev_state)


# ---------------------------------------------------------------------------
# Test 8 (T4) — OpenAI bearer pattern defense-in-depth (acceptance A2)
# ---------------------------------------------------------------------------


async def test_openai_bearer_pattern_not_in_logs(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """httpx request with Authorization header must not leak bearer prefix.

    Standard httpx INFO line does not include headers, so this test is a
    regression guard against a future httpx version that might add header
    logging.  Defense-in-depth for acceptance A2.

    The httpx logger is at WARNING after configure_logging(), so no INFO
    lines should appear regardless — this confirms no header echoing occurs.
    """
    prev_state = _save_logging_state_with_httpx()
    try:
        import app.core.logging as core_logging

        core_logging._configured = False
        configure_logging(verbose=True)

        def _mock_handler_401(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "unauthorized"})

        # BEFORE: request with Bearer token in Authorization header.
        async with httpx.AsyncClient(
            transport=httpx.MockTransport(_mock_handler_401)
        ) as client:
            await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {_OPENAI_FAKE_SENTINEL}"},
            )

        # AFTER: capture and assert no key signature leak.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        _assert_no_key_leaks(combined)
        assert "Bearer " not in combined, (
            "httpx logged 'Bearer ' in output — header echoing may have occurred."
        )
    finally:
        _restore_logging_state_with_httpx(*prev_state)


# ---------------------------------------------------------------------------
# Test 9 (T5) — Real Gemini request (skipif-gated, acceptance verification)
# ---------------------------------------------------------------------------


@_GEMINI_SKIP
async def test_httpx_real_gemini_request_no_key_leak(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Real Gemini API HTTP request must not leak the api key in verbose logs.

    This test uses the actual VERIFICATION_GEMINI_API_KEY (from .env.local,
    gitignored) to drive a real models-list request against Google Gemini.
    It is the literal verification command from task pack §12 acceptance #3,
    but scoped as a pytest test with isolation instead of a shell pipe.

    Skipped automatically when VERIFICATION_GEMINI_API_KEY is not set.
    Do NOT modify backend/tests/integration/test_admin_ai_discover_models.py
    for this slice — this test lives here per the T009 write_set_extension.
    """
    real_key = os.environ["VERIFICATION_GEMINI_API_KEY"]
    prev_state = _save_logging_state_with_httpx()
    try:
        import app.core.logging as core_logging

        core_logging._configured = False
        configure_logging(verbose=True)

        # BEFORE: real HTTP request to Gemini models endpoint.
        async with httpx.AsyncClient() as client:
            # Ignore actual response — we only care about what was logged.
            with contextlib.suppress(Exception):
                await client.get(
                    _GEMINI_BASE_URL,
                    params={"key": real_key},
                    timeout=10.0,
                )

        # AFTER: capture and assert no AIza* pattern in output.
        captured = capsys.readouterr()
        combined = captured.out + captured.err
        # Explicit check: real key must not appear verbatim.
        assert real_key not in combined, (
            "Real Gemini api key appeared in verbose log output — "
            "httpx suppression not working against real key."
        )
        # Regex check from acceptance criteria.
        _assert_no_key_leaks(combined)
    finally:
        _restore_logging_state_with_httpx(*prev_state)
