"""
Hilo People — Thin audit wrapper for RAG collection admin endpoints.

Slice:  P02-S06-T002 — RAG collection endpoints (§D-RAGCOLL-SPLIT)
Phase:  P02 Core Features (the motor)
Purpose: Wraps app.admin._audit.write_admin_ai_audit with the RAG-collection-
         specific action string so callers don't need to remember exact action
         names. Reuses D-S2 independent-session pattern from the shared helper.

Key deps:
  - app.admin._audit.write_admin_ai_audit (D-S2 independent-session pattern)

Source refs:
  - task pack P02-S06-T002 §H.2 (audit requirement on PATCH)
  - 01-non-negotiables.md §Security (audit log obligatorio on writes)
  - app/admin/_audit.py (reuse as-is — do NOT duplicate)
"""

from __future__ import annotations

import uuid
from typing import Any

from app.admin._audit import write_admin_ai_audit


def audit_collection_update(
    actor_user_id: uuid.UUID,
    collection_id: uuid.UUID,
    metadata: dict[str, Any],
) -> None:
    """Write audit row for admin.rag.collection.update action.

    Delegates to the shared helper (D-S2 independent-session pattern):
    the audit row is committed in its own session so it survives even if
    the caller's main transaction rolls back.

    Args:
        actor_user_id: Admin who performed the update.
        collection_id: UUID of the updated rag_collections row.
        metadata:      JSON-safe dict. Recommended keys: request_id, ip,
                       user_agent, changed_fields. Caller must filter PII.
    """
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.rag.collection.update",
        entity_type="rag_collection",
        entity_id=collection_id,
        metadata=metadata,
    )
