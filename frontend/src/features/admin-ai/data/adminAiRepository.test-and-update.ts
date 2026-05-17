/**
 * Hilo People — Admin AI repository extension: testModel + updateModel.
 *
 * Slice/Phase: P04-S01-T004 — ModelTestDrawer / Phase 4.
 * Write-set anchor: §D-T004-MODELTEST (authorized by task pack §6.2 — split from main repo
 *   because adminAiRepository.ts is at the ~300-line hard cap after T003 extensions).
 *
 * Responsibility: HTTP adapter for model test + model update operations.
 *   testModel  → POST /api/v1/admin/ai/models/{id}/test
 *   updateModel → PATCH /api/v1/admin/ai/models/{id}
 *
 *   Returns Result<T, AdminAiError> — never throws to presentation layer.
 *   Mirrors the same BEFORE/AFTER/ERROR logging contract as adminAiRepository.ts.
 *
 * PII contract (§D-T004-PII):
 *   - NEVER log prompt content or model output content.
 *   - Log only: model_id (excluded), prompt_len, output_length, latency_ms, cost,
 *     request_id, error_class, status.
 *   - Verified by test T36 (console spy on prompt/output strings).
 *
 * Clean Architecture: DATA layer only. Presentation hooks depend on this, not raw HTTP.
 * Security: authFetch (X-Request-ID, credentials:include, Bearer injection, single-flight 401).
 *   Relative URL per ADR-002 (same-origin).
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type {
  TestModelRequest,
  TestModelResponse,
  UpdateModelRequest,
  AiModel,
} from "../domain/types";
import { authFetch } from "../../auth/data/httpClient";
import { AuthSessionExpiredError } from "../../auth/data/errors";
import {
  AdminAiAuthExpiredError,
  AdminAiForbiddenError,
  AdminAiValidationError,
  AdminAiNetworkError,
  AdminAiInternalError,
  AdminAiNotFoundError,
  AdminAiUpstreamError,
  mapAdminAiError,
  type AdminAiError,
  type ValidationFieldError,
} from "./errors";
import { logVerbose, logWarn, logError } from "./logger";

// ---------------------------------------------------------------------------
// Constants — ADR-002 relative URLs
// ---------------------------------------------------------------------------

const MODELS_BASE_URL = "/api/v1/admin/ai/models";

// ---------------------------------------------------------------------------
// Helper: safely parse response JSON
// ---------------------------------------------------------------------------

async function _safeJson<T>(res: Response): Promise<T> {
  const text = await res.text();
  if (!text) throw new Error("Empty response body");
  return JSON.parse(text) as T;
}

// ---------------------------------------------------------------------------
// Public: testModel
// ---------------------------------------------------------------------------

/**
 * Tests a model via POST /api/v1/admin/ai/models/{id}/test.
 *
 * Source: TECHNICAL_GUIDE §6.2. Returns a Result — never throws upward.
 * Side effects on success: backend writes ai_model_tests row + llm_usage_logs row
 *   + audit_logs row (action: model.test).
 *
 * PII-clean logs (§D-T004-PII): NEVER log prompt content or output content.
 * Only log: prompt_len, status, latency_ms, cost, request_id, error_class.
 *
 * Status mapping:
 *   200 OK         → Result.ok(TestModelResponse)
 *   400/422        → Result.err(AdminAiValidationError) with optional fieldErrors
 *   401            → Result.err(AdminAiAuthExpiredError)
 *   403            → Result.err(AdminAiForbiddenError)
 *   404            → Result.err(AdminAiNotFoundError)
 *   502            → Result.err(AdminAiUpstreamError) — LiteLLM proxy failure
 *   5xx            → Result.err(AdminAiInternalError)
 *   network reject → Result.err(AdminAiNetworkError)
 *
 * @param modelId - UUID of the model to test.
 * @param payload - TestModelRequest with prompt string (1–4000 chars).
 * @param onAuthFailure - Called when session is fully expired.
 * @param signal - Optional AbortSignal for cancellation.
 * @returns Result<TestModelResponse, AdminAiError>
 */
