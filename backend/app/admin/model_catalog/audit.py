"""
Hilo People — Admin AI model audit writer.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Thin wrapper around the shared admin AI audit helper that builds the
         model-specific metadata payload (action='admin.ai.model.update').

Key deps:
  - app.admin._audit.write_admin_ai_audit
"""

from __future__ import annotations

import uuid
from typing import Any

from app.admin._audit import write_admin_ai_audit


def write_model_audit(
    *,
    actor_user_id: uuid.UUID,
    model_id: uuid.UUID,
    from_state: dict[str, Any],
    to_state: dict[str, Any],
    request_id: str,
    ip: str,
    user_agent: str,
    outcome: str,
    previous_default_id: uuid.UUID | None = None,
) -> None:
    """Write audit_logs row for admin.ai.model.update using D-S2 pattern.

    Args:
        actor_user_id:       Admin who performed the update.
        model_id:            Target model UUID.
        from_state:          Pre-patch {enabled, is_default}.
        to_state:            Post-patch {enabled, is_default}.
        request_id:          X-Request-ID for correlation.
        ip:                  Client IP address.
        user_agent:          User-Agent header.
        outcome:             'success' or 'failure'.
        previous_default_id: UUID of the model that lost is_default=true
                             (if any).
    """
    metadata: dict[str, Any] = {
        "request_id": request_id,
        "ip": ip,
        "user_agent": user_agent,
        "from": from_state,
        "to": to_state,
        "outcome": outcome,
    }
    if previous_default_id is not None:
        metadata["previous_default_id"] = str(previous_default_id)

    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.ai.model.update",
        entity_type="ai_model",
        entity_id=model_id,
        metadata=metadata,
    )
