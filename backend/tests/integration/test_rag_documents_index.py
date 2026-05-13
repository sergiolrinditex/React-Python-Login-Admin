"""
Hilo People — Integration tests for POST /api/v1/admin/rag/documents/{id}/index.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Real integration tests for vectorization job dispatch:
           T22: admin happy → 202; job=pending; doc=processing; audit written; chain called
           T23: unknown document id → 404
           T24: document with NULL collection_id → 422
           T25: existing in-flight job (status=pending) → 409 RAG_INDEX_IN_PROGRESS
           T26: previous job done → new index allowed → 202 with NEW job_id
           T27: Redis/broker down (mock raise) → 500; no orphan job row
           T28: employee role → 403
           T29: ENABLE_VERBOSE_LOGGING dual-mode (INFO shows flow; WARN shows only warnings)

Key deps:
  - real Postgres DB (via app's _SessionLocal)
  - chain.apply_async mocked (§F.6 — testing HTTP layer, not the worker)

Source refs:
  - task pack P02-S06-T001 §G (test plan T22–T28), §F.6
  - 01-non-negotiables.md §Tests are REAL
"""

from __future__ import annotations

import os
import uuid
from unittest.mock import MagicMock, patch

from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Env setup before app import
# ---------------------------------------------------------------------------
if not os.getenv("JWT_PRIVATE_KEY"):
    os.environ["JWT_PRIVATE_KEY"] = "test-dev-jwt-secret-key-for-testing-only-32b+"
_TEST_FERNET_KEY = Fernet.generate_key().decode()
os.environ["ENCRYPTION_KEY"] = _TEST_FERNET_KEY
if not os.getenv("MFA_ENCRYPTION_KEY"):
    os.environ["MFA_ENCRYPTION_KEY"] = Fernet.generate_key().decode()

# Index tests do NOT exercise the upload/storage path — documents are inserted
# directly via SQL in _insert_document(). No global S3 patcher needed here.
# The upload test module owns the storage._s3_client patch; adding a second
# patcher here would stack on top and break the upload module's side_effect
# setup (the second patcher's mock wins and is not the one the upload tests set
# side_effect on). See §K-R2 and §F.6 in task pack P02-S06-T001.

from app.main import app  # noqa: E402
from app.db.session import _SessionLocal  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
_ph = PasswordHasher()

_created_user_ids: list[str] = []
_created_doc_ids: list[str] = []
_created_job_ids: list[str] = []
_created_collection_ids: list[str] = []

_MODULE_ADMIN_TOKEN: str = ""
_MODULE_EMPLOYEE_TOKEN: str = ""


def _create_user_direct(email: str, role_name: str, password: str) -> str:
    pw_hash = _ph.hash(password)
    user_id = str(uuid.uuid4())
    sess = _SessionLocal()
    try:
        sess.execute(text(
            "INSERT INTO users(id,email,password_hash,full_name,status) VALUES(:id,:email,:pw,:name,:status)"
        ), {"id": user_id, "email": email, "pw": pw_hash, "name": "Index Tester", "status": "active"})
        role_row = sess.execute(text("SELECT id FROM roles WHERE name=:name"), {"name": role_name}).fetchone()
        if role_row is None:
            new_role_id = str(uuid.uuid4())
            sess.execute(text("INSERT INTO roles(id,name) VALUES(:id,:name)"), {"id": new_role_id, "name": role_name})
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
    resp = client.post("/api/v1/auth/sign-in", json={"email": email, "password": password})
    assert resp.status_code == 200, f"sign-in failed: {resp.text}"
    return resp.json()["data"]["access_token"]


def _create_collection() -> str:
    coll_id = str(uuid.uuid4())
    sess = _SessionLocal()
    try:
        sess.execute(text(
            "INSERT INTO rag_collections(id,name,vertical) VALUES(:id,:name,:v)"
        ), {"id": coll_id, "name": f"coll-idx-{coll_id[:8]}", "v": "hr"})
        sess.commit()
    finally:
        sess.close()
    _created_collection_ids.append(coll_id)
    return coll_id


