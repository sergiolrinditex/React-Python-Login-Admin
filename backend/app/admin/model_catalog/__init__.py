"""
Hilo People — Admin AI model catalog subpackage.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Re-exports the FastAPI router so `from app.admin.model_catalog import
         models_router` keeps working after the split (validator finding #1
         on the original 522-LoC monolith).

Layout (each file ≤ ~200 LoC):
  - schemas.py    — Pydantic v2 request/response models
  - repository.py — DB queries
  - audit.py      — Audit-row builder (delegates to admin/_audit.py)
  - service.py    — Orchestration (locate + patch + audit)
  - router.py     — FastAPI handlers (GET, PATCH)
"""

from __future__ import annotations

from app.admin.model_catalog.router import models_router

__all__ = ["models_router"]
