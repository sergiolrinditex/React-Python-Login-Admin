/**
 * Hilo People — Admin AI repository (concrete HTTP adapter).
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 *   Extended in P04-S01-T002 (§D-T002-FEATURE-DATA): getProviders + getModels added.
 *   Extended in P04-S01-T003 (§D-T003-CREATE-PROVIDER): createProvider added.
 * Write-set anchor: §D-T001-ADMINAI-FEATURE, §D-T002-FEATURE-DATA, §D-T003-CREATE-PROVIDER
 *
 * Responsibility: Fetches data from /api/v1/admin/* via authFetch.
 *   Returns Result<T, AdminAiError> — never throws to presentation layer.
 *   Mirrors chatRepository.ts pattern: BEFORE/AFTER/ERROR logging, Result shape.
 *
 * Clean Architecture: this is the DATA layer for the admin-ai feature.
 *   Presentation hooks depend on this module, not the raw HTTP client.
 *
 * Security:
 *   - Uses authFetch (X-Request-ID, credentials:include, Bearer injection, single-flight 401).
 *   - Relative URL per ADR-002 (same-origin via vite proxy in dev, Nginx in prod).
 *   - NEVER hardcode http://localhost:8000 here.
 *   - PII-clean logs (§D-T002-LOGS-PII-CLEAN): no provider names, no base_url contents,
 *     no credential metadata, no model_ids in error logs.
 *     Log only: provider_count, model_count, error class name, request IDs.
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public method.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type {
  GetUsageRequest,
  UsageSummary,
  AiProvider,
  AiModel,
  CreateProviderRequest,
} from "../domain/types";
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
  type ValidationFieldError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const USAGE_URL = "/api/v1/admin/usage";
// §D-T002-FEATURE-DATA — ADR-002 relative URLs (same-origin)
const PROVIDERS_URL = "/api/v1/admin/ai/providers";
const MODELS_URL = "/api/v1/admin/ai/models";

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

// ---------------------------------------------------------------------------
// Public: getProviders (§D-T002-FEATURE-DATA)
// ---------------------------------------------------------------------------

/**
 * Fetches AI provider list from GET /api/v1/admin/ai/providers.
 *
 * Source: TECHNICAL_GUIDE §6.2, backend ProviderOut shape. ADR-002 relative URL.
 * Returns a Result — never throws upward.
 *
 * PII-clean logs (§D-T002-LOGS-PII-CLEAN): logs provider_count and request_id only.
 * NEVER logs provider names, base_url, credential_auth_type, or created_by.
 *
 * Status mapping:
 *   200 OK         → Result.ok(AiProvider[])
 *   401            → Result.err(AdminAiAuthExpiredError)  — authFetch already retried
 *   403            → Result.err(AdminAiForbiddenError)
 *   5xx            → Result.err(AdminAiInternalError)
 *   network reject → Result.err(AdminAiNetworkError)
 *
 * @param onAuthFailure - Called when session is fully expired.
 * @param signal - Optional AbortSignal for cancellation.
 * @returns Result<AiProvider[], AdminAiError>
 */
