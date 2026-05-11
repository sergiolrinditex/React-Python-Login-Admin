"""
Hilo People — backend core package marker.

Slice:   P00-S01-T003 — Backend dependency pack
Phase:   P00 Scaffold + Design System
Purpose: Empty package marker for `backend/app/core/`. This file intentionally
         contains no business logic. Its presence keeps the write_set glob
         `backend/app/core/**` non-vacuous and allows future core modules
         (config, logging, security, etc.) to be imported as `from app.core.X
         import Y`.

Note: No functions defined here — the non-negotiables logging rule (BEFORE/AFTER
per function) does not apply to an empty marker. Per 01-non-negotiables.md §File
size: "One responsibility per file" — the responsibility here is solely to
declare the package namespace.

Dependencies: none (no imports; zero dependencies beyond Python stdlib).
"""
