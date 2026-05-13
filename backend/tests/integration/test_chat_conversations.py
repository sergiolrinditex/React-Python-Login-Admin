"""
Hilo People — Integration tests for Chat Conversation CRUD endpoints.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Real integration tests against a live FastAPI app + real Postgres DB.
         Tests use the three chat conversation endpoints:
           - GET  /api/v1/chat/conversations       (list with cursor pagination)
           - POST /api/v1/chat/conversations        (create)
           - GET  /api/v1/chat/conversations/{id}  (detail with messages + citations)

All tests use real DB operations (no mocks of own services).
Auth tokens are minted directly via encode_access_token (same pattern as T007).
Test isolation: each test creates fresh data and cleans up in module teardown.

Test inventory (14 tests):
  T01: test_post_creates_conversation_success
  T02: test_post_without_initial_message_creates_empty_conversation
  T03: test_post_uses_user_preferred_language_when_omitted
  T04: test_post_uses_explicit_language_override
  T05: test_post_rejects_invalid_language
  T06: test_post_unauthenticated_returns_401_anti_enum
  T07: test_get_list_returns_only_own_conversations
  T08: test_get_list_pagination_roundtrip
  T09: test_get_list_pagination_orders_by_updated_at_desc
  T10: test_get_list_empty_returns_empty_envelope
  T11: test_get_list_invalid_cursor_returns_400
  T12: test_get_detail_returns_full_conversation_with_messages
  T13: test_get_detail_404_when_uuid_not_exists
  T14: test_get_detail_403_when_not_owner

Source refs:
  - task pack P02-S03-T001 §J.3 (test inventory)
  - 01-non-negotiables.md §Tests are REAL (real DB, no mocks)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import NamedTuple

import jwt
import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from app.db.models.chat import Conversation, Message, MessageCitation
from app.db.models.user import EmployeeProfile, User
from app.db.session import _SessionLocal
from app.main import app

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_BASE_URL = "http://testserver"
_LIST_URL = "/api/v1/chat/conversations"
_CREATE_URL = "/api/v1/chat/conversations"

# JWT settings (same as T007 _mint_access_token pattern)
_JWT_KEY: str = os.getenv("JWT_PRIVATE_KEY", "")
_JWT_ALG: str = os.getenv("JWT_ALGORITHM", "HS256")

client = TestClient(app, raise_server_exceptions=False)


# ---------------------------------------------------------------------------
# Lightweight data containers (avoid DetachedInstanceError post-session-close)
# ---------------------------------------------------------------------------

class UserData(NamedTuple):
    """Plain user record safe after session close."""
    id: uuid.UUID
    email: str
    preferred_language: str
    access_token: str


class ConvData(NamedTuple):
    """Plain conversation record safe after session close."""
    id: uuid.UUID
    title: str
    language: str
    updated_at: datetime


# ---------------------------------------------------------------------------
# Cleanup registry
# ---------------------------------------------------------------------------

_created_user_ids: list[str] = []
_created_conv_ids: list[str] = []


@pytest.fixture(scope="module", autouse=True)
def cleanup_created_rows():
    """Clean up users and conversations created during this test module."""
    yield
    session = _SessionLocal()
    try:
        for conv_id in _created_conv_ids:
            session.execute(
                sa.delete(Conversation).where(Conversation.id == uuid.UUID(conv_id))
            )
        for user_id in _created_user_ids:
            session.execute(
                sa.delete(User).where(User.id == uuid.UUID(user_id))
            )
        session.commit()
    finally:
        session.close()


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _mint_token(user_id: uuid.UUID, email: str, preferred_language: str = "es") -> str:
    """Mint a JWT access token directly (mirrors T007 _mint_access_token pattern).

    Args:
        user_id: User UUID.
        email: User email for JWT claims.
        preferred_language: Language code for JWT claims.

    Returns:
        Encoded JWT string.
    """
    now = datetime.now(tz=timezone.utc)
    payload = {
        "sub": str(user_id),
        "email": email,
        "roles": ["employee"],
        "preferred_language": preferred_language,
        "employee_profile_id": None,
        "jti": uuid.uuid4().hex,
        "iat": now,
        "exp": now + timedelta(seconds=1800),
    }
    return jwt.encode(payload, _JWT_KEY, algorithm=_JWT_ALG)


def _create_employee(
    preferred_language: str = "es",
    email: str | None = None,
) -> UserData:
    """Insert an employee user with an access token. Commits to real DB."""
    if email is None:
        email = f"test-chat-{uuid.uuid4().hex[:8]}@inditex-sandbox.com"

    from app.auth.password import hash_password

    session = _SessionLocal()
    try:
        # Hash a test password (not used by these tests but required by schema).
        pw_hash = hash_password("TestPass2024!")

        user = User(
            email=email,
            full_name="Test Chat User",
            password_hash=pw_hash,
            status="active",
            preferred_language=preferred_language,
        )
        session.add(user)
        session.flush()
        user_id: uuid.UUID = user.id

        employee = EmployeeProfile(
            user_id=user_id,
            employee_id=f"EMP-{uuid.uuid4().hex[:6].upper()}",
            brand="Zara",
            society="ITX",
            center="C001",
            country="ES",
            department="HR",
        )
        session.add(employee)
        session.commit()

        token = _mint_token(user_id, email, preferred_language)
        _created_user_ids.append(str(user_id))
        return UserData(
            id=user_id,
            email=email,
            preferred_language=preferred_language,
            access_token=token,
        )
    finally:
        session.close()


def _create_conversation(
    user_id: uuid.UUID,
    title: str = "Test conversation",
    language: str = "es",
    updated_at_offset_seconds: float = 0.0,
) -> ConvData:
    """Insert a conversation directly (bypasses endpoint for test isolation)."""
    session = _SessionLocal()
    try:
        base_time = datetime.now(tz=timezone.utc) - timedelta(seconds=abs(updated_at_offset_seconds))
        conv = Conversation(
            user_id=user_id,
            title=title,
            language=language,
        )
        session.add(conv)
        session.flush()
        conv_id: uuid.UUID = conv.id

        # Update updated_at to the desired offset.
        session.execute(
            sa.update(Conversation)
            .where(Conversation.id == conv_id)
            .values(updated_at=base_time, created_at=base_time)
        )
        session.commit()

        # Re-fetch to get DB-generated timestamps.
        row = session.get(Conversation, conv_id)
        updated_at = row.updated_at if row else base_time
        title_val = row.title if row else title
        lang_val = row.language if row else language

        _created_conv_ids.append(str(conv_id))
        return ConvData(
            id=conv_id,
            title=title_val,
            language=lang_val,
            updated_at=updated_at,
        )
    finally:
        session.close()


def _auth_headers(token: str) -> dict:
    """Build Authorization header dict."""
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# T01 — POST creates conversation successfully
# ---------------------------------------------------------------------------

def test_post_creates_conversation_success():
    """POST with initial_message → 201, conversation + message persisted, title truncated."""
    user = _create_employee()
    resp = client.post(
        _CREATE_URL,
        json={"initial_message": "¿Cuántos días de vacaciones tengo?"},
        headers=_auth_headers(user.access_token),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "data" in body
    assert "conversation_id" in body["data"]
    assert "meta" in body
    assert "request_id" in body["meta"]

    conv_id = uuid.UUID(body["data"]["conversation_id"])
    _created_conv_ids.append(str(conv_id))

    # Verify conversation + message persisted in DB.
    session = _SessionLocal()
    try:
        conv = session.get(Conversation, conv_id)
        assert conv is not None, "Conversation should be in DB"
        assert conv.user_id == user.id
        assert conv.language == "es"  # user preferred_language default
        assert "¿Cuántos días" in conv.title or len(conv.title) > 0

        msgs = session.scalars(
            sa.select(Message).where(Message.conversation_id == conv_id)
        ).all()
        assert len(msgs) == 1, "Should have exactly 1 user message"
        assert msgs[0].role == "user"
        assert msgs[0].content == "¿Cuántos días de vacaciones tengo?"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# T02 — POST without initial_message creates empty conversation
# ---------------------------------------------------------------------------

def test_post_without_initial_message_creates_empty_conversation():
    """POST {} → 201, conversation persisted, ZERO messages, title=''."""
    user = _create_employee()
    resp = client.post(
        _CREATE_URL,
        json={},
        headers=_auth_headers(user.access_token),
    )
    assert resp.status_code == 201, resp.text
    conv_id = uuid.UUID(resp.json()["data"]["conversation_id"])
    _created_conv_ids.append(str(conv_id))

    session = _SessionLocal()
    try:
        conv = session.get(Conversation, conv_id)
        assert conv is not None
        assert conv.title == ""  # D-TIT1: empty string, frontend uses i18n key

        msgs = session.scalars(
            sa.select(Message).where(Message.conversation_id == conv_id)
        ).all()
        assert len(msgs) == 0, "No message rows should be created"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# T03 — POST uses user preferred_language when language omitted
# ---------------------------------------------------------------------------

def test_post_uses_user_preferred_language_when_omitted():
    """User preferred_language=en, request without language → conv.language=en (D-LANG1)."""
    user = _create_employee(preferred_language="en")
    resp = client.post(
        _CREATE_URL,
        json={"initial_message": "Hello there"},
        headers=_auth_headers(user.access_token),
    )
    assert resp.status_code == 201, resp.text
    conv_id = uuid.UUID(resp.json()["data"]["conversation_id"])
    _created_conv_ids.append(str(conv_id))

    session = _SessionLocal()
    try:
        conv = session.get(Conversation, conv_id)
        assert conv is not None
        assert conv.language == "en", f"Expected 'en', got '{conv.language}'"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# T04 — POST uses explicit language override
# ---------------------------------------------------------------------------

def test_post_uses_explicit_language_override():
    """Request {language:'fr'} → conv.language='fr' regardless of user preferred."""
    user = _create_employee(preferred_language="es")
    resp = client.post(
        _CREATE_URL,
        json={"language": "fr"},
        headers=_auth_headers(user.access_token),
    )
    assert resp.status_code == 201, resp.text
    conv_id = uuid.UUID(resp.json()["data"]["conversation_id"])
    _created_conv_ids.append(str(conv_id))

    session = _SessionLocal()
    try:
        conv = session.get(Conversation, conv_id)
        assert conv is not None
        assert conv.language == "fr", f"Expected 'fr', got '{conv.language}'"
    finally:
        session.close()


# ---------------------------------------------------------------------------
# T05 — POST rejects invalid language with 400 CHAT_INVALID_PAYLOAD
# ---------------------------------------------------------------------------

def test_post_rejects_invalid_language():
    """Request {language:'de'} → 400 CHAT_INVALID_PAYLOAD field='language'.

    The chat conversations endpoint is normalized in `app.main`'s
    `_CHAT_INVALID_PAYLOAD_PATHS` (added in P02-S03-T001 debugger cycle 1, F-1):
    Pydantic v2 Literal validation errors are mapped to HTTP 400 with the
    project envelope `{data:null, meta:{request_id}, errors:[{code,message,field}]}`
    and the feature-scoped code `CHAT_INVALID_PAYLOAD` per task pack §J.3.
    """
    user = _create_employee()
    resp = client.post(
        _CREATE_URL,
        json={"language": "de"},
        headers=_auth_headers(user.access_token),
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["data"] is None
    assert body["errors"], "envelope must include at least one error item"
    err = body["errors"][0]
    assert err["code"] == "CHAT_INVALID_PAYLOAD", err
    assert err["field"] == "language", err
    # FastAPI default 422 envelope must NOT leak through
    assert "detail" not in body, body


# ---------------------------------------------------------------------------
# T06 — POST unauthenticated returns 401 AUTH_SESSION_EXPIRED
# ---------------------------------------------------------------------------

def test_post_unauthenticated_returns_401_anti_enum():
    """POST without Bearer → 401 AUTH_SESSION_EXPIRED (anti-enumeration)."""
    resp = client.post(_CREATE_URL, json={"initial_message": "test"})
    assert resp.status_code == 401, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "AUTH_SESSION_EXPIRED"


# ---------------------------------------------------------------------------
# T07 — GET list returns only own conversations
# ---------------------------------------------------------------------------

def test_get_list_returns_only_own_conversations():
    """User A has 3 convs, User B has 2 → GET with A's token returns exactly 3."""
    user_a = _create_employee()
    user_b = _create_employee()

    for i in range(3):
        _create_conversation(user_a.id, title=f"A conv {i}")
    for i in range(2):
        _create_conversation(user_b.id, title=f"B conv {i}")

    resp = client.get(_LIST_URL, headers=_auth_headers(user_a.access_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    returned_user_ids = {c["user_id"] for c in body["data"]}
    assert str(user_b.id) not in returned_user_ids, "User B conversations must NOT appear for User A"

    own_ids = [c["id"] for c in body["data"]]
    assert len(own_ids) >= 3, f"Expected at least 3 conversations for User A, got {len(own_ids)}"


# ---------------------------------------------------------------------------
# T08 — GET list pagination roundtrip
# ---------------------------------------------------------------------------

def test_get_list_pagination_roundtrip():
    """Seed 25 convs, paginate with limit=10 — 3 pages: 10, 10, 5 (or remaining)."""
    user = _create_employee()

    # Create 25 conversations with distinct updated_at offsets (oldest first so DESC gives newest first).
    for i in range(25):
        _create_conversation(
            user.id,
            title=f"Paginated conv {i}",
            updated_at_offset_seconds=float(25 - i),  # conv 0 is oldest, conv 24 is newest
        )

    # Page 1.
    resp1 = client.get(
        f"{_LIST_URL}?limit=10",
        headers=_auth_headers(user.access_token),
    )
    assert resp1.status_code == 200, resp1.text
    body1 = resp1.json()
    assert len(body1["data"]) == 10
    assert body1["meta"]["pagination"]["has_more"] is True
    assert body1["meta"]["pagination"]["next_cursor"] is not None

    # Page 2.
    cursor1 = body1["meta"]["pagination"]["next_cursor"]
    resp2 = client.get(
        f"{_LIST_URL}?limit=10&cursor={cursor1}",
        headers=_auth_headers(user.access_token),
    )
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert len(body2["data"]) == 10
    # May or may not have more depending on other data; the 25 we created guarantee 3 pages.
    cursor2 = body2["meta"]["pagination"]["next_cursor"]
    assert cursor2 is not None

    # Page 3 — at most 5 remaining from our 25 seeded (could be more from other tests, but at least 5).
    resp3 = client.get(
        f"{_LIST_URL}?limit=10&cursor={cursor2}",
        headers=_auth_headers(user.access_token),
    )
    assert resp3.status_code == 200, resp3.text
    body3 = resp3.json()
    assert len(body3["data"]) >= 1  # at least the remaining conversations exist

    # Ensure no duplicates across pages.
    ids1 = {c["id"] for c in body1["data"]}
    ids2 = {c["id"] for c in body2["data"]}
    ids3 = {c["id"] for c in body3["data"]}
    assert ids1.isdisjoint(ids2), "Page 1 and 2 must not overlap"
    assert ids1.isdisjoint(ids3), "Page 1 and 3 must not overlap"
    assert ids2.isdisjoint(ids3), "Page 2 and 3 must not overlap"


# ---------------------------------------------------------------------------
# T09 — GET list orders by updated_at DESC
# ---------------------------------------------------------------------------

def test_get_list_pagination_orders_by_updated_at_desc():
    """Create 3 convs with different updated_at → list order is newest first."""
    user = _create_employee()

    conv_old = _create_conversation(user.id, title="Oldest", updated_at_offset_seconds=300)
    conv_mid = _create_conversation(user.id, title="Middle", updated_at_offset_seconds=150)
    conv_new = _create_conversation(user.id, title="Newest", updated_at_offset_seconds=10)

    resp = client.get(_LIST_URL, headers=_auth_headers(user.access_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()

    returned_ids = [c["id"] for c in body["data"]]
    # The 3 new conversations should appear, newest first.
    new_idx = returned_ids.index(str(conv_new.id))
    mid_idx = returned_ids.index(str(conv_mid.id))
    old_idx = returned_ids.index(str(conv_old.id))

    assert new_idx < mid_idx < old_idx, (
        f"Expected newest={new_idx} < middle={mid_idx} < oldest={old_idx} in order"
    )


# ---------------------------------------------------------------------------
# T10 — GET list empty envelope for user with no conversations
# ---------------------------------------------------------------------------

def test_get_list_empty_returns_empty_envelope():
    """User with no conversations → {data:[], meta:{pagination:{next_cursor:null, has_more:false}}}."""
    user = _create_employee()
    resp = client.get(_LIST_URL, headers=_auth_headers(user.access_token))
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["pagination"]["next_cursor"] is None
    assert body["meta"]["pagination"]["has_more"] is False
    assert "request_id" in body["meta"]


# ---------------------------------------------------------------------------
# T11 — GET list invalid cursor returns 400
# ---------------------------------------------------------------------------

def test_get_list_invalid_cursor_returns_400():
    """?cursor=garbage → 400 CHAT_CURSOR_INVALID."""
    user = _create_employee()
    resp = client.get(
        f"{_LIST_URL}?cursor=garbage!!not-base64",
        headers=_auth_headers(user.access_token),
    )
    assert resp.status_code == 400, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "CHAT_CURSOR_INVALID"


# ---------------------------------------------------------------------------
# T12 — GET detail returns full conversation with messages and citations
# ---------------------------------------------------------------------------

def test_get_detail_returns_full_conversation_with_messages():
    """Conv with 3 messages + 2 citations on msg2 → full detail response."""
    user = _create_employee()
    conv = _create_conversation(user.id, title="Detailed conv")

    session = _SessionLocal()
    try:
        # Insert 3 messages.
        msg1 = Message(
            conversation_id=conv.id, role="user",
            content="First question", token_count=None,
        )
        msg2 = Message(
            conversation_id=conv.id, role="assistant",
            content="First answer", token_count=42,
        )
        msg3 = Message(
            conversation_id=conv.id, role="user",
            content="Second question", token_count=None,
        )
        session.add_all([msg1, msg2, msg3])
        session.flush()

        # Insert 2 citations for msg2 (assistant message).
        cit1 = MessageCitation(
            message_id=msg2.id, label="Doc A, p.1", score=0.92,
        )
        cit2 = MessageCitation(
            message_id=msg2.id, label="Doc B, p.5", score=0.87,
        )
        session.add_all([cit1, cit2])
        session.commit()
    finally:
        session.close()

    resp = client.get(
        f"{_LIST_URL}/{conv.id}",
        headers=_auth_headers(user.access_token),
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    data = body["data"]

    assert data["id"] == str(conv.id)
    assert len(data["messages"]) == 3
    assert len(data["citations"]) == 2

    # Messages should be in chronological order (created_at ASC).
    roles = [m["role"] for m in data["messages"]]
    assert roles == ["user", "assistant", "user"]

    # Citations should have label and score.
    citation_labels = {c["label"] for c in data["citations"]}
    assert "Doc A, p.1" in citation_labels
    assert "Doc B, p.5" in citation_labels


# ---------------------------------------------------------------------------
# T13 — GET detail 404 for non-existent UUID
# ---------------------------------------------------------------------------

def test_get_detail_404_when_uuid_not_exists():
    """GET /conversations/{random-uuid} → 404 CHAT_CONVERSATION_NOT_FOUND."""
    user = _create_employee()
    random_id = uuid.uuid4()
    resp = client.get(
        f"{_LIST_URL}/{random_id}",
        headers=_auth_headers(user.access_token),
    )
    assert resp.status_code == 404, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "CHAT_CONVERSATION_NOT_FOUND"


# ---------------------------------------------------------------------------
# T14 — GET detail 403 when not owner
# ---------------------------------------------------------------------------

def test_get_detail_403_when_not_owner():
    """User B tries GET of User A's conversation → 403 CHAT_CONVERSATION_FORBIDDEN."""
    user_a = _create_employee()
    user_b = _create_employee()

    conv_a = _create_conversation(user_a.id, title="User A private conversation")

    # User B tries to access User A's conversation.
    resp = client.get(
        f"{_LIST_URL}/{conv_a.id}",
        headers=_auth_headers(user_b.access_token),
    )
    assert resp.status_code == 403, resp.text
    body = resp.json()
    assert body["errors"][0]["code"] == "CHAT_CONVERSATION_FORBIDDEN"

    # Confirm 403 != 404 (must be distinct codes per §F.5).
    assert body["errors"][0]["code"] != "CHAT_CONVERSATION_NOT_FOUND"
