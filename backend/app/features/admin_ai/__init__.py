"""
Admin AI feature package — AI provider and model management.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Implements: POST /api/v1/admin/ai/providers/{provider_id}/discover-models

Module layout:
  routes.py          — FastAPI router (HTTP layer)
  service.py         — Use-case orchestration (business logic)
  repository.py      — SQLAlchemy data access (read + upsert)
  provider_clients.py — Async HTTP clients per provider_type
  schemas.py         — Pydantic request/response models

Journey: J103 (Gobierno de modelos por Admin AI — participates, does not close)
Source: HILO_PEOPLE_TECHNICAL_GUIDE.md §10.3 + ADR-001 §15
"""
