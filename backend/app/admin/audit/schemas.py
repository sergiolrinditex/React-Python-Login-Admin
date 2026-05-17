"""
Hilo People — Admin audit endpoint Pydantic schemas.

Slice:  P04-S03-T003 — GET /api/v1/admin/audit endpoint
Phase:  P04 Complete Features
Purpose: Defines the Pydantic request/response models used by the audit
         endpoint. AuditLogOut serialises an AuditLog ORM row to JSON;
         ListAuditQuery validates the URL query parameters with FastAPI Query.

Key deps:
  - pydantic (BaseModel, ConfigDict)
  - fastapi (Query)
  - app.db.models.auth.AuditLog (ORM target — for field reference)

Source refs:
  - task pack P04-S03-T003 §Front → Back → DB contract
  - TECHNICAL_GUIDE §6.4 (envelope, AuditLog shape)
  - 01-non-negotiables.md §API contract (envelope), §Logging (no PII)

Decisions:
  - D-SCHEMA-METADATA: Pydantic field named `metadata` maps to ORM
    attribute `extra_metadata` (DB column `metadata`). The ORM uses
    `extra_metadata` to avoid SQLAlchemy class-attr clash; the API always
    exposes `metadata` for JSON consistency.
  - D-SCHEMA-WINDOW: `from_dt` + `to_dt` are REQUIRED (no default). This
    rejects unbounded window queries. 90-day cap enforced in service layer.
  - D-SCHEMA-PAGE-SIZE: default limit=50, max=200 (consistent with admin GETs).
  - D-SCHEMA-CURSOR: opaque base64-encoded "(created_at_iso|id_uuid)" string.
    Validated in repository layer; here it is typed as str | None.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Response schema: single AuditLog row
# ---------------------------------------------------------------------------

class AuditLogOut(BaseModel):
    """Serialised representation of one audit_logs row.

    Field `metadata` is populated from ORM attribute `extra_metadata`
    (see D-SCHEMA-METADATA). `actor_user_id` may be None when the user
    was deleted (GDPR Art. 17 ON DELETE SET NULL).

    Refs: task pack §Front→Back→DB contract, TECHNICAL_GUIDE §6.4.
    """

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    actor_user_id: uuid.UUID | None = None
    action: str
    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    @classmethod
    def from_orm_row(cls, row: Any) -> "AuditLogOut":
        """Build AuditLogOut from an AuditLog ORM instance.

        Maps ORM `extra_metadata` → Pydantic `metadata` (D-SCHEMA-METADATA).

        Args:
            row: AuditLog ORM instance.

        Returns:
            AuditLogOut Pydantic model.
        """
        return cls(
            id=row.id,
            actor_user_id=row.actor_user_id,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            metadata=row.extra_metadata or {},
            created_at=row.created_at,
        )


# ---------------------------------------------------------------------------
# Query parameters schema (FastAPI Query extraction)
# ---------------------------------------------------------------------------

def get_list_audit_query(
    from_dt: datetime = Query(..., alias="from", description="Window start (ISO 8601, required)"),
    to_dt: datetime = Query(..., alias="to", description="Window end (ISO 8601, required)"),
    actor: uuid.UUID | None = Query(default=None, description="Filter by actor user UUID"),
    action: str | None = Query(default=None, description="Filter by action string (exact match)"),
    cursor: str | None = Query(default=None, description="Opaque pagination cursor"),
    limit: int = Query(default=50, ge=1, le=200, description="Page size 1–200 (default 50)"),
) -> "ListAuditQuery":
    """FastAPI Query extractor that returns a validated ListAuditQuery.

    Args:
        from_dt:  Window start datetime (required).
        to_dt:    Window end datetime (required).
        actor:    Optional actor_user_id UUID filter.
        action:   Optional action string filter (exact match).
        cursor:   Optional opaque pagination cursor.
        limit:    Page size 1–200 (default 50).

    Returns:
        ListAuditQuery validated instance.
    """
    return ListAuditQuery(
        from_dt=from_dt,
        to_dt=to_dt,
        actor=actor,
        action=action,
        cursor=cursor,
        limit=limit,
    )


class ListAuditQuery(BaseModel):
    """Validated audit query parameters.

    Not used directly as a FastAPI dependency (FastAPI doesn't support Query
    inside a Pydantic model for GET requests without a custom dependency).
    Populated by get_list_audit_query().

    Refs: task pack §Front→Back→DB contract.
    """

    from_dt: datetime
    to_dt: datetime
    actor: uuid.UUID | None = None
    action: str | None = None
    cursor: str | None = None
    limit: int = 50


__all__ = ["AuditLogOut", "ListAuditQuery", "get_list_audit_query"]
