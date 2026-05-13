"""
Hilo People — Cursor-based pagination helpers for chat conversations.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Encode and decode opaque cursors used for the GET /api/v1/chat/conversations
         pagination. The cursor format is base64url("<ISO-8601 updated_at>|<uuid>").
         This design gives stable pagination over time-ordered feeds even when
         concurrent inserts happen between page fetches.

Cursor contract (D-PAG1 from task pack):
  - Cursor = base64url(f"{updated_at_iso}|{id_uuid}")
  - updated_at format: ISO-8601 with microseconds, UTC (Z suffix).
  - Separator: "|" (pipe).
  - Decoding errors (bad base64, bad format, unparseable datetime) raise CursorInvalidError.
  - A cursor that decodes cleanly but matches no rows is NOT an error — it returns
    an empty page (normal end-of-feed behaviour).

Source refs:
  - task pack P02-S03-T001 §G (pagination contract D-PAG1)
  - 01-non-negotiables.md §API contract (cursor pagination for time-ordered feeds)
"""

from __future__ import annotations

import base64
import uuid
from datetime import datetime, timezone

from app.chat.errors import CursorInvalidError


def encode_cursor(updated_at: datetime, row_id: uuid.UUID) -> str:
    """Encode a (updated_at, id) pair into an opaque base64url cursor string.

    The cursor is URL-safe (base64url) and padding-free so it can be passed
    as a query parameter without percent-encoding.

    Args:
        updated_at: The conversation's updated_at timestamp (should be UTC).
        row_id: The conversation's UUID primary key (tiebreaker for stable sort).

    Returns:
        A URL-safe base64-encoded string without padding.
    """
    # Normalize to UTC ISO-8601 with Z suffix.
    if updated_at.tzinfo is None:
        # Treat naive datetimes as UTC (all DB timestamps are TIMESTAMPTZ).
        updated_at = updated_at.replace(tzinfo=timezone.utc)
    iso_ts = updated_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    raw = f"{iso_ts}|{row_id}"
    return base64.urlsafe_b64encode(raw.encode()).rstrip(b"=").decode()


def decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    """Decode an opaque cursor string into (updated_at, id).

    Validates base64 encoding, pipe separator, ISO-8601 datetime, and UUID format.
    Raises CursorInvalidError for any malformed input.

    Args:
        cursor: URL-safe base64-encoded cursor string (may lack trailing '=').

    Returns:
        Tuple of (updated_at datetime with UTC tzinfo, conversation UUID).

    Raises:
        CursorInvalidError: If the cursor cannot be decoded or parsed.
    """
    # Restore padding before decoding (urlsafe_b64decode needs it).
    padding = 4 - (len(cursor) % 4)
    if padding != 4:
        cursor_padded = cursor + "=" * padding
    else:
        cursor_padded = cursor

    try:
        raw = base64.urlsafe_b64decode(cursor_padded).decode("utf-8")
    except Exception as exc:
        raise CursorInvalidError(f"Base64 decoding failed: {exc}") from exc

    parts = raw.split("|", 1)
    if len(parts) != 2:
        raise CursorInvalidError("Cursor missing pipe separator.")

    ts_str, id_str = parts

    try:
        # Python 3.11+ accepts Z suffix; 3.10 requires stripping it.
        ts_normalized = ts_str.replace("Z", "+00:00")
        updated_at = datetime.fromisoformat(ts_normalized)
    except ValueError as exc:
        raise CursorInvalidError(f"Cursor datetime not parseable: {exc}") from exc

    try:
        row_id = uuid.UUID(id_str)
    except ValueError as exc:
        raise CursorInvalidError(f"Cursor UUID not parseable: {exc}") from exc

    return updated_at, row_id
