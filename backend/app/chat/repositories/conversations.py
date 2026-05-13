"""
Hilo People — Chat conversation repository (SQLAlchemy 2.x sync).

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Pure data-access layer for the chat conversation bounded context.
         All queries use SQLAlchemy ORM (select / scalar_one_or_none / scalars().all())
         with sync Session (get_db_session). No business logic here — only DB I/O.

Functions:
  find_conversations_paginated     — list user's conversations with cursor pagination.
  find_conversation_with_messages  — get conversation + messages + citations by ID.
  create_conversation              — insert conversation + optional first user message.

Source refs:
  - task pack P02-S03-T001 §F.3 (tables: conversations, messages, message_citations)
  - task pack P02-S03-T001 §G (cursor pagination D-PAG1)
  - TECHNICAL_GUIDE §10.3#chat (schema + indexes)
  - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR in every function)

Decisions:
  - D-R3: conversations.user_id can be NULL (anonymous/system). WHERE user_id == :uid
    uses `==` not `is_()` because `current_user.id` is never None in this context.
  - D-R4: role='user' is hardcoded for the initial message in create_conversation.
    Only T001 creates user messages here; assistant messages are T002 (stream).
  - D-IDX: The `conversations_user_updated_idx(user_id, updated_at DESC)` index covers
    the pagination WHERE + ORDER BY clause for near-O(1) page fetches.
"""

from __future__ import annotations

import logging
import uuid

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.chat.cursor import decode_cursor, encode_cursor
from app.db.models.chat import Conversation, Message, MessageCitation

logger = logging.getLogger(__name__)


def find_conversations_paginated(
    session: Session,
    user_id: uuid.UUID,
    limit: int,
    cursor: str | None,
) -> tuple[list[Conversation], bool, str | None]:
    """Fetch a page of conversations for a user using cursor-based pagination.

    Implements the D-PAG1 algorithm:
      - Requests limit+1 rows.
      - If limit+1 rows returned: has_more=True, discard the last row.
      - next_cursor is built from the LAST row in the returned page (not the discarded one).

    Args:
        session: SQLAlchemy sync Session.
        user_id: The authenticated user's UUID.
        limit: Page size (already clamped to [1, 100] by the router).
        cursor: Opaque cursor from a previous response, or None for first page.

    Returns:
        Tuple of:
          - list[Conversation]: The page of conversation ORM objects.
          - has_more (bool): True if there are more rows beyond this page.
          - next_cursor (str | None): Opaque cursor for the next page, None if last.

    Raises:
        CursorInvalidError: If cursor is provided but cannot be decoded/parsed.
    """
    logger.debug(
        "chat.repo.find_conversations_paginated.start user_id_prefix=%s limit=%d has_cursor=%s",
        str(user_id)[:8],
        limit,
        cursor is not None,
    )  # BEFORE

    stmt = (
        sa.select(Conversation)
        .where(Conversation.user_id == user_id)
    )

    if cursor:
        # decode_cursor raises CursorInvalidError on bad input — propagated to service.
        cursor_updated_at, cursor_id = decode_cursor(cursor)
        # WHERE (updated_at, id) < (cursor_updated_at, cursor_id) for DESC order.
        stmt = stmt.where(
            sa.or_(
                Conversation.updated_at < cursor_updated_at,
                sa.and_(
                    Conversation.updated_at == cursor_updated_at,
                    Conversation.id < cursor_id,
                ),
            )
        )

    stmt = (
        stmt
        .order_by(Conversation.updated_at.desc(), Conversation.id.desc())
        .limit(limit + 1)
    )

    rows: list[Conversation] = list(session.scalars(stmt).all())
    has_more = len(rows) > limit

    if has_more:
        rows = rows[:limit]  # discard the (limit+1)-th sentinel row

    next_cursor: str | None = None
    if rows and has_more:
        last = rows[-1]
        next_cursor = encode_cursor(last.updated_at, last.id)

    logger.debug(
        "chat.repo.find_conversations_paginated.done user_id_prefix=%s count=%d has_more=%s",
        str(user_id)[:8],
        len(rows),
        has_more,
    )  # AFTER

    return rows, has_more, next_cursor


