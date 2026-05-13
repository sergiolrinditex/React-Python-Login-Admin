"""
Hilo People — Integration tests for POST /api/v1/admin/rag/documents (upload).

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Real integration tests for document upload:
           T01: no token → 401
           T02: employee role → 403
           T03: admin happy PDF → 201, sha256 in source_uri, audit row, status='uploaded'
           T04: admin happy DOCX → 201 same shape
           T05: same bytes same collection_id twice → 200 dedup
           T06: file > 25 MiB → 413 RAG_DOCUMENT_TOO_LARGE
           T07: empty file (0 bytes) → 422 RAG_DOCUMENT_INVALID
           T08: bad MIME (txt bytes with .pdf extension) → 422 RAG_DOCUMENT_INVALID
           T09: missing language → 422
           T10: invalid language='de' → 422 RAG_DOCUMENT_INVALID
           T11: missing collection_id → 422
           T12: non-existent collection_id → 422 RAG_DOCUMENT_INVALID
           T13: rate limit (21 calls/min) → 429 RAG_RATE_LIMITED
           T14: MinIO put_object raises → 500; no orphan DB row
           T15: X-Request-ID propagated to audit + response header

         MinIO: boundary mock via monkeypatch on storage._s3_client (acceptable
         per §K-R2, §E). Real MinIO is exercised by /verify-slice.

Key deps:
  - real Postgres DB (via app's _SessionLocal)
  - real Redis (rate-limit tests T13)
  - MinIO boundary mock for all upload tests

Source refs:
  - task pack P02-S06-T001 §G (test plan T01–T15)
  - 01-non-negotiables.md §Tests are REAL
"""

from __future__ import annotations

import io
import os
import uuid
import zipfile
from unittest.mock import MagicMock, patch

import pytest
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Set required env vars BEFORE importing app modules
# ---------------------------------------------------------------------------
if not os.getenv("JWT_PRIVATE_KEY"):
    os.environ["JWT_PRIVATE_KEY"] = "test-dev-jwt-secret-key-for-testing-only-32b+"

