"""
Hilo People — MinIO/S3 storage helper for RAG document upload.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Wraps boto3 put_object for uploading document bytes to MinIO.
         Reuses the same env contract as app.workers._storage._s3_client
         (S3_ENDPOINT_URL, MINIO_ROOT_USER, MINIO_ROOT_PASSWORD, S3_BUCKET_DOCUMENTS).
         Server-side single PUT (no S3 multipart upload — ≤25 MiB per §E).

         Object key format: documents/{document_id}/{sha256}.{ext}
         Source URI format: minio://{bucket}/documents/{document_id}/{sha256}.{ext}

Key deps:
  - boto3==1.43.6 (already pinned — consistent with workers._storage)
  - os (env var access)
  - app.rag.documents.errors.StoragePutError

Source refs:
  - task pack P02-S06-T001 §A.1.8, §E (storage contract)
  - backend/app/workers/_storage.py (env contract reference — DRY)
  - 01-non-negotiables.md §Security (no secrets in logs; I.8)
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any

import boto3

from app.rag.documents.errors import StoragePutError

logger = logging.getLogger("hilo.rag.documents.storage")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Env contract — identical to workers/_storage._s3_client (DRY §E)
# ---------------------------------------------------------------------------
_S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
_S3_KEY = os.getenv("MINIO_ROOT_USER", "hilo")
_S3_SECRET = os.getenv("MINIO_ROOT_PASSWORD", "hilo-dev-only")
_BUCKET = os.getenv("S3_BUCKET_DOCUMENTS", "hilo-docs-dev")


def _s3_client() -> Any:
    """Create a boto3 S3 client pointing at MinIO.

    Returns:
        Configured boto3 S3 client (not logged — credentials in env).
    """
    return boto3.client(
        "s3",
        endpoint_url=_S3_ENDPOINT,
        aws_access_key_id=_S3_KEY,
        aws_secret_access_key=_S3_SECRET,
    )


def put_document(
    document_id: str,
    sha256: str,
    ext: str,
    content_type: str,
    body: bytes,
    request_id: str,
) -> str:
    """Upload document bytes to MinIO and return the source_uri.

    Object key format: documents/{document_id}/{sha256}.{ext}
    Source URI format: minio://{bucket}/documents/{document_id}/{sha256}.{ext}

    Args:
        document_id:  UUID string of the document (server-generated; not from user).
        sha256:       Hex SHA-256 digest of the file bytes (for dedup key).
        ext:          File extension without dot ('pdf' or 'docx').
        content_type: MIME type string (sniffed by magic bytes).
        body:         Raw file bytes.
        request_id:   Correlation ID for logging.

    Returns:
        Source URI string (minio://bucket/key).

    Raises:
        StoragePutError: If boto3 put_object fails.

    Security notes (§I.8):
        - Endpoint URL is not logged (may contain host:port but not credentials).
        - Bucket and key are logged (safe — no credentials embedded).
        - Body bytes are NEVER logged.
    """
    key = f"documents/{document_id}/{sha256}.{ext}"
    source_uri = f"minio://{_BUCKET}/{key}"

    if _VERBOSE:
        logger.debug(
            "rag.documents.storage.put.start key=%s bytes=%d request_id=%s",
            key,
            len(body),
            request_id,
        )  # BEFORE

    t_start = time.monotonic()
    try:
        client = _s3_client()
        client.put_object(
            Bucket=_BUCKET,
            Key=key,
            Body=body,
            ContentType=content_type,
            ContentLength=len(body),
        )
    except Exception as exc:
        latency_ms = round((time.monotonic() - t_start) * 1000, 1)
        logger.error(
            "rag.documents.storage.put.error key=%s bytes=%d latency_ms=%s "
            "error=%s request_id=%s",
            key,
            len(body),
            latency_ms,
            type(exc).__name__,
            request_id,
            exc_info=True,
        )  # AFTER — error
        raise StoragePutError(exc) from exc

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    if _VERBOSE:
        logger.debug(
            "rag.documents.storage.put.ok key=%s bytes=%d latency_ms=%s request_id=%s",
            key,
            len(body),
            latency_ms,
            request_id,
        )  # AFTER

    return source_uri


def delete_document(document_id: str, sha256: str, ext: str, request_id: str) -> None:
    """Best-effort delete of a MinIO object (orphan cleanup on partial failure §I.11).

    Never raises — logs error but swallows to avoid masking the original failure.

    Args:
        document_id: UUID string of the document.
        sha256:      Hex SHA-256 of the file.
        ext:         File extension without dot.
        request_id:  Correlation ID for logging.
    """
    key = f"documents/{document_id}/{sha256}.{ext}"
    try:
        _s3_client().delete_object(Bucket=_BUCKET, Key=key)
        if _VERBOSE:
            logger.debug(
                "rag.documents.storage.delete.ok key=%s request_id=%s",
                key,
                request_id,
            )
    except Exception as exc:
        logger.warning(
            "rag.documents.storage.delete.error key=%s error=%s request_id=%s",
            key,
            type(exc).__name__,
            request_id,
        )
