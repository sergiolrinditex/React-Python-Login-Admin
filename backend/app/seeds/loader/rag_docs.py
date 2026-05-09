"""
Loader for the 'rag_docs' namespace.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Loads all documents from rag/documents/*.json (excluding DEPRECATED entries)
into the documents table. Table-tolerant: skips when table does not exist (P00/P01 state).

CHANGE from T003:
  - Reads ALL non-deprecated .json files from rag/documents/ directory
    instead of a single hard-coded filename.
  - A document is skipped if title starts with 'DEPRECATED-DO-NOT-LOAD'.
  - Logging: logs document title + language per upsert (no PII).

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
from app.seeds.schemas.rag import RagDocumentSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)

_DEPRECATED_TITLE_PREFIX = "DEPRECATED-DO-NOT-LOAD"


async def load_rag_docs(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
    bundle_type: BundleType = "synthetic",
) -> LoadReport:
    """Load the 'rag_docs' namespace: all documents from rag/documents/*.json.

    Purpose: pre-register document metadata for J104 RAG admin journey.
    NOTE: no binary PDF embeddings. Vectorization is P02-S04-T002.
    Tables targeted: documents.
    Table-tolerant: logs WARN and skips if the table does not exist.

    Documents with title starting 'DEPRECATED-DO-NOT-LOAD' are silently skipped.

    Params:
      engine      — async engine.
      source_dir  — bundle root directory.
      dry_run     — validate only; no DB writes.
      bundle_type — propagated for consistency (no schema guards here).
    Returns: LoadReport.
    Errors: BundleLoadError if fixture is missing or invalid.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="rag_docs", dry_run=dry_run)
    ns = "rag_docs"

    _logger.info("seed.namespace.start", namespace=ns, dry_run=dry_run, bundle_type=bundle_type)

    # Discover all .json files in rag/documents/.
    docs_dir = source_dir / "rag" / "documents"
    doc_files = sorted(docs_dir.glob("*.json")) if docs_dir.exists() else []

    docs: list[RagDocumentSeed] = []
    for doc_file in doc_files:
        doc = load_fixture(source_dir, "rag/documents", doc_file.name, RagDocumentSeed)
        if doc.title.startswith(_DEPRECATED_TITLE_PREFIX):
            _logger.debug(
                "seed.rag_docs.skip_deprecated",
                filename=doc_file.name,
            )
            continue
        docs.append(doc)

    _logger.info("seed.rag_docs.docs_discovered", count=len(docs), total_files=len(doc_files))

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
        for doc in docs:
            _logger.debug(
                "seed.rag_docs.upsert_document.before",
                title=doc.title[:50],
                language=doc.language,
                collection=doc.collection_name,
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO documents
                          (title, language, source_path, mime_type,
                           checksum_sha256, collection_name)
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
            _logger.debug(
                "seed.rag_docs.upsert_document.after",
                title=doc.title[:50],
                language=doc.language,
            )

    report.duration_ms = (time.monotonic() - t0) * 1000
    _logger.info(
        "seed.namespace.done",
        namespace=ns,
        persisted=report.rows_inserted,
        skipped_missing_table=len(report.skipped_tables),
        duration_ms=round(report.duration_ms, 1),
    )
    return report