_TEST_FERNET_KEY = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY"] = _TEST_FERNET_KEY
if not os.getenv("MFA_ENCRYPTION_KEY"):
    os.environ["MFA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

# Patch MinIO globally so tests pass without a live MinIO instance.
# Real MinIO is exercised by /verify-slice (§K-R2).
_mock_s3 = MagicMock()
_mock_s3.return_value.put_object.return_value = {}
_mock_s3.return_value.delete_object.return_value = {}
_S3_PATCHER = patch("app.rag.documents.storage._s3_client", _mock_s3)
_S3_PATCHER.start()

from app.main import app  # noqa: E402
from app.db.session import _SessionLocal  # noqa: E402

# ---------------------------------------------------------------------------
# TestClient
# ---------------------------------------------------------------------------
client = TestClient(app, raise_server_exceptions=False)

_ph = PasswordHasher()

# Track created rows for cleanup
_created_user_ids: list[str] = []
_created_doc_ids: list[str] = []
_created_collection_ids: list[str] = []

# Module-level shared admin/employee users (created once at setup_module)
_MODULE_ADMIN_EMAIL: str = ""
_MODULE_ADMIN_TOKEN: str = ""
_MODULE_ADMIN_ID: str = ""
_MODULE_EMPLOYEE_EMAIL: str = ""
_MODULE_EMPLOYEE_TOKEN: str = ""
_MODULE_EMPLOYEE_ID: str = ""


def _create_user_direct(email: str, role_name: str, password: str) -> str:
    """Create a user + role in DB and return user_id. Does NOT call sign-in."""
    pw_hash = _ph.hash(password)
    user_id = str(uuid.uuid4())
    sess = _SessionLocal()
    try:
        sess.execute(text(
            "INSERT INTO users(id, email, password_hash, full_name, status) "
            "VALUES(:id, :email, :pw, :name, :status)"
        ), {"id": user_id, "email": email, "pw": pw_hash, "name": "Test User", "status": "active"})
        role_row = sess.execute(text("SELECT id FROM roles WHERE name=:name"), {"name": role_name}).fetchone()
        if role_row is None:
            new_role_id = str(uuid.uuid4())
            sess.execute(text("INSERT INTO roles(id, name) VALUES(:id,:name)"), {"id": new_role_id, "name": role_name})
            role_id = new_role_id
        else:
            role_id = str(role_row[0])
        sess.execute(text("INSERT INTO user_roles(user_id,role_id) VALUES(:uid,:rid) ON CONFLICT DO NOTHING"),
                     {"uid": user_id, "rid": role_id})
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()
    _created_user_ids.append(user_id)
    return user_id


def _sign_in(email: str, password: str) -> str:
    """Sign in and return access_token. Asserts 200."""
    resp = client.post("/api/v1/auth/sign-in", json={"email": email, "password": password})
    assert resp.status_code == 200, f"sign-in failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _create_collection() -> str:
    """Insert a rag_collection row and return its UUID string."""
    coll_id = str(uuid.uuid4())
    sess = _SessionLocal()
    try:
        sess.execute(text(
            "INSERT INTO rag_collections(id, name, vertical) VALUES(:id, :name, :v)"
        ), {"id": coll_id, "name": f"coll-{coll_id[:8]}", "v": "hr"})
        sess.commit()
    finally:
        sess.close()
    _created_collection_ids.append(coll_id)
    return coll_id


def _reset_rate_limits():
    """Flush all RAG_DOC_CREATE and RAG_DOC_INDEX rate-limit keys from Redis."""
    try:
        from app.security._redis_client import get_redis_client
        rc = get_redis_client()
        for key in rc.scan_iter("RAG_DOC_CREATE:*"):
            rc.delete(key)
        for key in rc.scan_iter("RAG_DOC_INDEX:*"):
            rc.delete(key)
    except Exception:
        pass
    # Reset auth module in-memory rate limiter (sign-in)
    try:
        from app.auth import rate_limit as _auth_rl
        _auth_rl._store.clear()
    except Exception:
        pass


def _cleanup():
    sess = _SessionLocal()
    try:
        if _created_doc_ids:
            sess.execute(text("DELETE FROM documents WHERE id = ANY(:ids)"), {"ids": _created_doc_ids})
        if _created_collection_ids:
            sess.execute(text("DELETE FROM rag_collections WHERE id = ANY(:ids)"), {"ids": _created_collection_ids})
        if _created_user_ids:
            sess.execute(text("DELETE FROM users WHERE id = ANY(:ids)"), {"ids": _created_user_ids})
        sess.commit()
    except Exception:
        sess.rollback()
    finally:
        sess.close()
    _created_doc_ids.clear()
    _created_collection_ids.clear()
    _created_user_ids.clear()


def _minimal_pdf() -> bytes:
    """Return minimal valid-magic-bytes PDF."""
    return b"%PDF-1.4\n%minimal-test-document\n1 0 obj\n<< /Type /Catalog >>\nendobj\n%%EOF"


def _minimal_docx() -> bytes:
    """Return minimal DOCX (ZIP containing word/document.xml)."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", '<?xml version="1.0"?><w:document/>')
        zf.writestr("[Content_Types].xml", '<?xml version="1.0"?><Types/>')
    return buf.getvalue()


# ---------------------------------------------------------------------------
# Module-level setup/teardown
# ---------------------------------------------------------------------------

def setup_module(module):
    """Create module-level admin + employee users once, sign in to get tokens."""
    global _MODULE_ADMIN_EMAIL, _MODULE_ADMIN_TOKEN, _MODULE_ADMIN_ID
    global _MODULE_EMPLOYEE_EMAIL, _MODULE_EMPLOYEE_TOKEN, _MODULE_EMPLOYEE_ID

    _reset_rate_limits()

    _MODULE_ADMIN_EMAIL = f"admin_module_{uuid.uuid4().hex[:8]}@test.com"
    _MODULE_ADMIN_ID = _create_user_direct(_MODULE_ADMIN_EMAIL, "people_admin", "AdminRag2024!")
    _MODULE_ADMIN_TOKEN = _sign_in(_MODULE_ADMIN_EMAIL, "AdminRag2024!")

    _MODULE_EMPLOYEE_EMAIL = f"employee_module_{uuid.uuid4().hex[:8]}@test.com"
    _MODULE_EMPLOYEE_ID = _create_user_direct(_MODULE_EMPLOYEE_EMAIL, "employee", "AdminRag2024!")
    _MODULE_EMPLOYEE_TOKEN = _sign_in(_MODULE_EMPLOYEE_EMAIL, "AdminRag2024!")


def teardown_module(module):
    _cleanup()
    _S3_PATCHER.stop()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_T01_upload_no_token_401():
    """T01: No auth token → 401."""
    coll_id = _create_collection()
    resp = client.post(
        "/api/v1/admin/rag/documents",
        files={"file": ("test.pdf", _minimal_pdf(), "application/pdf")},
        data={"title": "T01", "language": "es", "collection_id": coll_id},
    )
    assert resp.status_code == 401, resp.text


def test_T02_upload_employee_role_403():
    """T02: Employee role → 403."""
    coll_id = _create_collection()
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_EMPLOYEE_TOKEN}"},
        files={"file": ("test.pdf", _minimal_pdf(), "application/pdf")},
        data={"title": "T02", "language": "es", "collection_id": coll_id},
    )
    assert resp.status_code == 403, resp.text


def test_T03_upload_admin_happy_pdf_201():
    """T03: Admin uploads valid PDF → 201, sha256 in source_uri, status='uploaded'."""
    _reset_rate_limits()
    import hashlib
    coll_id = _create_collection()
    pdf_bytes = _minimal_pdf()
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("policy.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Política de vacaciones", "language": "es", "collection_id": coll_id},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert "data" in body
    doc = body["data"]
    assert doc["status"] == "uploaded"
    assert doc["language"] == "es"
    assert "minio://" in doc["source_uri"]
    sha256 = hashlib.sha256(pdf_bytes).hexdigest()
    assert sha256 in doc["source_uri"]
    assert "x-request-id" in resp.headers
    _created_doc_ids.append(doc["id"])

    # Audit row written
    sess = _SessionLocal()
    try:
        audit_count = sess.execute(text(
            "SELECT COUNT(*) FROM audit_logs "
            "WHERE action='admin.rag.document.create' AND entity_id=:eid"
        ), {"eid": doc["id"]}).scalar_one()
    finally:
        sess.close()
    assert audit_count >= 1, "Audit row should have been written"


def test_T04_upload_admin_happy_docx_201():
    """T04: Admin uploads valid DOCX → 201."""
    _reset_rate_limits()
    coll_id = _create_collection()
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("guide.docx", _minimal_docx(),
                        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        data={"title": "Employment Guide", "language": "en", "collection_id": coll_id},
    )
    assert resp.status_code == 201, resp.text
    doc = resp.json()["data"]
    assert doc["status"] == "uploaded"
    _created_doc_ids.append(doc["id"])


def test_T05_upload_dedup_same_bytes_same_collection_200():
    """T05: Same bytes + same collection_id → 200 with same doc id."""
    _reset_rate_limits()
    coll_id = _create_collection()
    pdf_bytes = b"%PDF-1.4\n%dedup-test-unique-bytes-T05\n%%EOF"

    resp1 = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("dedup.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Dedup Doc", "language": "es", "collection_id": coll_id},
    )
    assert resp1.status_code == 201, resp1.text
    doc_id_1 = resp1.json()["data"]["id"]
    _created_doc_ids.append(doc_id_1)

    resp2 = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("dedup.pdf", pdf_bytes, "application/pdf")},
        data={"title": "Dedup Doc Again", "language": "es", "collection_id": coll_id},
    )
    assert resp2.status_code == 200, resp2.text
    doc_id_2 = resp2.json()["data"]["id"]
    assert doc_id_1 == doc_id_2, "Dedup must return the SAME document id"


def test_T06_upload_file_too_large_413():
    """T06: File > 25 MiB → 413 RAG_DOCUMENT_TOO_LARGE."""
    _reset_rate_limits()
    coll_id = _create_collection()
    big_pdf = b"%PDF-1.4\n" + b"A" * (26 * 1024 * 1024)
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={
            "Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}",
            "Content-Length": str(len(big_pdf) + 1000),
        },
        files={"file": ("big.pdf", big_pdf, "application/pdf")},
        data={"title": "Big File", "language": "es", "collection_id": coll_id},
    )
    assert resp.status_code == 413, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_DOCUMENT_TOO_LARGE" for e in errors)


def test_T07_upload_empty_file_422():
    """T07: Empty file (0 bytes) → 422 RAG_DOCUMENT_INVALID."""
    _reset_rate_limits()
    coll_id = _create_collection()
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("empty.pdf", b"", "application/pdf")},
        data={"title": "Empty", "language": "es", "collection_id": coll_id},
    )
    assert resp.status_code == 422, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_DOCUMENT_INVALID" for e in errors)


def test_T08_upload_bad_mime_422():
    """T08: txt bytes with .pdf extension → 422 (magic bytes check)."""
    _reset_rate_limits()
    coll_id = _create_collection()
    txt_bytes = b"This is plain text content, not a PDF at all."
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("fake.pdf", txt_bytes, "application/pdf")},
        data={"title": "Fake PDF", "language": "es", "collection_id": coll_id},
    )
    assert resp.status_code == 422, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_DOCUMENT_INVALID" for e in errors)


def test_T09_upload_missing_language_422():
    """T09: Missing language field → 422."""
    _reset_rate_limits()
    coll_id = _create_collection()
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("doc.pdf", _minimal_pdf(), "application/pdf")},
        data={"title": "No Lang", "collection_id": coll_id},
    )
    assert resp.status_code == 422, resp.text


def test_T10_upload_invalid_language_422():
    """T10: language='de' (unsupported) → 422 RAG_DOCUMENT_INVALID."""
    _reset_rate_limits()
    coll_id = _create_collection()
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("doc.pdf", _minimal_pdf(), "application/pdf")},
        data={"title": "Bad Lang", "language": "de", "collection_id": coll_id},
    )
    assert resp.status_code == 422, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_DOCUMENT_INVALID" for e in errors)


def test_T11_upload_missing_collection_id_422():
    """T11: Missing collection_id → 422."""
    _reset_rate_limits()
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("doc.pdf", _minimal_pdf(), "application/pdf")},
        data={"title": "No Coll", "language": "es"},
    )
    assert resp.status_code == 422, resp.text


def test_T12_upload_nonexistent_collection_422():
    """T12: Non-existent collection_id → 422 RAG_DOCUMENT_INVALID (pre-validated)."""
    _reset_rate_limits()
    fake_coll_id = str(uuid.uuid4())
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        files={"file": ("doc.pdf", _minimal_pdf(), "application/pdf")},
        data={"title": "Ghost Coll", "language": "es", "collection_id": fake_coll_id},
    )
    assert resp.status_code == 422, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_DOCUMENT_INVALID" for e in errors)


def test_T13_upload_rate_limit_429():
    """T13: 21 calls/min burst=5 → 429 RAG_RATE_LIMITED."""
    _reset_rate_limits()
    coll_id = _create_collection()

    last_status = None
    for i in range(21):
        resp = client.post(
            "/api/v1/admin/rag/documents",
            headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
            files={"file": (f"doc{i}.pdf", _minimal_pdf(), "application/pdf")},
            data={"title": f"T13 doc {i}", "language": "es", "collection_id": coll_id},
        )
        last_status = resp.status_code
        if resp.status_code == 429:
            errors = resp.json().get("errors", [])
            assert any(e.get("code") in ("RAG_RATE_LIMITED", "RATE_LIMITED") for e in errors)
            break
    else:
        pytest.fail(f"Expected 429 after 21 requests; last was {last_status}")
    _reset_rate_limits()


def test_T14_upload_minio_failure_500_no_orphan():
    """T14: MinIO put_object raises → 500; no orphan document row."""
    _reset_rate_limits()
    import hashlib
    coll_id = _create_collection()

    _mock_s3.return_value.put_object.side_effect = Exception("MinIO is down")
    try:
        pdf_bytes = b"%PDF-1.4\n%unique-T14-bytes\n%%EOF"
        resp = client.post(
            "/api/v1/admin/rag/documents",
            headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
            files={"file": ("fail.pdf", pdf_bytes, "application/pdf")},
            data={"title": "Storage Fail", "language": "es", "collection_id": coll_id},
        )
        assert resp.status_code == 500, resp.text
        errors = resp.json().get("errors", [])
        assert any(e.get("code") == "RAG_STORAGE_FAILED" for e in errors)
        # Scope the orphan check to this test's collection_id to avoid counting
        # leftover rows from previous test runs with the same sha256 hash.
        sha256 = hashlib.sha256(pdf_bytes).hexdigest()
        sess = _SessionLocal()
        try:
            count = sess.execute(text(
                "SELECT COUNT(*) FROM documents "
                "WHERE source_uri LIKE :pat AND collection_id=:cid"
            ), {"pat": f"%{sha256}%", "cid": coll_id}).scalar_one()
        finally:
            sess.close()
        assert count == 0, f"Orphan document row found in collection {coll_id} (count={count})"
    finally:
        _mock_s3.return_value.put_object.side_effect = None


def test_T15_x_request_id_propagated():
    """T15: X-Request-ID propagated to response header and audit metadata."""
    _reset_rate_limits()
    coll_id = _create_collection()
    custom_rid = f"test-rid-{uuid.uuid4().hex[:12]}"
    resp = client.post(
        "/api/v1/admin/rag/documents",
        headers={
            "Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}",
            "X-Request-ID": custom_rid,
        },
        files={"file": ("t15.pdf", _minimal_pdf(), "application/pdf")},
        data={"title": "T15 RequestID", "language": "fr", "collection_id": coll_id},
    )
    assert resp.status_code == 201, resp.text
    assert resp.headers.get("x-request-id") == custom_rid
    doc_id = resp.json()["data"]["id"]
    _created_doc_ids.append(doc_id)

    sess = _SessionLocal()
    try:
        row = sess.execute(text(
            "SELECT metadata FROM audit_logs "
            "WHERE action='admin.rag.document.create' AND entity_id=:eid LIMIT 1"
        ), {"eid": doc_id}).mappings().first()
    finally:
        sess.close()
    assert row is not None
    meta = row["metadata"] if isinstance(row["metadata"], dict) else {}
    assert meta.get("request_id") == custom_rid
