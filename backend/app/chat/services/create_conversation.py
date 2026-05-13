"""
Hilo People — Use case: create a conversation for a user.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Use case for POST /api/v1/chat/conversations. Derives the title and
         language, then calls the repository to insert the conversation (and
         optionally the first user message) within an atomic transaction.

Business rules:
  - D-TIT1: If initial_message provided → title = first 60 chars, stripped.
             If no initial_message → title = '' (empty string; frontend uses i18n key).
  - D-LANG1: If language is explicitly given → use that value.
             Otherwise → use current_user.preferred_language.
  - D-TX1: conversation row + optional first user message inserted atomically.
           Rollback on any failure.
  - D-AUD1: Chat CRUD is NOT an auditable action (not in §Security audit list).

Source refs:
  - task pack P02-S03-T001 §H.1 (D-TIT1), §H.2 (D-LANG1), §H.3 (D-TX1)
  - TECHNICAL_GUIDE §6.2 row 265 (POST /chat/conversations response)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR per use case)
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.chat.repositories.conversations import create_conversation
from app.db.models.chat import Conversation

logger = logging.getLogger(__name__)

_TITLE_MAX_LEN = 60


def _derive_title(initial_message: str | None) -> str:
    """Derive a conversation title from the optional initial message.

    D-TIT1: If initial_message provided, take first 60 chars (stripped + ellipsis
    if truncated). If not provided, return '' so the frontend can use its i18n key.

    Args:
        initial_message: The optional first message content.

    Returns:
        Title string (may be empty, may have '...' if truncated).
    """
    if initial_message is None:
        return ""
    stripped = initial_message.strip()
    if not stripped:
        return ""
    if len(stripped) <= _TITLE_MAX_LEN:
        return stripped
    return stripped[:_TITLE_MAX_LEN].rstrip() + "..."


def create_conversation_for_user(
    session: Session,
    user_id: uuid.UUID,
    preferred_language: str,
    initial_message: str | None,
    explicit_language: str | None,
    request_id: str,
) -> Conversation:
    """Create a new conversation (and optional first user message) for a user.

    Derives title (D-TIT1) and language (D-LANG1), then delegates to the
    repository which handles the atomic DB transaction.

    Args:
        session: SQLAlchemy sync Session (caller manages transaction boundary).
        user_id: The authenticated user's UUID.
        preferred_language: User's preferred_language fallback (D-LANG1).
        initial_message: Optional first user message content (None = no message).
        explicit_language: Language explicitly provided in the request (overrides).
        request_id: X-Request-ID for log correlation.

    Returns:
        The newly created Conversation ORM object with id populated.
    """
    user_id_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
    t0 = time.perf_counter()

    # D-LANG1: prefer explicit language, fall back to user's preferred language.
    language = explicit_language if explicit_language is not None else preferred_language

    # D-TIT1: derive title from initial_message or leave empty.
    title = _derive_title(initial_message)

    logger.debug(
        "chat.service.create_conversation.start request_id=%s user_id_hash=%s "
        "language=%s has_message=%s title_len=%d",
        request_id,
        user_id_hash,
        language,
        initial_message is not None,
        len(title),
    )  # BEFORE

    conv = create_conversation(
        session=session,
        user_id=user_id,
        title=title,
        language=language,
        initial_message=initial_message,
    )

    latency_ms = (time.perf_counter() - t0) * 1000

    logger.debug(
        "chat.service.create_conversation.done request_id=%s user_id_hash=%s "
        "conv_id_prefix=%s latency_ms=%.1f",
        request_id,
        user_id_hash,
        str(conv.id)[:8],
        latency_ms,
    )  # AFTER

    return conv