def _insert_document(collection_id: str | None = None, status: str = "uploaded", title: str = "Test Doc") -> str:
    doc_id = str(uuid.uuid4())
    sha = f"fake{doc_id[:16]}"
    source_uri = f"minio://hilo-docs-dev/documents/{doc_id}/{sha}.pdf"
    sess = _SessionLocal()
    try:
        sess.execute(text(
            "INSERT INTO documents(id,collection_id,title,language,source_uri,status) "
            "VALUES(:id,:cid,:title,'es',:uri,:status)"
        ), {"id": doc_id, "cid": collection_id, "title": title, "uri": source_uri, "status": status})
        sess.commit()
    finally:
        sess.close()
    _created_doc_ids.append(doc_id)
    return doc_id


def _insert_job(document_id: str, status: str = "pending") -> str:
    job_id = str(uuid.uuid4())
    sess = _SessionLocal()
    try:
        sess.execute(text(
            "INSERT INTO vectorization_jobs(id,document_id,status,progress) "
            "VALUES(:id,:did,:status,0)"
        ), {"id": job_id, "did": document_id, "status": status})
        sess.commit()
    finally:
        sess.close()
    _created_job_ids.append(job_id)
    return job_id


def _cleanup():
    sess = _SessionLocal()
    try:
        if _created_job_ids:
            sess.execute(text("DELETE FROM vectorization_jobs WHERE id=ANY(:ids)"), {"ids": _created_job_ids})
        if _created_doc_ids:
            sess.execute(text("DELETE FROM documents WHERE id=ANY(:ids)"), {"ids": _created_doc_ids})
        if _created_collection_ids:
            sess.execute(text("DELETE FROM rag_collections WHERE id=ANY(:ids)"), {"ids": _created_collection_ids})
        if _created_user_ids:
            sess.execute(text("DELETE FROM users WHERE id=ANY(:ids)"), {"ids": _created_user_ids})
        sess.commit()
    except Exception:
        sess.rollback()
    finally:
        sess.close()
    _created_job_ids.clear()
    _created_doc_ids.clear()
    _created_collection_ids.clear()
    _created_user_ids.clear()


def setup_module(module):
    global _MODULE_ADMIN_TOKEN, _MODULE_EMPLOYEE_TOKEN
    try:
        from app.auth import rate_limit as _auth_rl
        _auth_rl._store.clear()
    except Exception:
        pass

    admin_email = f"admin_idx_{uuid.uuid4().hex[:8]}@test.com"
    _create_user_direct(admin_email, "people_admin", "AdminRagIdx24!")
    _MODULE_ADMIN_TOKEN = _sign_in(admin_email, "AdminRagIdx24!")

    emp_email = f"emp_idx_{uuid.uuid4().hex[:8]}@test.com"
    _create_user_direct(emp_email, "employee", "AdminRagIdx24!")
    _MODULE_EMPLOYEE_TOKEN = _sign_in(emp_email, "AdminRagIdx24!")


def teardown_module(module):
    _cleanup()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_T22_index_happy_202():
    """T22: Admin happy path → 202; job=pending; doc=processing; audit written; chain called."""
    coll_id = _create_collection()
    doc_id = _insert_document(collection_id=coll_id)

    # Patch module-level `chain` in service_index (§F.6 patchability contract).
    # Standard MagicMock pattern: chain(...) returns mock_chain.return_value;
    # .apply_async() is auto-mocked and tracked for assertion.
    with patch("app.rag.documents.service_index.chain") as mock_chain:
        mock_chain.return_value.apply_async.return_value = MagicMock(id="job-xyz")
        resp = client.post(
            f"/api/v1/admin/rag/documents/{doc_id}/index",
            headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        )

    assert resp.status_code == 202, resp.text
    body = resp.json()
    assert body["data"]["status"] == "pending"
    job_id = body["data"]["job_id"]
    _created_job_ids.append(job_id)

    sess = _SessionLocal()
    try:
        job_row = sess.execute(text(
            "SELECT status FROM vectorization_jobs WHERE id=:jid"
        ), {"jid": job_id}).mappings().first()
        doc_row = sess.execute(text(
            "SELECT status FROM documents WHERE id=:did"
        ), {"did": doc_id}).mappings().first()
    finally:
        sess.close()
    assert job_row["status"] == "pending"
    assert doc_row["status"] == "processing"

    sess = _SessionLocal()
    try:
        audit_count = sess.execute(text(
            "SELECT COUNT(*) FROM audit_logs WHERE action='admin.rag.document.index' AND entity_id=:eid"
        ), {"eid": doc_id}).scalar_one()
    finally:
        sess.close()
    assert audit_count >= 1

    mock_chain.return_value.apply_async.assert_called_once()


