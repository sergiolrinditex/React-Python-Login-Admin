"""
Hilo People — Unit tests for SSE framing helpers.

Slice:  P02-S03-T002 — Chat streaming endpoint (§K-TEST-SPLIT)
Phase:  P02 Core Features (the motor)
Purpose: Verifies sse.py framing produces exact W3C text/event-stream wire bytes
         for each event type, with UTF-8 Spanish/French content and edge cases.

Tests map to task pack §J.2 (unit test for sse.py):
  - SSE framing for all event types (meta, chunk, citation, usage, error, done).
  - JSON encoding handles UTF-8 (Spanish/French content).
  - Edge case: empty delta is wire-valid.
  - Event separator is exactly \\n\\n.
  - JSON is single-line (no multi-line data fields).

Source refs:
  - task pack P02-S03-T002 §J.2
  - task pack P02-S03-T002 §C (SSE wire format spec)
  - 01-non-negotiables.md §Tests are REAL (unit tests for pure logic CAN be isolated)
"""
from __future__ import annotations

import json

import pytest

from app.chat.streaming.sse import (
    make_sse_bytes,
    sse_chunk,
    sse_citation,
    sse_done,
    sse_error,
    sse_meta,
    sse_usage,
)


class TestMakeSseBytes:
    """Direct tests for the make_sse_bytes framing primitive."""

    def test_framing_format(self):
        """Output follows exact W3C format: event:\\n, data:\\n, \\n."""
        result = make_sse_bytes("meta", {"key": "value"})
        lines = result.decode("utf-8").split("\n")
        assert lines[0] == "event: meta"
        assert lines[1].startswith("data: ")
        assert lines[2] == ""
        assert lines[3] == ""

    def test_double_newline_separator(self):
        """Each event ends with exactly \\n\\n."""
        result = make_sse_bytes("chunk", {"delta": "hello"})
        assert result.endswith(b"\n\n")

    def test_json_is_single_line(self):
        """data: line contains a single-line JSON object (no embedded newlines)."""
        result = make_sse_bytes("usage", {"tokens_in": 10, "tokens_out": 5})
        data_line = result.decode("utf-8").split("\n")[1]
        assert data_line.startswith("data: ")
        payload_str = data_line[len("data: "):]
        # Must be valid JSON and have no embedded newlines.
        parsed = json.loads(payload_str)
        assert "\n" not in payload_str
        assert parsed["tokens_in"] == 10

    def test_utf8_spanish_preserved(self):
        """Spanish accented characters are not escaped (ensure_ascii=False)."""
        result = make_sse_bytes("chunk", {"delta": "¿Cuántos días?"})
        decoded = result.decode("utf-8")
        assert "¿Cuántos días?" in decoded
        # Ensure no \\u escapes for these chars.
        assert "\\u00bf" not in decoded.lower()

    def test_utf8_french_preserved(self):
        """French characters preserved as UTF-8 (not ASCII-escaped)."""
        result = make_sse_bytes("chunk", {"delta": "Résumé: café"})
        decoded = result.decode("utf-8")
        assert "Résumé: café" in decoded

    def test_returns_bytes(self):
        """Return type is bytes."""
        result = make_sse_bytes("done", {"message_id": "abc", "request_id": "xyz"})
        assert isinstance(result, bytes)


class TestSseMeta:
    """Tests for sse_meta() helper."""

    def test_meta_event_name(self):
        """Event name is 'meta'."""
        result = sse_meta("msg-id", "model-id", "es", "req-id")
        assert b"event: meta\n" in result

    def test_meta_payload_fields(self):
        """All four required fields present in payload."""
        result = sse_meta("msg-1", "model-1", "es", "req-1")
        data_str = _extract_data(result)
        payload = json.loads(data_str)
        assert payload["message_id"] == "msg-1"
        assert payload["model_id"] == "model-1"
        assert payload["language"] == "es"
        assert payload["request_id"] == "req-1"


