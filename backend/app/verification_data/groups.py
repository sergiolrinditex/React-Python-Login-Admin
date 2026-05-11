"""
Hilo People — Group-to-loader mapping for verification data bootstrap.

Slice:  P00-S02-T003 — Verification data loader and reset
Phase:  P00 Scaffold + Design System
Purpose: Defines the canonical set of group names that `bootstrap.py --only`
         accepts. Each group key maps to the fixture sub-paths and loader
         functions. The VALID_GROUPS constant is the single source of truth
         for valid --only values.

Key deps:
  - app.verification_data.loader (load_users, load_rag_collections, etc.)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §6.5 table (6 rows)
  - docs/source-of-truth/instrucciones.md §15 (carga por grupo)
"""

# ---------------------------------------------------------------------------
# Canonical group names — MUST match §6.5 TECHNICAL_GUIDE exactly.
# bootstrap.py --only <group> uses this as argparse choices.
# ---------------------------------------------------------------------------
VALID_GROUPS: tuple[str, ...] = (
    "auth",
    "rag_chat",
    "history",
    "admin_ai",
    "rag_docs",
    "mcp_agents",
)
