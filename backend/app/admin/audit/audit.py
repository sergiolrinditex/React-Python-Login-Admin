"""
Hilo People — Admin audit feature-local audit writer (stub, read-only).

Slice:  P04-S03-T003 — GET /api/v1/admin/audit endpoint
Phase:  P04 Complete Features
Purpose: Feature-local audit writer module, kept for structural symmetry
         with providers/audit.py and model_catalog/audit.py even though
         GET /api/v1/admin/audit is a READ-ONLY endpoint.

         This module is intentionally a stub (D-AUDIT-READONLY): the GET
         audit endpoint does not write any audit_logs row. This is
         consistent with:
           - admin/usage.py decision "No audit row for GET /admin/usage"
           - admin/providers/router.py list_providers (no audit row for GETs)

         The reserved function below documents the intent and prevents
         accidental future addition of audit writes in the read path.
         If a future slice requires audit logging for audit-query events
         (e.g. compliance requirements for "who queried what"), a new
         task should add that behavior via write_admin_ai_audit or a
         dedicated writer here.

Key deps: None (intentionally stub — no _audit.py import).

Source refs:
  - task pack P04-S03-T003 §D-AUDIT-READONLY, §Module layout
  - admin/usage.py (precedent: "No audit row for GET /admin/usage")
"""

from __future__ import annotations


def write_audit_query_audit() -> None:
    """Reserved hook: write an audit row for an audit-query event.

    INTENTIONALLY A NO-OP (D-AUDIT-READONLY).

    GET /api/v1/admin/audit is a read-only endpoint. It does not write
    audit rows consistent with other admin GET endpoints in this codebase
    (usage.py, providers list). If this behavior changes, replace this
    stub with a real implementation calling
    `app.admin._audit.write_admin_ai_audit` and document the reason.

    Returns:
        None (always — this is a no-op stub).
    """
    return None


__all__ = ["write_audit_query_audit"]
