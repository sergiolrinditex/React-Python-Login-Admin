"""
Hilo People — Use case: get conversation detail with ownership check.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Use case for GET /api/v1/chat/conversations/{id}. Loads the conversation
         with its messages and citations, then enforces ownership semantics:
         404 if not found, 403 if found but owned by a different user.

Business rules:
  - 404 → ConversationNotFoundError if no row with given ID.
  - 403 → ConversationForbiddenError if row exists but user_id != current_user.id.
  - The distinction is intentional per §6.2 rows 264-266 (TECHNICAL_GUIDE lists
    401, 403, 404 as distinct codes — anti-enum does NOT apply here).

Source refs:
  - task pack P02-S03-T001 §F.5 (ownership semantics)
  - TECHNICAL_GUIDE §6.2 row 266 (GET /chat/conversations/{id} errors)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR per use case)
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.chat.errors import ConversationForbiddenError, ConversationNotFoundError
from app.chat.repositories.conversations import find_conversation_with_messages
from app.db.models.chat import Conversation

logger = logging.getLogger(__name__)


def get_conversation_detail_for_user(
    session: Session,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    request_id: str,
) -> Conversation:
    """Get a conversation detail by ID, enforcing ownership.

    Returns the conversation with ._messages and ._citations attributes populated
    by the repository. Raises typed domain errors for 404 and 403 cases.

    Args:
        session: SQLAlchemy sync Session.
        conversation_id: The requested conversation UUID.
        user_id: The authenticated user's UUID.
        request_id: X-Request-ID for log correlation.

    Returns:
        Conversation ORM object with ._messages and ._citations populated.

    Raises:
        ConversationNotFoundError: If no conversation with that ID exists.
        ConversationForbiddenError: If the conversation exists but belongs to another user.
    """
    user_id_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
    t0 = time.perf_counter()

    logger.debug(
        "chat.service.get_conversation_detail.start request_id=%s user_id_hash=%s "
        "conv_id_prefix=%s",
        request_id,
        user_id_hash,
        str(conversation_id)[:8],
    )  # BEFORE

    conv = find_conversation_with_messages(
        session=session,
        conversation_id=conversation_id,
    )

    if conv is None:
        logger.debug(
            "chat.service.get_conversation_detail.not_found request_id=%s conv_id_prefix=%s",
            request_id,
            str(conversation_id)[:8],
        )
        raise ConversationNotFoundError()

    if conv.user_id != user_id:
        logger.warning(
            "chat.service.get_conversation_detail.forbidden request_id=%s "
            "user_id_hash=%s owner_id_hash=%s",
            request_id,
            user_id_hash,
            hashlib.sha256(str(conv.user_id).encode()).hexdigest()[:16]
            if conv.user_id else "none",
        )
        raise ConversationForbiddenError()

    latency_ms = (time.perf_counter() - t0) * 1000
    msg_count = len(getattr(conv, "_messages", []))
    citation_count = len(getattr(conv, "_citations", []))

    logger.debug(
        "chat.service.get_conversation_detail.done request_id=%s user_id_hash=%s "
        "conv_id_prefix=%s msg_count=%d citation_count=%d latency_ms=%.1f",
        request_id,
        user_id_hash,
        str(conv.id)[:8],
        msg_count,
        citation_count,
        latency_ms,
    )  # AFTER

    return conv
