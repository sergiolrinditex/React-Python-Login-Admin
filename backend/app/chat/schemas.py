"""
Hilo People — Chat Pydantic v2 request/response schemas.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Data transfer objects (DTOs) for the chat conversation bounded context.
         Covers request bodies (CreateConversationRequest) and response envelopes
         ({data, meta, errors}) for the three CRUD endpoints:
           - GET /api/v1/chat/conversations
           - POST /api/v1/chat/conversations
           - GET /api/v1/chat/conversations/{id}

All DTOs use Pydantic v2 BaseModel. The ResponseMeta here extends the auth
ResponseMeta with an optional pagination field (option (a) from task pack §F.2).
The chat module owns ChatResponseMeta locally (option (b)) to keep WRITE_SET_DRIFT
minimal — the existing auth ResponseMeta remains unchanged.

Source refs:
  - TECHNICAL_GUIDE §6.2 rows 264-266 (endpoint request/response shapes)
  - TECHNICAL_GUIDE §6.3 (Conversation/Message/MessageCitation Pydantic shapes)
  - task pack P02-S03-T001 §F.2 (schema decisions: option b — local ChatResponseMeta)
  - 01-non-negotiables.md §API contract ({data, meta, errors} envelope)
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Core DTOs
# ---------------------------------------------------------------------------

class ConversationDTO(BaseModel):
    """Conversation summary DTO for list and detail responses.

    Attributes:
        id: Conversation UUID.
        user_id: Owner user UUID.
        title: Auto-generated or user-provided title.
        language: ISO 639-1 language code (es|en|fr).
        created_at: Creation timestamp (UTC).
        updated_at: Last update timestamp (UTC, changes when new message added).
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    user_id: uuid.UUID | None
    title: str
    language: Literal["es", "en", "fr"]
    created_at: datetime
    updated_at: datetime


class MessageDTO(BaseModel):
    """Single message turn DTO (user or assistant).

    Attributes:
        id: Message UUID.
        conversation_id: Parent conversation UUID.
        role: Message author — 'user', 'assistant', or 'system'.
        content: Raw message content. NEVER log full content (PII).
        token_count: LLM token count, null until assistant message is complete.
        created_at: Creation timestamp (UTC).
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    conversation_id: uuid.UUID
    role: Literal["user", "assistant", "system"]
    content: str
    token_count: int | None
    created_at: datetime


class MessageCitationDTO(BaseModel):
    """RAG citation attached to an assistant message.

    document_id and chunk_id are nullable per D-LATE: citations survive
    document deletion/versioning (no FK in the DB schema).

    Attributes:
        id: Citation UUID.
        message_id: Parent message UUID.
        document_id: Cited document UUID (nullable — D-LATE).
        chunk_id: Cited chunk UUID (nullable — D-LATE).
        label: Human-readable citation label shown in UI.
        score: Cosine similarity retrieval score (0.0–1.0).
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    message_id: uuid.UUID
    document_id: uuid.UUID | None
    chunk_id: uuid.UUID | None
    label: str
    score: float


class ConversationDetailDTO(ConversationDTO):
    """Extended conversation DTO for GET /conversations/{id}.

    Includes all messages and the citations for assistant messages.

    Attributes:
        messages: Ordered list of messages (ascending by created_at).
        citations: Citations across ALL assistant messages in this conversation.
    """

    messages: list[MessageDTO] = Field(default_factory=list)
    citations: list[MessageCitationDTO] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------

class CreateConversationRequest(BaseModel):
    """Request body for POST /api/v1/chat/conversations.

    All fields are optional:
    - If initial_message is provided, a first user message is created atomically
      with the conversation (D-TX1).
    - If language is omitted, the service uses current_user.preferred_language (D-LANG1).
    - If initial_message is omitted and no language is given, the title defaults
      to empty string '' (D-TIT1 — frontend renders placeholder via i18n key).

    Attributes:
        initial_message: Optional first user message (1–8000 chars).
        language: Explicit language override (es|en|fr). Defaults to user's preferred.
    """

    initial_message: str | None = Field(
        default=None,
        min_length=1,
        max_length=8000,
        description="Optional first user message. Creates a message row atomically.",
    )
    language: Literal["es", "en", "fr"] | None = Field(
        default=None,
        description="Language for the conversation. Defaults to user.preferred_language.",
    )


# ---------------------------------------------------------------------------
# Response metadata
# ---------------------------------------------------------------------------

class PaginationMeta(BaseModel):
    """Pagination metadata included in list responses.

    Attributes:
        next_cursor: Opaque base64url cursor for the next page, null if last page.
        has_more: True if there are more items beyond the current page.
    """

    next_cursor: str | None
    has_more: bool


class ChatResponseMeta(BaseModel):
    """Chat-specific response metadata wrapper.

    Extends the base auth ResponseMeta with an optional pagination field.
    This is a LOCAL variant (option b from task pack §F.2) to avoid WRITE_SET_DRIFT
    on app/auth/schemas.py. The envelope shape is {data, meta, errors}.

    Attributes:
        request_id: X-Request-ID correlation header value.
        pagination: Optional pagination metadata (only in list responses).
    """

    request_id: str = Field(description="X-Request-ID correlation header value.")
    pagination: PaginationMeta | None = None


# ---------------------------------------------------------------------------
# Response envelopes
# ---------------------------------------------------------------------------

class CreateConversationResponseData(BaseModel):
    """Data payload returned for POST /api/v1/chat/conversations (HTTP 201).

    Attributes:
        conversation_id: UUID of the newly created conversation.
    """

    conversation_id: uuid.UUID


class CreateConversationResponse(BaseModel):
    """Envelope for POST /api/v1/chat/conversations (HTTP 201).

    Shape: {data: {conversation_id}, meta: {request_id}, errors: []}.
    """

    data: CreateConversationResponseData
    meta: ChatResponseMeta
    errors: list[Any] = Field(default_factory=list)


class ListConversationsResponse(BaseModel):
    """Envelope for GET /api/v1/chat/conversations (HTTP 200).

    Shape: {data: [ConversationDTO], meta: {request_id, pagination}, errors: []}.
    """

    data: list[ConversationDTO]
    meta: ChatResponseMeta
    errors: list[Any] = Field(default_factory=list)


class GetConversationResponse(BaseModel):
    """Envelope for GET /api/v1/chat/conversations/{id} (HTTP 200).

    Shape: {data: ConversationDetailDTO, meta: {request_id}, errors: []}.
    """

    data: ConversationDetailDTO
    meta: ChatResponseMeta
    errors: list[Any] = Field(default_factory=list)
