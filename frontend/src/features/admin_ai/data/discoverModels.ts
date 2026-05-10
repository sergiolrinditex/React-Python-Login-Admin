/**
 * API client for the discover-models endpoint.
 *
 * What: Calls POST /api/v1/admin/ai/providers/{providerId}/discover-models
 *       and maps HTTP responses to a typed Result<DiscoverModelsData, AdminAiError>.
 *       Never throws across the layer boundary — all errors are returned as
 *       { ok: false, error: AdminAiError }.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   - ./auth — getAdminAuthHeader() (P00 stub)
 *   - ./types — DiscoverModelsData, AdminAiError, Result
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §3.1 Request
 *   - task-pack P00-S02-T007.md §3.2 Response
 *   - task-pack P00-S02-T007.md §3.3 Error codes
 *   - 01-non-negotiables.md §Logging (BEFORE/AFTER/ERROR structured logs)
 *   - 01-non-negotiables.md §Error handling (Result pattern)
 *   - 01-non-negotiables.md §Security (no auth header value in logs)
 *
 * Logging:
 *   BEFORE — logs event + truncated provider_id + X-Request-ID before fetch.
 *   AFTER  — logs event + status_code + latency_ms on success.
 *   ERROR  — logs event + error_code + latency_ms on failure.
 *   NEVER logs Authorization header value or full provider_id (first 8 chars only).
 *   ENABLE_VERBOSE_LOGGING semantics: frontend has no env-aware logger yet.
 *   Console.info is used for BEFORE/AFTER; console.warn for errors.
 *   Gap documented: a structured frontend logger respecting ENABLE_VERBOSE_LOGGING
 *   is deferred to P01-S03-T001 (auth slice introduces the logging infrastructure).
 */

import { getAdminAuthHeader } from './auth';
import type {
  DiscoverModelsData,
  DiscoverModelsResponse,
  AdminAiError,
  AdminAiErrorCode,
  Result,
} from './types';

// ── Constants ────────────────────────────────────────────────────────────────

const API_BASE = '/api/v1';

// ── Helpers ──────────────────────────────────────────────────────────────────

/**
 * Generates a UUID v4 for X-Request-ID correlation.
 * Falls back to a timestamp-based pseudo-ID if crypto is unavailable.
 *
 * @returns UUID v4 string or pseudo-ID.
 */
function generateRequestId(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `req-${Date.now()}-${Math.random().toString(36).slice(2, 9)}`;
}

/**
 * Maps an HTTP status code to an AdminAiErrorCode.
 *
 * @param status - HTTP status code.
 * @returns AdminAiErrorCode discriminant.
 */
function mapStatusToErrorCode(status: number): AdminAiErrorCode {
  if (status === 401) return 'unauthorized';
  if (status === 403) return 'forbidden';
  if (status === 404) return 'provider_not_found';
  if (status === 422) return 'validation_error';
  if (status === 502) return 'upstream_error';
  return 'server_error';
}

// ── Public API ───────────────────────────────────────────────────────────────

/**
 * Calls POST /api/v1/admin/ai/providers/{providerId}/discover-models.
 *
 * Returns a Result: success = { ok: true, value: DiscoverModelsData },
 * failure = { ok: false, error: AdminAiError }.
 *
 * @param providerId - UUID of the ai_provider row.
 * @returns Promise<Result<DiscoverModelsData, AdminAiError>>
 *
 * @throws Never — all errors are captured in the Result.
 */
export async function discoverModels(
  providerId: string,
): Promise<Result<DiscoverModelsData, AdminAiError>> {
  const requestId = generateRequestId();
  const truncatedId = providerId.slice(0, 8);
  const startMs = Date.now();

  // BEFORE log — no auth header value, no full provider_id
  console.info({
    event: 'discover_models.before',
    provider_id_prefix: truncatedId,
    request_id: requestId,
  });

  try {
    const response = await fetch(
      `${API_BASE}/admin/ai/providers/${providerId}/discover-models`,
      {
        method: 'POST',
        headers: {
          ...getAdminAuthHeader(),
          Accept: 'application/json',
          'X-Request-ID': requestId,
        },
      },
    );

    const latencyMs = Date.now() - startMs;

    if (response.ok) {
      const json = (await response.json()) as DiscoverModelsResponse;

      // AFTER log — latency + status, no payload that might contain secrets
      console.info({
        event: 'discover_models.after',
        status: response.status,
        latency_ms: latencyMs,
        request_id: requestId,
        added_count: json.data.added.length,
        existing_count: json.data.existing.length,
        skipped_count: json.data.skipped.length,
      });

      return { ok: true, value: json.data };
    }

    // Error response — map HTTP status to typed error code
    const errorCode = mapStatusToErrorCode(response.status);
    let errorMessage = `HTTP ${response.status}`;

    try {
      // Try to parse the FastAPI error envelope { detail: { error: { code, message } } }
      const errorBody = (await response.json()) as {
        detail?: { error?: { code?: string; message?: string } } | string;
      };
      if (
        typeof errorBody.detail === 'object' &&
        errorBody.detail !== null &&
        typeof errorBody.detail.error?.message === 'string'
      ) {
        errorMessage = errorBody.detail.error.message;
      }
    } catch {
      // JSON parse failed — keep the generic HTTP status message
    }

    // ERROR log — code + latency, no raw error body that might contain secrets
    console.warn({
      event: 'discover_models.error',
      error_code: errorCode,
      http_status: response.status,
      latency_ms: latencyMs,
      request_id: requestId,
    });

    return {
      ok: false,
      error: { code: errorCode, message: errorMessage, httpStatus: response.status },
    };
  } catch (err) {
    const latencyMs = Date.now() - startMs;

    // Network / transport error (fetch throws)
    const message = err instanceof Error ? err.message : 'Network error';

    console.warn({
      event: 'discover_models.error',
      error_code: 'network_error',
      latency_ms: latencyMs,
      request_id: requestId,
      reason: message,
    });

    return {
      ok: false,
      error: { code: 'network_error', message },
    };
  }
}
