"""
Hilo People — UploadDocument use case for RAG document admin.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Business logic for POST /api/v1/admin/rag/documents.
         Responsibilities:
           1. Validate language against {es,en,fr}.
           2. Validate collection_id exists.
           3. Read file bytes with streaming byte counter (2-layer size cap A.1.3).
           4. Reject empty file (A.1.4).
           5. MIME sniff by magic bytes (A.1.2 — hand-rolled, no python-magic).
           6. Compute SHA-256 and check dedup (A.1.7).
           7. INSERT documents row.
           8. PUT bytes to MinIO (§E — storage-first per R8 decision).
           9. Emit audit_log (A.1.9 — on create only, not on dedup).

         R8 decision: Storage happens AFTER documents INSERT commit. On put failure,
         the document row is deleted as cleanup before re-raising (§I.11 pattern B).
         On commit failure after put, best-effort MinIO delete is called.

Key deps:
  - fastapi.UploadFile (streaming read)
  - hashlib (sha256)
  - io, zipfile (DOCX magic bytes check)
  - app.rag.documents.{repository, storage, audit, errors}
  - app.db.session (get_db_session — caller provides)

Source refs:
  - task pack P02-S06-T001 §A.1, §E (upload contract), §I (security checklist)
  - 01-non-negotiables.md §Security (mime sniff, size cap, audit)
"""

from __future__ import annotations

import hashlib
import io
import logging
import os
import time
import uuid
import zipfile

import sqlalchemy as sa
from fastapi import UploadFile
from sqlalchemy.orm import Session

from app.db.models.rag import Document
from app.rag.documents import audit, repository, storage
from app.rag.documents.errors import (
    CollectionNotFoundError,
    DocumentInvalidError,
    DocumentTooLargeError,
    StoragePutError,
)

logger = logging.getLogger("hilo.rag.documents.service_upload")
_VERBOSE: bool = os.getenv("ENABLE_VERBOSE_LOGGING", "false").lower() == "true"

_MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024
_VALID_LANGUAGES = frozenset({"es", "en", "fr"})

# ---------------------------------------------------------------------------
# MIME magic bytes sniffer (hand-rolled — avoid python-magic OS dep §K-R1)
# ---------------------------------------------------------------------------
_PDF_MAGIC = b"%PDF"
_PK_MAGIC = b"PK\x03\x04"
_DOCX_SENTINEL = "word/document.xml"


def _sniff_mime(header_bytes: bytes, all_bytes: bytes | None = None) -> str | None:
    """Return MIME type from magic bytes, or None if not supported.

    PDF detection:  first 4 bytes == b'%PDF'.
    DOCX detection: first 4 bytes == b'PK\\x03\\x04' AND zip contains
                    'word/document.xml' (standard OOXML marker).

    Args:
        header_bytes: First N bytes (≥4) already read.
        all_bytes:    Full file bytes (needed for DOCX zip check). If None,
                      only PDF is detectable without the zip check.

    Returns:
        MIME type string or None if unsupported.
    """
    if header_bytes[:4] == _PDF_MAGIC:
        return "application/pdf"
    if header_bytes[:4] == _PK_MAGIC:
        # Need full bytes to confirm DOCX vs other ZIP variants.
        target = all_bytes if all_bytes is not None else header_bytes
        try:
            zf = zipfile.ZipFile(io.BytesIO(target))
            names = zf.namelist()
            zf.close()
            if _DOCX_SENTINEL in names:
                return (
                    "application/vnd.openxmlformats-officedocument"
                    ".wordprocessingml.document"
                )
        except (zipfile.BadZipFile, Exception):
            pass
    return None


# ---------------------------------------------------------------------------
# Use case
# ---------------------------------------------------------------------------

