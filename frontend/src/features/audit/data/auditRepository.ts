/**
 * Hilo People — Audit repository (concrete HTTP adapter).
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Calls GET /api/v1/admin/audit via authFetch.
 *   Returns Result<AuditPage, AuditError> — never throws to presentation layer.
 *   Mirrors usageRepository.ts pattern: BEFORE/AFTER/ERROR logging, Result shape.
 *
 * Clean Architecture: DATA layer for the audit feature.
 *   Presentation hooks depend on this module via IAuditRepository port.
 *
 * Security:
 *   - Uses authFetch (X-Request-ID, credentials:include, Bearer injection, 401 refresh).
 *   - Relative URL per ADR-002 (same-origin via vite proxy in dev, Nginx in prod).
 *   - NEVER hardcode http://localhost:8000 here (ADR-002 contract).
 *   - No PII in logs: only has_from, has_to, action_present, actor_present, count, request_id.
 *   - NEVER log full audit rows, actor UUIDs, IPs, or metadata blobs.
 *
 * §D-T001-DATA: Canonical write_set anchor for this file.
 * Source ref: §D-T001-DATA, task pack §7, TECHNICAL_GUIDE §6.1, §6.2.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type { AuditQuery, AuditPage } from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import {
  AuditValidationError,
  AuditAuthExpiredError,
  AuditForbiddenError,
  AuditNetworkError,
  AuditServerError,
  mapAuditError,
  type AuditError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/** Relative path per ADR-002 same-origin contract. NO localhost hardcode. */
const AUDIT_URL = "/api/v1/admin/audit";

// ---------------------------------------------------------------------------
// Backend response envelope types (internal to this module)
// ---------------------------------------------------------------------------

interface BackendAuditMeta {
  request_id: string;
  next_cursor: string | null;
  has_more: boolean;
  count: number;
}

interface BackendAuditEnvelope {
  data: Array<{
    id: string;
    actor_user_id: string | null;
    action: string;
    entity_type: string | null;
    entity_id: string | null;
    metadata: Record<string, unknown>;
    created_at: string;
  }>;
  meta: BackendAuditMeta;
  errors: unknown[];
}

// ---------------------------------------------------------------------------
// Helper: safely read response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Public: getAuditPage
// ---------------------------------------------------------------------------

/**
 * Calls GET /api/v1/admin/audit with query parameters.
 *
 * Returns Result.ok(AuditPage) on 200.
 * Returns typed Result.err for all failure paths (422, 403, 401, 5xx, network).
 *
 * Logging contract (D-T001-PII-LOGGING):
 *   BEFORE: has_from, has_to, action_present, actor_present, cursor_present, limit
 *   AFTER success: count, has_more, request_id
 *   ERROR: error_class, status, request_id (NO PII, NO full rows)
 *
 * @param query - Validated AuditQuery (from, to, optional actor/action/cursor/limit).
 * @param onAuthFailure - Called when session expires and cannot be refreshed.
 * @param signal - Optional AbortSignal for cancellation (TanStack v5 queryFn).
 * @returns Result<AuditPage, AuditError>
 */
export async function getAuditPage(
  query: AuditQuery,
  onAuthFailure: () => void = () => void 0,
  signal?: AbortSignal,
): Promise<Result<AuditPage, AuditError>> {
  const requestId = crypto.randomUUID();
  const fromIso = query.from.toISOString();
  const toIso = query.to.toISOString();

  // BEFORE log — no PII, no full row data
  logVerbose("audit.repo.fetch.before", {
    has_from: true,
    has_to: true,
    action_present: query.action !== undefined,
    actor_present: query.actor !== undefined,
    cursor_present: query.cursor !== undefined,
    limit: query.limit ?? 50,
    request_id: requestId,
  });

  // Build query string
  const params = new URLSearchParams();
  params.set("from", fromIso);
  params.set("to", toIso);
  if (query.actor) params.set("actor", query.actor);
  if (query.action) params.set("action", query.action);
  if (query.cursor) params.set("cursor", query.cursor);
  if (query.limit !== undefined) params.set("limit", String(query.limit));
  const url = `${AUDIT_URL}?${params.toString()}`;

  try {
    const response = await authFetch(
      url,
      { signal },
      { onAuthFailure },
    );

    const responseRequestId = response.headers.get("x-request-id") ?? requestId;

    if (response.status === 422) {
      logWarn("audit.repo.fetch.validation_error", {
        status: 422,
        request_id: responseRequestId,
      });
      return { ok: false, error: new AuditValidationError("Invalid audit parameters.") };
    }

    if (response.status === 401) {
      // authFetch already attempted refresh; final 401 = session expired.
      logWarn("audit.repo.fetch.auth_expired", {
        status: 401,
        request_id: responseRequestId,
      });
      return { ok: false, error: new AuditAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("audit.repo.fetch.forbidden", {
        status: 403,
        request_id: responseRequestId,
      });
      return { ok: false, error: new AuditForbiddenError() };
    }

    if (!response.ok) {
      logError("audit.repo.fetch.server_error", {
        status: response.status,
        request_id: responseRequestId,
      });
      return { ok: false, error: new AuditServerError(response.status) };
    }

    const body = await _safeJson<BackendAuditEnvelope>(response);
    const { data: rows, meta } = body;

    // AFTER success log — NO full rows, NO actor UUIDs
    logVerbose("audit.repo.fetch.after", {
      count: meta.count,
      has_more: meta.has_more,
      request_id: meta.request_id ?? responseRequestId,
    });

    const auditPage: AuditPage = {
      rows,
      next_cursor: meta.next_cursor,
      has_more: meta.has_more,
      count: meta.count,
    };

    return { ok: true, value: auditPage };
  } catch (err: unknown) {
    // Handle abort signal
    if (err instanceof DOMException && err.name === "AbortError") {
      logVerbose("audit.repo.fetch.aborted", { request_id: requestId });
      return { ok: false, error: new AuditNetworkError("Request aborted.") };
    }

    const domainErr = mapAuditError(err);
    // ERROR log — NO PII
    logError("audit.repo.fetch.error", {
      error_class: domainErr.code,
      message: domainErr.message,
      request_id: requestId,
    });
    return { ok: false, error: domainErr };
  }
}
