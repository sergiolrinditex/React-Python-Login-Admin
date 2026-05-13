"""
Hilo People — Admin AI model catalog repository (DB queries only).

Slice:  P02-S05-T001 — Admin AI providers and models endpoints (debugger cycle 1, §D-AASPLIT)
Phase:  P02 Core Features
Purpose: SQLAlchemy queries against ai_models. No business policy here —
         the service layer orchestrates transaction boundaries and audit;
         this module persists.

Key deps:
  - sqlalchemy.orm.Session
  - app.db.models.admin_ai.AiModel

Source refs:
  - task pack P02-S05-T001 §Front→Back→DB contract (GET, PATCH /models)
  - 01-non-negotiables.md §Database (parametrized queries, indexes)

Decisions:
  - get_model_by_id uses Session.get (PK fetch) — single-statement.
  - find_previous_default_id is called by the service before the patch to
    record FROM/TO state in the audit log even though the patch UPDATE will
    later clear the other model's is_default flag (D-DEF1).
"""

from __future__ import annotations

import logging
import os
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.admin_ai import AiModel

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def list_models(
    session: Session,
    provider_id: uuid.UUID | None,
) -> list[AiModel]:
    """Query ai_models, optionally filtered by provider_id.

    Args:
        session:     Active SQLAlchemy sync Session.
        provider_id: Optional filter — only return models for this provider.

    Returns:
        List of AiModel ORM instances ordered by provider_id, model_type, model_id.
    """
    if _VERBOSE:
        logger.debug(
            "admin.models.repository.list.start provider_filter=%s",
            str(provider_id) if provider_id else "none",
        )  # BEFORE

    stmt = sa.select(AiModel).order_by(
        AiModel.provider_id,
        AiModel.model_type,
        AiModel.model_id,
    )
    if provider_id is not None:
        stmt = stmt.where(AiModel.provider_id == provider_id)

    models = list(session.scalars(stmt))

    if _VERBOSE:
        logger.debug(
            "admin.models.repository.list.ok count=%d", len(models)
        )  # AFTER
    return models


def get_model_by_id(session: Session, model_id: uuid.UUID) -> AiModel | None:
    """Fetch a single AiModel by primary key.

    Args:
        session:  Active SQLAlchemy sync Session.
        model_id: Target model UUID.

    Returns:
        AiModel ORM instance or None if not found.
    """
    return session.get(AiModel, model_id)


def find_previous_default_id(
    session: Session,
    model_type: str,
    exclude_id: uuid.UUID,
) -> uuid.UUID | None:
    """Locate the model that currently holds is_default=true for model_type.

    Used by the service to record the previous default's UUID in the audit
    log before the patch clears its flag.

    Args:
        session:    Active SQLAlchemy sync Session.
        model_type: 'chat' | 'embeddings' | other.
        exclude_id: ID of the target model being patched (excluded from search).

    Returns:
        UUID of the previous default, or None if no prior default exists.
    """
    return session.execute(
        sa.select(AiModel.id).where(
            AiModel.model_type == model_type,
            AiModel.id != exclude_id,
            AiModel.is_default.is_(True),
        ).limit(1)
    ).scalar_one_or_none()


def apply_patch(
    session: Session,
    model: AiModel,
    *,
    enabled: bool | None,
    is_default: bool | None,
) -> AiModel:
    """Apply partial update to a model within the current transaction.

    If is_default=True, atomically clears is_default on all other models of
    the same model_type first (D-DEF1 app-layer invariant).

    Args:
        session:    Active SQLAlchemy sync Session (caller commits).
        model:      AiModel ORM instance to update.
        enabled:    New enabled value (None = no change).
        is_default: New is_default value (None = no change).

    Returns:
        Updated AiModel ORM instance.
    """
    if _VERBOSE:
        logger.debug(
            "admin.models.repository.patch.start model_id=%s "
            "enabled=%s is_default=%s",
            str(model.id),
            enabled,
            is_default,
        )  # BEFORE

    if enabled is not None:
        model.enabled = enabled

    if is_default is True:
        # D-DEF1: Clear is_default on all other models of same type
        # within the same transaction to maintain at-most-one invariant.
        session.execute(
            sa.update(AiModel)
            .where(
                AiModel.model_type == model.model_type,
                AiModel.id != model.id,
                AiModel.is_default.is_(True),
            )
            .values(is_default=False)
        )
        model.is_default = True
    elif is_default is False:
        model.is_default = False

    if _VERBOSE:
        logger.debug(
            "admin.models.repository.patch.ok model_id=%s",
            str(model.id),
        )  # AFTER

    return model
