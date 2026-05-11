"""
Backend test suite for Hilo People.

Slice: P00-S01-T001 — Repo scaffold + scripts + env.
Phase: P00 — Scaffold + Design System.

Tests use FastAPI's TestClient (backed by httpx) against the real app
instance — no mocks of business logic. Follows non-negotiables:
  - Real backend, real app, real request/response cycle.
  - Only external third-party APIs may be mocked (none in this slice).
"""
