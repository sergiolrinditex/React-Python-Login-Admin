/**
 * Hilo People — useModelTest presentation hook.
 *
 * Slice/Phase: P04-S01-T004 — ModelTestDrawer / Phase 4.
 * Write-set anchor: §D-T004-HOOK (authorized by task pack §6.2 file #4).
 *
 * Responsibility: Presentation logic for the ModelTestDrawer page.
 *   - Manages prompt state + local validation (1–4000 chars).
 *   - TanStack Query mutation for POST /models/{id}/test (testModel).
 *   - TanStack Query mutation for PATCH /models/{id} (updateModel → activate).
 *   - Exposes typed submissionState + activateState for UX state machine.
 *   - After activate success: invalidates ["admin","ai","models"] query cache.
 *
 * PII contract (§D-T004-PII):
 *   - NEVER log prompt content — only prompt_len.
 *   - NEVER log output content — only output_length, latency_ms, cost.
 *   - VITE_ENABLE_VERBOSE_LOGGING gate applied.
 *
 * Clean Architecture: PRESENTATION layer.
 *   Depends on: testModel, updateModel (DATA), AdminAi error types (DATA), AuthProvider (AUTH).
 *   Domain imports only types (no business logic from domain layer leaked here).
 *
 * Key deps: @tanstack/react-query ^5.x, react ^18.x, react-i18next.
 */

