/**
 * Hilo People — Admin AI repository (concrete HTTP adapter).
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-ADMINAI-FEATURE
 *
 * Responsibility: Fetches data from /api/v1/admin/usage via authFetch.
 *   Returns Result<UsageSummary, AdminAiError> — never throws to presentation layer.
 *   Mirrors chatRepository.ts pattern: BEFORE/AFTER/ERROR logging, Result shape.
 *
 * Clean Architecture: this is the DATA layer for the admin-ai feature.
 *   Presentation hooks depend on this module, not the raw HTTP client.
 *
 * Security:
 *   - Uses authFetch (X-Request-ID, credentials:include, Bearer injection, single-flight 401).
 *   - Relative URL per ADR-002 (same-origin via vite proxy in dev, Nginx in prod).
 *   - NEVER hardcode http://localhost:8000 here.
 *   - PII-clean logs: no email, no model API keys, no prompt text.
 *     Log only: row count, error class name, request IDs, window dates.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 *
 * Will be extended in P04-S01-T002..T004 with: listProviders, createProvider,
 * listModels, patchModel, testModel. The barrel index.ts is designed for this reuse.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type { GetUsageRequest, UsageSummary } from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import { AuthSessionExpiredError } from "../../auth/data/errors";
import {
  AdminAiAuthExpiredError,
  AdminAiForbiddenError,
  AdminAiValidationError,
  AdminAiNetworkError,
  AdminAiInternalError,
  mapAdminAiError,
  type AdminAiError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const USAGE_URL = "/api/v1/admin/usage";

// ---------------------------------------------------------------------------
// Helper: safely parse response JSON
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
 * Fetches usage summary from GET /api/v1/admin/usage.
 *
 * Source: TECHNICAL_GUIDE §6.2. Returns a Result — never throws upward.
 * Status mapping:
 *   200 OK         → Result.ok(UsageSummary)
 *   401            → Result.err(AdminAiAuthExpiredError)  — authFetch already retried
 *   403            → Result.err(AdminAiForbiddenError)
 *   422            → Result.err(AdminAiValidationError)   — defensive; log loud
 *   5xx            → Result.err(AdminAiInternalError)
 *   network reject → Result.err(AdminAiNetworkError)
 *
 * @param params - Query parameters for the usage endpoint.
 * @param onAuthFailure - Called when session is fully expired (401 cannot recover).
 * @returns Result<UsageSummary, AdminAiError>
 */
export async function getUsage(
  params: GetUsageRequest,
  onAuthFailure: () => void,
): Promise<Result<UsageSummary, AdminAiError>> {
  const query = new URLSearchParams({
    from: params.from,
    to: params.to,
    ...(params.group_by ? { group_by: params.group_by } : {}),
    ...(params.model_id ? { model_id: params.model_id } : {}),
    ...(params.provider_id ? { provider_id: params.provider_id } : {}),
  });

  const url = `${USAGE_URL}?${query.toString()}`;

  logVerbose("admin-ai.repo.getUsage.start", {
    from: params.from,
    to: params.to,
    group_by: params.group_by ?? "model",
  });

  try {
    const response = await authFetch(url, { method: "GET" }, { onAuthFailure });
    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      // authFetch already attempted refresh; final 401 = session expired.
      logWarn("admin-ai.repo.getUsage.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("admin-ai.repo.getUsage.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiForbiddenError() };
    }

    if (response.status === 422) {
      // Defensive: should not happen with client's hard-coded 30d window + group_by=model.
      // Log loud so developers notice if params drift.
      let serverCode = "ADMIN_USAGE_INVALID_PAYLOAD";
      try {
        const body = await _safeJson<{ errors?: Array<{ code?: string }> }>(response);
        serverCode = body.errors?.[0]?.code ?? serverCode;
      } catch {
        // Ignore parse error — use default code
      }
      logError("admin-ai.repo.getUsage.validation_error", {
        status: 422,
        server_code: serverCode,
        request_id: requestId,
        note: "422 from admin/usage — client params may have drifted from spec",
      });
      return { ok: false, error: new AdminAiValidationError(serverCode) };
    }

    if (response.status >= 500) {
      logError("admin-ai.repo.getUsage.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiInternalError(response.status) };
    }

    if (!response.ok) {
      logError("admin-ai.repo.getUsage.unexpected_status", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiNetworkError(`Unexpected status ${response.status}`) };
    }

    const body = await _safeJson<{ data: UsageSummary; meta?: { request_id?: string } }>(response);
    const summary = body.data;

    logVerbose("admin-ai.repo.getUsage.ok", {
      row_count: summary.rows.length,
      total_invocations: summary.totals.invocations,
      request_id: requestId,
    });

    return { ok: true, value: summary };
  } catch (err: unknown) {
    if (err instanceof AdminAiAuthExpiredError) return { ok: false, error: err };
    if (err instanceof AdminAiForbiddenError) return { ok: false, error: err };
    if (err instanceof AuthSessionExpiredError) {
      logWarn("admin-ai.repo.getUsage.auth_expired_via_client", {});
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }
    const mapped = mapAdminAiError(err);
    logError("admin-ai.repo.getUsage.network_error", {
      error_class: mapped.constructor.name,
    });
    return { ok: false, error: mapped };
  }
}
