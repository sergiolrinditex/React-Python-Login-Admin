"""
Hilo People — RAG collections subpackage public API.

Slice:  P02-S06-T002 — RAG collection endpoints (§D-RAGCOLL-SPLIT)
Phase:  P02 Core Features (the motor)
Purpose: Re-exports rag_collections_router so that main.py can import it with:
           from app.rag.collections import rag_collections_router
         The same import string works whether the implementation is a single file
         or this subpackage (§I.2 DRIFT §D-RAGCOLL-SPLIT).

Source refs:
  - task pack P02-S06-T002 §N (wiring in main.py)
  - task pack P02-S06-T002 §I.2 (§D-RAGCOLL-SPLIT split plan)
"""

from app.rag.collections.router import rag_collections_router

__all__ = ["rag_collections_router"]
