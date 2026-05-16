/**
 * Hilo People — RAG repository extras (indexDocument + listCollections).
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Extracted HTTP adapter methods for indexing and collections.
 *   Split from ragRepository.ts to honor the ~300 substantive line cap.
 *   Consumed exclusively by RagRepository class in ragRepository.ts.
 *
 * §D-RAGDOC-REPO-SPLIT: proactive split analogous to AccountPage.styles.ts pattern.
 *
 * Key deps: authFetch, errors, logger.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type { IndexDocumentOutcome, RagCollection } from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import {
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
