/**
 * Hilo People — useModelWizard presentation hook.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-WIZARD-HOOK
 *
 * Responsibility: Wizard step machine + form state + submit mutation
 *   (TanStack useMutation) + the models query filtered by the newly created
 *   provider_id.
 *
 *   Pure helpers (validators + masked-secret formatter) live in
 *   ./useModelWizard.helpers.ts. Public types + the submit-error classifier
 *   live in ./useModelWizard.types.ts. Both modules are re-exported from this
 *   file for backward-compatible imports.
 *
 * Step machine: provider → credentials → submitting → models → success.
 *   Error states (error_network, error_validation, permission_denied) are
 *   surfaced via `submitError` + `submissionState`, not via a separate step.
 *
 * Security: secret_plain lives ONLY in this hook's state. Cleared on success,
 *   on unmount, and NEVER serialized to storage or log (§D-T003-LOGS-PII-CLEAN).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR on every public action,
 *   gated by VITE_ENABLE_VERBOSE_LOGGING. NEVER log secret_plain.
 *
 * Key deps: @tanstack/react-query v5, adminAiRepository, AuthProvider,
 *   ./useModelWizard.helpers, ./useModelWizard.types.
 */

import { useState, useCallback, useEffect } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { createProvider, getModels } from "../data/adminAiRepository";
import { type AdminAiError } from "../data/errors";
import type {
  WizardStep,
  WizardFormState,
  WizardFieldErrors,
  AiModel,
  CreateProviderRequest,
  ProviderCredentialsInput,
  AiProvider,
} from "../domain/types";
import { logVerbose, logWarn, logError } from "../data/logger";
import {
  validateProviderType,
  validateName,
  validateSecret,
  validateAuthType,
  formatMaskedSecret,
} from "./useModelWizard.helpers";
import {
  INITIAL_FORM,
  classifySubmitError,
  type SubmissionState,
  type UseModelWizardResult,
} from "./useModelWizard.types";

// Re-export pure helpers + public types so existing test imports stay stable.
export {
  validateProviderType,
  validateName,
  validateSecret,
  validateAuthType,
  formatMaskedSecret,
};
export type { SubmissionState, UseModelWizardResult };

const MODELS_GC_TIME_MS = 120_000;

/**
 * Wizard state machine for ModelWizardPage.
 *
 * @returns UseModelWizardResult
 */
