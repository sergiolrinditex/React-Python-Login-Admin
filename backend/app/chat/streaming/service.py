"""
Hilo People — Chat streaming use-case orchestrator.

Slice:  P02-S03-T002 — Chat streaming endpoint (§D-CHATSTREAM-SVC)
Phase:  P02 Core Features (the motor)
Purpose: Orchestrates the 5-step pipeline for one streaming turn:
           1. Validate conversation ownership (404/403).
           2. Persist user message before streaming (AC-6).
           3. Retrieve RAG context (embed query → vector search).
           4. Stream-generate LLM response, emit SSE events.
           5. Persist assistant msg + citations + usage atomically.

         Yields bytes (SSE events). FastAPI wraps in StreamingResponse.

         Partial-persist logic and build_citation_label live in
         persistence.py to keep this file under the ~300 LoC target.

Logging:
  VERBOSE=true: BEFORE/AFTER per step (validate/retrieve/generate/persist).
  VERBOSE=false: WARNING and ERROR only.
  NEVER log: message content, assistant content, chunk text, api_key.
  Log only: lengths, counts, UUIDs, timing.

Source refs:
  - task pack P02-S03-T002 §G (pipeline + §G.1 system prompt + §G.2 cancel)
  - task pack P02-S03-T002 §H (decisions D-CHATSTREAM-*)
  - 01-non-negotiables.md §Logging
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import os
import time
import uuid
from typing import AsyncIterator

from sqlalchemy.orm import Session

from app.chat.errors import (
    ConversationForbiddenError,
    ConversationNotFoundError,
    NoActiveChatModelError,
)
from app.chat.streaming.model_selector import (
    get_active_chat_model,
    get_active_embeddings_model,
)
from app.chat.streaming.persistence import (
    build_citation_label,
    persist_partial_turn,
    persist_turn_result,
    persist_user_message,
)
from app.chat.streaming.sse import (
    sse_chunk,
    sse_citation,
    sse_done,
    sse_error,
    sse_meta,
    sse_usage,
)
from app.db.models.chat import Conversation
from app.llm_gateway.litellm_client import stream_chat
from app.llm_gateway.errors import EmbeddingError
from app.rag import retrieve, RetrieverFilters, RetrievedChunk
from app.security.encryption import decrypt_secret

logger = logging.getLogger(__name__)
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# System prompt constant (D-CHATSTREAM-SVC; §G.1; YAGNI for single-prompt V1).
SYSTEM_PROMPT_PEOPLE_ASSISTANT = """\
Eres Hilo, asistente de People/RRHH para empleados de Inditex y sus marcas.
Responde de forma breve, profesional y cercana. Usa el idioma del usuario.
Cuando la respuesta venga de un documento del contexto, cita su título.
Si no encuentras información suficiente, di que no lo sabes y deriva a People.
NUNCA inventes políticas, fechas, importes ni procedimientos.
"""


def _get_conversation(
    session: Session,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    request_id: str,
) -> Conversation:
    """Validate conversation existence and ownership.

    Args:
        session: Active sync Session.
        conversation_id: Conversation UUID to look up.
        user_id: Requesting user UUID.
        request_id: X-Request-ID for log correlation.

    Returns:
        Conversation ORM object.

    Raises:
        ConversationNotFoundError: If no row with that ID.
        ConversationForbiddenError: If row exists but owner mismatch.
    """
    uid_hash = hashlib.sha256(str(user_id).encode()).hexdigest()[:16]

    if _VERBOSE:
        logger.debug(
            "chat.stream.validate.start request_id=%s user_id_hash=%s conv_id_prefix=%s",
            request_id,
            uid_hash,
            str(conversation_id)[:8],
        )  # BEFORE

    conv = session.get(Conversation, conversation_id)

    if conv is None:
        logger.debug(
            "chat.stream.validate.not_found request_id=%s conv_id_prefix=%s",
            request_id,
            str(conversation_id)[:8],
        )
        raise ConversationNotFoundError()

    if conv.user_id != user_id:
        logger.warning(
            "chat.stream.validate.forbidden request_id=%s user_id_hash=%s conv_id_prefix=%s",
            request_id,
            uid_hash,
            str(conversation_id)[:8],
        )
        raise ConversationForbiddenError()

    if _VERBOSE:
        logger.debug(
            "chat.stream.validate.done request_id=%s conv_id_prefix=%s language=%s",
            request_id,
            str(conversation_id)[:8],
            conv.language,
        )  # AFTER

    return conv


async def run_stream(
    session: Session,
    *,
    conversation_id: uuid.UUID,
    user_id: uuid.UUID,
    message: str,
    request_id: str,
) -> AsyncIterator[bytes]:
    """Main async generator: orchestrates the 5-step streaming pipeline.

    Yields SSE-framed bytes. Handles client disconnect and LLM errors with
    partial-persist cleanup.

    Args:
        session: Request-scoped SQLAlchemy sync Session.
        conversation_id: Target conversation UUID.
        user_id: Authenticated user UUID.
        message: User's raw message text. NOT logged (PII).
        request_id: X-Request-ID for log correlation.

    Yields:
        bytes: SSE-framed event bytes (meta, citation*, chunk*, usage, done | error).
    """
    # -----------------------------------------------------------------------
    # Step 1: Validate conversation ownership
    # -----------------------------------------------------------------------
    conv = _get_conversation(session, conversation_id, user_id, request_id)

    # -----------------------------------------------------------------------
    # Step 2: Persist user message (AC-6 — before any streaming)
    # -----------------------------------------------------------------------
    if _VERBOSE:
        logger.debug(
            "chat.stream.persist_user_msg.start request_id=%s content_len=%d",
            request_id,
            len(message),
        )  # BEFORE step 2

    persist_user_message(session, conversation_id, message, request_id)

    if _VERBOSE:
        logger.debug("chat.stream.persist_user_msg.done request_id=%s", request_id)  # AFTER step 2

    # -----------------------------------------------------------------------
    # Step 3: Retrieve RAG context
    # -----------------------------------------------------------------------
    if _VERBOSE:
        logger.debug(
            "chat.stream.retrieve.start request_id=%s language=%s", request_id, conv.language
        )  # BEFORE step 3

    chunks: list[RetrievedChunk] = []
    try:
        embed_model, embed_provider, embed_cred = get_active_embeddings_model(session)
        embed_api_key = decrypt_secret(embed_cred.encrypted_secret)
        from app.llm_gateway.litellm_client import embed_query
        query_embedding = await embed_query(
            model=embed_model,
            provider=embed_provider,
            api_key=embed_api_key,
            text=message,
            request_id=request_id,
        )
        filters = RetrieverFilters(language=conv.language, collection_ids=[], k=5)
        chunks = retrieve(
            session=session,
            query_embedding=query_embedding,
            filters=filters,
            request_id=request_id,
        )
    except (NoActiveChatModelError, EmbeddingError) as exc:
        logger.warning(
            "chat.stream.retrieve.skip request_id=%s reason=%s",
            request_id,
            type(exc).__name__,
        )
        chunks = []  # RAG is optional augmentation — continue without context.

    if _VERBOSE:
        logger.debug(
            "chat.stream.retrieve.done request_id=%s chunk_count=%d", request_id, len(chunks)
        )  # AFTER step 3

    # -----------------------------------------------------------------------
    # Step 4: Stream-generate (emit SSE events)
    # -----------------------------------------------------------------------
    chat_model, chat_provider, chat_cred = get_active_chat_model(session)
    chat_api_key = decrypt_secret(chat_cred.encrypted_secret)

    # Pre-assign assistant message UUID so we can include it in the meta event.
    assistant_message_id = uuid.uuid4()

    if _VERBOSE:
        logger.debug(
            "chat.stream.generate.start request_id=%s model_id=%s chunk_count=%d",
            request_id,
            str(chat_model.id),
            len(chunks),
        )  # BEFORE step 4

    # Emit meta event.
    yield sse_meta(
        message_id=str(assistant_message_id),
        model_id=str(chat_model.id),
        language=conv.language,
        request_id=request_id,
    )

    # Emit citation events BEFORE generation (D-CHATSTREAM-CITORDER).
    for chunk in chunks:
        label = build_citation_label(chunk)
        yield sse_citation(
            document_id=str(chunk.document_id),
            chunk_id=str(chunk.chunk_id),
            label=label,
            score=chunk.score,
        )

    # Build messages for LLM.
    context_text = "\n---\n".join(c.content for c in chunks) if chunks else ""
    system_content = SYSTEM_PROMPT_PEOPLE_ASSISTANT
    if context_text:
        system_content = system_content + "\n\nContext:\n" + context_text

    llm_messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": message},
    ]

    # Stream from LLM.
    assistant_content_buffer: list[str] = []
    usage_payload: dict = {"tokens_in": 0, "tokens_out": 0, "estimated_cost": 0.0, "latency_ms": 0}
    t0 = time.perf_counter()

    try:
        async for event in stream_chat(
            model=chat_model,
            provider=chat_provider,
            api_key=chat_api_key,
            messages=llm_messages,
            request_id=request_id,
        ):
            if event.kind == "delta":
                delta = event.payload.get("delta", "")
                if delta:
                    assistant_content_buffer.append(delta)
                    yield sse_chunk(delta)
            elif event.kind == "usage":
                usage_payload = event.payload
            elif event.kind == "error":
                yield sse_error(
                    code=event.payload.get("code", "STREAM_ERROR"),
                    message=event.payload.get("message", "Stream error"),
                )
                # Persist partial and return.
                await persist_partial_turn(
                    conversation_id=conversation_id,
                    user_id=user_id,
                    model_id=chat_model.id,
                    assistant_message_id=assistant_message_id,
                    buffer=assistant_content_buffer,
                    chunks=chunks,
                    usage_payload=usage_payload,
                    t0=t0,
                    request_id=request_id,
                )
                return

        if _VERBOSE:
            logger.debug(
                "chat.stream.generate.done request_id=%s delta_chunks=%d tokens_out=%d",
                request_id,
                len(assistant_content_buffer),
                usage_payload.get("tokens_out", 0),
            )  # AFTER step 4

    except asyncio.CancelledError:
        logger.warning(
            "chat.stream.client_disconnect request_id=%s partial_chars=%d citations=%d",
            request_id,
            sum(len(d) for d in assistant_content_buffer),
            len(chunks),
        )
        await persist_partial_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            model_id=chat_model.id,
            assistant_message_id=assistant_message_id,
            buffer=assistant_content_buffer,
            chunks=chunks,
            usage_payload=usage_payload,
            t0=t0,
            request_id=request_id,
        )
        raise  # Must re-raise CancelledError.

    # -----------------------------------------------------------------------
    # Step 5: Persist + close
    # -----------------------------------------------------------------------
    if _VERBOSE:
        logger.debug(
            "chat.stream.persist_result.start request_id=%s content_len=%d citations=%d",
            request_id,
            sum(len(d) for d in assistant_content_buffer),
            len(chunks),
        )  # BEFORE step 5

    full_content = "".join(assistant_content_buffer)
    tokens_out = usage_payload.get("tokens_out", 0)

    persist_turn_result(
        session,
        conversation_id=conversation_id,
        user_id=user_id,
        model_id=chat_model.id,
        assistant_message_id=assistant_message_id,
        assistant_content=full_content,
        token_count=tokens_out if tokens_out else None,
        chunks=chunks,
        tokens_in=usage_payload.get("tokens_in", 0),
        tokens_out=tokens_out,
        estimated_cost=float(usage_payload.get("estimated_cost", 0.0)),
        latency_ms=usage_payload.get("latency_ms", int((time.perf_counter() - t0) * 1000)),
        request_id=request_id,
    )

    if _VERBOSE:
        logger.debug(
            "chat.stream.persist_result.done request_id=%s msg_id=%s",
            request_id,
            str(assistant_message_id),
        )  # AFTER step 5

    # Emit usage + done events.
    yield sse_usage(
        tokens_in=usage_payload.get("tokens_in", 0),
        tokens_out=usage_payload.get("tokens_out", 0),
        estimated_cost=float(usage_payload.get("estimated_cost", 0.0)),
        latency_ms=usage_payload.get("latency_ms", int((time.perf_counter() - t0) * 1000)),
    )
    yield sse_done(message_id=str(assistant_message_id), request_id=request_id)