export async function getProviders(
  onAuthFailure: () => void,
  signal?: AbortSignal,
): Promise<Result<AiProvider[], AdminAiError>> {
  logVerbose("admin-ai.repo.getProviders.start", {});

  try {
    const response = await authFetch(
      PROVIDERS_URL,
      { method: "GET", signal },
      { onAuthFailure },
    );
    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("admin-ai.repo.getProviders.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("admin-ai.repo.getProviders.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiForbiddenError() };
    }

    if (response.status >= 500) {
      logError("admin-ai.repo.getProviders.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiInternalError(response.status) };
    }

    if (!response.ok) {
      logError("admin-ai.repo.getProviders.unexpected_status", {
        status: response.status,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AdminAiNetworkError(`Unexpected status ${response.status}`),
      };
    }

    const body = await _safeJson<{ data: AiProvider[]; meta?: { request_id?: string } }>(response);
    const providers = body.data;

    // PII-clean: log count only — never provider names or credentials
    logVerbose("admin-ai.repo.getProviders.ok", {
      provider_count: providers.length,
      request_id: requestId,
    });

    return { ok: true, value: providers };
  } catch (err: unknown) {
    if (err instanceof AdminAiAuthExpiredError) return { ok: false, error: err };
    if (err instanceof AdminAiForbiddenError) return { ok: false, error: err };
    if (err instanceof AuthSessionExpiredError) {
      logWarn("admin-ai.repo.getProviders.auth_expired_via_client", {});
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }
    const mapped = mapAdminAiError(err);
    logError("admin-ai.repo.getProviders.network_error", {
      error_class: mapped.constructor.name,
    });
    return { ok: false, error: mapped };
  }
}

// ---------------------------------------------------------------------------
// Public: getModels (§D-T002-FEATURE-DATA)
// ---------------------------------------------------------------------------

/**
 * Optional filter parameters for getModels.
 * provider_id is future-proofed for T003 (not passed by AdminAiModelsPage v1).
 */
export interface GetModelsParams {
  /** Optional UUID to filter models by provider. Not used by AdminAiModelsPage v1. */
  provider_id?: string;
}

/**
 * Fetches AI model list from GET /api/v1/admin/ai/models.
 *
 * Source: TECHNICAL_GUIDE §6.2, backend ModelOut shape. ADR-002 relative URL.
 * Returns a Result — never throws upward.
 *
 * PII-clean logs (§D-T002-LOGS-PII-CLEAN): logs model_count and request_id only.
 * NEVER logs model_ids, provider names, pricing values, or capabilities.
 *
 * Status mapping:
 *   200 OK         → Result.ok(AiModel[])
 *   401            → Result.err(AdminAiAuthExpiredError)
 *   403            → Result.err(AdminAiForbiddenError)
 *   5xx            → Result.err(AdminAiInternalError)
 *   network reject → Result.err(AdminAiNetworkError)
 *
 * @param params - Optional filter parameters (provider_id for future T003).
 * @param onAuthFailure - Called when session is fully expired.
 * @param signal - Optional AbortSignal for cancellation.
 * @returns Result<AiModel[], AdminAiError>
 */
export async function getModels(
  params: GetModelsParams | undefined,
  onAuthFailure: () => void,
  signal?: AbortSignal,
): Promise<Result<AiModel[], AdminAiError>> {
  const query = params?.provider_id
    ? new URLSearchParams({ provider_id: params.provider_id })
    : null;
  const url = query ? `${MODELS_URL}?${query.toString()}` : MODELS_URL;

  logVerbose("admin-ai.repo.getModels.start", {
    has_provider_filter: Boolean(params?.provider_id),
  });

  try {
    const response = await authFetch(
      url,
      { method: "GET", signal },
      { onAuthFailure },
    );
    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("admin-ai.repo.getModels.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("admin-ai.repo.getModels.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiForbiddenError() };
    }

    if (response.status >= 500) {
      logError("admin-ai.repo.getModels.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiInternalError(response.status) };
    }

    if (!response.ok) {
      logError("admin-ai.repo.getModels.unexpected_status", {
        status: response.status,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AdminAiNetworkError(`Unexpected status ${response.status}`),
      };
    }

    const body = await _safeJson<{ data: AiModel[]; meta?: { request_id?: string } }>(response);
    const models = body.data;

    // PII-clean: log count only — never model_ids or pricing
    logVerbose("admin-ai.repo.getModels.ok", {
      model_count: models.length,
      request_id: requestId,
    });

    return { ok: true, value: models };
  } catch (err: unknown) {
    if (err instanceof AdminAiAuthExpiredError) return { ok: false, error: err };
    if (err instanceof AdminAiForbiddenError) return { ok: false, error: err };
    if (err instanceof AuthSessionExpiredError) {
      logWarn("admin-ai.repo.getModels.auth_expired_via_client", {});
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }
    const mapped = mapAdminAiError(err);
    logError("admin-ai.repo.getModels.network_error", {
      error_class: mapped.constructor.name,
    });
    return { ok: false, error: mapped };
  }
}

// ---------------------------------------------------------------------------
// Public: createProvider (§D-T003-CREATE-PROVIDER)
// ---------------------------------------------------------------------------

/**
 * Creates a new AI provider via POST /api/v1/admin/ai/providers.
 *
 * Source: TECHNICAL_GUIDE §6.2, backend CreateProviderRequest / ProviderOut schema.
 * ADR-002 relative URL (same-origin via vite proxy in dev, Nginx in prod).
 * Returns a Result — never throws upward.
 *
 * SECURITY: payload.credentials.secret_plain is a live secret.
 *   - NEVER logged — only provider_type, auth_type, name_len, request_id logged.
 *   - Caller is responsible for zeroing state after calling this function.
 *
 * Status mapping:
 *   201 Created     → Result.ok(AiProvider) — ProviderOut without secret_plain
 *   400             → Result.err(AdminAiValidationError) — bad request
 *   401             → Result.err(AdminAiAuthExpiredError)
 *   403             → Result.err(AdminAiForbiddenError)
 *   409             → Result.err(AdminAiValidationError) — duplicate name
 *   422             → Result.err(AdminAiValidationError) with parsed fieldErrors[]
 *   5xx             → Result.err(AdminAiInternalError)
 *   network reject  → Result.err(AdminAiNetworkError)
 *
 * @param payload - Provider creation request (name, provider_type, credentials).
 * @param onAuthFailure - Called when session is fully expired.
 * @returns Result<AiProvider, AdminAiError>
 */
export async function createProvider(
  payload: CreateProviderRequest,
  onAuthFailure: () => void,
): Promise<Result<AiProvider, AdminAiError>> {
  // BEFORE log — PII-clean: log provider_type, auth_type, name length only.
  // NEVER log secret_plain, name value, base_url, or any PII.
  logVerbose("admin-ai.repo.createProvider.start", {
    provider_type: payload.provider_type,
    auth_type: payload.credentials.auth_type,
    name_len: payload.name.length,
  });

  // Build a PII-clean request body — secret_plain travels to backend but never to logs
  const requestBody = {
    provider_type: payload.provider_type,
    name: payload.name,
    base_url: payload.base_url ?? null,
    credentials: {
      auth_type: payload.credentials.auth_type,
      secret_plain: payload.credentials.secret_plain,
      refresh_token_plain: payload.credentials.refresh_token_plain ?? null,
      expires_at: payload.credentials.expires_at ?? null,
    },
  };

  try {
    const response = await authFetch(
      PROVIDERS_URL,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(requestBody),
      },
      { onAuthFailure },
    );
    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("admin-ai.repo.createProvider.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("admin-ai.repo.createProvider.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiForbiddenError() };
    }

    if (response.status === 400 || response.status === 409) {
      let serverCode = "ADMIN_PROVIDER_BAD_REQUEST";
      try {
        const errBody = await _safeJson<{
          error?: string;
          code?: string;
          errors?: Array<{ code?: string; field?: string; message?: string }>;
        }>(response);
        serverCode =
          errBody.code ??
          errBody.errors?.[0]?.code ??
          (response.status === 409 ? "ADMIN_PROVIDER_DUPLICATE_NAME" : serverCode);
      } catch {
        // Ignore parse error — use default code
      }
      logError("admin-ai.repo.createProvider.bad_request", {
        status: response.status,
        server_code: serverCode,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AdminAiValidationError(
          serverCode,
          response.status === 409
            ? "A provider with this name already exists."
            : "Invalid request.",
        ),
      };
    }

    if (response.status === 422) {
      let serverCode = "ADMIN_PROVIDER_VALIDATION_ERROR";
      let fieldErrors: ValidationFieldError[] | undefined;
      try {
        const errBody = await _safeJson<{
          error?: string;
          code?: string;
          errors?: Array<{ code?: string; field?: string; message?: string }>;
        }>(response);
        serverCode = errBody.code ?? errBody.errors?.[0]?.code ?? serverCode;
        if (errBody.errors && errBody.errors.length > 0) {
          fieldErrors = errBody.errors.map((e) => ({
            field: e.field ?? "unknown",
            code: e.code ?? "INVALID",
            message: e.message ?? "Invalid value.",
          }));
        }
      } catch {
        // Ignore parse error — use defaults
      }
      logError("admin-ai.repo.createProvider.validation_error", {
        status: 422,
        server_code: serverCode,
        request_id: requestId,
        field_count: fieldErrors?.length ?? 0,
      });
      return {
        ok: false,
        error: new AdminAiValidationError(serverCode, "Validation failed.", fieldErrors),
      };
    }

    if (response.status >= 500) {
      logError("admin-ai.repo.createProvider.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiInternalError(response.status) };
    }

    if (response.status !== 201 && !response.ok) {
      logError("admin-ai.repo.createProvider.unexpected_status", {
        status: response.status,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AdminAiNetworkError(`Unexpected status ${response.status}`),
      };
    }

    const body = await _safeJson<{ data: AiProvider; meta?: { request_id?: string } }>(response);
    const provider = body.data;

    // PII-clean AFTER log — provider_type + id only, NEVER name or credentials
    logVerbose("admin-ai.repo.createProvider.ok", {
      provider_type: provider.provider_type,
      status: provider.status,
      request_id: requestId,
    });

    return { ok: true, value: provider };
  } catch (err: unknown) {
    if (err instanceof AdminAiAuthExpiredError) return { ok: false, error: err };
    if (err instanceof AdminAiForbiddenError) return { ok: false, error: err };
    if (err instanceof AuthSessionExpiredError) {
      logWarn("admin-ai.repo.createProvider.auth_expired_via_client", {});
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }
    const mapped = mapAdminAiError(err);
    logError("admin-ai.repo.createProvider.network_error", {
      error_class: mapped.constructor.name,
    });
    return { ok: false, error: mapped };
  }
}
