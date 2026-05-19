/**
 * Hilo People — Admin usage repository (concrete HTTP adapter).
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Calls GET /api/v1/admin/usage via authFetch.
 *   Returns Result<UsageSummary, UsageError> — never throws to presentation layer.
 *   Mirrors chatRepository.ts pattern: BEFORE/AFTER/ERROR logging, Result shape.
 *
 * Clean Architecture: DATA layer for the admin usage feature.
 *   Presentation hooks depend on this module via IUsageRepository port.
 *
 * Security:
 *   - Uses authFetch (X-Request-ID, credentials:include, Bearer injection, 401 refresh).
 *   - Relative URL per ADR-002 (same-origin via vite proxy in dev, Nginx in prod).
 *   - NEVER hardcode http://localhost:8000 here (ADR-002 contract).
 *   - No PII in logs: only from, to, group_by, row_count, request_id.
 *
 * D-T002-DATA-REPO: Canonical write_set anchor for this file.
 * Source ref: §D-T002-DATA-REPO, task pack §7, TECHNICAL_GUIDE §6.1.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type { UsageSummary, UsageQuery } from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import {
  UsageValidationError,
  UsageAuthExpiredError,
  UsageForbiddenError,
  UsageNetworkError,
  UsageServerError,
  mapUsageError,
  type UsageError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Relative path per ADR-002 same-origin contract. NO localhost hardcode. */
const USAGE_URL = "/api/v1/admin/usage";

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Public: getUsage
// ---------------------------------------------------------------------------

/**
 * Calls GET /api/v1/admin/usage with query parameters.
 *
 * Returns Result.ok(UsageSummary) on 200.
 * Returns typed Result.err for all failure paths (422, 403, 401, 5xx, network).
 *
 * Logging contract (D-T002-PII-LOGGING):
 *   BEFORE: from, to, group_by, request_id
 *   AFTER success: row_count, range_days, request_id
 *   ERROR: error_class, status, request_id (NO PII, NO cost data)
 *
 * @param query - Validated UsageQuery (from, to, groupBy).
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @param signal - Optional AbortSignal for cancellation (TanStack v5 queryFn).
 * @returns Result<UsageSummary, UsageError>
 */
export async function getUsage(
  query: UsageQuery,
  onAuthFailure: () => void = () => void 0,
  signal?: AbortSignal,
): Promise<Result<UsageSummary, UsageError>> {
  const requestId = crypto.randomUUID();
  const fromIso = query.from.toISOString();
  const toIso = query.to.toISOString();
  const rangeDays = Math.round((query.to.getTime() - query.from.getTime()) / 86_400_000);

  // BEFORE
  logVerbose("usage.repo.fetch.before", {
    from: fromIso,
    to: toIso,
    group_by: query.groupBy,
    request_id: requestId,
  });

  const url = `${USAGE_URL}?from=${encodeURIComponent(fromIso)}&to=${encodeURIComponent(toIso)}&group_by=${encodeURIComponent(query.groupBy)}`;

  try {
    const response = await authFetch(
      url,
      { signal },
      { onAuthFailure },
    );

    const responseRequestId = response.headers.get("x-request-id") ?? requestId;

    if (response.status === 422) {
      logWarn("usage.repo.fetch.validation_error", {
        status: 422,
        request_id: responseRequestId,
      });
      return { ok: false, error: new UsageValidationError("Invalid usage parameters.") };
    }

    if (response.status === 401) {
      // authFetch already attempted refresh; final 401 = session expired.
      logWarn("usage.repo.fetch.auth_expired", {
        status: 401,
        request_id: responseRequestId,
      });
      return { ok: false, error: new UsageAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("usage.repo.fetch.forbidden", {
        status: 403,
        request_id: responseRequestId,
      });
      return { ok: false, error: new UsageForbiddenError() };
    }

    if (!response.ok) {
      logError("usage.repo.fetch.server_error", {
        status: response.status,
        request_id: responseRequestId,
      });
      return { ok: false, error: new UsageServerError(response.status) };
    }

    const body = await _safeJson<{ data: UsageSummary }>(response);

    // AFTER success
    logVerbose("usage.repo.fetch.after", {
      row_count: body.data.rows.length,
      range_days: rangeDays,
      request_id: responseRequestId,
    });

    return { ok: true, value: body.data };
  } catch (err: unknown) {
    // Handle abort signal
    if (err instanceof DOMException && err.name === "AbortError") {
      logVerbose("usage.repo.fetch.aborted", { request_id: requestId });
      return { ok: false, error: new UsageNetworkError("Request aborted.") };
    }

    const domainErr = mapUsageError(err);
    // ERROR log
    logError("usage.repo.fetch.error", {
      error_class: domainErr.code,
      message: domainErr.message,
      request_id: requestId,
    });
    return { ok: false, error: domainErr };
  }
}
