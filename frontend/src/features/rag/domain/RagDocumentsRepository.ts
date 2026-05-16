/**
 * Hilo People — RAG documents repository port (interface).
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Port defining the operations the domain needs for RAG documents.
 *   Data layer implements this; presentation hooks depend on it.
 *   No imports of external libs, no React, no fetch calls here — pure interface.
 *
 * Clean Architecture: presentation/ depends on this port, NOT on ragRepository.ts
 *   directly. This decouples UI from HTTP implementation details.
 *
 * Source refs: TECHNICAL_GUIDE §6.2 (endpoint contracts), instrucciones.md §3.1.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type {
  ListDocumentsRequest,
  ListDocumentsResponse,
  UploadDocumentRequest,
  UploadDocumentOutcome,
  IndexDocumentOutcome,
  RagCollection,
} from "./types";
import type { RagError } from "../data/errors";

// ---------------------------------------------------------------------------
// Repository port
// ---------------------------------------------------------------------------

/**
 * Port interface for all RAG document operations.
 *
 * Implemented by data/ragRepository.ts; consumed by presentation hooks.
 * All methods return Result<T, RagError> — never throw to the presentation layer.
 */
export interface IRagDocumentsRepository {
  /**
   * List documents with optional filters and pagination.
   *
   * Calls GET /api/v1/admin/rag/documents.
   * Returns the first page (limit ≤ 100) of documents matching the filters.
   *
   * @param request - Query params (collection_id, status, cursor, limit, signal).
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   * @returns Result<ListDocumentsResponse, RagError>
   */
  listDocuments(
    request: ListDocumentsRequest,
    onAuthFailure: () => void,
  ): Promise<Result<ListDocumentsResponse, RagError>>;

  /**
   * Upload a new document via multipart/form-data.
   *
   * Calls POST /api/v1/admin/rag/documents.
   * Returns UploadDocumentOutcome with kind=created (201) or kind=dedup (200).
   * NEVER set Content-Type manually — the browser must add the multipart boundary.
   *
   * @param request - Upload request (file, title, language, collection_id).
   * @param opts.signal - AbortSignal for cancellation.
   * @param opts.onAuthFailure - Called when session expires.
   * @returns Result<UploadDocumentOutcome, RagError>
   */
  uploadDocument(
    request: UploadDocumentRequest,
    opts: { signal?: AbortSignal; onAuthFailure: () => void },
  ): Promise<Result<UploadDocumentOutcome, RagError>>;

  /**
   * Enqueue vectorization for a document.
   *
   * Calls POST /api/v1/admin/rag/documents/{id}/index.
   * Returns kind=enqueued (202) or kind=in_progress (409).
   *
   * @param id - Document UUID.
   * @param opts.signal - AbortSignal for cancellation.
   * @param opts.onAuthFailure - Called when session expires.
   * @returns Result<IndexDocumentOutcome, RagError>
   */
  indexDocument(
    id: string,
    opts: { signal?: AbortSignal; onAuthFailure: () => void },
  ): Promise<Result<IndexDocumentOutcome, RagError>>;

  /**
   * List all active RAG collections (for the collection dropdown in upload form).
   *
   * Calls GET /api/v1/admin/rag/collections.
   *
   * @param opts.signal - AbortSignal for cancellation.
   * @param opts.onAuthFailure - Called when session expires.
   * @returns Result<RagCollection[], RagError>
   */
  listCollections(opts: {
    signal?: AbortSignal;
    onAuthFailure: () => void;
  }): Promise<Result<RagCollection[], RagError>>;
}