export function useModelWizard(): UseModelWizardResult {
  const { logout } = useAuth();
  const queryClient = useQueryClient();

  const onAuthFailure = useCallback(() => {
    logWarn("admin-ai.hook.useModelWizard.auth_failure");
    void logout();
  }, [logout]);

  logVerbose("admin-ai.hook.useModelWizard.render.start", {});

  const [step, setStep] = useState<WizardStep>("provider");
  const [form, setForm] = useState<WizardFormState>(INITIAL_FORM);
  const [fieldErrors, setFieldErrors] = useState<WizardFieldErrors>({});
  const [submitError, setSubmitError] = useState<AdminAiError | null>(null);
  const [submissionState, setSubmissionState] = useState<SubmissionState>("idle");
  const [createdProvider, setCreatedProvider] = useState<AiProvider | null>(null);

  // Security: clear secret on unmount.
  useEffect(() => {
    return () => {
      setForm((prev) => ({ ...prev, secret_plain: "" }));
      logVerbose("admin-ai.hook.useModelWizard.unmount.secret_cleared", {});
    };
  }, []);

  // Models query — fires only after a provider is created.
  const { data: modelsData, isLoading: areModelsLoading } = useQuery<AiModel[], AdminAiError>({
    queryKey: ["admin", "ai", "models", "byProvider", createdProvider?.id],
    queryFn: async () => {
      if (!createdProvider) return [];
      logVerbose("admin-ai.hook.useModelWizard.modelsQuery.start", { has_provider: true });
      const result = await getModels({ provider_id: createdProvider.id }, onAuthFailure);
      if (!result.ok) {
        logError("admin-ai.hook.useModelWizard.modelsQuery.error", {
          error_class: result.error.constructor.name,
        });
        throw result.error;
      }
      logVerbose("admin-ai.hook.useModelWizard.modelsQuery.ok", {
        model_count: result.value.length,
      });
      return result.value;
    },
    enabled: Boolean(createdProvider),
    staleTime: 0,
    gcTime: MODELS_GC_TIME_MS,
    retry: false,
  });

  // Submit mutation.
  const mutation = useMutation<AiProvider, AdminAiError, CreateProviderRequest>({
    mutationFn: async (req) => {
      logVerbose("admin-ai.hook.useModelWizard.submit.start", {
        provider_type: req.provider_type,
        auth_type: req.credentials.auth_type,
        name_len: req.name.length,
      });
      const result = await createProvider(req, onAuthFailure);
      if (!result.ok) throw result.error;
      return result.value;
    },
    onSuccess: (provider) => {
      logVerbose("admin-ai.hook.useModelWizard.submit.ok", {
        provider_type: provider.provider_type,
        status: provider.status,
      });
      // Security: zero secret immediately after successful submit
      setForm((prev) => ({ ...prev, secret_plain: "" }));
      setCreatedProvider(provider);
      setSubmissionState("success");
      setStep("models");
      void queryClient.invalidateQueries({ queryKey: ["admin", "ai", "models"] });
    },
    onError: (err) => {
      logError("admin-ai.hook.useModelWizard.submit.error", {
        error_class: err.constructor.name,
      });
      setSubmitError(err);
      const { state, fieldErrors: feFromServer } = classifySubmitError(err);
      setSubmissionState(state);
      if (Object.keys(feFromServer).length > 0) {
        setFieldErrors(feFromServer);
      }
      setStep("credentials");
    },
  });

  // Step navigation.
  function validateProviderStep(): boolean {
    const errors: WizardFieldErrors = {};
    const ptErr = validateProviderType(form.provider_type);
    if (ptErr) errors.provider_type = ptErr;
    const nameErr = validateName(form.name);
    if (nameErr) errors.name = nameErr;
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function validateCredentialsStep(): boolean {
    const errors: WizardFieldErrors = {};
    const authErr = validateAuthType(form.auth_type);
    if (authErr) errors.auth_type = authErr;
    const secretErr = validateSecret(form.secret_plain);
    if (secretErr) errors.secret_plain = secretErr;
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  const goNext = useCallback(() => {
    logVerbose("admin-ai.hook.useModelWizard.goNext", { step });
    if (step === "provider") {
      if (validateProviderStep()) {
        setFieldErrors({});
        setStep("credentials");
      }
    } else if (step === "credentials") {
      submit();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [step, form]);

  const goBack = useCallback(() => {
    logVerbose("admin-ai.hook.useModelWizard.goBack", { step });
    if (step === "credentials") {
      setFieldErrors({});
      setSubmitError(null);
      setSubmissionState("idle");
      setStep("provider");
    }
  }, [step]);

  // Form field updates.
  const setField = useCallback(
    (field: keyof Omit<WizardFormState, "secret_plain">, value: string) => {
      setForm((prev) => ({ ...prev, [field]: value }));
      setFieldErrors((prev) => {
        if (!prev[field]) return prev;
        const next = { ...prev };
        delete next[field];
        return next;
      });
    },
    [],
  );

  const setSecret = useCallback((value: string) => {
    // SECURITY: never log the secret value — only presence
    setForm((prev) => ({ ...prev, secret_plain: value }));
    setFieldErrors((prev) => {
      if (!prev.secret_plain) return prev;
      const next = { ...prev };
      delete next.secret_plain;
      return next;
    });
  }, []);

  // Submit.
  function submit(): void {
    if (!validateCredentialsStep()) return;

    logVerbose("admin-ai.hook.useModelWizard.submit.called", {
      provider_type: form.provider_type,
      auth_type: form.auth_type,
      name_len: form.name.length,
    });

    setSubmissionState("submitting");
    setSubmitError(null);
    setStep("submitting");

    const req: CreateProviderRequest = {
      provider_type: form.provider_type as CreateProviderRequest["provider_type"],
      name: form.name.trim(),
      base_url: form.base_url.trim() || null,
      credentials: {
        auth_type: form.auth_type as ProviderCredentialsInput["auth_type"],
        secret_plain: form.secret_plain as ProviderCredentialsInput["secret_plain"],
        refresh_token_plain: null,
        expires_at: null,
      },
    };

    mutation.mutate(req);
  }

  // Reset.
  const reset = useCallback(() => {
    logVerbose("admin-ai.hook.useModelWizard.reset");
    setStep("provider");
    setForm(INITIAL_FORM);
    setFieldErrors({});
    setSubmitError(null);
    setSubmissionState("idle");
    setCreatedProvider(null);
  }, []);

  // Strip secret_plain from the public return shape (security boundary).
  const { secret_plain: _secret, ...publicForm } = form;

  return {
    step,
    form: publicForm,
    hasSecret: form.secret_plain.length > 0,
    maskedSecret: formatMaskedSecret(form.secret_plain),
    fieldErrors,
    submitError,
    submissionState,
    createdProvider,
    providerModels: modelsData ?? [],
    areModelsLoading,
    goNext,
    goBack,
    setField,
    setSecret,
    submit,
    reset,
  };
}