async def upload_document(
    session: Session,
    file: UploadFile,
    title: str,
    language: str,
    collection_id: uuid.UUID,
    admin_user_id: uuid.UUID,
    content_length_header: int | None,
    request_id: str,
    client_ip: str,
    user_agent: str,
) -> tuple[Document, int]:
    """Execute the upload-document use case.

    Returns (Document, http_status) where http_status is 201 (new) or 200 (dedup).

    Args:
        session:               SQLAlchemy session (caller manages lifecycle).
        file:                  FastAPI UploadFile (streaming).
        title:                 Document title (already validated by Form).
        language:              Language code (validated here against {es,en,fr}).
        collection_id:         Target collection UUID.
        admin_user_id:         Authenticated admin UUID.
        content_length_header: Value from Content-Length header (may be None/lie).
        request_id:            X-Request-ID correlation string.
        client_ip:             Client IP for audit.
        user_agent:            User-Agent header for audit.

    Returns:
        Tuple of (Document ORM instance, HTTP status code 201 or 200).

    Raises:
        DocumentInvalidError:  Invalid language, mime, empty file.
        CollectionNotFoundError: collection_id does not exist.
        DocumentTooLargeError: File exceeds MAX_UPLOAD_MB.
        StoragePutError:       MinIO upload failure.
    """
    t_start = time.monotonic()

    if _VERBOSE:
        logger.debug(
            "rag.documents.upload.start admin_id=%s title_len=%d "
            "language=%s collection_id=%s request_id=%s",
            str(admin_user_id),
            len(title),
            language,
            str(collection_id),
            request_id,
        )  # BEFORE

    # --- A.1.5 Language validation ---
    if language not in _VALID_LANGUAGES:
        raise DocumentInvalidError(
            "language",
            f"Language '{language}' is not supported. Use one of: es, en, fr.",
        )

    # --- A.1.6 Collection existence pre-check (not relying on FK error) ---
    if not repository.collection_exists(session, collection_id):
        raise CollectionNotFoundError(str(collection_id))

    # --- A.1.3 Layer-1: Content-Length header precheck ---
    if content_length_header is not None and content_length_header > _MAX_UPLOAD_BYTES:
        raise DocumentTooLargeError(content_length_header, _MAX_UPLOAD_BYTES)

    # --- A.1.3 Layer-2: Streaming read with byte counter ---
    chunk_size = 1024 * 1024  # 1 MiB
    chunks: list[bytes] = []
    total_bytes = 0
    # Read the first chunk for magic-byte sniffing
    first_chunk = await file.read(chunk_size)
    if not first_chunk:
        # A.1.4: Empty file
        raise DocumentInvalidError("file", "File must not be empty (0 bytes).")
    total_bytes += len(first_chunk)
    chunks.append(first_chunk)

    while True:
        chunk = await file.read(chunk_size)
        if not chunk:
            break
        total_bytes += len(chunk)
        if total_bytes > _MAX_UPLOAD_BYTES:
            raise DocumentTooLargeError(total_bytes, _MAX_UPLOAD_BYTES)
        chunks.append(chunk)

    all_bytes = b"".join(chunks)

    # --- A.1.4: Explicit empty-file guard (content-length lied: 0 actual bytes) ---
    if len(all_bytes) == 0:
        raise DocumentInvalidError("file", "File must not be empty (0 bytes).")

    # --- A.1.2 MIME sniff (magic bytes — I.2) ---
    mime = _sniff_mime(all_bytes[:4], all_bytes)
    if mime is None:
        raise DocumentInvalidError(
            "file",
            "Unsupported file type. Only PDF and DOCX are accepted.",
        )

    ext = "pdf" if mime == "application/pdf" else "docx"

    # --- A.1.7 SHA-256 dedup ---
    sha256 = hashlib.sha256(all_bytes).hexdigest()
    existing = repository.find_by_sha_and_collection(session, sha256, collection_id)
    if existing is not None:
        if _VERBOSE:
            logger.debug(
                "rag.documents.upload.dedup document_id=%s sha256_prefix=%s request_id=%s",
                str(existing.id),
                sha256[:8],
                request_id,
            )
        return existing, 200

    # --- A.1.8 INSERT documents row ---
    # Source URI placeholder — will be updated after successful MinIO put.
    # Generate the document_id here so we can form the storage key.
    doc_id = uuid.uuid4()
    source_uri = f"minio://hilo-docs-dev/documents/{doc_id}/{sha256}.{ext}"

    doc = Document(
        id=doc_id,
        title=title,
        language=language,
        collection_id=collection_id,
        source_uri=source_uri,
        uploaded_by=admin_user_id,
        status="uploaded",
    )
    session.add(doc)
    session.commit()

    if _VERBOSE:
        logger.debug(
            "rag.documents.upload.db_commit.ok document_id=%s request_id=%s",
            str(doc_id),
            request_id,
        )

    # --- §E MinIO PUT (after DB commit — R8 decision: storage-last) ---
    try:
        storage.put_document(
            document_id=str(doc_id),
            sha256=sha256,
            ext=ext,
            content_type=mime,
            body=all_bytes,
            request_id=request_id,
        )
    except StoragePutError:
        # §I.11: Best-effort cleanup of the documents row on storage failure.
        # Use direct SQL DELETE to avoid ORM state issues after commit.
        try:
            session.execute(sa.delete(Document).where(Document.id == doc_id))
            session.commit()
        except Exception as _cleanup_exc:
            logger.warning(
                "rag.documents.upload.cleanup.error document_id=%s error=%s request_id=%s",
                str(doc_id),
                type(_cleanup_exc).__name__,
                request_id,
            )
            try:
                session.rollback()
            except Exception:
                pass
        raise

    # --- A.1.9 audit_log (only on create, not on dedup per R7) ---
    audit.audit_document_create(
        actor_user_id=admin_user_id,
        document_id=doc_id,
        metadata={
            "request_id": request_id,
            "ip": client_ip,
            "user_agent": user_agent[:256],
            "sha256": sha256,
            "bytes": len(all_bytes),
            "mime": mime,
            "language": language,
            "collection_id": str(collection_id),
        },
    )

    latency_ms = round((time.monotonic() - t_start) * 1000, 1)
    if _VERBOSE:
        logger.debug(
            "rag.documents.upload.ok document_id=%s sha256_prefix=%s "
            "latency_ms=%s request_id=%s",
            str(doc_id),
            sha256[:8],
            latency_ms,
            request_id,
        )  # AFTER
    else:
        logger.warning(
            "rag.documents.upload.ok document_id=%s latency_ms=%s request_id=%s",
            str(doc_id),
            latency_ms,
            request_id,
        )

    return doc, 201
