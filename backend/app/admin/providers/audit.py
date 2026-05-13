"""
Hilo People — Admin AI providers audit writer.

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: Thin wrapper around the shared admin AI audit helper that builds the
         provider-specific metadata payload. Keeps the router free of audit
         boilerplate while reusing the D-S2 independent-session pattern.

Key deps:
  - app.admin._audit.write_admin_ai_audit — shared D-S2 writer

Source refs:
  - task pack P02-S05-T001 §D-AASPLIT (split audit into its own file)
  - validator review of P02-S05-T001 (DRY across providers/model_catalog)

Decisions:
  - Provider entity_type is the canonical 'ai_provider' string.
  - On failure paths the caller passes uuid.UUID(int=0) as a placeholder
    entity_id; the limitation is tracked as a non-blocking validator
    observation (audit_logs.entity_id is NOT NULL in schema).
"""

from __future__ import annotations

import uuid

from app.admin._audit import write_admin_ai_audit


def write_provider_audit(
    *,
    actor_user_id: uuid.UUID,
    provider_id: uuid.UUID,
    name: str,
    provider_type: str,
    request_id: str,
    ip: str,
    user_agent: str,
    outcome: str,
) -> None:
    """Write audit_logs row for admin.ai.provider.create using D-S2 pattern.

    Args:
        actor_user_id: Admin who performed the action.
        provider_id:   Created provider UUID (UUID(int=0) if not persisted).
        name:          Provider name (for audit metadata).
        provider_type: Provider type key.
        request_id:    X-Request-ID for correlation.
        ip:            Client IP.
        user_agent:    User-Agent header value.
        outcome:       'success' or 'failure'.
    """
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.ai.provider.create",
        entity_type="ai_provider",
        entity_id=provider_id,
        metadata={
            "request_id": request_id,
            "ip": ip,
            "user_agent": user_agent,
            "name": name,
            "provider_type": provider_type,
            "outcome": outcome,
        },
    )
