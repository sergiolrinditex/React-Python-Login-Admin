"""
Hilo People — Pydantic v2 schemas for RAG document admin endpoints.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Request/response schemas for POST /documents, GET /documents,
         POST /documents/{id}/index. Follows the {data, meta, errors} envelope
         contract (TECHNICAL_GUIDE §6.2).

Key deps:
  - pydantic v2 (BaseModel, Field)
  - fastapi (Form, UploadFile) — only in DocumentUploadForm

Source refs:
  - task pack P02-S06-T001 §B (endpoint contracts, frozen)
  - TECHNICAL_GUIDE §6.2 (envelope contract)
  - 01-non-negotiables.md §API contract
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from fastapi import Form
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Upload form (multipart/form-data) — declared as a class so FastAPI's
# dependency injection can bind Form() fields alongside UploadFile.
# ---------------------------------------------------------------------------
_VALID_LANGUAGES = {"es", "en", "fr"}


class DocumentUploadForm:
    """FastAPI Form-dependency class for multipart/form-data upload.

    FastAPI resolves Form() fields from the request; consumers inject it via
    Depends(DocumentUploadForm). UploadFile is declared separately in the
    route signature so FastAPI can apply async streaming logic.

    Attributes:
        title:         Document title (1–512 chars, required).
        language:      Document language ('es', 'en', 'fr').
        collection_id: Target RAG collection UUID.
    """

    def __init__(
        self,
        title: str = Form(..., min_length=1, max_length=512),
        language: str = Form(...),
        collection_id: uuid.UUID = Form(...),
    ) -> None:
        self.title = title
        self.language = language
        self.collection_id = collection_id


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------

class DocumentOut(BaseModel):
    """Document output schema — shape returned by POST /documents and GET /documents.

    Matches documents table columns (§C).

    Attributes:
        id:            Document UUID.
        collection_id: Parent collection UUID (nullable — orphaned doc).
        title:         Document title.
        language:      Language code (es/en/fr).
        source_uri:    MinIO URI (minio://bucket/key).
        status:        Processing status.
        uploaded_by:   Admin user ID (nullable).
        created_at:    UTC creation timestamp.
    """

    model_config = {"from_attributes": True}

    id: uuid.UUID
    collection_id: uuid.UUID | None
    title: str
    language: str
    source_uri: str
    status: str
    uploaded_by: uuid.UUID | None
    created_at: datetime


class PaginationMeta(BaseModel):
    """Pagination meta block returned by GET /documents.

    Attributes:
        cursor: Opaque cursor for the next page; null on last page.
        limit:  Page size that was applied.
    """

    cursor: str | None = None
    limit: int


class ResponseMeta(BaseModel):
    """Top-level response meta with optional pagination.

    Attributes:
        pagination: Cursor pagination block (present on list responses).
        request_id: Correlation ID from X-Request-ID header.
    """

    pagination: PaginationMeta | None = None
    request_id: str | None = None


class DocumentListResponse(BaseModel):
    """Response envelope for GET /api/v1/admin/rag/documents.

    Attributes:
        data: List of document records.
        meta: Pagination metadata.
    """

    data: list[DocumentOut]
    meta: ResponseMeta


class DocumentCreateResponse(BaseModel):
    """Response envelope for POST /api/v1/admin/rag/documents (201 or 200 dedup).

    Attributes:
        data: The created or existing document record.
    """

    data: DocumentOut


class IndexJobOut(BaseModel):
    """Job output schema returned by POST /documents/{id}/index.

    Attributes:
        job_id: UUID of the vectorization_jobs row.
        status: Initial job status ('pending').
    """

    job_id: uuid.UUID
    status: str


class IndexJobResponse(BaseModel):
    """Response envelope for POST /api/v1/admin/rag/documents/{id}/index.

    Attributes:
        data: The vectorization job reference.
    """

    data: IndexJobOut


class ErrorItem(BaseModel):
    """Single error item inside the errors array.

    Attributes:
        code:    Machine-readable error code.
        message: Human-readable description.
        field:   Offending request field (optional).
        details: Additional details dict (optional).
    """

    code: str
    message: str
    field: str | None = None
    details: dict[str, Any] | None = None


class ErrorEnvelope(BaseModel):
    """Standard error response envelope.

    Attributes:
        errors: List of error items.
    """

    errors: list[ErrorItem]
