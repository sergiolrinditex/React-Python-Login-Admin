"""
Shared primitives for the seed loader package.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

This module hosts symbols genuinely shared by ≥2 namespace loaders:
  - BundleType       : Literal type for synthetic vs productive bundles.
  - BundleLoadError  : re-exported from app.seeds.io for convenience.
  - LoadReport       : dataclass returned by every load_* function.
  - _hash_email      : PII-safe email hashing (auth + history).
  - resolve_env_var  : reads env var for productive bundle fields, fail-fast when
                       required=True and the var is not set.

CHANGE from T003: added BundleType and resolve_env_var to support productive bundle
  delivery (FU-20260509073000). Synthetic path remains unchanged for back-compat.

Dependencies:
  - dataclasses (stdlib)
  - hashlib    (stdlib)
  - os         (stdlib)
"""
from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

# Canonical bundle type — controls schema validators and env-var resolution.
BundleType = Literal["synthetic", "productive"]


def _hash_email(email: str) -> str:
    """Return first 12 chars of SHA-256 hash of an email for safe logging.

    Purpose: avoid logging PII (email addresses) in any log event.
    """
    return hashlib.sha256(email.encode()).hexdigest()[:12]


def resolve_env_var(name: str | None, *, required: bool) -> str | None:
    """Resolve an env-var reference from the productive bundle.

    Purpose: read the real API key / token from the process environment.
    Called by loaders when _bundle_type=productive and a field uses *_env naming.

    Params:
      name     — name of the env var to read (e.g. 'VERIFICATION_GEMINI_API_KEY').
                 If None, returns None without checking required.
      required — if True and the env var is not set (or empty), raises BundleLoadError.
    Returns: the env var value, or None if name is None.
    Errors:
      BundleLoadError if required=True and the var is unset/empty.

    NOTE: imported lazily from app.seeds.io to avoid circular imports.
    """
    # Lazy import to avoid circular dependency between _common and io.
    from app.seeds.io import BundleLoadError  # noqa: PLC0415

    if name is None:
        return None

    value = os.environ.get(name, "").strip()
    if required and not value:
        raise BundleLoadError(
            Path(".env.local"),
            f"Productive bundle env var '{name}' is required but not set. "
            "Set it in .env.local (gitignored) and run: set -a; source .env.local; set +a",
        )
    return value or None


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
