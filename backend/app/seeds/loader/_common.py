"""
Shared primitives for the seed loader package.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

This module hosts symbols genuinely shared by ≥2 namespace loaders:
  - LoadReport          : dataclass returned by every load_* function.
  - _hash_email         : PII-safe email hashing (auth + history).

NOTE on encryption: admin_ai loader writes plaintext synthetic credentials.
  This is acceptable because they are labelled 'synthetic-' and have no real
  value. When P02-S02-T001 adds encryption-at-rest, a follow-up will add
  encrypt-on-write there. Documented per task pack §Security.

Dependencies:
  - dataclasses (stdlib)
  - hashlib    (stdlib)
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field


def _hash_email(email: str) -> str:
    """Return first 12 chars of SHA-256 hash of an email for safe logging.

    Purpose: avoid logging PII (email addresses) in any log event.
    """
    return hashlib.sha256(email.encode()).hexdigest()[:12]


@dataclass
class LoadReport:
    """Summary of one namespace's loading run.

    Attributes:
      namespace          — the namespace identifier ('auth', 'rag_chat', etc.).
      rows_inserted      — new rows written to DB.
      rows_updated       — existing rows updated.
      skipped_tables     — list of table names that did not exist (WARN path).
      duration_ms        — elapsed time in milliseconds.
      dry_run            — True if no DB writes were performed.
    """

    namespace: str
    rows_inserted: int = 0
    rows_updated: int = 0
    skipped_tables: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    dry_run: bool = False
