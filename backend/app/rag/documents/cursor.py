"""
Hilo People — Cursor-based pagination helpers for RAG document list.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Encode/decode opaque cursors for GET /api/v1/admin/rag/documents.
         Cursor format: base64url("<created_at_iso>|<uuid>") — mirrors the
         chat cursor pattern (D-PAG1) but keyed on created_at DESC.

         Ordering: created_at DESC, id DESC (stable for cursor — §A.2.3).

Key deps:
  - base64, uuid, datetime (stdlib)
  - app.rag.documents.errors.DocumentInvalidError (400 on bad cursor)

Source refs:
  - task pack P02-S06-T001 §A.2 (cursor pagination, A.2.4 bad cursor → 400)
  - app/chat/cursor.py — precedent (same encode/decode pattern D-PAG1)
  - 01-non-negotiables.md §API contract (cursor pagination)
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone

from app.rag.documents.errors import DocumentInvalidError


def encode_cursor(created_at: datetime, row_id: uuid.UUID) -> str:
    """Encode (created_at, id) into an opaque base64url cursor.

    Args:
        created_at: Document created_at timestamp (should be UTC).
        row_id:     Document UUID primary key (tiebreaker for stable sort).

    Returns:
        URL-safe base64-encoded string without padding.
    """
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    iso_ts = created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    raw = f"{iso_ts}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode an opaque cursor string into (created_at, id).

    Args:
        cursor: URL-safe base64-encoded cursor (may lack trailing '=').

    Returns:
        Tuple of (created_at datetime with UTC tzinfo, document UUID).

    Raises:
        DocumentInvalidError: If cursor cannot be decoded or parsed (→ 400).
    """
    padding = 4 - (len(cursor) % 4)
    cursor_padded = cursor + "=" * padding if padding != 4 else cursor

    try:
        raw = base64.urlsafe_b64decode(cursor_padded).decode("utf-8")
    except Exception as exc:
        raise DocumentInvalidError("cursor", f"Base64 decoding failed: {exc}") from exc

    parts = raw.split("|", 1)
    if len(parts) != 2:
        raise DocumentInvalidError("cursor", "Cursor missing pipe separator.")

    ts_str, id_str = parts

    try:
        ts_normalized = ts_str.replace("Z", "+00:00")
        created_at = datetime.fromisoformat(ts_normalized)
    except ValueError as exc:
        raise DocumentInvalidError("cursor", f"Cursor datetime not parseable: {exc}") from exc

    try:
        row_id = uuid.UUID(id_str)
    except ValueError as exc:
        raise DocumentInvalidError("cursor", f"Cursor UUID not parseable: {exc}") from exc

    return created_at, row_id
