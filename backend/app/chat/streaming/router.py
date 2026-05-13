"""
Hilo People — Chat streaming HTTP endpoint router.

Slice:  P02-S03-T002 — Chat streaming endpoint (§D-CHATSTREAM-ROUTER)
Phase:  P02 Core Features (the motor)
Purpose: FastAPI APIRouter for the SSE streaming endpoint:
           POST /api/v1/chat/conversations/{conversation_id}/stream

         Responsibilities (HTTP layer only):
           - Auth: get_current_user → 401 if not authenticated.
           - Body parse: StreamRequest → 400 if invalid.
           - StreamingResponse (text/event-stream) wrapping run_stream generator.
           - Error mapping: domain errors → HTTP codes BEFORE headers sent.
             (After headers sent, errors arrive as SSE 'error' events.)

         Does NOT contain business logic — all orchestration is in service.py.

Decisions:
  - D-CHATSTREAM-WIRE: included via chat/routers/__init__.py aggregator (not main.py).
  - D-CHATSTREAM-AUTH: reuses app.users.deps.get_current_user exactly.
  - D-CHATSTREAM-RL: rate limit deferred (§H D-CHATSTREAM-RL).
  - D-CHATSTREAM-AUD1: no audit_log writes from this slice.
  - Pydantic body validation 422→400: chat endpoint errors emit
    CHAT_STREAM_BAD_REQUEST (mirrors pattern from app/main.py for chat paths).
    We handle it manually here by catching ValidationError from model_validate.

Source refs:
  - task pack P02-S03-T002 §C (endpoint contract)
  - task pack P02-S03-T002 §B (acceptance criteria)
  - task pack P02-S03-T002 §H (decisions)
  - 01-non-negotiables.md §API contract, §Logging
"""

from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.orm import Session

from app.auth.routers._helpers import _error_response, _get_request_id
from app.chat.errors import (
    ConversationForbiddenError,
    ConversationNotFoundError,
    NoActiveChatModelError,
)
from app.chat.streaming.model_selector import get_active_chat_model
from app.chat.streaming.schemas import StreamRequest
from app.chat.streaming.service import run_stream
from app.db.models.user import User
from app.db.session import get_db_session
from app.users.deps import get_current_user

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post(
    "/conversations/{conversation_id}/stream",
    summary="Stream a chat response (SSE)",
    description=(
        "POST a user message to start SSE streaming. "
        "Emits: meta → citation* → chunk* → usage → done. "
        "Auth required (Bearer). "
        "Rate limit deferred (D-CHATSTREAM-RL)."
    ),
    response_class=StreamingResponse,
    response_model=None,
)
async def stream_conversation(
    conversation_id: uuid.UUID,
    request: Request,
    current_user: User | JSONResponse = Depends(get_current_user),
    session: Session = Depends(get_db_session),
) -> StreamingResponse | JSONResponse:
    """SSE endpoint: POST /api/v1/chat/conversations/{id}/stream.

    Validates ownership, persists user message, retrieves RAG context,
    streams LLM response, and persists the turn result atomically.

    Args:
        conversation_id: Target conversation UUID (path param).
        request: FastAPI Request (body + headers).
        current_user: Authenticated User or 401 JSONResponse.
        session: SQLAlchemy sync Session.

    Returns:
        StreamingResponse (text/event-stream) on success.
        JSONResponse with error envelope on pre-stream failure (400/401/403/404/502).
    """
    request_id = _get_request_id(request)

    if _VERBOSE:
        logger.debug(
            "chat.stream.router.start request_id=%s conv_id_prefix=%s",
            request_id,
            str(conversation_id)[:8],
        )  # BEFORE

    # Step 0a: Auth check (401).
    if isinstance(current_user, JSONResponse):
        return current_user

    # Step 0b: Parse request body (400).
    # Pydantic ValidationError (IS-A Exception) + JSON decode/value errors all map to 400.
    try:
        raw_body = await request.json()
        body = StreamRequest.model_validate(raw_body)
    except Exception as exc:
        logger.warning(
            "chat.stream.router.bad_request request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
        return _error_response(
            request_id=request_id,
            code="CHAT_STREAM_BAD_REQUEST",
            message="Invalid request body. 'message' field must be 1–8000 characters.",
            http_status=400,
        )

    if _VERBOSE:
        logger.debug(
            "chat.stream.router.body_ok request_id=%s msg_len=%d",
            request_id,
            len(body.message),
        )

    # Step 0c: Pre-flight checks (ownership and model) BEFORE starting StreamingResponse.
    # These must happen before we send headers, or the error can't be a JSON envelope.
    try:
        from app.db.models.chat import Conversation

        conv_check = session.get(Conversation, conversation_id)
        if conv_check is None:
            return _error_response(
                request_id=request_id,
                code="CHAT_CONVERSATION_NOT_FOUND",
                message="Conversation not found.",
                http_status=404,
            )
        if conv_check.user_id != current_user.id:
            return _error_response(
                request_id=request_id,
                code="CHAT_CONVERSATION_FORBIDDEN",
                message="You do not have access to this conversation.",
                http_status=403,
            )
        # Check active chat model before starting stream.
        get_active_chat_model(session)

    except NoActiveChatModelError:
        logger.error(
            "chat.stream.router.no_model request_id=%s", request_id
        )
        return _error_response(
            request_id=request_id,
            code="AI_PROVIDER_NOT_CONFIGURED",
            message="No active chat model configured. Contact your administrator.",
            http_status=502,
        )
    except (ConversationNotFoundError, ConversationForbiddenError):
        raise  # Already handled above; should not reach here.

    if _VERBOSE:
        logger.debug(
            "chat.stream.router.preflight_ok request_id=%s", request_id
        )

    # Build and return StreamingResponse.
    async def _generate():
        async for chunk in run_stream(
            session,
            conversation_id=conversation_id,
            user_id=current_user.id,
            message=body.message,
            request_id=request_id,
        ):
            yield chunk

    if _VERBOSE:
        logger.debug(
            "chat.stream.router.streaming_start request_id=%s", request_id
        )  # AFTER setup — streaming begins

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream; charset=utf-8",
        headers={
            "X-Request-ID": request_id,
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )
