"""
Hilo People — Celery worker tasks package.

Slice:  P02-S04-T002 — Celery vectorization worker
Phase:  P02 Core Features (the motor)
Purpose: Package marker for app.workers. Exports the two public task functions
         so callers can import them without knowing internal module layout.

WRITE_SET_DRIFT §D-WORKER1: This file is outside the registry write_set
  but is required as a Python package marker. Pre-declared in handoff
  P02-S04-T002.md §D-WORKER1.

Source refs:
  - task pack P02-S04-T002 §3.3 (module layout)
"""

from __future__ import annotations

from app.workers.tasks_documents import extract_and_chunk
from app.workers.tasks_embeddings import embed_chunks

__all__ = ["extract_and_chunk", "embed_chunks"]
