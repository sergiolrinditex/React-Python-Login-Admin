"""
Hilo People — Chat streaming persistence helpers.

Slice:  P02-S03-T002 — Chat streaming endpoint (§D-CHATSTREAM-PERSIST)
Phase:  P02 Core Features (the motor)
Purpose: All DB write operations for one streaming turn:
           1. persist_user_message  — INSERT user turn BEFORE streaming (AC-6).
           2. persist_turn_result   — INSERT assistant msg + citations + usage log +
                                     UPDATE conversation.updated_at (AC-3/4/5/9).
           3. persist_partial_turn  — Background-session partial persist on cancel
                                     (D-CHATSTREAM-PARTIAL / §K-CHATSTREAM-BGSESSION).
           4. build_citation_label  — Shared label builder (DRY; used by service too).

         Each function accepts its own Session so the partial-persist path can use
         a fresh SessionLocal() when the request-scoped session is aborted.

Business rules:
  - User message persisted + committed BEFORE any LLM call (survives disconnect).
  - Assistant message + citations + usage log in ONE atomic transaction.
  - On partial result: token_count=None; latency_ms = time elapsed so far.
  - Citations link to the ASSISTANT message, never the user message (AC-4).

Security:
  - NEVER log message content, chunk content, or assistant content (PII).
  - Log only lengths, counts, and UUIDs.

Source refs:
  - task pack P02-S03-T002 §D (data model touchpoints — exact columns)
  - task pack P02-S03-T002 §G (pipeline steps 2 + 5)
  - task pack P02-S03-T002 §H D-CHATSTREAM-PARTIAL (partial persist policy)
  - 01-non-negotiables.md §Database (transactions, parametrized queries)
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.chat import Conversation, Message, MessageCitation
from app.db.models.admin_ai import LlmUsageLog
from app.db.session import _SessionLocal
from app.rag.schemas import RetrievedChunk

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"


def persist_user_message(
    session: Session,
    conversation_id: uuid.UUID,
    content: str,
    request_id: str,
) -> uuid.UUID:
    """INSERT the user's message row and COMMIT immediately (AC-6).

    The commit ensures this row survives even if the client disconnects
    mid-stream or the LLM call fails entirely.

    Args:
        session: SQLAlchemy sync Session (request-scoped).
        conversation_id: UUID of the conversation this message belongs to.
        content: User's raw message text. NOT logged (PII).
        request_id: X-Request-ID for log correlation.

    Returns:
        UUID of the newly created user message row.
    """
    if _VERBOSE:
        logger.debug(
            "chat.stream.persist.user_message.start request_id=%s conv_id_prefix=%s content_len=%d",
            request_id,
            str(conversation_id)[:8],
            len(content),
        )  # BEFORE

    msg_id = uuid.uuid4()
    msg = Message(
        id=msg_id,
        conversation_id=conversation_id,
        role="user",
        content=content,
        token_count=None,
    )
    session.add(msg)
    session.commit()

    if _VERBOSE:
        logger.debug(
            "chat.stream.persist.user_message.done request_id=%s msg_id=%s",
            request_id,
            str(msg_id),
        )  # AFTER

    return msg_id


def persist_turn_result(
    session: Session,
    *,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    model_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    assistant_content: str,
    token_count: int | None,
    chunks: list[RetrievedChunk],
    tokens_in: int,
    tokens_out: int,
    estimated_cost: float,
    latency_ms: int,
    request_id: str,
) -> None:
    """Atomically INSERT assistant message + citations + usage log, UPDATE conversation.

    Single atomic transaction covering:
      - INSERT messages (role='assistant') — AC-3
      - INSERT message_citations (one per retrieved chunk) — AC-4
      - INSERT llm_usage_logs — AC-5
      - UPDATE conversations SET updated_at=now() — AC-9

    On partial result (D-CHATSTREAM-PARTIAL): token_count=None is passed when the
    stream was cancelled; the schema allows NULL.

    Args:
        session: SQLAlchemy sync Session. MUST be a fresh session if called from
                 a cancelled-context cleanup (§K-CHATSTREAM-BGSESSION).
        conversation_id: Parent conversation UUID.
        user_id: Requesting user UUID (for llm_usage_logs).
        model_id: Active chat model UUID (for llm_usage_logs).
        assistant_message_id: Pre-assigned UUID for the assistant message row.
        assistant_content: Full concatenated assistant response. NOT logged (PII).
        token_count: Completion tokens count (None on partial/cancelled).
        chunks: RAG-retrieved chunks; used to build message_citations rows.
        tokens_in: Input token count from usage payload.
        tokens_out: Output token count from usage payload.
        estimated_cost: Estimated USD cost from usage payload.
        latency_ms: Total generation latency in ms.
        request_id: X-Request-ID for log correlation.

    Returns:
        None. Commits the session on success.
    """
    if _VERBOSE:
        logger.debug(
            "chat.stream.persist.turn_result.start request_id=%s conv_id_prefix=%s "
            "content_len=%d citation_count=%d tokens_out=%d partial=%s",
            request_id,
            str(conversation_id)[:8],
            len(assistant_content),
            len(chunks),
            tokens_out,
            str(token_count is None),
        )  # BEFORE

    # INSERT assistant message.
    assistant_msg = Message(
        id=assistant_message_id,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        token_count=token_count,
    )
    session.add(assistant_msg)
    session.flush()  # Ensure assistant_message_id is visible for citations FK.

    # INSERT message_citations (bulk).
    for chunk in chunks:
        label = build_citation_label(chunk)
        citation = MessageCitation(
            id=uuid.uuid4(),
            message_id=assistant_message_id,
            document_id=chunk.document_id,
            chunk_id=chunk.chunk_id,
            label=label,
            score=chunk.score,
        )
        session.add(citation)

    # INSERT llm_usage_logs.
    usage_log = LlmUsageLog(
        id=uuid.uuid4(),
        user_id=user_id,
        model_id=model_id,
        conversation_id=conversation_id,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        estimated_cost=estimated_cost,
        latency_ms=latency_ms,
    )
    session.add(usage_log)

    # UPDATE conversations.updated_at.
    session.execute(
        sa.update(Conversation)
        .where(Conversation.id == conversation_id)
        .values(updated_at=sa.func.now())
    )

    session.commit()

    if _VERBOSE:
        logger.debug(
            "chat.stream.persist.turn_result.done request_id=%s msg_id=%s "
            "citations=%d latency_ms=%d",
            request_id,
            str(assistant_message_id),
            len(chunks),
            latency_ms,
        )  # AFTER


async def persist_partial_turn(
    *,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    model_id: uuid.UUID,
    assistant_message_id: uuid.UUID,
    buffer: list[str],
    chunks: list[RetrievedChunk],
    usage_payload: dict,
    t0: float,
    request_id: str,
) -> None:
    """Persist a partial streaming result using a fresh background session.

    Opens a new SessionLocal() so the request-scoped session (which may be in
    an aborted state after client disconnect) is not used (§K-CHATSTREAM-BGSESSION).
    Called on asyncio.CancelledError or LLM mid-stream error (D-CHATSTREAM-PARTIAL).

    Args:
        conversation_id: Parent conversation UUID.
        user_id: Requesting user UUID (for llm_usage_logs).
        model_id: Active chat model UUID.
        assistant_message_id: Pre-assigned assistant message UUID.
        buffer: Accumulated delta text list (may be empty).
        chunks: Retrieved RAG chunks (for citations).
        usage_payload: Usage dict from LLM (may be empty if error was early).
        t0: Stream start time from time.perf_counter().
        request_id: X-Request-ID for log correlation.
    """
    logger.warning(
        "chat.stream.partial_persist.start request_id=%s partial_chars=%d citations=%d",
        request_id,
        sum(len(d) for d in buffer),
        len(chunks),
    )

    partial_content = "".join(buffer) if buffer else ""
    elapsed_ms = int((time.perf_counter() - t0) * 1000)

    bg_session = _SessionLocal()
    try:
        persist_turn_result(
            bg_session,
            conversation_id=conversation_id,
            user_id=user_id,
            model_id=model_id,
            assistant_message_id=assistant_message_id,
            assistant_content=partial_content,
            token_count=None,  # partial — AC-7 D-CHATSTREAM-PARTIAL
            chunks=chunks,
            tokens_in=usage_payload.get("tokens_in", 0),
            tokens_out=0,
            estimated_cost=0.0,
            latency_ms=elapsed_ms,
            request_id=request_id,
        )
        logger.warning(
            "chat.stream.partial_persist.done request_id=%s elapsed_ms=%d",
            request_id,
            elapsed_ms,
        )
    except Exception as exc:
        logger.error(
            "chat.stream.partial_persist.error request_id=%s error=%s",
            request_id,
            type(exc).__name__,
        )
    finally:
        bg_session.close()


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

def build_citation_label(chunk: RetrievedChunk) -> str:
    """Build a human-readable citation label from a retrieved chunk.

    Shared by service.py (for SSE citation events) and persist_turn_result
    (for message_citations rows). Centralised here to enforce DRY.

    Per D-RET1: the label construction is the caller's (P02-S03-T002) responsibility.

    Args:
        chunk: RetrievedChunk with metadata dict (JSONB from DB).

    Returns:
        Human-readable citation label (e.g. 'Política vacaciones, p.3').
    """
    metadata: dict[str, Any] = chunk.metadata or {}
    title = metadata.get("title") or metadata.get("document_title") or "Fuente"
    page = metadata.get("page") or metadata.get("page_number")
    if page:
        return f"{title}, p.{page}"
    return str(title)
