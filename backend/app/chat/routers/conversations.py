"""
Hilo People — Chat conversation HTTP endpoints.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: FastAPI APIRouter for chat conversation CRUD:
           - GET  /api/v1/chat/conversations       — list (cursor-paginated)
           - POST /api/v1/chat/conversations        — create
           - GET  /api/v1/chat/conversations/{id}  — detail with messages + citations

Auth: `get_current_user` dep returns `User | JSONResponse`; routes do isinstance
check and propagate 401 early-returns (aggregate anti-enum pattern from auth module).

Errors: 400 CHAT_CURSOR_INVALID, 401 AUTH_SESSION_EXPIRED, 403 CHAT_CONVERSATION_FORBIDDEN,
        404 CHAT_CONVERSATION_NOT_FOUND.

Decisions:
  - D-RL1: No rate limit — deferred to hardening task (chat threshold not business-specified).
  - D-AUD1: Chat CRUD is not an auditable action (see §Security/Audit log list).

Source refs: task pack §F.1, §H.6; TECHNICAL_GUIDE §6.2 rows 264-266.
"""

from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, Depends, Query, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.auth.routers._helpers import _get_request_id
from app.chat.errors import (
    ConversationForbiddenError,
    ConversationNotFoundError,
    CursorInvalidError,
)
from app.chat.routers._helpers import (
    build_conversation_detail,
    hash_user_id,
    make_error_response,
)
from app.chat.schemas import (
    ChatResponseMeta,
    ConversationDTO,
    CreateConversationRequest,
    CreateConversationResponse,
    CreateConversationResponseData,
    GetConversationResponse,
    ListConversationsResponse,
    PaginationMeta,
)
from app.chat.services.create_conversation import create_conversation_for_user
from app.chat.services.get_conversation_detail import get_conversation_detail_for_user
from app.chat.services.list_conversations import list_conversations_for_user
from app.db.models.user import User
from app.db.session import get_db_session
from app.users.deps import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])


# ---------------------------------------------------------------------------
# GET /api/v1/chat/conversations
# ---------------------------------------------------------------------------

