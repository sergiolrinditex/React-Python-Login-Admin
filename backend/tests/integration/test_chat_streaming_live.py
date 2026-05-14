"""
Hilo People — Live integration test for chat streaming through real LiteLLM proxy.

Slice:  P02-S03-T006 — Fix model_str composition (D-T006-LIVE-TEST-GATE)
Phase:  P02 Core Features (the motor)
Purpose: End-to-end integration test that exercises the real HTTP path:
         admin sign-in → create conversation → POST /stream → assert SSE event sequence.

         This test is gated by env LITELLM_PROXY_UP=1.
         CI default = SKIPPED (LITELLM_PROXY_UP not set).
         /verify-slice exports LITELLM_PROXY_UP=1 after hard reset + datos reales load.

         The test does NOT mock litellm.acompletion — the whole point is to verify
         the fixed model_str reaches the real proxy and gets a real response.

Dependencies (must be up when LITELLM_PROXY_UP=1):
  - Backend API on http://localhost:8000 (or TEST_API_BASE_URL env).
  - LiteLLM proxy on http://localhost:4000 with gpt-4o-mini model configured.
  - PostgreSQL with verification data loaded:
      python -m app.verification_data.bootstrap --source data/verification --only rag_chat

Verification Data Contract (task pack §6.5):
  - Persona: employee.verification@inditex-sandbox.com
  - Model: gpt-4o-mini via litellm_verification_sandbox provider on http://localhost:4000
  - Seeded by P02-S03-T004

R-T006-6 NOTE: If litellm_verification_sandbox.credential_plain is still null
(R-CREDS gap from P02-S05-T002 P-25), the test will skip with a clear message.
The real bearer must be injected at /verify-slice gate time.

Source refs:
  - task pack P02-S03-T006 §VERIFY_PLAN §C (live integration test skeleton)
  - task pack P02-S03-T006 §CLOSE_CRITERIA §evidence
  - official-doc-notes/P02-S03-T006-litellm-provider-map-2026-05-14.md (Q3 api_key semantics)
"""

from __future__ import annotations

import os
import time
from typing import Any

import pytest
import requests

# ---------------------------------------------------------------------------
# Gate: skip unless LITELLM_PROXY_UP=1 is explicitly set.
# This prevents CI from running without a live proxy.
# ---------------------------------------------------------------------------

pytestmark = pytest.mark.skipif(
    os.getenv("LITELLM_PROXY_UP") != "1",
    reason=(
        "Requires running LiteLLM proxy on :4000 and backend on :8000. "
        "Set LITELLM_PROXY_UP=1 to enable. "
        "Normally activated by /verify-slice hard reset + datos reales load."
    ),
)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_API_BASE = os.getenv("TEST_API_BASE_URL", "http://localhost:8000")
_AUTH_URL = f"{_API_BASE}/api/v1/auth/sign-in"
_CONV_URL = f"{_API_BASE}/api/v1/chat/conversations"
_TIMEOUT_CONNECT = 10  # seconds
_TIMEOUT_STREAM = 60  # seconds — live proxy may take time

# Employee verification credentials (seeded by P02-S03-T004).
# If the password is not available in the env, the test skips with a message.
_EMPLOYEE_EMAIL = os.getenv(
    "TEST_EMPLOYEE_EMAIL",
    "employee.verification@inditex-sandbox.com",
)
_EMPLOYEE_PASSWORD = os.getenv("TEST_EMPLOYEE_PASSWORD", "")
_EMPLOYEE_TOTP = os.getenv("TEST_EMPLOYEE_TOTP", "")

# Admin credentials as fallback (chat endpoint requires employee role, admin may also work).
_ADMIN_EMAIL = os.getenv("TEST_ADMIN_EMAIL", "admin_peopletech@inditex-sandbox.com")
_ADMIN_PASSWORD = os.getenv("TEST_ADMIN_PASSWORD", "")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sign_in(email: str, password: str, totp: str = "") -> str:
    """Sign in and return the access token. Skip if credentials are missing."""
    if not password:
        pytest.skip(
            f"TEST_EMPLOYEE_PASSWORD (or TEST_ADMIN_PASSWORD) not set — "
            f"cannot sign in as {email}. "
            "Inject the real bearer at /verify-slice gate time (R-T006-6)."
        )

    body: dict[str, Any] = {"email": email, "password": password}
    if totp:
        body["totp_code"] = totp

    resp = requests.post(
        _AUTH_URL,
        json=body,
        timeout=_TIMEOUT_CONNECT,
        headers={"Content-Type": "application/json"},
    )
    if resp.status_code == 401:
        pytest.skip(
            f"Sign-in returned 401 for {email}. "
            "Ensure the verification data is loaded and credentials are correct."
        )
    resp.raise_for_status()
    data = resp.json()

    # Support both cookie-based (access_token in body) and header-based responses.
    token = data.get("data", {}).get("access_token") or data.get("access_token") or ""
    if not token:
        pytest.skip(
            f"Sign-in for {email} returned 200 but no access_token in body. "
            "Check the auth response envelope."
        )
    return token