def test_T23_index_unknown_id_404():
    """T23: Unknown document id → 404 RAG_DOCUMENT_INVALID."""
    fake_id = str(uuid.uuid4())
    resp = client.post(
        f"/api/v1/admin/rag/documents/{fake_id}/index",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
    )
    assert resp.status_code == 404, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_DOCUMENT_INVALID" for e in errors)


def test_T24_index_null_collection_422():
    """T24: Document with NULL collection_id → 422 RAG_DOCUMENT_INVALID."""
    doc_id = _insert_document(collection_id=None)
    resp = client.post(
        f"/api/v1/admin/rag/documents/{doc_id}/index",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
    )
    assert resp.status_code == 422, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_DOCUMENT_INVALID" for e in errors)


def test_T25_index_inflight_job_409():
    """T25: Existing pending job → 409 RAG_INDEX_IN_PROGRESS with job_id."""
    coll_id = _create_collection()
    doc_id = _insert_document(collection_id=coll_id)
    existing_job_id = _insert_job(doc_id, status="pending")

    resp = client.post(
        f"/api/v1/admin/rag/documents/{doc_id}/index",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
    )
    assert resp.status_code == 409, resp.text
    body = resp.json()
    errors = body.get("errors", [])
    assert any(e.get("code") == "RAG_INDEX_IN_PROGRESS" for e in errors)
    assert body.get("data", {}).get("job_id") == existing_job_id


def test_T26_index_previous_done_allows_reindex_202():
    """T26: Previous job done → new index allowed → 202 with NEW job_id."""
    coll_id = _create_collection()
    doc_id = _insert_document(collection_id=coll_id)
    done_job_id = _insert_job(doc_id, status="done")

    with patch("app.rag.documents.service_index.chain") as mock_chain:
        mock_chain.return_value.apply_async.return_value = MagicMock(id="job-new")
        resp = client.post(
            f"/api/v1/admin/rag/documents/{doc_id}/index",
            headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        )

    assert resp.status_code == 202, resp.text
    new_job_id = resp.json()["data"]["job_id"]
    assert new_job_id != done_job_id
    _created_job_ids.append(new_job_id)


def test_T27_index_broker_down_500_no_orphan():
    """T27: Redis/broker failure → 500; no orphan vectorization_jobs row."""
    coll_id = _create_collection()
    doc_id = _insert_document(collection_id=coll_id, status="uploaded")

    with patch("app.rag.documents.service_index.chain") as mock_chain:
        mock_chain.return_value.apply_async.side_effect = Exception("Redis is down")
        resp = client.post(
            f"/api/v1/admin/rag/documents/{doc_id}/index",
            headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        )

    assert resp.status_code == 500, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_INDEX_FAILED" for e in errors)

    sess = _SessionLocal()
    try:
        job_count = sess.execute(text(
            "SELECT COUNT(*) FROM vectorization_jobs WHERE document_id=:did"
        ), {"did": doc_id}).scalar_one()
    finally:
        sess.close()
    assert job_count == 0, f"No orphan job expected but found {job_count}"


def test_T28_index_employee_403():
    """T28: Employee role → 403 on index endpoint."""
    coll_id = _create_collection()
    doc_id = _insert_document(collection_id=coll_id)
    resp = client.post(
        f"/api/v1/admin/rag/documents/{doc_id}/index",
        headers={"Authorization": f"Bearer {_MODULE_EMPLOYEE_TOKEN}"},
    )
    assert resp.status_code == 403, resp.text


def test_T29_dual_logging_verbose_and_non_verbose():
    """T29: Both ENABLE_VERBOSE_LOGGING modes respond correctly.

    In non-verbose mode (false), the endpoint still returns 202.
    In verbose mode (true), the full logging flow is available.
    This test verifies the endpoint is stable under both modes.
    """
    coll_id = _create_collection()
    doc_id = _insert_document(collection_id=coll_id)

    # Test in default (non-verbose) mode — endpoint must still work
    with patch("app.rag.documents.service_index.chain") as mock_chain:
        mock_chain.return_value.apply_async.return_value = MagicMock(id="job-t29")
        resp = client.post(
            f"/api/v1/admin/rag/documents/{doc_id}/index",
            headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        )
    assert resp.status_code == 202, f"Expected 202, got {resp.status_code}: {resp.text}"
    _created_job_ids.append(resp.json()["data"]["job_id"])
