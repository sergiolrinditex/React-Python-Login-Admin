/**
 * Hilo People — RAG documents feature domain types.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *   Extended in P04-S02-T002 — RagCollectionsPage (UpdateCollectionRequest,
 *   UpdateCollectionOutcome, RagCollection.language nullable).
 *
 * Responsibility: Pure domain types for RAG document management.
 *   No external framework imports; no fetch calls; no React.
 *   Used by presentation hooks and page components.
 *
 * Source refs:
 *   TECHNICAL_GUIDE §6.1 (route row /admin/rag/documents), §6.2 (endpoint contracts),
 *   §10.3 (DB schema), instrucciones.md §3.1 (RAG admin business rules).
 *   §D-T002-COLLECTION-LANGUAGE-NULLABLE: backend CollectionOut.language is str | None.
 *   §D-T002-TYPES: UpdateCollectionRequest/Outcome for PATCH collections endpoint.
 *
 * Key deps: none (pure domain types).
 */

// ---------------------------------------------------------------------------
// Document status
// ---------------------------------------------------------------------------

/**
 * Status lifecycle for a RAG document.
 *
 * - uploaded: file stored in MinIO, not yet vectorized.
 * - pending: vectorization job enqueued.
 * - processing: Celery job running.
 * - indexed: vectorization complete; document is searchable.
 * - failed: vectorization job failed; document not searchable.
 *
 * Mirrors backend DocumentStatus enum in backend/app/rag/documents/schemas.py.
 */
export type DocumentStatus = "uploaded" | "pending" | "processing" | "indexed" | "failed";

/** Non-terminal states that require polling to update. */
export const INFLIGHT_STATUSES: DocumentStatus[] = ["uploaded", "pending", "processing"];

/** Terminal states — polling stops when all docs reach these. */
export const TERMINAL_STATUSES: DocumentStatus[] = ["indexed", "failed"];

// ---------------------------------------------------------------------------
// Core entities
// ---------------------------------------------------------------------------

/**
 * A RAG document record returned by the backend.
 * Mirrors DocumentOut from backend/app/rag/documents/schemas.py.
 */
export interface RagDocument {
  id: string;
  collection_id: string | null;
  title: string;
  language: "es" | "en" | "fr";
  source_uri: string;
  status: DocumentStatus;
  uploaded_by: string | null;
  created_at: string;
}

/**
 * A RAG collection (read-only in T001; inline-editable in P04-S02-T002).
 * Mirrors RagCollection from backend/app/rag/collections/schemas.py.
 *
 * §D-T002-COLLECTION-LANGUAGE-NULLABLE: language is str | None in CollectionOut.
 *   Null means "multilingual" or unset. UI displays "—" for null language.
 */
export interface RagCollection {
  id: string;
  name: string;
  vertical: string;
  language: "es" | "en" | "fr" | null;
  enabled: boolean;
}

// ---------------------------------------------------------------------------
// Request / response types
// ---------------------------------------------------------------------------

/** Input for the multipart document upload. */
export interface UploadDocumentRequest {
  file: File;
  title: string;
  language: "es" | "en" | "fr";
  collection_id: string;
}

/**
 * Outcome of a document upload.
 *
 * - created: new document stored (HTTP 201).
 * - dedup: sha256 matched an existing document; backend returned 200.
 */
export type UploadDocumentOutcome =
  | { kind: "created"; document: RagDocument }
  | { kind: "dedup"; document: RagDocument };

/**
 * Outcome of an index-document request.
 *
 * - enqueued: new vectorization job created (HTTP 202).
 * - in_progress: a job already exists for this document (HTTP 409 RAG_INDEX_IN_PROGRESS).
 */
export type IndexDocumentOutcome =
  | { kind: "enqueued"; job_id: string; status: "pending" }
  | { kind: "in_progress"; job_id: string; status: string };

// ---------------------------------------------------------------------------
// Collection update types (P04-S02-T002)
// ---------------------------------------------------------------------------

/**
 * Request for PATCH /api/v1/admin/rag/collections/{id}.
 *
 * §D-T002-TYPES: matches backend CollectionPatchIn (name?, vertical?, language?, enabled?).
 * At least one field must be present (backend validator "at_least_one_field").
 * §D-T002-LANGUAGE-NULL-READ-ONLY-CLEAR: language null cannot be sent via PATCH
 *   (backend pattern only accepts es|en|fr). The UI only reads null, never sends it.
 */
export interface UpdateCollectionRequest {
  id: string;
  patch: Partial<Pick<RagCollection, "name" | "vertical" | "language" | "enabled">>;
  signal?: AbortSignal;
}

/**
 * Outcome of a successful collection update.
 *
 * - updated: PATCH 200, new collection state returned.
 */
export type UpdateCollectionOutcome = { kind: "updated"; collection: RagCollection };

// ---------------------------------------------------------------------------
// Pagination
// ---------------------------------------------------------------------------

/** Pagination cursor for list requests. */
export interface PaginationCursor {
  cursor: string | null;
  limit: number;
}

/** Request params for list documents. */
export interface ListDocumentsRequest {
  collection_id?: string;
  status?: DocumentStatus;
  cursor?: string;
  limit?: number;
  signal?: AbortSignal;
}

/** Response from list documents endpoint. */
export interface ListDocumentsResponse {
  data: RagDocument[];
  meta: {
    pagination: PaginationCursor;
    request_id: string;
  };
}
