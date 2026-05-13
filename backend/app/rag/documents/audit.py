"""
Hilo People — Thin audit helpers for RAG document admin endpoints.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Wraps app.admin._audit.write_admin_ai_audit with RAG-specific action
         strings so callers don't need to remember the exact action names.
         WRITE_SET_DRIFT §D-RAGDOCS-AUDIT: reuses write_admin_ai_audit as-is.

Key deps:
  - app.admin._audit.write_admin_ai_audit (D-S2 independent-session pattern)

Source refs:
  - task pack P02-S06-T001 §A.1.9, §A.3.7 (audit_log requirements)
  - 01-non-negotiables.md §Security (audit log obligatorio on writes)
  - app/admin/_audit.py (reuse as-is per §D-RAGDOCS-AUDIT)
"""

from __future__ import annotations

import uuid
from typing import Any

from app.admin._audit import write_admin_ai_audit


def audit_document_create(
    actor_user_id: uuid.UUID,
    document_id: uuid.UUID,
    metadata: dict[str, Any],
) -> None:
    """Write audit row for admin.rag.document.create action (A.1.9).

    Args:
        actor_user_id: Admin who uploaded the document.
        document_id:   UUID of the created document row.
        metadata:      JSON-safe dict — caller filters PII/secrets.
                       Recommended keys: request_id, ip, user_agent, sha256,
                       bytes, mime, language, collection_id.
    """
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.rag.document.create",
        entity_type="document",
        entity_id=document_id,
        metadata=metadata,
    )


def audit_document_index(
    actor_user_id: uuid.UUID,
    document_id: uuid.UUID,
    metadata: dict[str, Any],
) -> None:
    """Write audit row for admin.rag.document.index action (A.3.7).

    Args:
        actor_user_id: Admin who triggered indexing.
        document_id:   UUID of the document being indexed.
        metadata:      JSON-safe dict. Recommended keys: request_id, ip,
                       document_id, job_id.
    """
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.rag.document.index",
        entity_type="document",
        entity_id=document_id,
        metadata=metadata,
    )
