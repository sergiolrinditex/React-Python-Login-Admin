/**
 * Hilo People — useModelWizard public types.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-WIZARD-HOOK-TYPES
 *
 * Responsibility: Public types + the submit-error → submission-state classifier
 *   extracted from useModelWizard.ts to keep the hook within the ~300-line cap
 *   declared in `.claude/rules/01-non-negotiables.md §file-size`. Pure module —
 *   no React, no side effects.
 *
 * Consumers: useModelWizard.ts (this slice). Public types are re-exported from
 *   useModelWizard.ts for backward-compatible imports across page + tests.
 *
 * Key deps: ../data/errors, ../domain/types.
 */

import {
  AdminAiForbiddenError,
  AdminAiNetworkError,
  AdminAiInternalError,
  AdminAiValidationError,
  type AdminAiError,
} from "../data/errors";
import type {
  WizardStep,
  WizardFormState,
  WizardFieldErrors,
  AiModel,
  AiProvider,
} from "../domain/types";

// ---------------------------------------------------------------------------
// Submission state
// ---------------------------------------------------------------------------

export type SubmissionState =
  | "idle"
  | "submitting"
  | "success"
  | "error_network"
  | "error_validation"
  | "permission_denied";

// ---------------------------------------------------------------------------
// Initial form state
// ---------------------------------------------------------------------------

export const INITIAL_FORM: WizardFormState = {
  provider_type: "",
  name: "",
  base_url: "",
  auth_type: "api_key",
  secret_plain: "",
};

// ---------------------------------------------------------------------------
// Hook result type
// ---------------------------------------------------------------------------

export interface UseModelWizardResult {
  /** Current step in the wizard. */
  step: WizardStep;
  /** Current form state (without secret_plain exposed). */
  form: Omit<WizardFormState, "secret_plain">;
  /** Whether the credential input currently has a non-empty value (never exposes value). */
  hasSecret: boolean;
  /** Masked display of the secret (last 4 chars only — safe for UI). */
  maskedSecret: string;
  /** Per-field validation errors. */
  fieldErrors: WizardFieldErrors;
  /** Server-side error from the last submit attempt. */
  submitError: AdminAiError | null;
  /** Submission lifecycle state. */
  submissionState: SubmissionState;
  /** Created provider after success. */
  createdProvider: AiProvider | null;
  /** Models for the created provider (populated after POST success). */
  providerModels: AiModel[];
  /** Whether models are loading (after provider create). */
  areModelsLoading: boolean;
  /** Move to the next wizard step (validates current). */
  goNext: () => void;
  /** Move to the previous step. */
  goBack: () => void;
  /** Update a form field (excluding secret_plain — use setSecret for that). */
  setField: (field: keyof Omit<WizardFormState, "secret_plain">, value: string) => void;
  /** Update secret_plain (kept separate for type safety and auditing). */
  setSecret: (value: string) => void;
  /** Submit the form (step 'credentials' → POST → models step). */
  submit: () => void;
  /** Reset the entire wizard to initial state (also clears secret). */
  reset: () => void;
}

// ---------------------------------------------------------------------------
// Submit-error classifier (pure)
// ---------------------------------------------------------------------------

/**
 * Maps a typed AdminAiError into the matching submissionState + per-field errors.
 * Pure — no React, no state writes. Returned object is consumed by the hook's
 * mutation onError callback to update local state in one batch.
 */
export function classifySubmitError(
  err: AdminAiError,
): { state: SubmissionState; fieldErrors: WizardFieldErrors } {
  if (err instanceof AdminAiForbiddenError) {
    return { state: "permission_denied", fieldErrors: {} };
  }
  if (err instanceof AdminAiValidationError) {
    const fieldErrors: WizardFieldErrors = {};
    if (err.fieldErrors && err.fieldErrors.length > 0) {
      for (const fe of err.fieldErrors) {
        const key = fe.field as keyof WizardFieldErrors;
        if (key in INITIAL_FORM) {
          fieldErrors[key] = fe.message;
        }
      }
    }
    return { state: "error_validation", fieldErrors };
  }
  if (err instanceof AdminAiNetworkError || err instanceof AdminAiInternalError) {
    return { state: "error_network", fieldErrors: {} };
  }
  return { state: "error_network", fieldErrors: {} };
}