class TestSseChunk:
    """Tests for sse_chunk() helper."""

    def test_chunk_event_name(self):
        """Event name is 'chunk'."""
        result = sse_chunk("Hello")
        assert b"event: chunk\n" in result

    def test_chunk_delta_present(self):
        """delta field present in payload."""
        result = sse_chunk("Hola mundo")
        payload = json.loads(_extract_data(result))
        assert payload["delta"] == "Hola mundo"

    def test_empty_delta_wire_valid(self):
        """Empty delta string is a valid wire event (edge case)."""
        result = sse_chunk("")
        payload = json.loads(_extract_data(result))
        assert payload["delta"] == ""
        assert result.endswith(b"\n\n")

    def test_multiline_delta_single_data_line(self):
        """Delta with newline chars is JSON-encoded on a single data: line."""
        result = sse_chunk("line1\nline2")
        data_line = result.decode("utf-8").split("\n")[1]
        assert data_line.startswith("data: ")
        payload = json.loads(data_line[len("data: "):])
        assert "line1" in payload["delta"]


class TestSseCitation:
    """Tests for sse_citation() helper."""

    def test_citation_event_name(self):
        """Event name is 'citation'."""
        result = sse_citation("doc-id", "chunk-id", "Política vacaciones, p.3", 0.87)
        assert b"event: citation\n" in result

    def test_citation_payload_fields(self):
        """All four required fields present."""
        result = sse_citation("doc-1", "chunk-1", "Fuente A, p.1", 0.9)
        payload = json.loads(_extract_data(result))
        assert payload["document_id"] == "doc-1"
        assert payload["chunk_id"] == "chunk-1"
        assert payload["label"] == "Fuente A, p.1"
        assert payload["score"] == pytest.approx(0.9)


class TestSseUsage:
    """Tests for sse_usage() helper."""

    def test_usage_event_name(self):
        """Event name is 'usage'."""
        result = sse_usage(100, 50, 0.00045, 1200)
        assert b"event: usage\n" in result

    def test_usage_payload_fields(self):
        """All four token/cost fields present."""
        result = sse_usage(100, 50, 0.00045, 1200)
        payload = json.loads(_extract_data(result))
        assert payload["tokens_in"] == 100
        assert payload["tokens_out"] == 50
        assert payload["estimated_cost"] == pytest.approx(0.00045)
        assert payload["latency_ms"] == 1200


class TestSseError:
    """Tests for sse_error() helper."""

    def test_error_event_name(self):
        """Event name is 'error'."""
        result = sse_error("STREAM_ERROR", "upstream failed")
        assert b"event: error\n" in result

    def test_error_payload_fields(self):
        """code and message fields present."""
        result = sse_error("LITELLM_ERROR", "timeout")
        payload = json.loads(_extract_data(result))
        assert payload["code"] == "LITELLM_ERROR"
        assert payload["message"] == "timeout"


class TestSseDone:
    """Tests for sse_done() helper."""

    def test_done_event_name(self):
        """Event name is 'done'."""
        result = sse_done("msg-id", "req-id")
        assert b"event: done\n" in result

    def test_done_payload_fields(self):
        """message_id and request_id fields present."""
        result = sse_done("msg-42", "req-42")
        payload = json.loads(_extract_data(result))
        assert payload["message_id"] == "msg-42"
        assert payload["request_id"] == "req-42"

    def test_done_ends_with_double_newline(self):
        """Terminal event still ends with \\n\\n."""
        result = sse_done("msg-id", "req-id")
        assert result.endswith(b"\n\n")


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _extract_data(sse_bytes: bytes) -> str:
    """Extract the JSON string from the data: line of an SSE event."""
    for line in sse_bytes.decode("utf-8").split("\n"):
        if line.startswith("data: "):
            return line[len("data: "):]
    raise AssertionError(f"No data: line found in: {sse_bytes!r}")
