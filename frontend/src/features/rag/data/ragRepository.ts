/**
 * Hilo People — RAG documents repository (concrete HTTP adapter).
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: HTTP adapter implementing IRagDocumentsRepository.
 *   Uses authFetch for authenticated calls (X-Request-ID, Bearer, 401 single-flight).
 *   Returns Result<T, RagError> — never throws to the presentation layer.
 *   Mirrors the pattern from features/chat/data/chatRepository.ts.
 *
 *   indexDocument and listCollections are extracted to _ragRepositoryExtras.ts
 *   (§D-RAGDOC-REPO-SPLIT) to honor the ~300 substantive line cap.
 *
 * §D-RAGDOC-AUTHFETCH-FORMDATA: When body is FormData, NEVER set Content-Type manually.
 *   The browser must add "multipart/form-data; boundary=..." automatically.
 *   authFetch does NOT inject Content-Type unless the caller adds it to headers.
 *
 * Security:
 *   - Relative URLs per ADR-002 (same-origin proxy in dev/prod).
 *   - Logs: ONLY safe metadata (no filename PII, no title, no file bytes).
 *     Safe fields: mime_type, size_kb_bucketed, sha256_prefix, doc.id, language, status.
 *
 * Key deps: authFetch (features/auth/data/httpClient.ts).
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type {
  ListDocumentsRequest,
  ListDocumentsResponse,
  UploadDocumentRequest,
  UploadDocumentOutcome,
  IndexDocumentOutcome,
  RagDocument,
  RagCollection,
} from "../domain/types";
import type { IRagDocumentsRepository } from "../domain/RagDocumentsRepository";
import { authFetch } from "../../auth/data/httpClient";
import {
  RagDocumentInvalidError,
  RagDocumentTooLargeError,
  RagDocumentUnsupportedMimeError,
  RagPermissionDeniedError,
  RagDocumentRateLimitedError,
  RagInternalError,
  mapRagError,
  type RagError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";
import { indexDocumentHttp, listCollectionsHttp } from "./_ragRepositoryExtras";

// ---------------------------------------------------------------------------
// URL constants
// ---------------------------------------------------------------------------

const DOCUMENTS_URL = "/api/v1/admin/rag/documents";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

/**
 * Bucket file size into human-safe categories for logging.
 * Prevents inadvertent size leakage for PII-adjacent data.
 */
function _bucketSize(bytes: number): string {
  if (bytes < 100_000) return "<100KB";
  if (bytes < 1_000_000) return "<1MB";
  if (bytes < 10_000_000) return "<10MB";
  return ">=10MB";
}

// ---------------------------------------------------------------------------
// Error parsing from response
// ---------------------------------------------------------------------------

interface ErrorEnvelope {
  errors?: Array<{ code?: string; field?: string; message?: string }>;
}

async function _parseErrorCode(res: Response): Promise<{ code?: string; field?: string }> {
  try {
    const body = await _safeJson<ErrorEnvelope>(res);
    const first = body.errors?.[0];
    return { code: first?.code, field: first?.field };
  } catch {
    return {};
  }
}

// ---------------------------------------------------------------------------
// Concrete repository implementation
// ---------------------------------------------------------------------------

/**
 * Concrete HTTP adapter for RAG document operations.
 *
 * Implements IRagDocumentsRepository using authFetch.
 * All methods log BEFORE/AFTER/ERROR and return Result<T, RagError>.
 */
export class RagRepository implements IRagDocumentsRepository {
  /**
   * List documents with optional filters and pagination.
   *
   * GET /api/v1/admin/rag/documents
   *
   * @param request - Query params for filtering.
   * @param onAuthFailure - Session expired callback.
   */
  async listDocuments(
    request: ListDocumentsRequest,
    onAuthFailure: () => void,
  ): Promise<Result<ListDocumentsResponse, RagError>> {
    const params = new URLSearchParams();
    if (request.collection_id) params.set("collection_id", request.collection_id);
    if (request.status) params.set("status", request.status);
    if (request.cursor) params.set("cursor", request.cursor);
    if (request.limit !== undefined) params.set("limit", String(request.limit));

    const url = `${DOCUMENTS_URL}${params.toString() ? `?${params}` : ""}`;

    logVerbose("rag.repo.listDocuments.start", {
      collection_id: request.collection_id ?? null,
      status: request.status ?? null,
      has_cursor: !!request.cursor,
      limit: request.limit ?? 50,
    });

    try {
      const response = await authFetch(
        url,
        { method: "GET", signal: request.signal },
        { onAuthFailure },
      );

      const requestId = response.headers.get("x-request-id") ?? "unknown";

      if (response.status === 403) {
        logWarn("rag.repo.listDocuments.forbidden", { status: 403, request_id: requestId });
        return { ok: false, error: new RagPermissionDeniedError() };
      }

      if (response.status === 429) {
        logWarn("rag.repo.listDocuments.rate_limited", { status: 429, request_id: requestId });
        return { ok: false, error: new RagDocumentRateLimitedError() };
      }

      if (!response.ok) {
        logError("rag.repo.listDocuments.server_error", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new RagInternalError(response.status) };
      }

      const body = await _safeJson<ListDocumentsResponse>(response);
      logVerbose("rag.repo.listDocuments.ok", {
        count: body.data.length,
        has_next_cursor: !!body.meta.pagination.cursor,
        request_id: requestId,
      });

      return { ok: true, value: body };
    } catch (err: unknown) {
      const domainErr = mapRagError(err);
      logError("rag.repo.listDocuments.error", { error: domainErr.code });
      return { ok: false, error: domainErr };
    }
  }

