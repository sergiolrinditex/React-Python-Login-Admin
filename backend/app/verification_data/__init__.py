"""
Hilo People — verification_data package.

Slice:  P00-S02-T003 — Verification data loader and reset
Phase:  P00 Scaffold + Design System
Purpose: Idempotent fixture loader for sandbox verification data. Reads JSON
         fixtures from data/verification/, validates them with Pydantic v2,
         and loads them into Postgres using UPSERT (INSERT ON CONFLICT).
         If a target table does not exist yet (pre-migration), the group is
         deferred with WARN instead of raising an error.

Entrypoint: python -m app.verification_data.bootstrap --source data/verification
            [--only <group>] [--dry-run]

Source refs:
  - docs/source-of-truth/instrucciones.md §15 Verification Data
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §6.5
  - 01-non-negotiables.md §Logging, §Security
"""