def find_conversation_with_messages(
    session: Session,
    conversation_id: uuid.UUID,
) -> Conversation | None:
    """Fetch a conversation by ID with eager-loaded messages and citations.

    The caller (service) is responsible for ownership checks (403 vs 404).

    Args:
        session: SQLAlchemy sync Session.
        conversation_id: Conversation UUID to look up.

    Returns:
        Conversation ORM object with `.messages` and `.citations` attributes
        populated, or None if no conversation with that ID exists.
    """
    logger.debug(
        "chat.repo.find_conversation_with_messages.start conv_id_prefix=%s",
        str(conversation_id)[:8],
    )  # BEFORE

    conv = session.scalar(
        sa.select(Conversation).where(Conversation.id == conversation_id)
    )

    if conv is None:
        logger.debug(
            "chat.repo.find_conversation_with_messages.not_found conv_id_prefix=%s",
            str(conversation_id)[:8],
        )
        return None

    # Load messages ordered by created_at ASC (chronological conversation order).
    messages: list[Message] = list(
        session.scalars(
            sa.select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        ).all()
    )

    # Collect message IDs to load citations in one query.
    msg_ids = [m.id for m in messages]
    citations: list[MessageCitation] = []
    if msg_ids:
        citations = list(
            session.scalars(
                sa.select(MessageCitation)
                .where(MessageCitation.message_id.in_(msg_ids))
                .order_by(MessageCitation.message_id, MessageCitation.id)
            ).all()
        )

    # Attach as plain Python attributes (not ORM relationships — no relationship
    # defined on models to keep P02-S01-T001 models untouched).
    conv._messages = messages  # type: ignore[attr-defined]
    conv._citations = citations  # type: ignore[attr-defined]

    logger.debug(
        "chat.repo.find_conversation_with_messages.done conv_id_prefix=%s "
        "msg_count=%d citation_count=%d",
        str(conversation_id)[:8],
        len(messages),
        len(citations),
    )  # AFTER

    return conv


def create_conversation(
    session: Session,
    user_id: uuid.UUID,
    title: str,
    language: str,
    initial_message: str | None,
) -> Conversation:
    """Insert a conversation and optionally a first user message (atomic transaction).

    Implements D-TX1: if initial_message is provided, both the conversation row
    and the message row are inserted in the same transaction context. If any step
    fails, the session is rolled back by the caller's transaction manager.

    After inserting the message, updates conversation.updated_at to DB server time
    so the conversation surfaces at the top of subsequent list queries.

    Args:
        session: SQLAlchemy sync Session (caller manages transaction boundary).
        user_id: The authenticated user's UUID.
        title: Auto-generated title (empty string or truncated initial_message).
        language: ISO 639-1 language code (es|en|fr).
        initial_message: Optional first user message content. D-R4: role='user'.

    Returns:
        The newly created Conversation ORM object (id populated after flush).
    """
    logger.debug(
        "chat.repo.create_conversation.start user_id_prefix=%s language=%s "
        "has_message=%s title_len=%d",
        str(user_id)[:8],
        language,
        initial_message is not None,
        len(title),
    )  # BEFORE

    conv = Conversation(
        user_id=user_id,
        title=title,
        language=language,
    )
    session.add(conv)
    session.flush()  # populate conv.id without committing

    if initial_message is not None:
        msg = Message(
            conversation_id=conv.id,
            role="user",  # D-R4: only user messages created in T001
            content=initial_message,
            token_count=None,
        )
        session.add(msg)
        # Update conv.updated_at to DB server clock so it rises to top of list.
        session.execute(
            sa.update(Conversation)
            .where(Conversation.id == conv.id)
            .values(updated_at=sa.func.now())
        )
        # Refresh conv to pick up DB-generated updated_at.
        session.refresh(conv)

    logger.debug(
        "chat.repo.create_conversation.done conv_id_prefix=%s has_message=%s",
        str(conv.id)[:8],
        initial_message is not None,
    )  # AFTER

    return conv
