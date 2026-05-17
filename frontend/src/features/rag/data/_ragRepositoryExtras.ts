/**
 * Hilo People — RAG repository extras (indexDocument + listCollections + updateCollection).
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *   Extended in P04-S02-T002 — RagCollectionsPage (updateCollectionHttp).
 *
 * Responsibility: Extracted HTTP adapter methods for indexing, collections, and
 *   collection mutations. Split from ragRepository.ts to honor the ~300 LOC cap.
 *   Consumed exclusively by RagRepository class in ragRepository.ts.
 *
 * §D-RAGDOC-REPO-SPLIT: proactive split analogous to AccountPage.styles.ts pattern.
 * §D-T002-REPO-EXTRAS: updateCollectionHttp added here (file has +127 LOC headroom).
 * §D-T002-LOGS-PII-CLEAN: logs contain collection_id and field keys only, never values.
 *
 * Key deps: authFetch, errors, logger.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type {
  IndexDocumentOutcome,
  RagCollection,
  UpdateCollectionRequest,
  UpdateCollectionOutcome,
} from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import {
  RagDocumentInvalidError,
  RagPermissionDeniedError,
  RagDocumentNotFoundError,
  RagDocumentRateLimitedError,
  RagIndexInProgressError,
  RagInternalError,
  mapRagError,
  type RagError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

const DOCUMENTS_URL = "/api/v1/admin/rag/documents";
const COLLECTIONS_URL = "/api/v1/admin/rag/collections";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// indexDocument
// ---------------------------------------------------------------------------

/**
 * HTTP adapter for POST /api/v1/admin/rag/documents/{id}/index.
 *
 * @param id - Document UUID.
 * @param opts - Signal and auth failure callback.
 */
