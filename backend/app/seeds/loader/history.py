"""
Loader for the 'history' namespace.

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Loads history/conversations.json into conversations (table-tolerant).

CHANGE from T003: added bundle_type kwarg for API consistency with other loaders.
  No bundle_type-specific logic needed for conversations (no credentials).

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
from app.seeds.loader._common import BundleType, LoadReport, _hash_email
from app.seeds.schemas.history import ConversationListSeed
from app.seeds.table_probe import table_exists

_logger = get_logger(__name__)


async def load_history(
    engine: AsyncEngine,
    source_dir: Path,
    *,
    dry_run: bool = False,
    bundle_type: BundleType = "synthetic",
) -> LoadReport:
    """Load the 'history' namespace: history/conversations.json.

    Purpose: seed 2+ conversation records for J102 history/language journey.
    Tables targeted: conversations.
    Table-tolerant: logs WARN and skips if the table does not exist.

    Params/Returns/Errors: see load_auth docstring.
    """
    t0 = time.monotonic()
    report = LoadReport(namespace="history", dry_run=dry_run)
    ns = "history"

    _logger.info("seed.namespace.start", namespace=ns, dry_run=dry_run, bundle_type=bundle_type)

    convo_data = load_fixture(source_dir, ns, "conversations.json", ConversationListSeed)

    if dry_run:
        report.duration_ms = (time.monotonic() - t0) * 1000
        _logger.info("seed.namespace.done", namespace=ns, persisted=0, dry_run=True)
        return report

    conv_exist = await table_exists(engine, "conversations")
    if not conv_exist:
        _logger.warning(
            "seed.namespace.table_missing",
            namespace=ns,
            table="conversations",
            reason="table_missing",
            action="skipped",
        )
        report.skipped_tables.append("conversations")
    else:
        for convo in convo_data.conversations:
            email_hash = _hash_email(convo.user_email)
            _logger.debug(
                "seed.history.upsert_conversation.before",
                title_len=len(convo.title),
                email_hash=email_hash,
            )
            async with engine.begin() as conn:
                result = await conn.execute(
                    text(
                        """
                        INSERT INTO conversations (user_email, title, language)
                        VALUES (:user_email, :title, :language)
                        ON CONFLICT (user_email, title) DO UPDATE
                          SET language = EXCLUDED.language
                        """
                    ),
                    {
                        "user_email": convo.user_email,
                        "title": convo.title,
                        "language": convo.language,
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
