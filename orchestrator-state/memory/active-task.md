# Active task

- ID: P00-S02-T004
- Title: Disable structlog Rich-traceback show_locals globally to prevent DSN/secret leaks in error logs
- Status: blocked
- Phase: P00

## Acceptance
- 1) app/core/logging.py configures structlog's traceback formatter with show_locals=False (or installs a frame-locals redaction processor that scrubs keys matching password|pwd|token|secret|api_key|encrypted_secret|dsn|database_url|connection_string and values matching DSN-like substrings). 2) New test in backend/tests/test_logging.py exercises a real exception with sensitive locals (e.g. asyncpg auth failure with a fake DSN) and asserts that the rendered log line does NOT contain the secret value
- the host
- the port
- the user
- or the password key value. 3) ENABLE_VERBOSE_LOGGING toggle still works correctly. 4) ruff + mypy clean. 5) Regression: existing 8 health tests + 39 dep-smoke tests still pass. 6) Existing /ready 503 path continues to log error_class + db_detail (sanitized) without exc_info=True OR with a configuration that no longer leaks.

## Allowed paths

## DAG conflict guardrails
### Conflict groups
- infra:logging
### Write set
- backend/app/core/logging.py
- backend/tests/test_logging.py

## Verification commands
- `Real reproduction: launch uvicorn with bad DATABASE_URL (port without listener)`
- `curl /ready`
- `grep stdout for 'password'`
- `'pwd'`
- `the actual password value`
- `host`
- `port — all must be absent. Run with both ENABLE_VERBOSE_LOGGING=true and =false. Also reproduce with a deliberate failing path elsewhere (any other use case that catches an exception and logs with exc_info=True). Capture logs in evidence dir.`
