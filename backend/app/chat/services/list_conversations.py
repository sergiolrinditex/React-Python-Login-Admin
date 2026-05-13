"""
Hilo People — Use case: list conversations for a user.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Use case for GET /api/v1/chat/conversations. Validates pagination
         parameters, delegates to the repository, and builds the pagination
         metadata for the response.

Business rule:
  - An employee can only see their own conversations (user_id filter).
  - Cursor pagination (D-PAG1): stable, no COUNT(*), safe with concurrent inserts.
  - Limit is clamped to [1, 100]; default 20 (enforced by FastAPI Query, but
    service also clamps defensively).

Source refs:
  - task pack P02-S03-T001 §G (D-PAG1 cursor pagination contract)
  - TECHNICAL_GUIDE §6.2 row 264 (GET /chat/conversations response)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR per use case)
"""

from __future__ import annotations

import hashlib
import logging
import time
import uuid

from sqlalchemy.orm import Session

from app.chat.errors import CursorInvalidError
from app.chat.repositories.conversations import find_conversations_paginated
from app.db.models.chat import Conversation

logger = logging.getLogger(__name__)

_MAX_LIMIT = 100
_DEFAULT_LIMIT = 20


def list_conversations_for_user(
    session: Session,
    user_id: uuid.UUID,
    cursor: str | None,
    limit: int,
    request_id: str,
) -> tuple[list[Conversation], bool, str | None]:
    """List paginated conversations for a user.

    Clamps limit to [1, 100]. Decodes the cursor (raises CursorInvalidError
    if malformed). Delegates to find_conversations_paginated.

    Args:
        session: SQLAlchemy sync Session.
        user_id: The authenticated user's UUID.
        cursor: Opaque pagination cursor from a previous response (None = first page).
        limit: Requested page size. Will be clamped to [1, _MAX_LIMIT].
        request_id: X-Request-ID for log correlation.

    Returns:
        Tuple of:
          - list[Conversation]: The conversation rows for this page.
          - has_more (bool): True if there are more pages.
          - next_cursor (str | None): Opaque cursor for the next page, None if last.

    Raises:
        CursorInvalidError: Propagated from the repository when cursor is malformed.
    """
    user_id_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]
    clamped_limit = max(1, min(limit, _MAX_LIMIT))
    t0 = time.perf_counter()

    logger.debug(
        "chat.service.list_conversations.start request_id=%s user_id_hash=%s "
        "limit=%d has_cursor=%s",
        request_id,
        user_id_hash,
        clamped_limit,
        cursor is not None,
    )  # BEFORE

    try:
        rows, has_more, next_cursor = find_conversations_paginated(
            session=session,
            user_id=user_id,
            limit=clamped_limit,
            cursor=cursor,
        )
    except CursorInvalidError:
        logger.warning(
            "chat.service.list_conversations.invalid_cursor request_id=%s user_id_hash=%s",
            request_id,
            user_id_hash,
        )
        raise

    latency_ms = (time.perf_counter() - t0) * 1000

    logger.debug(
        "chat.service.list_conversations.done request_id=%s user_id_hash=%s "
        "count=%d has_more=%s latency_ms=%.1f",
        request_id,
        user_id_hash,
        len(rows),
        has_more,
        latency_ms,
    )  # AFTER

    return rows, has_more, next_cursor
