"""
Hilo People — Admin model-test audit helper.

WRITE_SET_DRIFT §D-MT-AUDIT (P02-S05-T002): New file in backend/app/admin/model_test/
subpackage. Not in declared write_set but required for the model_test feature module.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: Thin wrappers over app.admin._audit.write_admin_ai_audit for the
         admin.ai.model.test action. Callers pass event metadata; this module
         ensures the audit_logs row is written in a D-S2 independent session
         (commits even when the caller's main transaction rolls back).

         Audit metadata MUST NOT contain: prompt content, output content,
         api_key, encrypted_secret (R-AUDIT-PROMPT). Only safe fields are
         passed: request_id, ip, user_agent, model_id, status, latency_ms,
         tokens_in, tokens_out, estimated_cost, outcome, failure_reason.

Key deps:
  - app.admin._audit.write_admin_ai_audit — shared D-S2 audit helper
  - uuid

Source refs:
  - task pack P02-S05-T002 §D.2.A (side effects: audit admin.ai.model.test)
  - task pack P02-S05-T002 §F.1 R-AUDIT-PROMPT (no prompt/output in audit)
  - 01-non-negotiables.md §Security (audit log)
"""

from __future__ import annotations

import uuid
from typing import Any

from app.admin._audit import write_admin_ai_audit


def write_model_test_audit_success(
    *,
    actor_user_id: uuid.UUID,
    model_id: uuid.UUID,
    test_id: uuid.UUID,
    latency_ms: int,
    tokens_in: int,
    tokens_out: int,
    estimated_cost: float | None,
    request_id: str,
    ip: str,
    user_agent: str,
) -> None:
    """Write audit row for a successful model test invocation.

    Uses the D-S2 independent session pattern via write_admin_ai_audit.
    NEVER includes prompt content, output content, or api_key in metadata.

    Args:
        actor_user_id:  Admin user who triggered the test.
        model_id:       UUID of the tested AiModel.
        test_id:        UUID of the ai_model_tests row created.
        latency_ms:     Round-trip latency in ms.
        tokens_in:      Input token count.
        tokens_out:     Output token count.
        estimated_cost: USD cost estimate (None if unknown).
        request_id:     X-Request-ID for correlation.
        ip:             Caller IP address.
        user_agent:     Caller User-Agent string.
    """
    metadata: dict[str, Any] = {
        "outcome": "success",
        "model_id": str(model_id),
        "test_id": str(test_id),
        "latency_ms": latency_ms,
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "estimated_cost": str(estimated_cost) if estimated_cost is not None else None,
        "request_id": request_id,
        "ip": ip,
        "user_agent": user_agent,
        # NOTE: prompt, output, api_key are intentionally EXCLUDED (R-AUDIT-PROMPT)
    }
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.ai.model.test",
        entity_type="ai_model_test",
        entity_id=test_id,
        metadata=metadata,
    )


def write_model_test_audit_failure(
    *,
    actor_user_id: uuid.UUID,
    model_id: uuid.UUID,
    test_id: uuid.UUID,
    failure_reason: str,
    status: str,
    request_id: str,
    ip: str,
    user_agent: str,
) -> None:
    """Write audit row for a failed model test invocation (D-S2 pattern).

    Uses the D-S2 independent session so this audit row commits even when
    the main transaction rolls back (e.g. after a ModelTestFailedError).
    NEVER includes prompt content, output content, or api_key in metadata.

    Args:
        actor_user_id:  Admin user who triggered the test.
        model_id:       UUID of the tested AiModel.
        test_id:        UUID of the ai_model_tests row (may be a placeholder
                        UUID(int=0) if no row was persisted).
        failure_reason: Short description of why the test failed (no secrets).
        status:         'failure' | 'timeout' — matches ai_model_tests.status.
        request_id:     X-Request-ID for correlation.
        ip:             Caller IP address.
        user_agent:     Caller User-Agent string.
    """
    metadata: dict[str, Any] = {
        "outcome": "failure",
        "model_id": str(model_id),
        "test_id": str(test_id),
        "status": status,
        "failure_reason": failure_reason,
        "request_id": request_id,
        "ip": ip,
        "user_agent": user_agent,
        # NOTE: prompt, output, api_key intentionally EXCLUDED (R-AUDIT-PROMPT)
    }
    write_admin_ai_audit(
        actor_user_id=actor_user_id,
        action="admin.ai.model.test",
        entity_type="ai_model_test",
        entity_id=test_id,
        metadata=metadata,
    )
