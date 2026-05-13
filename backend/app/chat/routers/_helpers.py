"""
Hilo People — Chat router shared helpers.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Shared utilities for chat HTTP endpoints:
           - _hash_user_id: hash user UUID for PII-safe logging.
           - _make_error_response: build {data:null, meta, errors:[…]} envelope.
           - _build_conversation_detail: convert ORM+extras to ConversationDetailDTO.

Extracted to keep conversations.py ≤300 LOC (mirrors auth routers/_helpers.py pattern).

Source refs:
  - task pack P02-S03-T001 §H.6 (D-LOG1: never log plain user UUID)
  - 01-non-negotiables.md §API contract (consistent error envelope)
  - 01-non-negotiables.md §File size (≤300 LOC per file)
"""

from __future__ import annotations

import hashlib
import uuid

from fastapi.responses import JSONResponse

from app.auth.schemas import ErrorItem, ErrorResponse, ResponseMeta
from app.chat.schemas import (
    ConversationDetailDTO,
    MessageCitationDTO,
    MessageDTO,
)
from app.db.models.chat import Conversation


def hash_user_id(user_id: uuid.UUID) -> str:
    """Hash user UUID for log fields. Returns first 16 hex chars of SHA-256.

    NEVER log plain UUIDs — they are PII-adjacent identifiers per D-LOG1.

    Args:
        user_id: Authenticated user's UUID.

    Returns:
        16-char hex string (first 16 chars of SHA-256(str(user_id))).
    """
    return hashlib.sha256(str(user_id).encode()).hexdigest()[:16]


def make_error_response(
    request_id: str,
    code: str,
    message: str,
    http_status: int,
) -> JSONResponse:
    """Build the standard {data:null, meta, errors:[{code, message}]} envelope.

    Args:
        request_id: X-Request-ID for correlation.
        code: Machine-readable error code (e.g. 'CHAT_CURSOR_INVALID').
        message: Debug message (not shown to users).
        http_status: HTTP response status code.

    Returns:
        JSONResponse with the error envelope.
    """
    envelope = ErrorResponse(
        meta=ResponseMeta(request_id=request_id),
        errors=[ErrorItem(code=code, message=message)],
    )
    return JSONResponse(
        content=envelope.model_dump(),
        status_code=http_status,
    )


def build_conversation_detail(conv: Conversation) -> ConversationDetailDTO:
    """Build ConversationDetailDTO from a Conversation ORM object with attached extras.

    The repository attaches ._messages and ._citations as plain Python lists
    (not ORM relationships) to avoid mutating the models defined in P02-S01-T001.

    Args:
        conv: Conversation ORM object with ._messages: list[Message] and
              ._citations: list[MessageCitation] attributes attached.

    Returns:
        ConversationDetailDTO with messages and citations populated.
    """
    messages_dto = [
        MessageDTO.model_validate(m)
        for m in getattr(conv, "_messages", [])
    ]
    citations_dto = [
        MessageCitationDTO.model_validate(c)
        for c in getattr(conv, "_citations", [])
    ]
    return ConversationDetailDTO(
        id=conv.id,
        user_id=conv.user_id,
        title=conv.title,
        language=conv.language,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=messages_dto,
        citations=citations_dto,
    )
