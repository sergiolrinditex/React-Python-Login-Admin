"""
Loader for the 'rag_chat' namespace.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Loads rag/collections.json into rag_collections (table-tolerant).

CHANGE from T003: added bundle_type kwarg for API consistency with other loaders.
  No bundle_type-specific logic needed for collections (no credentials).

Dependencies:
  - sqlalchemy[asyncio] 2.0.49
  - pydantic 2.12.5
  - structlog 25.5.0
"""
from __future__ import annotations

import time
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.logging import get_logger
from app.seeds.io import load_fixture
from app.seeds.loader._common import BundleType, LoadReport
from app.seeds.schemas.rag import RagCollectionListSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)


async def load_rag_chat(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
    bundle_type: BundleType = "synthetic",
) -> LoadReport:
    """Load the 'rag_chat' namespace: rag/collections.json.

    Purpose: seed the RAG collection definition for J101 chat journey.
    Tables targeted: rag_collections.
    Table-tolerant: logs WARN and skips if the table does not exist.

    Params:
      engine      — async engine.
      source_dir  — bundle root directory.
      dry_run     — validate only; no DB writes.
      bundle_type — propagated for API consistency (no credential guards here).
    Returns: LoadReport.
    Errors: BundleLoadError if fixture is missing or invalid.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="rag_chat", dry_run=dry_run)
    ns = "rag_chat"

    _logger.info("seed.namespace.start", namespace=ns, dry_run=dry_run, bundle_type=bundle_type)

    collections_data = load_fixture(source_dir, "rag", "collections.json", RagCollectionListSeed)

    if dry_run:
        report.duration_ms = (time.monotonic() - t0) * 1000
        _logger.info("seed.namespace.done", namespace=ns, persisted=0, dry_run=True)
        return report

    coll_exist = await table_exists(engine, "rag_collections")
    if not coll_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="rag_collections",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("rag_collections")
    else:
        for coll in collections_data.collections:
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO rag_collections (name, language, vertical, enabled, description)
                        VALUES (:name, :language, :vertical, :enabled, :description)
                        ON CONFLICT (name) DO UPDATE
                          SET language = EXCLUDED.language,
                              vertical = EXCLUDED.vertical,
                              enabled = EXCLUDED.enabled,
                              description = EXCLUDED.description
                        """
                    ),
                    {
                        "name": coll.name,
                        "language": coll.language,
                        "vertical": coll.vertical,
                        "enabled": coll.enabled,
                        "description": coll.description,
                    },
                )
            report.rows_inserted += max(result.rowcount, 1)

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report