  /**
   * Upload a document via multipart/form-data.
   *
   * POST /api/v1/admin/rag/documents
   * §D-RAGDOC-AUTHFETCH-FORMDATA: DO NOT set Content-Type — browser adds boundary.
   *
   * @param request - File + metadata.
   * @param opts - Signal and auth failure callback.
   */
  async uploadDocument(
    request: UploadDocumentRequest,
    opts: { signal?: AbortSignal; onAuthFailure: () => void },
  ): Promise<Result<UploadDocumentOutcome, RagError>> {
    logVerbose("rag.repo.uploadDocument.start", {
      mime_type: request.file.type,
      size_bucketed: _bucketSize(request.file.size),
      language: request.language,
      collection_id: request.collection_id,
    });

    try {
      const form = new FormData();
      form.append("file", request.file);
      form.append("title", request.title);
      form.append("language", request.language);
      form.append("collection_id", request.collection_id);

      const response = await authFetch(
        DOCUMENTS_URL,
        { method: "POST", body: form, signal: opts.signal },
        { onAuthFailure: opts.onAuthFailure },
      );

      const requestId = response.headers.get("x-request-id") ?? "unknown";

      if (response.status === 400 || response.status === 422) {
        const { field } = await _parseErrorCode(response);
        logWarn("rag.repo.uploadDocument.validation_error", {
          status: response.status,
          field: field ?? null,
          request_id: requestId,
        });
        return { ok: false, error: new RagDocumentInvalidError("Validation failed.", field) };
      }

      if (response.status === 403) {
        logWarn("rag.repo.uploadDocument.forbidden", { status: 403, request_id: requestId });
        return { ok: false, error: new RagPermissionDeniedError() };
      }

      if (response.status === 413) {
        logWarn("rag.repo.uploadDocument.too_large", { status: 413, request_id: requestId });
        return { ok: false, error: new RagDocumentTooLargeError() };
      }

      if (response.status === 415) {
        logWarn("rag.repo.uploadDocument.unsupported_mime", {
          status: 415,
          request_id: requestId,
        });
        return { ok: false, error: new RagDocumentUnsupportedMimeError() };
      }

      if (response.status === 429) {
        logWarn("rag.repo.uploadDocument.rate_limited", { status: 429, request_id: requestId });
        return { ok: false, error: new RagDocumentRateLimitedError() };
      }

      if (!response.ok) {
        logError("rag.repo.uploadDocument.server_error", {
          status: response.status,
          request_id: requestId,
        });
        return { ok: false, error: new RagInternalError(response.status) };
      }

      const body = await _safeJson<{ data: RagDocument }>(response);
      const kind: "created" | "dedup" = response.status === 201 ? "created" : "dedup";

      logVerbose("rag.repo.uploadDocument.ok", {
        kind,
        doc_id: body.data.id,
        status: body.data.status,
        language: body.data.language,
        request_id: requestId,
      });

      return { ok: true, value: { kind, document: body.data } };
    } catch (err: unknown) {
      const domainErr = mapRagError(err);
      logError("rag.repo.uploadDocument.error", { error: domainErr.code });
      return { ok: false, error: domainErr };
    }
  }

  /**
   * Delegates to _ragRepositoryExtras.indexDocumentHttp.
   * POST /api/v1/admin/rag/documents/{id}/index
   *
   * @param id - Document UUID.
   * @param opts - Signal and auth failure callback.
   */
  async indexDocument(
    id: string,
    opts: { signal?: AbortSignal; onAuthFailure: () => void },
  ): Promise<Result<IndexDocumentOutcome, RagError>> {
    return indexDocumentHttp(id, opts);
  }

  /**
   * Delegates to _ragRepositoryExtras.listCollectionsHttp.
   * GET /api/v1/admin/rag/collections
   *
   * @param opts - Signal and auth failure callback.
   */
  async listCollections(opts: {
    signal?: AbortSignal;
    onAuthFailure: () => void;
  }): Promise<Result<RagCollection[], RagError>> {
    return listCollectionsHttp(opts);
  }
}

// ---------------------------------------------------------------------------
// Singleton instance
// ---------------------------------------------------------------------------

/** Default repository instance for use in hooks. */
export const ragRepository = new RagRepository();
