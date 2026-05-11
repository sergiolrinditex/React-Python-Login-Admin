"""
Hilo People — integration test package.

Slice:  P00-S02-T003 — Verification data loader and reset
Phase:  P00 Scaffold + Design System
Purpose: Integration tests that require a live Postgres instance.
         Tests are marked with @pytest.mark.integration and require
         DATABASE_URL env var pointing to a real Postgres DB.
"""
