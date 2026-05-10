# Official Doc Note — httpx 0.28.1 Transport Logger & API Key Leak

**TASK_ID**: P00-S02-T009
**Date**: 2026-05-10
**Status**: VERIFIED — no discrepancy with planner strategy
**RESOLVED**: Plan aligns with official docs; no action required from developer beyond implementing as planned.

## Findings Summary

### 1. httpx Logger Names (Official: python-httpx.org/logging/)

Two and only two loggers are documented for httpx 0.28.1:

| Logger | Level | What it emits |
|---|---|---|
| `httpx` | **INFO** | `HTTP Request: GET https://host.com/path?key=AIza... HTTP/1.1 200 OK` |
| `httpcore` | **DEBUG** | TCP/TLS connection events, request headers bytes, response header/body bytes |

**The URL line (including `?key=AIza...` query string) is emitted by the `httpx` logger at INFO level.**

There is NO third logger or separate transport-layer logger. The only two loggers are `httpx` and `httpcore`.

### 2. Fix Correctness

```python
logging.getLogger("httpx").setLevel(logging.WARNING)
```

This is the correct, idiomatic, sufficient fix:
- Targets the right logger (`httpx`)
- Suppresses the INFO-level URL line (the only place `?key=...` appears)
- `httpcore` does NOT emit the URL; targeting `httpx` alone is complete
- No structlog changes needed — structlog's `LoggerFactory()` delegates to stdlib; stdlib level gate fires before structlog processing

### 3. structlog 25.5.0 Interaction

When `structlog.stdlib.LoggerFactory()` is used (as in this project), structlog wraps stdlib loggers. The stdlib level check (`logging.getLogger("httpx").setLevel(logging.WARNING)`) runs before structlog ever receives the record. Setting the stdlib logger level is the correct layer to operate on — no `ProcessorFormatter` changes or structlog processor modifications are needed.

Source: Context7 `/hynek/structlog` — standard-library.md confirms `LoggerFactory` wraps stdlib loggers; stdlib level gate is the first filter.

### 4. httpx.MockTransport API (0.28.1)

- **Class**: `httpx.MockTransport(handler)` — stable, documented, no deprecation warnings
- **Sync handler**: `def handler(request: httpx.Request) -> httpx.Response` — for use with `httpx.Client`
- **Async handler**: `async def handler(request: httpx.Request) -> httpx.Response` — for use with `httpx.AsyncClient`
- `handle_async_request()` detects if the handler returns a coroutine and awaits it automatically
- A sync handler cannot be passed to `AsyncClient` — developer must use `async def` for async test cases

Source: WebFetch of `github.com/encode/httpx/blob/0.28.1/httpx/_transports/mock.py` + official transports docs.

## Official Sources

- https://www.python-httpx.org/logging/ — logger names, levels, output format
- https://raw.githubusercontent.com/encode/httpx/master/docs/logging.md — verbatim log output examples
- https://www.python-httpx.org/advanced/transports/ — MockTransport API
- https://github.com/encode/httpx/blob/0.28.1/httpx/_transports/mock.py — MockTransport source at tag 0.28.1
- Context7 `/encode/httpx` — logging + transports
- Context7 `/hynek/structlog` — stdlib integration (standard-library.md, bound-loggers.md)

## Discrepancy with Planner Strategy

**NONE.** The planner's fix is correct and complete as stated.

RESOLVED: Confirmed — plan aligns with official documentation.
