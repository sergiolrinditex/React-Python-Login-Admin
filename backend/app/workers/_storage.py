"""
Hilo People — Storage and text-extraction helpers for the vectorization worker.

Slice:  P02-S04-T002 — Celery vectorization worker
Phase:  P02 Core Features (the motor)
Purpose: Private helpers used by tasks_documents.extract_and_chunk:
           - _read_bytes: download bytes from file://, s3://, or minio:// URI.
           - _detect_mime: detect MIME type from URI extension.
           - _extract_text: extract plain text from PDF, DOCX, or plain-text bytes.
           - _get_or_create_version: create or reuse DocumentVersion by checksum.

WRITE_SET_DRIFT §D-STORAGE: Extracted from tasks_documents.py to keep that
  file within the ~300 LOC cap. Declared in handoff P02-S04-T002.md.
  Per task pack §6.3: "backend/app/workers/storage.py — if the helpers boto3
  (s3/minio/file resolver) grow > 50 LOC".

Key deps:
  - boto3==1.43.6    (S3/MinIO download)
  - pypdf==6.11.0   (PDF text extraction)
  - python-docx==1.2.0 (DOCX text extraction)
  - sqlalchemy==2.0.49 (DocumentVersion ORM)
  - os               (env var access)

Source refs:
  - task pack P02-S04-T002 §3.5, §5.2, §9 D-IDX-REUSE
"""

from __future__ import annotations

import hashlib
import io
import os
import uuid
from typing import Any

import boto3
import sqlalchemy as sa
from sqlalchemy.orm import Session

from app.db.models.rag import Document, DocumentVersion

# ---------------------------------------------------------------------------
# S3/MinIO client factory
# ---------------------------------------------------------------------------
_S3_ENDPOINT = os.getenv("S3_ENDPOINT_URL", "http://localhost:9000")
_S3_KEY = os.getenv("MINIO_ROOT_USER", "hilo")
_S3_SECRET = os.getenv("MINIO_ROOT_PASSWORD", "hilo-dev-only")


def _s3_client() -> Any:
    """Create a boto3 S3 client pointing at MinIO or real S3.

    Returns:
        boto3 S3 client configured from env vars.
    """
    return boto3.client(
        "s3",
        endpoint_url=_S3_ENDPOINT,
        aws_access_key_id=_S3_KEY,
        aws_secret_access_key=_S3_SECRET,
    )


# ---------------------------------------------------------------------------
# Storage resolver
# ---------------------------------------------------------------------------


def read_bytes(source_uri: str) -> bytes:
    """Download or read document bytes from the given URI.

    Supported schemes: file://, s3://, minio://.

    Args:
        source_uri: Document storage URI.

    Returns:
        Raw file bytes.

    Raises:
        IOError:          Unknown scheme or S3 failure.
        ConnectionError:  MinIO/S3 unreachable (triggers Celery autoretry).
    """
    if source_uri.startswith("file://"):
        with open(source_uri[len("file://"):], "rb") as fh:
            return fh.read()

    if source_uri.startswith("s3://") or source_uri.startswith("minio://"):
        without_scheme = source_uri.split("://", 1)[1]
        parts = without_scheme.split("/", 1)
        if len(parts) != 2:
            raise IOError(f"Invalid S3 URI (no key): {source_uri}")
        bucket, key = parts
        try:
            resp = _s3_client().get_object(Bucket=bucket, Key=key)
            return resp["Body"].read()
        except Exception as exc:
            raise ConnectionError(f"S3 download failed: {exc}") from exc

    raise IOError(f"Unsupported URI scheme: {source_uri}")


# ---------------------------------------------------------------------------
# MIME detection and text extraction
# ---------------------------------------------------------------------------


def detect_mime(source_uri: str) -> str:
    """Detect MIME type from URI extension.

    Returns:
        MIME type string.

    Raises:
        ValueError: Unsupported extension → maps to UnsupportedMimeType failure.
    """
    lower = source_uri.lower().split("?")[0]
    if lower.endswith(".pdf"):
        return "application/pdf"
    if lower.endswith(".docx"):
        return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    if lower.endswith(".md") or lower.endswith(".txt"):
        return "text/plain"
    ext = lower.rsplit(".", 1)[-1] if "." in lower else lower
    raise ValueError(f"UnsupportedMimeType: .{ext}")


def extract_text(raw_bytes: bytes, mime: str) -> str:
    """Extract plain text from raw document bytes.

    Args:
        raw_bytes: Raw file content.
        mime:      MIME type from detect_mime().

    Returns:
        Extracted plain text.

    Raises:
        ValueError: Unsupported MIME (triggers failed status, not retry).
    """
    if mime == "application/pdf":
        import pypdf
        reader = pypdf.PdfReader(io.BytesIO(raw_bytes))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    if mime.startswith("application/vnd.openxmlformats"):
        from docx import Document as DocxDocument
        doc = DocxDocument(io.BytesIO(raw_bytes))
        return "\n".join(p.text for p in doc.paragraphs if p.text)

    if mime == "text/plain":
        return raw_bytes.decode("utf-8", errors="replace")

    raise ValueError(f"UnsupportedMimeType: {mime}")


# ---------------------------------------------------------------------------
# Version resolution (D-IDX-REUSE)
# ---------------------------------------------------------------------------


def get_or_create_version(
    session: Session,
    document_id: uuid.UUID,
    raw_bytes: bytes,
    source_uri: str,
) -> tuple[DocumentVersion, bool]:
    """Return the matching version or create version=max+1.

    Uses FOR UPDATE to serialise concurrent re-index calls (D-IDX-REUSE).

    Args:
        session:     Active session (caller commits the INSERT if new).
        document_id: Document UUID.
        raw_bytes:   Raw file bytes (for SHA-256 checksum).
        source_uri:  Storage URI stored as version.storage_key.

    Returns:
        Tuple (DocumentVersion, created: bool).
        created=True means a new row was INSERTed (caller must commit).
    """
    checksum = hashlib.sha256(raw_bytes).hexdigest()
    session.execute(
        sa.select(Document).where(Document.id == document_id).with_for_update()
    )
    latest = session.execute(
        sa.select(DocumentVersion)
        .where(DocumentVersion.document_id == document_id)
        .order_by(DocumentVersion.version.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest is not None and latest.checksum == checksum:
        return latest, False

    next_version = (latest.version + 1) if latest is not None else 1
    new_ver = DocumentVersion(
        document_id=document_id,
        version=next_version,
        storage_key=source_uri,
        checksum=checksum,
    )
    session.add(new_ver)
    session.flush()
    return new_ver, True
