"""
Hilo People — Admin model-test use case (service layer).

WRITE_SET_DRIFT §D-MT-SVC (P02-S05-T002): New file in backend/app/admin/model_test/
subpackage. Not in declared write_set but required for the model_test feature module.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: Orchestrates the model-test use case:
  1. Load AiModel → 404 if missing.
  2. Load AiProvider → 502 if missing (data integrity).
  3. Load AiProviderCredential → 404 if missing.
  4. Decrypt credential → 502 if Fernet fails.
  5. Call complete_chat() → CompletionResult (real LLM call).
  6. INSERT ai_model_tests + llm_usage_logs in main session; COMMIT.
  7. Write success audit row via D-S2 independent session.
  On failure: INSERT failure test row, write failure audit row, re-raise.

Key deps:
  - app.llm_gateway.complete_chat (complete_chat, CompletionResult)
  - app.llm_gateway.errors (LiteLLMTimeoutError, ModelTestFailedError)
  - app.admin.model_test.errors (ModelNotFoundError, CredentialNotFoundError)
  - app.admin.model_test.repository (all repo helpers)
  - app.admin.model_test.audit (write_model_test_audit_success/failure)
  - app.security.encryption (decrypt_secret)

Source refs:
  - task pack P02-S05-T002 §D.2.A, §D.4 §D-MT-SVC
  - 01-non-negotiables.md §Logging, §Security (never log api_key/prompt)
"""

from __future__ import annotations

import logging
import os
import uuid

from sqlalchemy.orm import Session

from app.admin.model_test.audit import (
    write_model_test_audit_failure,
    write_model_test_audit_success,
)
from app.admin.model_test.errors import CredentialNotFoundError, ModelNotFoundError
from app.admin.model_test.repository import (
    get_credential_for_model,
    get_model_by_id,
    get_provider_by_id,
    insert_model_test,
    insert_usage_log,
)
from app.llm_gateway.complete_chat import CompletionResult, complete_chat
from app.llm_gateway.errors import LiteLLMTimeoutError, ModelTestFailedError
from app.security.encryption import decrypt_secret

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# Sentinel UUID for audit rows when no ai_model_tests row was persisted.
_NO_TEST_ID = uuid.UUID(int=0)