export async function indexDocumentHttp(
  id: string,
  opts: { signal?: AbortSignal; onAuthFailure: () => void },
): Promise<Result<IndexDocumentOutcome, RagError>> {
  logVerbose("rag.repo.indexDocument.start", { doc_id: id });

  try {
    const response = await authFetch(
      `${DOCUMENTS_URL}/${id}/index`,
      { method: "POST", signal: opts.signal },
      { onAuthFailure: opts.onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 403) {
      logWarn("rag.repo.indexDocument.forbidden", { doc_id: id, request_id: requestId });
      return { ok: false, error: new RagPermissionDeniedError() };
    }

    if (response.status === 404) {
      logWarn("rag.repo.indexDocument.not_found", { doc_id: id, request_id: requestId });
      return { ok: false, error: new RagDocumentNotFoundError() };
    }

    if (response.status === 409) {
      const body = await _safeJson<{ data: { job_id: string; status: string } }>(response);
      logWarn("rag.repo.indexDocument.in_progress", {
        doc_id: id,
        job_id: body.data.job_id,
        job_status: body.data.status,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new RagIndexInProgressError(body.data.job_id, body.data.status),
      };
    }

    if (response.status === 429) {
      logWarn("rag.repo.indexDocument.rate_limited", { doc_id: id, request_id: requestId });
      return { ok: false, error: new RagDocumentRateLimitedError() };
    }

    if (!response.ok) {
      logError("rag.repo.indexDocument.server_error", {
        doc_id: id,
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new RagInternalError(response.status) };
    }

    const body = await _safeJson<{ data: { job_id: string; status: string } }>(response);
    logVerbose("rag.repo.indexDocument.ok", {
      doc_id: id,
      job_id: body.data.job_id,
      job_status: body.data.status,
      request_id: requestId,
    });

    return {
      ok: true,
      value: { kind: "enqueued", job_id: body.data.job_id, status: "pending" },
    };
  } catch (err: unknown) {
    const domainErr = mapRagError(err);
    logError("rag.repo.indexDocument.error", { doc_id: id, error: domainErr.code });
    return { ok: false, error: domainErr };
  }
}

// ---------------------------------------------------------------------------
// listCollections
// ---------------------------------------------------------------------------

/**
 * HTTP adapter for GET /api/v1/admin/rag/collections.
 *
 * @param opts - Signal and auth failure callback.
 */
export async function listCollectionsHttp(opts: {
  signal?: AbortSignal;
  onAuthFailure: () => void;
}): Promise<Result<RagCollection[], RagError>> {
  logVerbose("rag.repo.listCollections.start");

  try {
    const response = await authFetch(
      COLLECTIONS_URL,
      { method: "GET", signal: opts.signal },
      { onAuthFailure: opts.onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 403) {
      logWarn("rag.repo.listCollections.forbidden", { status: 403, request_id: requestId });
      return { ok: false, error: new RagPermissionDeniedError() };
    }

    if (!response.ok) {
      logError("rag.repo.listCollections.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new RagInternalError(response.status) };
    }

    const body = await _safeJson<{ data: RagCollection[] }>(response);
    logVerbose("rag.repo.listCollections.ok", {
      count: body.data.length,
      request_id: requestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    const domainErr = mapRagError(err);
    logError("rag.repo.listCollections.error", { error: domainErr.code });
    return { ok: false, error: domainErr };
  }
}

// ---------------------------------------------------------------------------
// updateCollection (P04-S02-T002)
// ---------------------------------------------------------------------------

/**
 * Error envelope shape for PATCH error responses.
 * Mirrors the backend error envelope from TECHNICAL_GUIDE §6.4.
 */
interface CollectionErrorEnvelope {
  errors?: Array<{ code?: string; field?: string; message?: string }>;
}

async function _parseCollectionErrorCode(
  res: Response,
): Promise<{ code?: string; field?: string }> {
  try {
    const text = await res.text();
    if (!text) return {};
    const body = JSON.parse(text) as CollectionErrorEnvelope;
    const first = body.errors?.[0];
    return { code: first?.code, field: first?.field };
  } catch {
    return {};
  }
}

/**
 * HTTP adapter for PATCH /api/v1/admin/rag/collections/{id}.
 *
 * §D-T002-REPO-EXTRAS: added in P04-S02-T002.
 * §D-T002-LOGS-PII-CLEAN: logs collection_id and field keys only, never values.
 * ADR-002: relative URL, no host.
 *
 * @param req - UpdateCollectionRequest with id and partial patch.
 * @param opts - Auth failure callback.
 */
export async function updateCollectionHttp(
  req: UpdateCollectionRequest,
  opts: { onAuthFailure: () => void },
): Promise<Result<UpdateCollectionOutcome, RagError>> {
  logVerbose("rag.repo.updateCollection.start", {
    collection_id: req.id,
    fields: Object.keys(req.patch),
  });

  try {
    const response = await authFetch(
      `${COLLECTIONS_URL}/${req.id}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(req.patch),
        signal: req.signal,
      },
      { onAuthFailure: opts.onAuthFailure },
    );

    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 400 || response.status === 422) {
      const { field } = await _parseCollectionErrorCode(response);
      logWarn("rag.repo.updateCollection.validation_error", {
        collection_id: req.id,
        status: response.status,
        field: field ?? null,
        request_id: requestId,
      });
      return { ok: false, error: new RagDocumentInvalidError("Validation failed.", field) };
    }

    if (response.status === 403) {
      logWarn("rag.repo.updateCollection.forbidden", {
        collection_id: req.id,
        request_id: requestId,
      });
      return { ok: false, error: new RagPermissionDeniedError() };
    }

    if (response.status === 404) {
      logWarn("rag.repo.updateCollection.not_found", {
        collection_id: req.id,
        request_id: requestId,
      });
      return { ok: false, error: new RagDocumentNotFoundError() };
    }

    if (response.status === 429) {
      logWarn("rag.repo.updateCollection.rate_limited", {
        collection_id: req.id,
        request_id: requestId,
      });
      return { ok: false, error: new RagDocumentRateLimitedError() };
    }

    if (!response.ok) {
      logError("rag.repo.updateCollection.server_error", {
        collection_id: req.id,
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new RagInternalError(response.status) };
    }

    const body = await _safeJson<{ data: RagCollection; meta: { request_id: string } }>(response);
    logVerbose("rag.repo.updateCollection.ok", {
      collection_id: body.data.id,
      request_id: body.meta?.request_id ?? requestId,
    });

    return { ok: true, value: { kind: "updated", collection: body.data } };
  } catch (err: unknown) {
    const domainErr = mapRagError(err);
    logError("rag.repo.updateCollection.error", {
      collection_id: req.id,
      error: domainErr.code,
    });
    return { ok: false, error: domainErr };
  }
}
