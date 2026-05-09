"""
Loader for the 'rag_docs' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Loads rag/documents/politica_vacaciones_es.json metadata into documents
(table-tolerant). No binary PDFs; vectorization is P02-S04-T002.

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
from app.seeds.loader._common import LoadReport
from app.seeds.schemas.rag import RagDocumentSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)


async def load_rag_docs(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
) -> LoadReport:
    """Load the 'rag_docs' namespace: rag/documents/politica_vacaciones_es.json.

    Purpose: pre-register document metadata for J104 RAG admin journey.
    NOTE: no binary PDF, no embeddings. Vectorization is P02-S04-T002.
    Tables targeted: documents.
    Table-tolerant: logs WARN and skips if the table does not exist.

    Params/Returns/Errors: see load_auth docstring.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="rag_docs", dry_run=dry_run)
    ns = "rag_docs"

    _logger.info("seed.namespace.start", namespace=ns, dry_run=dry_run)

    doc = load_fixture(
        source_dir, "rag/documents", "politica_vacaciones_es.json", RagDocumentSeed
    )

    if dry_run:
        report.duration_ms = (time.monotonic() - t0) * 1000
        _logger.info("seed.namespace.done", namespace=ns, persisted=0, dry_run=True)
        return report

    doc_exist = await table_exists(engine, "documents")
    if not doc_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="documents",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("documents")
    else:
        async with engine.begin() as conn:
            result = await conn.execute(
                text(
                    """
                    INSERT INTO documents
                      (title, language, source_path, mime_type, checksum_sha256, collection_name)
                    VALUES
                      (:title, :language, :source_path,
                       :mime_type, :checksum_sha256, :collection_name)
                    ON CONFLICT (title, language) DO UPDATE
                      SET source_path = EXCLUDED.source_path,
                          mime_type = EXCLUDED.mime_type,
                          checksum_sha256 = EXCLUDED.checksum_sha256,
                          collection_name = EXCLUDED.collection_name
                    """
                ),
                {
                    "title": doc.title,
                    "language": doc.language,
                    "source_path": doc.source_path,
                    "mime_type": doc.mime_type,
                    "checksum_sha256": doc.checksum_sha256,
                    "collection_name": doc.collection_name,
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
