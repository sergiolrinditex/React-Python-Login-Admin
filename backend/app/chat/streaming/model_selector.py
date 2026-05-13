"""
Hilo People — Active chat/embeddings model selector.

Slice:  P02-S03-T002 — Chat streaming endpoint (§D-CHATSTREAM-SEL)
Phase:  P02 Core Features (the motor)
Purpose: Queries DB for the currently active chat and embeddings models.
         Returns the (AiModel, AiProvider, AiProviderCredential) triple needed
         by the LLM gateway.

Functions:
  get_active_chat_model(session)       — raises NoActiveChatModelError if none
  get_active_embeddings_model(session) — raises NoActiveChatModelError if none

Business rules (D-CHATSTREAM-MODELTYPE):
  - model_type='chat' exact string (open enum from §10.3).
  - model must be enabled=True AND is_default=True.
  - One credential per provider (first active credential found).
  - If no matching triple → NoActiveChatModelError → HTTP 502.

Security (D-ENC3):
  - The credential's encrypted_secret is returned as-is (Fernet token).
  - Decryption happens at the call site (chat/streaming/service.py).
  - NEVER log encrypted_secret or the decrypted key.

Source refs:
  - task pack P02-S03-T002 §E.2 (model selector API contract)
  - task pack P02-S03-T002 §H D-CHATSTREAM-MODELTYPE
  - 01-non-negotiables.md §Security (Fernet; no key in logs)
"""

from __future__ import annotations

import logging
import os

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.chat.errors import NoActiveChatModelError
from app.db.models.admin_ai import AiModel, AiProvider, AiProviderCredential

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_MODEL_TYPE_CHAT = "chat"
_MODEL_TYPE_EMBEDDINGS = "embeddings"


def get_active_chat_model(
    session: Session,
) -> tuple[AiModel, AiProvider, AiProviderCredential]:
    """Return the active chat model + provider + credential triple.

    Queries ai_models WHERE model_type='chat' AND enabled=True AND is_default=True,
    then joins to ai_providers and ai_provider_credentials.

    Args:
        session: SQLAlchemy sync Session.

    Returns:
        Tuple of (AiModel, AiProvider, AiProviderCredential).

    Raises:
        NoActiveChatModelError: If no enabled default chat model + credential exists.
    """
    if _VERBOSE:
        logger.debug("chat.streaming.model_selector.get_active_chat_model.start")  # BEFORE

    result = _query_active_model(session, _MODEL_TYPE_CHAT)

    if _VERBOSE:
        if result:
            logger.debug(
                "chat.streaming.model_selector.get_active_chat_model.done model_id=%s provider_id=%s",
                str(result[0].id),
                str(result[1].id),
            )  # AFTER
        else:
            logger.debug("chat.streaming.model_selector.get_active_chat_model.not_found")

    if result is None:
        logger.warning(
            "chat.streaming.model_selector.no_active_model model_type=%s", _MODEL_TYPE_CHAT
        )
        raise NoActiveChatModelError()

    return result


def get_active_embeddings_model(
    session: Session,
) -> tuple[AiModel, AiProvider, AiProviderCredential]:
    """Return the active embeddings model + provider + credential triple.

    Queries ai_models WHERE model_type='embeddings' AND enabled=True AND is_default=True.

    Args:
        session: SQLAlchemy sync Session.

    Returns:
        Tuple of (AiModel, AiProvider, AiProviderCredential).

    Raises:
        NoActiveChatModelError: If no enabled default embeddings model + credential exists.
    """
    if _VERBOSE:
        logger.debug("chat.streaming.model_selector.get_active_embeddings_model.start")  # BEFORE

    result = _query_active_model(session, _MODEL_TYPE_EMBEDDINGS)

    if _VERBOSE:
        if result:
            logger.debug(
                "chat.streaming.model_selector.get_active_embeddings_model.done model_id=%s",
                str(result[0].id),
            )  # AFTER
        else:
            logger.debug("chat.streaming.model_selector.get_active_embeddings_model.not_found")

    if result is None:
        logger.warning(
            "chat.streaming.model_selector.no_active_model model_type=%s", _MODEL_TYPE_EMBEDDINGS
        )
        raise NoActiveChatModelError(
            f"No active {_MODEL_TYPE_EMBEDDINGS} model configured. Contact your administrator."
        )

    return result


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------

def _query_active_model(
    session: Session,
    model_type: str,
) -> tuple[AiModel, AiProvider, AiProviderCredential] | None:
    """Query DB for the default enabled model of the given type with its credential.

    Args:
        session: SQLAlchemy sync Session.
        model_type: 'chat' or 'embeddings'.

    Returns:
        (AiModel, AiProvider, AiProviderCredential) tuple or None if not found.
    """
    stmt = (
        sa.select(AiModel, AiProvider, AiProviderCredential)
        .join(AiProvider, AiModel.provider_id == AiProvider.id)
        .join(
            AiProviderCredential,
            AiProviderCredential.provider_id == AiProvider.id,
        )
        .where(
            AiModel.model_type == model_type,
            AiModel.enabled.is_(True),
            AiModel.is_default.is_(True),
        )
        .limit(1)
    )

    row = session.execute(stmt).first()
    if row is None:
        return None

    return row[0], row[1], row[2]
