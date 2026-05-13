"""
Hilo People — Admin AI providers subpackage.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Re-exports the FastAPI router so `from app.admin.providers import
         providers_router` keeps working after the file-size-driven split
         (validator finding #1 on the original 590-LoC monolith).

Layout (each file ≤ ~200 LoC):
  - schemas.py    — Pydantic v2 request/response models
  - repository.py — DB queries (list_providers, create_provider)
  - audit.py      — Audit-row builder (delegates to admin/_audit.py)
  - service.py    — Orchestration: encrypt + persist + audit + RateLimiter
  - router.py     — FastAPI handlers (GET, POST)
"""

from __future__ import annotations

from app.admin.providers.router import providers_router

__all__ = ["providers_router"]