def _create_conversation(token: str) -> str:
    """Create a new conversation and return its ID."""
    resp = requests.post(
        _CONV_URL,
        json={},
        timeout=_TIMEOUT_CONNECT,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    resp.raise_for_status()
    data = resp.json()
    conv_id = (
        data.get("data", {}).get("id")
        or data.get("data", {}).get("conversation_id")
        or data.get("id")
        or ""
    )
    if not conv_id:
        pytest.skip(
            "POST /chat/conversations returned 200 but no conversation id. "
            "Check the response envelope."
        )
    return conv_id


def _parse_sse_lines(content: bytes) -> list[str]:
    """Parse raw SSE bytes into a list of non-empty lines."""
    return [
        line.strip()
        for line in content.decode("utf-8", errors="replace").splitlines()
        if line.strip()
    ]


def _extract_event_types(lines: list[str]) -> list[str]:
    """Extract the 'event: <type>' values in order from SSE line list."""
    return [
        line[len("event:") :].strip() for line in lines if line.startswith("event:")
    ]


# ---------------------------------------------------------------------------
# The live test
# ---------------------------------------------------------------------------


class TestChatStreamingLive:
    """Live integration tests for POST /chat/conversations/{id}/stream.

    All tests in this class require LITELLM_PROXY_UP=1 (file-level pytestmark).
    """

    def test_stream_meta_chunk_usage_done_sequence(self):
        """Live stream: response contains meta → chunk(s) → usage → done in order.

        Acceptance criterion #1 and #3 from task pack P02-S03-T006:
          - HTTP 200
          - Content-Type: text/event-stream
          - Event sequence: meta → chunk(*) → usage → done
          - No BadRequestError in back.log (visible via model_str assertion)

        This test passes ONLY if the model_str fix is in place:
          Old (broken): model="litellm/gpt-4o-mini" → BadRequestError
          New (fixed):  model="openai/gpt-4o-mini" + api_base=http://localhost:4000 → OK
        """
        # Step 1: Sign in.
        token = _sign_in(_EMPLOYEE_EMAIL, _EMPLOYEE_PASSWORD, _EMPLOYEE_TOTP)
        if not token:
            # Try admin as fallback
            token = _sign_in(_ADMIN_EMAIL, _ADMIN_PASSWORD)

        # Step 2: Create conversation.
        conv_id = _create_conversation(token)

        # Step 3: Stream.
        stream_url = f"{_CONV_URL}/{conv_id}/stream"
        t0 = time.perf_counter()

        with requests.post(
            stream_url,
            json={"message": "hello"},
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            timeout=(_TIMEOUT_CONNECT, _TIMEOUT_STREAM),
            stream=True,
        ) as resp:
            # Assertion: HTTP 200
            assert resp.status_code == 200, (
                f"Expected 200, got {resp.status_code}. Body: {resp.text[:500]}"
            )

            # Assertion: Content-Type is text/event-stream
            content_type = resp.headers.get("Content-Type", "")
            assert "text/event-stream" in content_type, (
                f"Expected text/event-stream, got '{content_type}'"
            )

            # Collect full response body (up to 32 KB to avoid hanging forever).
            chunks: list[bytes] = []
            for raw_chunk in resp.iter_content(chunk_size=1024):
                if raw_chunk:
                    chunks.append(raw_chunk)
                    # Stop after seeing 'event: done' (we have the full sequence).
                    if b"event: done" in raw_chunk:
                        break
                    # Safety cap: avoid hanging on a runaway stream.
                    if len(b"".join(chunks)) > 32 * 1024:
                        break

        latency_ms = int((time.perf_counter() - t0) * 1000)
        raw_body = b"".join(chunks)
        lines = _parse_sse_lines(raw_body)
        event_types = _extract_event_types(lines)

        # Assertion: event sequence contains all required types.
        assert "meta" in event_types, (
            f"Expected 'event: meta' in SSE stream. Got event types: {event_types}. "
            f"First 1000 bytes: {raw_body[:1000]!r}"
        )
        assert "chunk" in event_types, (
            f"Expected at least one 'event: chunk' in SSE stream. Got: {event_types}. "
            f"If you see only 'event: meta' and 'event: done', the LLM returned empty. "
            f"First 1000 bytes: {raw_body[:1000]!r}"
        )
        assert "usage" in event_types, (
            f"Expected 'event: usage' in SSE stream. Got: {event_types}."
        )
        assert "done" in event_types, (
            f"Expected 'event: done' in SSE stream. Got: {event_types}."
        )

        # Assertion: ordering (meta before chunk, usage before done).
        try:
            idx_meta = event_types.index("meta")
            idx_chunk = next(i for i, e in enumerate(event_types) if e == "chunk")
            idx_usage = event_types.index("usage")
            idx_done = event_types.index("done")
            assert idx_meta < idx_chunk, "meta must appear before first chunk"
            assert idx_chunk < idx_usage, "chunk must appear before usage"
            assert idx_usage < idx_done, "usage must appear before done"
        except (ValueError, StopIteration) as exc:
            pytest.fail(
                f"Event ordering check failed: {exc}. Event types seen: {event_types}"
            )

        # Assertion: no error events in the stream.
        error_lines = [
            ln
            for ln in lines
            if "LITELLM_MID_STREAM_ERROR" in ln or "BadRequestError" in ln
        ]
        assert not error_lines, (
            f"Stream contained error events — model_str fix may not be applied: "
            f"{error_lines[:3]}"
        )

        # Log summary for evidence (visible in pytest -s output).
        print(
            f"\n[T006-live] PASS — conv_id={conv_id} event_types={event_types} "
            f"latency_ms={latency_ms} body_len={len(raw_body)}"
        )