import { useState, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { testModel, updateModel } from "../data/adminAiRepository.test-and-update";
import {
  AdminAiValidationError,
  AdminAiForbiddenError,
  AdminAiUpstreamError,
  AdminAiNotFoundError,
  type AdminAiError,
} from "../data/errors";
import type { TestModelResponse, UpdateModelRequest } from "../domain/types";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Submission state machine for the test action.
 * Maps directly to data-testid UX markers (task pack §7).
 */
export type TestSubmissionState =
  | "idle"
  | "submitting"
  | "success"
  | "error_network"
  | "error_validation"
  | "error_upstream"
  | "permission_denied";

/**
 * State machine for the activate (PATCH) action.
 */
export type ActivateState =
  | "idle"
  | "pending"
  | "success"
  | "error";

/**
 * Per-field validation error for the prompt field.
 */
export interface TestFieldErrors {
  prompt?: string;
}

/**
 * Public return type of useModelTest.
 * Consumed by ModelTestDrawer.tsx page component.
 */
export interface UseModelTestResult {
  /** Current prompt value. */
  prompt: string;
  /** Update prompt value. */
  setPrompt: (value: string) => void;
  /** Whether the test mutation is in-flight. */
  isSubmitting: boolean;
  /** Typed submission state. */
  submissionState: TestSubmissionState;
  /** Result from a successful test call. */
  testResult: TestModelResponse | null;
  /** Per-field validation errors (prompt). */
  fieldErrors: TestFieldErrors;
  /** Submit the test prompt. */
  submit: () => void;
  /** Reset the submission state. */
  reset: () => void;
  /** Whether the activate mutation is in-flight. */
  isActivating: boolean;
  /** Typed activate state. */
  activateState: ActivateState;
  /** Trigger model activation (enabled=true, is_default=true). */
  activate: (patch?: UpdateModelRequest) => void;
}

// ---------------------------------------------------------------------------
// Validation helpers
// ---------------------------------------------------------------------------

/**
 * Validates the prompt field.
 * Returns an error message string or null if valid.
 */
function validatePrompt(prompt: string): string | null {
  if (!prompt.trim()) return "El prompt no puede estar vacío.";
  if (prompt.length > 4000) return "El prompt no puede superar los 4000 caracteres.";
  return null;
}

// ---------------------------------------------------------------------------
// Latency formatter (pure helper)
// ---------------------------------------------------------------------------

/**
 * Formats latency_ms for display.
 * < 1000 → "Xms"; >= 1000 → "X.Xs".
 *
 * @param ms - Latency in milliseconds.
 * @returns Formatted string.
 */
export function formatLatencyMs(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

/**
 * Formats estimated cost for display.
 * 0 or undefined → em-dash (§D-T002-COST-FORMAT).
 *
 * @param cost - Estimated cost in USD.
 * @returns Formatted string or "—".
 */
export function formatCostUsd(cost: number): string {
  if (cost === 0) return "—";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 6,
  }).format(cost);
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * useModelTest — presentation hook for ModelTestDrawer.
 *
 * Business rules:
 *   - Prompt must be 1–4000 chars (frontend validation mirrors backend Pydantic).
 *   - Empty prompt → sets fieldErrors.prompt; does NOT call testModel.
 *   - 403 response → permission_denied state (defensive; route guard already fired).
 *   - 502 response → error_upstream sub-state with specific copy.
 *   - 404 response → error_network (model not found).
 *   - After activate success → invalidates ["admin","ai","models"] cache so
 *     AdminAiModelsPage refetches on next focus.
 *
 * @param modelId - UUID of the model to test.
 * @returns UseModelTestResult
 */
export function useModelTest(modelId: string): UseModelTestResult {
  const { logout } = useAuth();
  const queryClient = useQueryClient();

  const [prompt, setPromptState] = useState<string>("");
  const [fieldErrors, setFieldErrors] = useState<TestFieldErrors>({});
  const [submissionState, setSubmissionState] = useState<TestSubmissionState>("idle");
  const [testResult, setTestResult] = useState<TestModelResponse | null>(null);
  const [activateState, setActivateState] = useState<ActivateState>("idle");

  const onAuthFailure = useCallback(() => {
    logWarn("admin-ai.hook.useModelTest.auth_expired", {});
    logout();
  }, [logout]);

  // ---- Test mutation -------------------------------------------------------

  const testMutation = useMutation({
    mutationFn: (promptText: string) =>
      testModel(modelId, { prompt: promptText }, onAuthFailure),
    onMutate: () => {
      logVerbose("admin-ai.hook.useModelTest.submit.start", {
        prompt_len: prompt.length,
      });
      setSubmissionState("submitting");
      setFieldErrors({});
      setTestResult(null);
    },
    onSuccess: (result) => {
      if (result.ok) {
        logVerbose("admin-ai.hook.useModelTest.submit.ok", {
          latency_ms: result.value.latency_ms,
          cost: result.value.cost,
          output_length: result.value.output.length,
        });
        setTestResult(result.value);
        setSubmissionState("success");
      } else {
        handleTestError(result.error);
      }
    },
    onError: (err: unknown) => {
      logError("admin-ai.hook.useModelTest.submit.error", {
        error_class: err instanceof Error ? err.constructor.name : "unknown",
      });
      setSubmissionState("error_network");
    },
  });

  // ---- Activate mutation ---------------------------------------------------

  const activateMutation = useMutation({
    mutationFn: (patch: UpdateModelRequest) =>
      updateModel(modelId, patch, onAuthFailure),
    onMutate: () => {
      logVerbose("admin-ai.hook.useModelTest.activate.start", {});
      setActivateState("pending");
    },
    onSuccess: (result) => {
      if (result.ok) {
        logVerbose("admin-ai.hook.useModelTest.activate.ok", {
          enabled: result.value.enabled,
          is_default: result.value.is_default,
        });
        setActivateState("success");
        // Invalidate model list cache so AdminAiModelsPage reflects new default.
        queryClient.invalidateQueries({ queryKey: ["admin", "ai", "models"] }).catch(() => {});
      } else {
        logError("admin-ai.hook.useModelTest.activate.error", {
          error_class: result.error.constructor.name,
        });
        setActivateState("error");
      }
    },
    onError: (err: unknown) => {
      logError("admin-ai.hook.useModelTest.activate.network_error", {
        error_class: err instanceof Error ? err.constructor.name : "unknown",
      });
      setActivateState("error");
    },
  });

  // ---- Internal: handle test errors ---------------------------------------

  function handleTestError(error: AdminAiError): void {
    if (error instanceof AdminAiForbiddenError) {
      logWarn("admin-ai.hook.useModelTest.submit.forbidden", {});
      setSubmissionState("permission_denied");
      return;
    }
    if (error instanceof AdminAiUpstreamError) {
      logError("admin-ai.hook.useModelTest.submit.upstream", {
        status: error.status,
      });
      setSubmissionState("error_upstream");
      return;
    }
    if (error instanceof AdminAiValidationError) {
      logError("admin-ai.hook.useModelTest.submit.validation_error", {
        server_code: error.serverCode,
        field_count: error.fieldErrors?.length ?? 0,
      });
      if (error.fieldErrors && error.fieldErrors.length > 0) {
        const newErrors: TestFieldErrors = {};
        for (const fe of error.fieldErrors) {
          if (fe.field === "prompt") newErrors.prompt = fe.message;
        }
        if (Object.keys(newErrors).length === 0) newErrors.prompt = error.message;
        setFieldErrors(newErrors);
      } else {
        setFieldErrors({ prompt: error.message });
      }
      setSubmissionState("error_validation");
      return;
    }
    if (error instanceof AdminAiNotFoundError) {
      logWarn("admin-ai.hook.useModelTest.submit.not_found", {});
      setSubmissionState("error_network");
      return;
    }
    logError("admin-ai.hook.useModelTest.submit.error", {
      error_class: error.constructor.name,
    });
    setSubmissionState("error_network");
  }

  // ---- Public API ---------------------------------------------------------

  const setPrompt = useCallback((value: string) => {
    setPromptState(value);
    // Clear field error on change
    if (fieldErrors.prompt) setFieldErrors({});
  }, [fieldErrors.prompt]);

  const submit = useCallback(() => {
    const validationError = validatePrompt(prompt);
    if (validationError) {
      logVerbose("admin-ai.hook.useModelTest.submit.validation_frontend", {
        prompt_len: prompt.length,
      });
      setFieldErrors({ prompt: validationError });
      setSubmissionState("error_validation");
      return;
    }
    testMutation.mutate(prompt);
  }, [prompt, testMutation]);

  const reset = useCallback(() => {
    logVerbose("admin-ai.hook.useModelTest.reset", {});
    setSubmissionState("idle");
    setTestResult(null);
    setFieldErrors({});
    setActivateState("idle");
  }, []);

  const activate = useCallback((patch?: UpdateModelRequest) => {
    activateMutation.mutate(patch ?? { enabled: true, is_default: true });
  }, [activateMutation]);

  return {
    prompt,
    setPrompt,
    isSubmitting: testMutation.isPending,
    submissionState,
    testResult,
    fieldErrors,
    submit,
    reset,
    isActivating: activateMutation.isPending,
    activateState,
    activate,
  };
}
