"""
Hilo People — Admin model-test repository (DB queries only).

WRITE_SET_DRIFT §D-MT-REPO (P02-S05-T002): New file in backend/app/admin/model_test/
subpackage. Not in declared write_set but required for the model_test feature module.

Slice:  P02-S05-T002 — Model test and usage endpoints
Phase:  P02 Core Features
Purpose: SQLAlchemy inserts into ai_model_tests and llm_usage_logs, plus
         lookup helpers for AiModel and AiProviderCredential. No business
         policy here — the service layer orchestrates transactions and audit.

         get_credential_for_model is NEW: providers/repository.py only LISTs
         credentials (never gets-one). This module adds the first single-row
         credential lookup needed by the test execution flow.

Key deps:
  - sqlalchemy.orm.Session
  - app.db.models.admin_ai (AiModel, AiProviderCredential, AiModelTest, LlmUsageLog)

Source refs:
  - task pack P02-S05-T002 §D.2.A (side effects: ai_model_tests + llm_usage_logs)
  - task pack P02-S05-T002 §D.4 §D-MT-REPO
  - task pack P02-S05-T002 §F.2 R-PROVIDER-CREDENTIAL-MULTIPLE (ORDER BY id LIMIT 1)
  - 01-non-negotiables.md §Database (parametrized queries, indexes)

Decisions:
  - D-CRED-ONE: get_credential_for_model returns the first credential row
    (ORDER BY id LIMIT 1). Schema allows multiple per provider; V1 uses at most one.
    Same convention as providers/repository.py list_providers lateral join.
  - D-MT-USAGE-CONV: llm_usage_logs.conversation_id is NULL for model-test rows
    (test invocations are not chat conversations, per §F.2 D-MT-USAGE-CONVERSATION-ID).
"""

from __future__ import annotations

import logging
import os
import uuid
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.admin_ai import (
    AiModel,
    AiModelTest,
    AiProvider,
    AiProviderCredential,
    LlmUsageLog,
)

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def get_model_by_id(session: Session, model_id: uuid.UUID) -> AiModel | None:
    """Fetch a single AiModel by primary key.

    Args:
        session:  Active SQLAlchemy sync Session.
        model_id: Target model UUID.

    Returns:
        AiModel ORM instance or None if not found.
    """
    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.get_model.start model_id=%s",
            str(model_id),
        )  # BEFORE

    model = session.get(AiModel, model_id)

    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.get_model.ok model_id=%s found=%s",
            str(model_id),
            model is not None,
        )  # AFTER
    return model


def get_provider_by_id(session: Session, provider_id: uuid.UUID) -> AiProvider | None:
    """Fetch a single AiProvider by primary key.

    Args:
        session:     Active SQLAlchemy sync Session.
        provider_id: Target provider UUID.

    Returns:
        AiProvider ORM instance or None if not found.
    """
    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.get_provider.start provider_id=%s",
            str(provider_id),
        )  # BEFORE

    provider = session.get(AiProvider, provider_id)

    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.get_provider.ok provider_id=%s found=%s",
            str(provider_id),
            provider is not None,
        )  # AFTER
    return provider


def get_credential_for_model(
    session: Session, provider_id: uuid.UUID
) -> AiProviderCredential | None:
    """Fetch the first credential row for a provider (D-CRED-ONE).

    ORDER BY id LIMIT 1 — deterministic when multiple exist (R-PROVIDER-CREDENTIAL-MULTIPLE).

    Args:
        session:     Active SQLAlchemy sync Session.
        provider_id: AiProvider UUID to look up credentials for.

    Returns:
        AiProviderCredential ORM instance or None if provider has no credentials.
    """
    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.get_credential.start provider_id=%s",
            str(provider_id),
        )  # BEFORE

    cred = session.execute(
        sa.select(AiProviderCredential)
        .where(AiProviderCredential.provider_id == provider_id)
        .order_by(AiProviderCredential.id)
        .limit(1)
    ).scalar_one_or_none()

    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.get_credential.ok provider_id=%s found=%s",
            str(provider_id),
            cred is not None,
        )  # AFTER
    return cred


