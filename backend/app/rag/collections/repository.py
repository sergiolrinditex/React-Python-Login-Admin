"""
Hilo People — Repository layer for RAG collection admin endpoints.

Slice:  P02-S06-T002 — RAG collection endpoints (§D-RAGCOLL-SPLIT)
Phase:  P02 Core Features (the motor)
Purpose: Pure DB layer — no business logic. All operations use parametrized
         SQLAlchemy queries. Provides:
           - list_all:       Fetch all RagCollection rows ordered by name ASC.
           - find_by_id:     Fetch single row by UUID.
           - update_partial: Apply partial field update and flush.

Key deps:
  - sqlalchemy==2.0.49 (sync Session, parametrized queries)
  - app.db.models.rag.RagCollection

Source refs:
  - task pack P02-S06-T002 §H (DB ops contract)
  - 01-non-negotiables.md §Database (parametrized, transactions)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.rag import RagCollection

logger = logging.getLogger("hilo.rag.collections.repository")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def list_all(session: Session) -> list[RagCollection]:
    """Fetch all RAG collections ordered by name ASC.

    Returns an empty list if the table is empty (valid 200 scenario).

    Args:
        session: Active SQLAlchemy session.

    Returns:
        List of RagCollection ORM instances ordered by name ASC.
    """
    if _VERBOSE:
        logger.debug("rag.collections.repository.list_all.start")  # BEFORE
    t_start = time.monotonic()
    rows: list[RagCollection] = list(
        session.execute(sa.select(RagCollection).order_by(RagCollection.name.asc()))
        .scalars()
        .all()
    )
    if _VERBOSE:
        logger.debug(
            "rag.collections.repository.list_all.ok count=%d latency_ms=%s",
            len(rows),
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER
    return rows


def find_by_id(session: Session, collection_id: uuid.UUID) -> RagCollection | None:
    """Fetch a single RagCollection by primary key.

    Args:
        session:       Active SQLAlchemy session.
        collection_id: UUID to look up.

    Returns:
        RagCollection ORM instance or None if not found.
    """
    if _VERBOSE:
        logger.debug(
            "rag.collections.repository.find_by_id.start collection_id=%s",
            str(collection_id),
        )  # BEFORE
    t_start = time.monotonic()
    row: RagCollection | None = session.execute(
        sa.select(RagCollection).where(RagCollection.id == collection_id)
    ).scalar_one_or_none()
    if _VERBOSE:
        logger.debug(
            "rag.collections.repository.find_by_id.ok found=%s latency_ms=%s",
            row is not None,
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER
    return row


def update_partial(
    session: Session,
    collection: RagCollection,
    fields: dict[str, Any],
) -> RagCollection:
    """Apply a partial update to a RagCollection and flush to the session.

    Caller is responsible for committing. Only the keys present in `fields`
    are written; absent keys are left unchanged.

    Args:
        session:    Active SQLAlchemy session.
        collection: RagCollection ORM instance to mutate.
        fields:     Dict of {attr_name: new_value} to apply.

    Returns:
        The mutated RagCollection instance (flushed, not yet committed).
    """
    if _VERBOSE:
        logger.debug(
            "rag.collections.repository.update_partial.start "
            "collection_id=%s changed_fields=%s",
            str(collection.id),
            sorted(fields.keys()),
        )  # BEFORE — field names only, no values
    t_start = time.monotonic()
    for attr, value in fields.items():
        setattr(collection, attr, value)
    session.flush()
    if _VERBOSE:
        logger.debug(
            "rag.collections.repository.update_partial.ok "
            "collection_id=%s changed_fields=%s latency_ms=%s",
            str(collection.id),
            sorted(fields.keys()),
            round((time.monotonic() - t_start) * 1000, 1),
        )  # AFTER
    return collection