async def run_model_test(
    session: Session,
    *,
    actor_user_id: uuid.UUID,
    model_id: uuid.UUID,
    prompt: str,
    max_tokens: int,
    request_id: str,
    ip: str,
    user_agent: str,
) -> CompletionResult:
    """Execute the model-test use case and persist the result.

    Orchestrates model lookup, credential decrypt, LLM call, and DB persistence.

    Args:
        session:       SQLAlchemy sync Session (this use case commits it).
        actor_user_id: Admin user who triggered the test.
        model_id:      AiModel UUID to test.
        prompt:        Test prompt (validated by schema). NEVER logged.
        max_tokens:    Maximum completion tokens.
        request_id:    X-Request-ID for log correlation.
        ip:            Caller IP for audit.
        user_agent:    Caller User-Agent for audit.

    Returns:
        CompletionResult on success.

    Raises:
        ModelNotFoundError:      Model UUID not found.
        CredentialNotFoundError: Provider has no credential row.
        ModelTestFailedError:    Decrypt failure or LiteLLM error.
        LiteLLMTimeoutError:     LiteLLM request timed out.
    """
    if _VERBOSE:
        logger.debug(
            "admin.model_test.service.run.start actor=%s model_id=%s prompt_len=%d request_id=%s",
            str(actor_user_id), str(model_id), len(prompt), request_id,
        )  # BEFORE — prompt content NEVER logged

    model = get_model_by_id(session, model_id)
    if model is None:
        logger.warning(
            "admin.model_test.service.model_not_found actor=%s model_id=%s request_id=%s",
            str(actor_user_id), str(model_id), request_id,
        )
        raise ModelNotFoundError(f"Model {model_id} not found.")

    provider = get_provider_by_id(session, model.provider_id)
    if provider is None:
        logger.error(
            "admin.model_test.service.provider_not_found actor=%s model_id=%s provider_id=%s request_id=%s",
            str(actor_user_id), str(model_id), str(model.provider_id), request_id,
        )
        _write_failure_audit(actor_user_id, model_id, _NO_TEST_ID, "provider_not_found", "failure", request_id, ip, user_agent)
        raise ModelTestFailedError("Provider not found (data integrity error).", status="failure")

    cred = get_credential_for_model(session, model.provider_id)
    if cred is None:
        logger.warning(
            "admin.model_test.service.credential_not_found actor=%s model_id=%s provider_id=%s request_id=%s",
            str(actor_user_id), str(model_id), str(model.provider_id), request_id,
        )
        _write_failure_audit(actor_user_id, model_id, _NO_TEST_ID, "credential_not_found", "failure", request_id, ip, user_agent)
        raise CredentialNotFoundError(f"No credential for provider {model.provider_id}.")

    try:
        api_key = decrypt_secret(cred.encrypted_secret)  # NEVER log this value
    except Exception as exc:
        logger.error(
            "admin.model_test.service.decrypt_error actor=%s model_id=%s request_id=%s error=%s",
            str(actor_user_id), str(model_id), request_id, type(exc).__name__,
        )
        _persist_failure_test(session, model_id=model_id, prompt=prompt, status="failure", created_by=actor_user_id, request_id=request_id)
        _write_failure_audit(actor_user_id, model_id, _NO_TEST_ID, "decrypt_error", "failure", request_id, ip, user_agent)
        raise ModelTestFailedError("Credential decryption failed.", cause=exc, status="failure") from exc

    try:
        result = await complete_chat(
            model=model, provider=provider, api_key=api_key,  # NEVER log api_key
            prompt=prompt, max_tokens=max_tokens, request_id=request_id,
        )
    except LiteLLMTimeoutError:
        logger.error("admin.model_test.service.litellm_timeout actor=%s model_id=%s request_id=%s",
                     str(actor_user_id), str(model_id), request_id)
        row = _persist_failure_test(session, model_id=model_id, prompt=prompt, status="timeout", created_by=actor_user_id, request_id=request_id)
        _write_failure_audit(actor_user_id, model_id, row.id, "litellm_timeout", "timeout", request_id, ip, user_agent)
        raise
    except ModelTestFailedError as exc:
        logger.error("admin.model_test.service.litellm_error actor=%s model_id=%s request_id=%s error=%s",
                     str(actor_user_id), str(model_id), request_id, type(exc.cause).__name__ if exc.cause else "unknown")
        row = _persist_failure_test(session, model_id=model_id, prompt=prompt, status="failure", created_by=actor_user_id, request_id=request_id)
        _write_failure_audit(actor_user_id, model_id, row.id, "litellm_error", "failure", request_id, ip, user_agent)
        raise

    test_row = insert_model_test(
        session, model_id=model_id, prompt=prompt, output=result.text,
        latency_ms=result.latency_ms, estimated_cost=result.cost_usd, status="success", created_by=actor_user_id,
    )
    insert_usage_log(
        session, user_id=actor_user_id, model_id=model_id,
        tokens_in=result.prompt_tokens, tokens_out=result.completion_tokens,
        estimated_cost=result.cost_usd or 0.0, latency_ms=result.latency_ms,
    )
    session.commit()

    write_model_test_audit_success(
        actor_user_id=actor_user_id, model_id=model_id, test_id=test_row.id,
        latency_ms=result.latency_ms, tokens_in=result.prompt_tokens, tokens_out=result.completion_tokens,
        estimated_cost=result.cost_usd, request_id=request_id, ip=ip, user_agent=user_agent,
    )

    if _VERBOSE:
        logger.debug(
            "admin.model_test.service.run.ok actor=%s model_id=%s test_id=%s latency_ms=%d request_id=%s",
            str(actor_user_id), str(model_id), str(test_row.id), result.latency_ms, request_id,
        )  # AFTER — no output content, no api_key
    else:
        logger.info(
            "admin.model_test.service.run.ok actor=%s model_id=%s latency_ms=%d tokens_in=%d tokens_out=%d",
            str(actor_user_id), str(model_id), result.latency_ms, result.prompt_tokens, result.completion_tokens,
        )
    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _persist_failure_test(
    session: Session,
    *,
    model_id: uuid.UUID,
    prompt: str,
    status: str,
    created_by: uuid.UUID,
    request_id: str,
) -> object:
    """Insert a failure ai_model_tests row and commit (D-FAIL-ROW).

    Args:
        session:    Active SQLAlchemy sync Session.
        model_id:   UUID of the tested AiModel.
        prompt:     Test prompt (stored, NEVER logged).
        status:     'failure' | 'timeout'.
        created_by: Admin user UUID.
        request_id: For log correlation.

    Returns:
        AiModelTest row (or sentinel with id=_NO_TEST_ID on DB error).
    """
    if _VERBOSE:
        logger.debug("admin.model_test.service._persist_failure.start model_id=%s status=%s request_id=%s",
                     str(model_id), status, request_id)  # BEFORE
    try:
        row = insert_model_test(session, model_id=model_id, prompt=prompt, output=None,
                                latency_ms=None, estimated_cost=None, status=status, created_by=created_by)
        session.commit()
        if _VERBOSE:
            logger.debug("admin.model_test.service._persist_failure.ok test_id=%s request_id=%s",
                         str(row.id), request_id)  # AFTER
        return row
    except Exception as e:
        logger.error("admin.model_test.service._persist_failure.error model_id=%s request_id=%s error=%s",
                     str(model_id), request_id, type(e).__name__)
        session.rollback()
        from app.db.models.admin_ai import AiModelTest
        sentinel = AiModelTest.__new__(AiModelTest)
        sentinel.id = _NO_TEST_ID
        return sentinel


def _write_failure_audit(
    actor_user_id: uuid.UUID,
    model_id: uuid.UUID,
    test_id: uuid.UUID,
    failure_reason: str,
    status: str,
    request_id: str,
    ip: str,
    user_agent: str,
) -> None:
    """Write a D-S2 failure audit row. Never logs prompt or api_key.

    Args:
        actor_user_id: Admin user.
        model_id:      Tested model UUID.
        test_id:       Test row UUID (or _NO_TEST_ID sentinel).
        failure_reason: Short reason key (no secrets).
        status:        'failure' | 'timeout'.
        request_id:    X-Request-ID.
        ip:            Caller IP.
        user_agent:    Caller UA.
    """
    write_model_test_audit_failure(
        actor_user_id=actor_user_id, model_id=model_id, test_id=test_id,
        failure_reason=failure_reason, status=status,
        request_id=request_id, ip=ip, user_agent=user_agent,
    )