def get_latest_test_row(
    session: Session,
    *,
    model_id: uuid.UUID,
    created_by: uuid.UUID,
) -> AiModelTest | None:
    """Fetch the most recently inserted ai_model_tests row for this model+user.

    Used by the router to retrieve the test row id + created_at after commit.

    Args:
        session:    Active SQLAlchemy sync Session.
        model_id:   UUID of the tested AiModel.
        created_by: Admin user UUID.

    Returns:
        Most recent AiModelTest row or None.
    """
    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.get_latest_test.start "
            "model_id=%s created_by=%s",
            str(model_id),
            str(created_by),
        )  # BEFORE

    row = session.execute(
        sa.select(AiModelTest)
        .where(
            AiModelTest.model_id == model_id,
            AiModelTest.created_by == created_by,
        )
        .order_by(AiModelTest.created_at.desc())
        .limit(1)
    ).scalar_one_or_none()

    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.get_latest_test.ok found=%s",
            row is not None,
        )  # AFTER
    return row


def insert_model_test(
    session: Session,
    *,
    model_id: uuid.UUID,
    prompt: str,
    output: str | None,
    latency_ms: int | None,
    estimated_cost: float | None,
    status: str,
    created_by: uuid.UUID,
) -> AiModelTest:
    """Insert a new row into ai_model_tests within the current transaction.

    NEVER logs prompt or output content (R-AUDIT-PROMPT, security rule).

    Args:
        session:        Active SQLAlchemy sync Session (caller commits).
        model_id:       UUID of the AiModel being tested.
        prompt:         Test prompt — stored in DB but NEVER logged.
        output:         Model response text; None if test failed before response.
        latency_ms:     Round-trip latency; None if failed before timing.
        estimated_cost: USD cost estimate; None if unknown.
        status:         'success' | 'failure' | 'timeout'.
        created_by:     Admin user UUID.

    Returns:
        Newly created AiModelTest ORM instance (post-flush, id assigned by DB).
    """
    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.insert_test.start "
            "model_id=%s status=%s prompt_len=%d",
            str(model_id),
            status,
            len(prompt),
        )  # BEFORE — only prompt_len, never prompt content

    row = AiModelTest(
        model_id=model_id,
        prompt=prompt,  # persisted in DB; never in logs
        output=output,
        latency_ms=latency_ms,
        estimated_cost=estimated_cost,
        status=status,
        created_by=created_by,
    )
    session.add(row)
    session.flush()  # materialise row.id

    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.insert_test.ok "
            "test_id=%s model_id=%s status=%s",
            str(row.id),
            str(model_id),
            status,
        )  # AFTER
    return row


def insert_usage_log(
    session: Session,
    *,
    user_id: uuid.UUID,
    model_id: uuid.UUID,
    tokens_in: int,
    tokens_out: int,
    estimated_cost: float,
    latency_ms: int,
) -> LlmUsageLog:
    """Insert a new row into llm_usage_logs within the current transaction.

    conversation_id is always NULL for model-test invocations (D-MT-USAGE-CONV).

    Args:
        session:        Active SQLAlchemy sync Session (caller commits).
        user_id:        Admin user UUID.
        model_id:       UUID of the tested AiModel.
        tokens_in:      Input (prompt) token count.
        tokens_out:     Output (completion) token count.
        estimated_cost: USD cost estimate.
        latency_ms:     Round-trip latency in ms.

    Returns:
        Newly created LlmUsageLog ORM instance (post-flush, id assigned by DB).
    """
    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.insert_usage.start "
            "model_id=%s tokens_in=%d tokens_out=%d",
            str(model_id),
            tokens_in,
            tokens_out,
        )  # BEFORE

    row = LlmUsageLog(
        user_id=user_id,
        model_id=model_id,
        conversation_id=None,  # D-MT-USAGE-CONV: NULL for test invocations
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
    )
    session.add(row)
    session.flush()

    if _VERBOSE:
        logger.debug(
            "admin.model_test.repository.insert_usage.ok "
            "usage_id=%s model_id=%s",
            str(row.id),
            str(model_id),
        )  # AFTER
    return row
