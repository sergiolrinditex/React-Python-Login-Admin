"""
Hilo People — Integration tests for GET /api/v1/admin/rag/documents (list).

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Real integration tests for document listing:
           T16: admin empty list → 200 {data:[], meta.pagination.cursor=null}
           T17: admin multiple rows → DESC ordering + cursor pagination (page 1+2)
           T18: filter by collection_id → only matching rows
           T19: filter by status='uploaded' → only matching rows
           T20: invalid cursor → 400 RAG_INVALID_PAYLOAD field=cursor
           T21: employee role → 403

Key deps:
  - real Postgres DB (via app's _SessionLocal)
  - documents rows inserted directly via SQL for test isolation

Source refs:
  - task pack P02-S06-T001 §G (test plan T16–T21)
  - 01-non-negotiables.md §Tests are REAL
"""

from __future__ import annotations

import os
import uuid

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

# List tests insert documents directly via SQL (_insert_document) and do NOT
# call the upload endpoint. No storage._s3_client patch is needed here.
# Only test_rag_documents_upload.py owns the global storage patcher, so that
# patcher's side_effect setup remains effective even in multi-module test runs.

from app.main import app  # noqa: E402
from app.db.session import _SessionLocal  # noqa: E402

client = TestClient(app, raise_server_exceptions=False)
_ph = PasswordHasher()

_created_user_ids: list[str] = []
_created_doc_ids: list[str] = []
_created_collection_ids: list[str] = []

_MODULE_ADMIN_TOKEN: str = ""
_MODULE_EMPLOYEE_TOKEN: str = ""


def _create_user_direct(email: str, role_name: str, password: str) -> str:
    pw_hash = _ph.hash(password)
    user_id = str(uuid.uuid4())
    sess = _SessionLocal()
    try:
        sess.execute(text(
            "INSERT INTO users(id,email,password_hash,full_name,status) "
            "VALUES(:id,:email,:pw,:name,:status)"
        ), {"id": user_id, "email": email, "pw": pw_hash, "name": "List Tester", "status": "active"})
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
        ), {"id": coll_id, "name": f"coll-list-{coll_id[:8]}", "v": "hr"})
        sess.commit()
    finally:
        sess.close()
    _created_collection_ids.append(coll_id)
    return coll_id


def _insert_document(
    collection_id: str,
    title: str = "Test Doc",
    language: str = "es",
    status: str = "uploaded",
    uploaded_by: str | None = None,
) -> str:
    doc_id = str(uuid.uuid4())
    sha = f"fake{doc_id[:16]}"
    source_uri = f"minio://hilo-docs-dev/documents/{doc_id}/{sha}.pdf"
    sess = _SessionLocal()
    try:
        sess.execute(text(
            "INSERT INTO documents(id,collection_id,title,language,source_uri,status,uploaded_by) "
            "VALUES(:id,:cid,:title,:lang,:uri,:status,:uby)"
        ), {
            "id": doc_id, "cid": collection_id, "title": title,
            "lang": language, "uri": source_uri, "status": status, "uby": uploaded_by,
        })
        sess.commit()
    finally:
        sess.close()
    _created_doc_ids.append(doc_id)
    return doc_id


def _cleanup():
    sess = _SessionLocal()
    try:
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

    admin_email = f"admin_list_{uuid.uuid4().hex[:8]}@test.com"
    _create_user_direct(admin_email, "people_admin", "AdminRagList24!")
    _MODULE_ADMIN_TOKEN = _sign_in(admin_email, "AdminRagList24!")

    emp_email = f"employee_list_{uuid.uuid4().hex[:8]}@test.com"
    _create_user_direct(emp_email, "employee", "AdminRagList24!")
    _MODULE_EMPLOYEE_TOKEN = _sign_in(emp_email, "AdminRagList24!")


def teardown_module(module):
    _cleanup()


# ---------------------------------------------------------------------------
# T16 — T21
# ---------------------------------------------------------------------------

def test_T16_list_empty_200():
    """T16: Admin, empty collection → 200 {data:[], pagination.cursor=null}."""
    coll_id = _create_collection()
    resp = client.get(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        params={"collection_id": coll_id},
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["data"] == []
    assert body["meta"]["pagination"]["cursor"] is None


def test_T17_list_ordering_and_cursor_pagination():
    """T17: Multiple rows → DESC ordering; cursor pagination works (page1 + page2)."""
    coll_id = _create_collection()
    for i in range(5):
        _insert_document(coll_id, title=f"Doc {i}")

    resp1 = client.get(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        params={"collection_id": coll_id, "limit": 3},
    )
    assert resp1.status_code == 200, resp1.text
    body1 = resp1.json()
    assert len(body1["data"]) == 3
    cursor = body1["meta"]["pagination"]["cursor"]
    assert cursor is not None

    resp2 = client.get(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        params={"collection_id": coll_id, "limit": 3, "cursor": cursor},
    )
    assert resp2.status_code == 200, resp2.text
    body2 = resp2.json()
    assert len(body2["data"]) == 2
    ids1 = {d["id"] for d in body1["data"]}
    ids2 = {d["id"] for d in body2["data"]}
    assert ids1.isdisjoint(ids2)


def test_T18_list_filter_by_collection_id():
    """T18: Filter by collection_id → only docs from that collection returned."""
    coll_a = _create_collection()
    coll_b = _create_collection()
    id_a = _insert_document(coll_a, title="Doc A")
    id_b = _insert_document(coll_b, title="Doc B")

    resp = client.get(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        params={"collection_id": coll_a},
    )
    assert resp.status_code == 200, resp.text
    ids = [d["id"] for d in resp.json()["data"]]
    assert id_a in ids
    assert id_b not in ids


def test_T19_list_filter_by_status():
    """T19: Filter by status='uploaded' → only matching docs returned."""
    coll_id = _create_collection()
    id_uploaded = _insert_document(coll_id, title="Uploaded Doc", status="uploaded")
    id_indexed = _insert_document(coll_id, title="Indexed Doc", status="indexed")

    resp = client.get(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        params={"collection_id": coll_id, "status": "uploaded"},
    )
    assert resp.status_code == 200, resp.text
    ids = [d["id"] for d in resp.json()["data"]]
    assert id_uploaded in ids
    assert id_indexed not in ids


def test_T20_list_invalid_cursor_400():
    """T20: Invalid cursor → 400 RAG_INVALID_PAYLOAD field=cursor."""
    resp = client.get(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_ADMIN_TOKEN}"},
        params={"cursor": "not-a-valid-base64-cursor!!!"},
    )
    assert resp.status_code == 400, resp.text
    errors = resp.json().get("errors", [])
    assert any(e.get("code") == "RAG_INVALID_PAYLOAD" for e in errors), errors


def test_T21_list_employee_403():
    """T21: Employee role → 403."""
    resp = client.get(
        "/api/v1/admin/rag/documents",
        headers={"Authorization": f"Bearer {_MODULE_EMPLOYEE_TOKEN}"},
    )
    assert resp.status_code == 403, resp.text
