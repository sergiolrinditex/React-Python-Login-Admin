"""
Pydantic schema models for each seed namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Each sub-module defines strict models (extra='forbid') for its namespace.
Credential fields with synthetic- guard are validated at schema level.

Dependencies:
  - pydantic 2.12.5
"""