@router.get(
    "/conversations",
    response_model=ListConversationsResponse,
    summary="List user's conversations (cursor-paginated)",
)
def list_conversations(
    request: Request,
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    current: User | JSONResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """List conversations for the authenticated user with cursor pagination (D-PAG1).

    Args:
        request: HTTP request (X-Request-ID, logging).
        cursor: Opaque base64url cursor (None = first page).
        limit: Page size 1-100, default 20.
        current: Authenticated User or 401 JSONResponse.
        session: SQLAlchemy sync Session.

    Returns:
        200 with {data: [Conversation], meta: {pagination, request_id}, errors: []},
        400 on bad cursor, 401 if unauthenticated.
    """
    request_id = _get_request_id(request)
    t0 = time.perf_counter()

    if isinstance(current, JSONResponse):
        return current

    uid_hash = hash_user_id(current.id)
    logger.debug(
        "chat.routers.list_conversations.start request_id=%s uid_hash=%s limit=%d cursor=%s",
        request_id, uid_hash, limit, cursor is not None,
    )  # BEFORE

    try:
        rows, has_more, next_cursor = list_conversations_for_user(
            session=session, user_id=current.id,
            cursor=cursor, limit=limit, request_id=request_id,
        )
    except CursorInvalidError as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.warning(
            "chat.routers.list_conversations.cursor_invalid request_id=%s uid_hash=%s ms=%.1f",
            request_id, uid_hash, latency_ms,
        )
        return make_error_response(request_id, exc.code, exc.message, status.HTTP_400_BAD_REQUEST)

    latency_ms = (time.perf_counter() - t0) * 1000
    dtos = [ConversationDTO.model_validate(r) for r in rows]
    logger.debug(
        "chat.routers.list_conversations.done request_id=%s uid_hash=%s count=%d "
        "has_more=%s status=200 ms=%.1f",
        request_id, uid_hash, len(dtos), has_more, latency_ms,
    )  # AFTER

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=ListConversationsResponse(
            data=dtos,
            meta=ChatResponseMeta(
                request_id=request_id,
                pagination=PaginationMeta(next_cursor=next_cursor, has_more=has_more),
            ),
        ).model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# POST /api/v1/chat/conversations
# ---------------------------------------------------------------------------

@router.post(
    "/conversations",
    response_model=CreateConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
def create_conversation(
    request: Request,
    body: CreateConversationRequest,
    current: User | JSONResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Create a conversation and optionally an initial user message (D-TX1).

    Title derived per D-TIT1 (first 60 chars or ''). Language per D-LANG1
    (explicit override or user.preferred_language). Atomic: conversation + message
    committed together; rollback on any failure.

    Args:
        request: HTTP request.
        body: CreateConversationRequest (initial_message?, language?).
        current: Authenticated User or 401 JSONResponse.
        session: SQLAlchemy sync Session.

    Returns:
        201 with {data: {conversation_id}, meta, errors: []}, 401 if unauthenticated.
    """
    request_id = _get_request_id(request)
    t0 = time.perf_counter()

    if isinstance(current, JSONResponse):
        return current

    uid_hash = hash_user_id(current.id)
    logger.debug(
        "chat.routers.create_conversation.start request_id=%s uid_hash=%s "
        "has_msg=%s lang=%s",
        request_id, uid_hash, body.initial_message is not None, body.language,
    )  # BEFORE

    try:
        conv = create_conversation_for_user(
            session=session,
            user_id=current.id,
            preferred_language=current.preferred_language or "es",
            initial_message=body.initial_message,
            explicit_language=body.language,
            request_id=request_id,
        )
        session.commit()
    except Exception as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.error(
            "chat.routers.create_conversation.error request_id=%s uid_hash=%s ms=%.1f err=%s",
            request_id, uid_hash, latency_ms, str(exc),
        )  # ERROR
        raise

    latency_ms = (time.perf_counter() - t0) * 1000
    logger.debug(
        "chat.routers.create_conversation.done request_id=%s uid_hash=%s "
        "conv_prefix=%s status=201 ms=%.1f",
        request_id, uid_hash, str(conv.id)[:8], latency_ms,
    )  # AFTER

    return JSONResponse(
        status_code=status.HTTP_201_CREATED,
        content=CreateConversationResponse(
            data=CreateConversationResponseData(conversation_id=conv.id),
            meta=ChatResponseMeta(request_id=request_id),
        ).model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# GET /api/v1/chat/conversations/{conversation_id}
# ---------------------------------------------------------------------------

@router.get(
    "/conversations/{conversation_id}",
    response_model=GetConversationResponse,
    summary="Get conversation detail with messages and citations",
)
def get_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    current: User | JSONResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> JSONResponse:
    """Get conversation detail with all messages and citations.

    Ownership enforced per §F.5:
      - 404 CHAT_CONVERSATION_NOT_FOUND — no row with given ID.
      - 403 CHAT_CONVERSATION_FORBIDDEN — row exists, wrong owner.
    These are distinct codes (TECHNICAL_GUIDE §6.2 row 266 lists 403+404 separately).

    Args:
        conversation_id: UUID path parameter.
        request: HTTP request.
        current: Authenticated User or 401 JSONResponse.
        session: SQLAlchemy sync Session.

    Returns:
        200 {data: ConversationDetail, meta, errors: []}, 401/403/404 on error.
    """
    request_id = _get_request_id(request)
    t0 = time.perf_counter()

    if isinstance(current, JSONResponse):
        return current

    uid_hash = hash_user_id(current.id)
    logger.debug(
        "chat.routers.get_conversation.start request_id=%s uid_hash=%s conv_prefix=%s",
        request_id, uid_hash, str(conversation_id)[:8],
    )  # BEFORE

    try:
        conv = get_conversation_detail_for_user(
            session=session, conversation_id=conversation_id,
            user_id=current.id, request_id=request_id,
        )
    except ConversationNotFoundError as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "chat.routers.get_conversation.not_found request_id=%s conv_prefix=%s ms=%.1f",
            request_id, str(conversation_id)[:8], latency_ms,
        )
        return make_error_response(request_id, exc.code, exc.message, status.HTTP_404_NOT_FOUND)
    except ConversationForbiddenError as exc:
        latency_ms = (time.perf_counter() - t0) * 1000
        logger.warning(
            "chat.routers.get_conversation.forbidden request_id=%s uid_hash=%s "
            "conv_prefix=%s ms=%.1f",
            request_id, uid_hash, str(conversation_id)[:8], latency_ms,
        )
        return make_error_response(request_id, exc.code, exc.message, status.HTTP_403_FORBIDDEN)

    latency_ms = (time.perf_counter() - t0) * 1000
    detail = build_conversation_detail(conv)
    logger.debug(
        "chat.routers.get_conversation.done request_id=%s uid_hash=%s conv_prefix=%s "
        "msgs=%d citations=%d status=200 ms=%.1f",
        request_id, uid_hash, str(conversation_id)[:8],
        len(detail.messages), len(detail.citations), latency_ms,
    )  # AFTER

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=GetConversationResponse(
            data=detail,
            meta=ChatResponseMeta(request_id=request_id),
        ).model_dump(mode="json"),
    )
