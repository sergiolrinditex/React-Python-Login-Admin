# Contract Observed — P02-S06-T001

## Endpoints verified (via TestClient hitting real FastAPI + real Postgres)

- POST /api/v1/admin/rag/documents → router_upload.py → service_upload.py → repository.py + storage.py (mock) + audit.py
- GET /api/v1/admin/rag/documents → router_list.py → service_list.py → repository.py
- POST /api/v1/admin/rag/documents/{id}/index → router_index.py → service_index.py → repository.py + chain.apply_async (mock) + audit.py

## Router / Provider / API client observed

- Router aggregator: backend/app/rag/documents/router.py (mounts sub-routers at /api/v1/admin/rag)
- Mounted in: backend/app/main.py (rag_documents_router)
- Auth: app.security.permissions.require_admin (tested: 401 no token, 403 employee role, 200/201/202 admin role)
- Rate limiter: app.security.RateLimiter (tested: T13 → 429 RAG_RATE_LIMITED after 21 calls)

## DTO / Schema observed

- DocumentOut (id, collection_id, title, language, source_uri, status, uploaded_by, created_at)
- ListResponse (data: list[DocumentOut], meta: {pagination: {cursor, limit}})
- IndexResponse (data: {job_id, status})

## Repository methods observed (real Postgres)

- collection_exists(collection_id) → bool
- find_by_sha_collection(sha256, collection_id) → Document | None
- create_document(...) → Document
- list_documents_paginated(filters, cursor, limit) → (list[Document], has_next)
- get_document_by_id(document_id) → Document | None
- find_inflight_job(document_id) → VectorizationJob | None
- create_job(document_id) → VectorizationJob
- update_document_status(document_id, status) → None

## DB tables written/read (real Postgres transactions)

- documents (INSERT, SELECT, status update)
- vectorization_jobs (INSERT, SELECT)
- audit_logs (INSERT via app.admin._audit.write_admin_ai_audit)
- rag_collections (SELECT for collection_id validation)

## Boundary mocks (acceptable third-party infrastructure)

- app.rag.documents.storage._s3_client → boto3/MinIO (worktree port conflict)
- app.rag.documents.service_index.chain → Celery broker (third-party)
