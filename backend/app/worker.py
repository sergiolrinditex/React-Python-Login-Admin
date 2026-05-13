"""
Hilo People — Celery application entry point.

Slice:  P02-S04-T002 — Celery vectorization worker
Phase:  P02 Core Features (the motor)
Purpose: Defines the central Celery app instance used by all task modules.
         Required by docker-compose.yml worker service:
           command: celery -A app.worker worker --loglevel=info
         Tasks are auto-discovered via the `include` list below.

WRITE_SET_DRIFT §D-WORKER1: This file is outside the registry write_set
  (tasks_documents.py / tasks_embeddings.py / test_vectorization_worker.py)
  but is intrinsically required — without it the worker container cannot start
  and the tasks cannot register. Pre-declared in handoff P02-S04-T002.md §D-WORKER1.

Key deps:
  - celery==5.6.3  (Celery, app.conf.update)
  - redis==7.4.0   (broker + result backend via REDIS_URL)
  - os             (env var access — REDIS_URL, CELERY_RESULT_BACKEND)

Source refs:
  - docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md §10.4#rag-ingestion
  - task pack P02-S04-T002 §3.4 (Celery app shape)
  - .claude/rules/01-non-negotiables.md §Logging, §Security

Decisions:
  - D-WORKER1: New file outside declared write_set; intrinsic to deliverable.
  - task_acks_late=True: avoids losing tasks on worker crash (message re-queued).
  - task_reject_on_worker_lost=True: paired with acks_late to re-queue on SIGKILL.
  - worker_prefetch_multiplier=1: one task at a time per worker (CPU/IO heavy).
  - task_default_retry_delay=2: base delay for exponential backoff in autoretry_for.
"""

from __future__ import annotations

import os

from celery import Celery

_BROKER = os.getenv("REDIS_URL", "redis://localhost:6379/0")
_BACKEND = os.getenv("CELERY_RESULT_BACKEND", _BROKER)

app = Celery(
    "hilo_workers",
    broker=_BROKER,
    backend=_BACKEND,
    include=[
        "app.workers.tasks_documents",
        "app.workers.tasks_embeddings",
    ],
)

app.conf.update(
    task_acks_late=True,                # avoid losing tasks on worker crash
    task_reject_on_worker_lost=True,    # re-queue on SIGKILL (paired with acks_late)
    worker_prefetch_multiplier=1,       # one-at-a-time: vectorization is CPU/IO heavy
    task_default_retry_delay=2,         # base seconds for exponential autoretry
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)
