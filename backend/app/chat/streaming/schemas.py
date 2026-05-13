"""
Hilo People — Chat streaming Pydantic schemas.

Slice:  P02-S03-T002 — Chat streaming endpoint (§D-CHATSTREAM-SCH)
Phase:  P02 Core Features (the motor)
Purpose: Pydantic v2 request body and internal SSE event DTOs for the
         POST /api/v1/chat/conversations/{id}/stream endpoint.

         StreamRequest is the parsed request body (message field 1–8000 chars).
         The SSE events are emitted as raw bytes via sse.py — no Pydantic
         serialization at wire time (performance). These schemas document the
         contract for tests and documentation.

Source refs:
  - task pack P02-S03-T002 §C (endpoint contract — request body)
  - task pack P02-S03-T002 §B (AC-1 first chunk before LLM completes)
  - task pack P02-S03-T002 §F.2 §D-CHATSTREAM-SCH
  - 01-non-negotiables.md §API contract (input validation at controller level)
"""

from __future__ import annotations

import uuid

from pydantic import BaseModel, Field


class StreamRequest(BaseModel):
    """Request body for POST /api/v1/chat/conversations/{id}/stream.

    Validates the message field at controller level before any DB or LLM work.

    Attributes:
        message: The user's message (1–8000 chars; mirrors CreateConversationRequest).
    """

    message: str = Field(
        min_length=1,
        max_length=8000,
        description="User's message to send (1–8000 chars).",
    )


# ---------------------------------------------------------------------------
# SSE event payload shapes (documentation / test assertions only)
# ---------------------------------------------------------------------------

class MetaEventPayload(BaseModel):
    """Payload for the SSE 'meta' event emitted before any chunks.

    Attributes:
        message_id: Pre-assigned UUID of the assistant message row.
        model_id: UUID of the active AI model.
        language: Conversation language ('es'|'en'|'fr').
        request_id: X-Request-ID for end-to-end traceability.
    """

    message_id: uuid.UUID
    model_id: uuid.UUID
    language: str
    request_id: str


class ChunkEventPayload(BaseModel):
    """Payload for each SSE 'chunk' event (incremental LLM output).

    Attributes:
        delta: Incremental text fragment from the LLM.
    """

    delta: str


class CitationEventPayload(BaseModel):
    """Payload for each SSE 'citation' event (RAG source attribution).

    Attributes:
        document_id: UUID of the cited document.
        chunk_id: UUID of the cited chunk.
        label: Human-readable citation label (e.g. 'Política vacaciones, p.3').
        score: Cosine similarity score [0.0–1.0].
    """

    document_id: uuid.UUID
    chunk_id: uuid.UUID
    label: str
    score: float


class UsageEventPayload(BaseModel):
    """Payload for the SSE 'usage' event (token accounting).

    Attributes:
        tokens_in: Input token count.
        tokens_out: Output token count.
        estimated_cost: Estimated USD cost.
        latency_ms: Total generation latency in milliseconds.
    """

    tokens_in: int
    tokens_out: int
    estimated_cost: float
    latency_ms: int


class ErrorEventPayload(BaseModel):
    """Payload for the SSE 'error' event (mid-stream fatal error).

    Attributes:
        code: Machine-readable error code.
        message: Human-readable error description.
    """

    code: str
    message: str


class DoneEventPayload(BaseModel):
    """Payload for the SSE 'done' event (terminal event).

    Attributes:
        message_id: UUID of the persisted assistant message.
        request_id: X-Request-ID for end-to-end traceability.
    """

    message_id: uuid.UUID
    request_id: str
