"""
Hilo People — SSE framing helpers.

Slice:  P02-S03-T002 — Chat streaming endpoint (§D-CHATSTREAM-SSE)
Phase:  P02 Core Features (the motor)
Purpose: Low-level SSE framing utilities. Produces wire-format bytes for each
         SSE event type following W3C text/event-stream spec:
           event: <name>\ndata: <json>\n\n

         The frontend's fetch-stream parser (P03-S02-T002) expects:
           - One JSON object per data: line (no multi-line data fields).
           - event: prefix present on every event.
           - Double-newline (\n\n) as event separator.

         NEVER include raw content (prompt, assistant text, document content)
         in logs — only lengths and IDs.

Source refs:
  - task pack P02-S03-T002 §C (SSE wire format §D-CHATSTREAM-SSE)
  - task pack P02-S03-T002 §M.5 (W3C text/event-stream framing confirmation)
  - W3C Server-Sent Events spec (https://html.spec.whatwg.org/multipage/server-sent-events.html)

Decisions:
  - D-SSE1: Each event is exactly two lines: `event: <name>\n` + `data: <json>\n\n`.
    No id: or retry: fields in V1 (YAGNI — frontend will reconnect on network error
    via its own retry logic, not via EventSource reconnect).
  - D-SSE2: JSON is serialized with ensure_ascii=False so Spanish/French characters
    are preserved as UTF-8 (not escaped as \\uXXXX). The response charset is utf-8.
"""

from __future__ import annotations

import json
from typing import Any


_ENCODING = "utf-8"


def make_sse_bytes(event_name: str, payload: dict[str, Any]) -> bytes:
    """Produce W3C SSE wire bytes for one event.

    Format (per D-SSE1):
        event: <event_name>\n
        data: <json_payload>\n
        \n

    Args:
        event_name: SSE event name (meta|chunk|citation|usage|error|done).
        payload: Dict to serialize as JSON. Must be JSON-serializable.
                 NEVER pass raw text/content fields.

    Returns:
        UTF-8 encoded bytes ready to yield from an async generator.
    """
    data_str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    raw = f"event: {event_name}\ndata: {data_str}\n\n"
    return raw.encode(_ENCODING)


def sse_meta(
    message_id: str,
    model_id: str,
    language: str,
    request_id: str,
) -> bytes:
    """Produce SSE 'meta' event bytes.

    Args:
        message_id: Pre-assigned UUID string for the assistant message.
        model_id: UUID string of the active AI model.
        language: Conversation language code.
        request_id: X-Request-ID correlation header.

    Returns:
        SSE wire bytes for the meta event.
    """
    return make_sse_bytes("meta", {
        "message_id": message_id,
        "model_id": model_id,
        "language": language,
        "request_id": request_id,
    })


def sse_chunk(delta: str) -> bytes:
    """Produce SSE 'chunk' event bytes for an incremental text fragment.

    Args:
        delta: Incremental text from the LLM. Length is logged; value is NOT logged.

    Returns:
        SSE wire bytes for the chunk event.
    """
    return make_sse_bytes("chunk", {"delta": delta})


def sse_citation(
    document_id: str,
    chunk_id: str,
    label: str,
    score: float,
) -> bytes:
    """Produce SSE 'citation' event bytes for a RAG source citation.

    Args:
        document_id: UUID string of the cited document.
        chunk_id: UUID string of the cited chunk.
        label: Human-readable citation label.
        score: Cosine similarity retrieval score.

    Returns:
        SSE wire bytes for the citation event.
    """
    return make_sse_bytes("citation", {
        "document_id": document_id,
        "chunk_id": chunk_id,
        "label": label,
        "score": score,
    })


def sse_usage(
    tokens_in: int,
    tokens_out: int,
    estimated_cost: float,
    latency_ms: int,
) -> bytes:
    """Produce SSE 'usage' event bytes for token/cost accounting.

    Args:
        tokens_in: Input token count.
        tokens_out: Output token count.
        estimated_cost: Estimated USD cost.
        latency_ms: Total generation latency in ms.

    Returns:
        SSE wire bytes for the usage event.
    """
    return make_sse_bytes("usage", {
        "tokens_in": tokens_in,
        "tokens_out": tokens_out,
        "estimated_cost": estimated_cost,
        "latency_ms": latency_ms,
    })


def sse_error(code: str, message: str) -> bytes:
    """Produce SSE 'error' event bytes for a mid-stream fatal error.

    Args:
        code: Machine-readable error code.
        message: Human-readable description (no PII, no content).

    Returns:
        SSE wire bytes for the error event.
    """
    return make_sse_bytes("error", {"code": code, "message": message})


def sse_done(message_id: str, request_id: str) -> bytes:
    """Produce SSE 'done' terminal event bytes.

    Args:
        message_id: UUID string of the persisted assistant message.
        request_id: X-Request-ID for end-to-end traceability.

    Returns:
        SSE wire bytes for the done event (terminal).
    """
    return make_sse_bytes("done", {"message_id": message_id, "request_id": request_id})