export async function testModel(
  modelId: string,
  payload: TestModelRequest,
  onAuthFailure: () => void,
  signal?: AbortSignal,
): Promise<Result<TestModelResponse, AdminAiError>> {
  // BEFORE log — PII-clean: log prompt_len only, NEVER the prompt content.
  logVerbose("admin-ai.repo.testModel.start", {
    prompt_len: payload.prompt.length,
  });

  const url = `${MODELS_BASE_URL}/${modelId}/test`;

  try {
    const response = await authFetch(
      url,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ prompt: payload.prompt }),
        signal,
      },
      { onAuthFailure },
    );
    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("admin-ai.repo.testModel.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("admin-ai.repo.testModel.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiForbiddenError() };
    }

    if (response.status === 404) {
      logWarn("admin-ai.repo.testModel.not_found", {
        status: 404,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiNotFoundError("Model not found.") };
    }

    if (response.status === 502) {
      // LiteLLM proxy upstream failure — specific copy required by task pack §3.
      logError("admin-ai.repo.testModel.upstream_error", {
        status: 502,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiUpstreamError() };
    }

    if (response.status === 400) {
      let serverCode = "MODEL_TEST_BAD_PROMPT";
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
            field: e.field ?? "prompt",
            code: e.code ?? "INVALID",
            message: e.message ?? "Invalid value.",
          }));
        }
      } catch {
        // Ignore parse error — use defaults
      }
      logError("admin-ai.repo.testModel.bad_request", {
        status: 400,
        server_code: serverCode,
        request_id: requestId,
        field_count: fieldErrors?.length ?? 0,
      });
      return {
        ok: false,
        error: new AdminAiValidationError(serverCode, "Invalid prompt.", fieldErrors),
      };
    }

    if (response.status === 422) {
      let serverCode = "MODEL_TEST_VALIDATION_ERROR";
      let fieldErrors: ValidationFieldError[] | undefined;
      try {
        const errBody = await _safeJson<{
          detail?: Array<{ loc?: string[]; msg?: string; type?: string }>;
          error?: string;
          code?: string;
          errors?: Array<{ code?: string; field?: string; message?: string }>;
        }>(response);
        // Handle Pydantic native shape {detail:[{loc,msg,type}]}
        if (errBody.detail && Array.isArray(errBody.detail)) {
          fieldErrors = errBody.detail.map((d) => ({
            field: d.loc ? d.loc[d.loc.length - 1] ?? "prompt" : "prompt",
            code: d.type ?? "INVALID",
            message: d.msg ?? "Invalid value.",
          }));
        } else if (errBody.errors && errBody.errors.length > 0) {
          serverCode = errBody.code ?? errBody.errors[0]?.code ?? serverCode;
          fieldErrors = errBody.errors.map((e) => ({
            field: e.field ?? "prompt",
            code: e.code ?? "INVALID",
            message: e.message ?? "Invalid value.",
          }));
        }
      } catch {
        // Ignore parse error — use defaults
      }
      logError("admin-ai.repo.testModel.validation_error", {
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
      logError("admin-ai.repo.testModel.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiInternalError(response.status) };
    }

    if (!response.ok) {
      logError("admin-ai.repo.testModel.unexpected_status", {
        status: response.status,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AdminAiNetworkError(`Unexpected status ${response.status}`),
      };
    }

    const body = await _safeJson<{ data: TestModelResponse }>(response);
    const result = body.data;

    // AFTER log — PII-clean: log latency_ms + cost + output_length; NEVER output content.
    logVerbose("admin-ai.repo.testModel.ok", {
      latency_ms: result.latency_ms,
      cost: result.cost,
      output_length: result.output.length,
      request_id: requestId,
    });

    return { ok: true, value: result };
  } catch (err: unknown) {
    if (err instanceof AdminAiAuthExpiredError) return { ok: false, error: err };
    if (err instanceof AdminAiForbiddenError) return { ok: false, error: err };
    if (err instanceof AdminAiUpstreamError) return { ok: false, error: err };
    if (err instanceof AuthSessionExpiredError) {
      logWarn("admin-ai.repo.testModel.auth_expired_via_client", {});
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }
    const mapped = mapAdminAiError(err);
    logError("admin-ai.repo.testModel.network_error", {
      error_class: mapped.constructor.name,
    });
    return { ok: false, error: mapped };
  }
}

// ---------------------------------------------------------------------------
// Public: updateModel
// ---------------------------------------------------------------------------

/**
 * Updates a model's enabled/is_default flags via PATCH /api/v1/admin/ai/models/{id}.
 *
 * Source: TECHNICAL_GUIDE §6.2. Returns a Result — never throws upward.
 * Side effects on success: backend updates ai_models row + audit_logs row (action: model.update).
 *
 * Status mapping:
 *   200 OK         → Result.ok(AiModel)
 *   400/422        → Result.err(AdminAiValidationError)
 *   401            → Result.err(AdminAiAuthExpiredError)
 *   403            → Result.err(AdminAiForbiddenError)
 *   404            → Result.err(AdminAiNotFoundError)
 *   5xx            → Result.err(AdminAiInternalError)
 *   network reject → Result.err(AdminAiNetworkError)
 *
 * @param modelId - UUID of the model to update.
 * @param patch - Partial update payload (enabled, is_default).
 * @param onAuthFailure - Called when session is fully expired.
 * @param signal - Optional AbortSignal for cancellation.
 * @returns Result<AiModel, AdminAiError>
 */
export async function updateModel(
  modelId: string,
  patch: UpdateModelRequest,
  onAuthFailure: () => void,
  signal?: AbortSignal,
): Promise<Result<AiModel, AdminAiError>> {
  logVerbose("admin-ai.repo.updateModel.start", {
    has_enabled: patch.enabled !== undefined,
    has_is_default: patch.is_default !== undefined,
  });

  const url = `${MODELS_BASE_URL}/${modelId}`;

  try {
    const response = await authFetch(
      url,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(patch),
        signal,
      },
      { onAuthFailure },
    );
    const requestId = response.headers.get("x-request-id") ?? "unknown";

    if (response.status === 401) {
      logWarn("admin-ai.repo.updateModel.auth_expired", {
        status: 401,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }

    if (response.status === 403) {
      logWarn("admin-ai.repo.updateModel.forbidden", {
        status: 403,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiForbiddenError() };
    }

    if (response.status === 404) {
      logWarn("admin-ai.repo.updateModel.not_found", {
        status: 404,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiNotFoundError("Model not found.") };
    }

    if (response.status === 400 || response.status === 422) {
      let serverCode = "MODEL_UPDATE_BAD_PAYLOAD";
      try {
        const errBody = await _safeJson<{ code?: string; error?: string }>(response);
        serverCode = errBody.code ?? serverCode;
      } catch {
        // Ignore parse error
      }
      logError("admin-ai.repo.updateModel.validation_error", {
        status: response.status,
        server_code: serverCode,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AdminAiValidationError(serverCode, "Invalid update payload."),
      };
    }

    if (response.status >= 500) {
      logError("admin-ai.repo.updateModel.server_error", {
        status: response.status,
        request_id: requestId,
      });
      return { ok: false, error: new AdminAiInternalError(response.status) };
    }

    if (!response.ok) {
      logError("admin-ai.repo.updateModel.unexpected_status", {
        status: response.status,
        request_id: requestId,
      });
      return {
        ok: false,
        error: new AdminAiNetworkError(`Unexpected status ${response.status}`),
      };
    }

    const body = await _safeJson<{ data: AiModel }>(response);
    const model = body.data;

    logVerbose("admin-ai.repo.updateModel.ok", {
      enabled: model.enabled,
      is_default: model.is_default,
      request_id: requestId,
    });

    return { ok: true, value: model };
  } catch (err: unknown) {
    if (err instanceof AdminAiAuthExpiredError) return { ok: false, error: err };
    if (err instanceof AdminAiForbiddenError) return { ok: false, error: err };
    if (err instanceof AuthSessionExpiredError) {
      logWarn("admin-ai.repo.updateModel.auth_expired_via_client", {});
      return { ok: false, error: new AdminAiAuthExpiredError() };
    }
    const mapped = mapAdminAiError(err);
    logError("admin-ai.repo.updateModel.network_error", {
      error_class: mapped.constructor.name,
    });
    return { ok: false, error: mapped };
  }
}
