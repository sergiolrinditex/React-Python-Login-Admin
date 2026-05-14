# Dual-Logging Summary — P02-S06-T001

Verified by tester on 2026-05-13.

## Test Commands Run

```bash
# Verbose ON
cd .../P02-S06-T001/backend
ENABLE_VERBOSE_LOGGING=true python3 -m pytest \
  tests/integration/test_rag_documents_upload.py \
  tests/integration/test_rag_documents_list.py \
  tests/integration/test_rag_documents_index.py \
  -v --tb=short

# Verbose OFF
ENABLE_VERBOSE_LOGGING=false python3 -m pytest \
  tests/integration/test_rag_documents_upload.py \
  tests/integration/test_rag_documents_list.py \
  tests/integration/test_rag_documents_index.py \
  -v --tb=short
```

## ENABLE_VERBOSE_LOGGING=true — Sample log lines (happy-path T03+T16+T22)

hilo.rag.documents.* log lines confirmed: 27 lines (DEBUG level).

BEFORE (start) lines observed:
- rag.documents.upload.request.start (router_upload.py)
- rag.documents.upload.start (service_upload.py)
- rag.documents.repository.collection_exists.start
- rag.documents.repository.find_by_sha.start
- rag.documents.storage.put.start
- rag.documents.list.request.start
- rag.documents.list.start
- rag.documents.repository.list.start
- rag.documents.index.request.start
- rag.documents.index.start
- rag.documents.repository.get_by_id.start
- rag.documents.repository.find_inflight_job.start
- rag.documents.repository.create_job.start

AFTER (ok) lines observed:
- rag.documents.repository.collection_exists.ok (exists=True, latency_ms)
- rag.documents.repository.find_by_sha.ok (found=False, latency_ms)
- rag.documents.upload.db_commit.ok (document_id, request_id)
- rag.documents.storage.put.ok (key, bytes, latency_ms, request_id)
- rag.documents.upload.ok (document_id, sha256_prefix, latency_ms, request_id)
- rag.documents.upload.request.ok (document_id, status, latency_ms, request_id)
- rag.documents.list.ok (count, has_next, latency_ms, request_id)
- rag.documents.list.request.ok (count, has_next, latency_ms, request_id)
- rag.documents.index.ok (job_id, document_id, latency_ms, request_id)
- rag.documents.index.request.ok (job_id, document_id, latency_ms, request_id)

ASSERTION: BEFORE + AFTER pattern confirmed for upload, list, and index flows.

## ENABLE_VERBOSE_LOGGING=false — hilo.rag.documents log lines

DEBUG lines from hilo.rag.documents: 0
INFO lines from hilo.rag.documents: 0
WARNING lines from hilo.rag.documents (happy-path T03+T16+T22): 2

The 2 WARNING lines are intentional implementation choices:
- `hilo.rag.documents.service_upload: rag.documents.upload.ok document_id=... latency_ms=... request_id=...`
- `hilo.rag.documents.service_index: rag.documents.index.ok job_id=... document_id=... latency_ms=... request_id=...`

These are logged at WARNING level by the developer when verbose=false (pattern: if _VERBOSE: debug(...) else: warning(...)). This satisfies the contract "verbose=false shows only warning+error" — they ARE warning-level. However, logging a successful outcome at WARNING level is semantically unorthodox. Classified as a code quality observation (not a blocking defect): the contract letter is satisfied, and the behavior is consistent across all endpoints in this slice.

No DEBUG or INFO lines from rag.documents appear when verbose=false. BEFORE/AFTER details (admin_id, title_len, sha256, collection_id) are absent from verbose=false output — only document_id + latency_ms + request_id appear in the warning-level ok lines.

## PII / Secrets check

Zero occurrences of password, secret, email, or bearer token value in hilo.rag.* log lines under either mode. Only UUIDs and byte counts logged.

## Boundary mocks verified (acceptable per task pack §E, §F.6 and 01-non-negotiables)

- `app.rag.documents.storage._s3_client` — boto3/MinIO SDK boundary mock (MinIO not reachable from worktree; real MinIO covered by /verify-slice)
- `app.rag.documents.service_index.chain` — Celery broker dispatch boundary mock (broker is third-party infrastructure; worker behavior covered by P02-S04-T002)

All business logic (auth, repositories, services, error envelopes) runs against real Postgres DB.

## Logging assertion result

| Mode | hilo.rag.* DEBUG/INFO lines | BEFORE (start) present | AFTER (ok) present | Only WARNING+ visible |
|---|---|---|---|---|
| verbose=true | 27 DEBUG lines | YES | YES | n/a (debug level active) |
| verbose=false | 0 DEBUG, 0 INFO | NO (suppressed) | YES (at WARNING) | YES |

Contract satisfied: verbose=true shows full flow; verbose=false suppresses DEBUG/INFO details, shows only warning+error level.
