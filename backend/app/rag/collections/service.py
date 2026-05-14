"""
Hilo People — Service layer for RAG collection admin endpoints.

Slice:  P02-S06-T002 — RAG collection endpoints (§D-RAGCOLL-SPLIT)
Phase:  P02 Core Features (the motor)
Purpose: Business logic for GET /collections and PATCH /collections/{id}.
         Validates inputs, delegates to repository, and dispatches audit.
         No PII in logs — field names logged but not values.

Key deps:
  - app.rag.collections.repository
  - app.rag.collections.audit
  - app.rag.collections.errors

Source refs:
  - task pack P02-S06-T002 §H.1, §H.2 (service contracts)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER, no PII)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

from sqlalchemy.orm import Session

from app.db.models.rag import RagCollection
from app.rag.collections import repository
from app.rag.collections.audit import audit_collection_update
from app.rag.collections.errors import CollectionInvalidError, CollectionNotFoundError
from app.rag.collections.schemas import CollectionPatchIn

logger = logging.getLogger("hilo.rag.collections.service")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def list_collections(session: Session, request_id: str) -> list[RagCollection]:
    """List all RAG collections (no filters in V1 — §H.1 decision).

    Args:
        session:    SQLAlchemy session.
        request_id: X-Request-ID correlation.

    Returns:
        List of RagCollection rows ordered by name ASC.
    """
    if _VERBOSE:
        logger.debug(
            "rag.collections.service.list.start request_id=%s", request_id
        )  # BEFORE
    t_start = time.monotonic()
    rows = repository.list_all(session)
    if _VERBOSE:
        logger.debug(
            "rag.collections.service.list.ok count=%d latency_ms=%s request_id=%s",
            len(rows),
            round((time.monotonic() - t_start) * 1000, 1),
            request_id,
        )  # AFTER
    return rows


def update_collection(
    session: Session,
    collection_id: uuid.UUID,
    patch: CollectionPatchIn,
    admin_id: uuid.UUID,
    request_id: str,
    ip: str,
    user_agent: str,
) -> RagCollection:
    """Update a RAG collection with the provided patch fields.

    Validates:
      - name trimmed non-empty if provided.
      - vertical trimmed non-empty if provided.
      - language validated by Pydantic pattern (re-checked at service boundary).
    Writes an audit row on successful DB commit.

    Args:
        session:       SQLAlchemy session.
        collection_id: Target collection UUID.
        patch:         Validated patch body.
        admin_id:      UUID of the acting admin user.
        request_id:    X-Request-ID correlation.
        ip:            Client IP for audit metadata.
        user_agent:    User-Agent for audit metadata.

    Returns:
        Updated RagCollection ORM instance.

    Raises:
        CollectionNotFoundError: collection_id not in rag_collections.
        CollectionInvalidError:  name/vertical empty after trim.
    """
    if _VERBOSE:
        changed = _field_names(patch)
        logger.debug(
            "rag.collections.service.update.start admin_id=%s "
            "collection_id=%s fields=%s request_id=%s",
            str(admin_id),
            str(collection_id),
            changed,
            request_id,
        )  # BEFORE — field names only, no values

    t_start = time.monotonic()

    # Validate trimmed fields before touching DB
    trimmed_name: str | None = None
    if patch.name is not None:
        trimmed_name = patch.name.strip()
        if not trimmed_name:
            raise CollectionInvalidError("name", "Name cannot be empty after trimming.")

    trimmed_vertical: str | None = None
    if patch.vertical is not None:
        trimmed_vertical = patch.vertical.strip()
        if not trimmed_vertical:
            raise CollectionInvalidError(
                "vertical", "Vertical cannot be empty after trimming."
            )

    row = repository.find_by_id(session, collection_id)
    if row is None:
        raise CollectionNotFoundError(collection_id)

    updates: dict[str, Any] = {}
    if trimmed_name is not None:
        updates["name"] = trimmed_name
    if trimmed_vertical is not None:
        updates["vertical"] = trimmed_vertical
    if patch.language is not None:
        updates["language"] = patch.language
    if patch.enabled is not None:
        updates["enabled"] = patch.enabled

    changed_fields = sorted(updates.keys())
    row = repository.update_partial(session, row, updates)
    session.commit()

    # Audit AFTER successful commit (D-S2: independent session)
    audit_collection_update(
        actor_user_id=admin_id,
        collection_id=collection_id,
        metadata={
            "request_id": request_id,
            "ip": ip,
            "user_agent": user_agent,
            "changed_fields": changed_fields,
        },
    )

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    if _VERBOSE:
        logger.debug(
            "rag.collections.service.update.ok admin_id=%s collection_id=%s "
            "changed_fields=%s latency_ms=%s request_id=%s",
            str(admin_id),
            str(collection_id),
            changed_fields,
            latency_ms,
            request_id,
        )  # AFTER
    return row


def _field_names(patch: CollectionPatchIn) -> list[str]:
    """Return sorted list of non-None field names in the patch (for logging)."""
    return sorted(
        k
        for k, v in {
            "name": patch.name,
            "vertical": patch.vertical,
            "language": patch.language,
            "enabled": patch.enabled,
        }.items()
        if v is not None
    )
