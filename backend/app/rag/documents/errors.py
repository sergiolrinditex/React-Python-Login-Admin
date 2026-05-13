"""
Hilo People — Typed domain errors for RAG document admin endpoints.

Slice:  P02-S06-T001 — RAG document admin endpoints
Phase:  P02 Core Features (the motor)
Purpose: Defines all typed exceptions raised by the RAG document upload/list/index
         flow. Callers catch typed errors and map them to HTTP error envelopes.
         This module has NO external dependencies (importable from domain layer).

Key deps: none (domain layer — no FastAPI, no DB)

Source refs:
  - task pack P02-S06-T001 §D-RAGDOCS-PKG
  - 01-non-negotiables.md §Error handling (typed domain errors, never catch generic)
"""

from __future__ import annotations


class RagDocumentError(Exception):
    """Base class for all RAG document domain errors."""


class DocumentTooLargeError(RagDocumentError):
    """File exceeds the configured MAX_UPLOAD_MB limit (A.1.3).

    Attributes:
        size_bytes: Actual file size in bytes.
        max_bytes:  Configured limit in bytes.
    """

    def __init__(self, size_bytes: int, max_bytes: int) -> None:
        self.size_bytes = size_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"File size {size_bytes} bytes exceeds limit {max_bytes} bytes."
        )


class DocumentInvalidError(RagDocumentError):
    """File or payload is invalid (wrong MIME, empty file, bad field).

    Attributes:
        field:   The offending field name (e.g. 'file', 'language', 'collection_id').
        reason:  Human-readable explanation.
    """

    def __init__(self, field: str, reason: str) -> None:
        self.field = field
        self.reason = reason
        super().__init__(f"Invalid document field '{field}': {reason}")


class CollectionNotFoundError(RagDocumentError):
    """The referenced collection_id does not exist in rag_collections (A.1.6).

    Attributes:
        collection_id: The UUID that was not found.
    """

    def __init__(self, collection_id: str) -> None:
        self.collection_id = collection_id
        super().__init__(f"Collection {collection_id} not found.")


class IndexInProgressError(RagDocumentError):
    """A vectorization job for this document is already pending/running (A.3.3).

    Attributes:
        job_id: UUID of the existing in-flight job.
        status: Current job status ('pending' or 'running').
    """

    def __init__(self, job_id: str, status: str) -> None:
        self.job_id = job_id
        self.status = status
        super().__init__(
            f"Job {job_id} is already {status} for this document."
        )


class IndexDispatchError(RagDocumentError):
    """Celery/Redis dispatch failed — broker is unavailable (A.3.4, F.8).

    Attributes:
        cause: The underlying exception that triggered the failure.
    """

    def __init__(self, cause: Exception) -> None:
        self.cause = cause
        super().__init__(f"Index dispatch failed: {cause}")


class StoragePutError(RagDocumentError):
    """MinIO put_object failed (§E — storage boundary error).

    Attributes:
        cause: The underlying exception from boto3.
    """

    def __init__(self, cause: Exception) -> None:
        self.cause = cause
        super().__init__(f"Storage put failed: {cause}")
