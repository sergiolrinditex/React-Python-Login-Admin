/**
 * Hilo People — ModelWizardPage credentials step.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-FILESIZE-SPLIT-STEPS
 *
 * Responsibility: Step 2 of the model wizard — pick auth_type and enter the
 *   live secret credential. The secret input is type=password by default and
 *   toggles to text only while `showSecret=true`. The secret value itself
 *   lives in the wizard hook, never in this component.
 *
 *   Renders all error banners that surface mid-step (error_network,
 *   error_validation generic-no-field-level, permission_denied).
 *
 * Consumers: ModelWizardPage.tsx only.
 * Design: token-only styles from ./ModelWizardPage.styles.ts.
 * Security: §D-T003-SECRET-SECURITY. type=password, autocomplete=new-password,
 *   never persisted, cleared by the hook on unmount/success.
 * Accessibility: labels + aria-required/aria-invalid/aria-describedby +
 *   show/hide toggle keyboard-accessible.
 *
 * Key deps: useModelWizard (hook result type), shared/design-system primitives,
 *   ../../../features/admin-ai/data/errors (AdminAiValidationError discriminator),
 *   react-i18next.
 */

import type { ReactNode } from "react";
import type { TFunction } from "i18next";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { AdminAiValidationError } from "../../../features/admin-ai/data/errors";
import type { UseModelWizardResult } from "../../../features/admin-ai/presentation/useModelWizard";
import {
  FORM_SECTION,
  FIELD_ROW,
  FORM_ACTIONS,
  SELECT_STYLE,
  SELECT_ERROR_STYLE,
  ERROR_TEXT,
  SECRET_WRAPPER,
  SHOW_HIDE_BUTTON,
  CENTER_BLOCK,
  BODY_TEXT,
  STEP_HEADING,
} from "./ModelWizardPage.styles";

export const AUTH_TYPE_OPTIONS = ["api_key", "oauth2", "bearer"] as const;

interface CredentialsStepProps {
  wizard: UseModelWizardResult;
  t: TFunction;
  showSecret: boolean;
  onToggleShowSecret: () => void;
}

/**
 * Renders step 2: auth_type select + masked secret input + submit.
 */
export function CredentialsStep({
  wizard,
  t,
  showSecret,
  onToggleShowSecret,
}: CredentialsStepProps): ReactNode {
  const isSubmitting = wizard.step === "submitting";
  const hasFieldLevelValidationErrors = Boolean(
    wizard.submitError instanceof AdminAiValidationError &&
      wizard.submitError.fieldErrors?.length,
  );

  return (
    <section
      aria-labelledby="wizard-credentials-heading"
      data-testid="wizard-step-credentials"
    >
      <h2 id="wizard-credentials-heading" style={STEP_HEADING}>
        {t("admin-ai:modelsNew.steps.credentials.title")}
      </h2>

      {/* Error banners */}
      {wizard.submissionState === "error_network" && (
        <div
          role="alert"
          aria-live="assertive"
          style={{ ...CENTER_BLOCK, marginBottom: "1.5rem" }}
          data-testid="wizard-error-network"
        >
          <p style={BODY_TEXT}>{t("admin-ai:modelsNew.errors.network.body")}</p>
        </div>
      )}
      {wizard.submissionState === "error_validation" && !hasFieldLevelValidationErrors && (
        <div
          role="alert"
          aria-live="assertive"
          style={{ ...CENTER_BLOCK, marginBottom: "1.5rem" }}
          data-testid="wizard-error-validation"
        >
          <p style={BODY_TEXT}>{t("admin-ai:modelsNew.errors.validation.generic")}</p>
        </div>
      )}
      {wizard.submissionState === "permission_denied" && (
        <div
          role="alert"
          aria-live="assertive"
          style={{ ...CENTER_BLOCK, marginBottom: "1.5rem" }}
          data-testid="wizard-error-permission"
        >
          <p style={BODY_TEXT}>{t("admin-ai:modelsNew.errors.permissionDenied.body")}</p>
        </div>
      )}

      <div style={FORM_SECTION}>
        {/* Auth type select */}
        <div style={FIELD_ROW}>
          <TrackedLabel
            as="label"
            htmlFor="wizard-auth-type"
            variant={wizard.fieldErrors.auth_type ? "default" : "muted"}
          >
            {t("admin-ai:modelsNew.fields.authType")}
          </TrackedLabel>
          <select
            id="wizard-auth-type"
            value={wizard.form.auth_type}
            onChange={(e) => wizard.setField("auth_type", e.target.value)}
            aria-required="true"
            aria-invalid={Boolean(wizard.fieldErrors.auth_type)}
            aria-describedby={wizard.fieldErrors.auth_type ? "wizard-auth-type-error" : undefined}
            style={wizard.fieldErrors.auth_type ? SELECT_ERROR_STYLE : SELECT_STYLE}
            disabled={isSubmitting}
            data-testid="wizard-auth-type-select"
          >
            {AUTH_TYPE_OPTIONS.map((at) => (
              <option key={at} value={at}>
                {t(`admin-ai:modelsNew.authTypeOptions.${at}`)}
              </option>
            ))}
          </select>
          {wizard.fieldErrors.auth_type && (
            <span id="wizard-auth-type-error" role="alert" style={ERROR_TEXT}>
              {t(wizard.fieldErrors.auth_type)}
            </span>
          )}
        </div>

        {/* Secret credential — type=password, masked, show/hide toggle */}
        <div style={FIELD_ROW}>
          <TrackedLabel
            as="label"
            htmlFor="wizard-secret-plain"
            variant={wizard.fieldErrors.secret_plain ? "default" : "muted"}
          >
            {t("admin-ai:modelsNew.fields.secretPlain")}
          </TrackedLabel>
          <div style={SECRET_WRAPPER}>
            {/* SECURITY: type=password masks the secret in the DOM. The value
                lives only in the hook state — never serialized, never logged. */}
            <input
              id="wizard-secret-plain"
              type={showSecret ? "text" : "password"}
              autoComplete="new-password"
              aria-required="true"
              aria-invalid={Boolean(wizard.fieldErrors.secret_plain) ? "true" : undefined}
              aria-describedby="wizard-secret-hint wizard-secret-error"
              style={{
                fontFamily: "var(--font-sans)",
                fontSize: "1rem",
                color: "var(--color-ink)",
                background: "transparent",
                border: "none",
                borderBottom: wizard.fieldErrors.secret_plain
                  ? "2px solid var(--color-ink)"
                  : "var(--hairline)",
                borderRadius: 0,
                padding: "0.625rem 3rem 0.625rem 0",
                width: "100%",
                minHeight: "44px",
                outline: "none",
                lineHeight: 1.4,
                boxSizing: "border-box",
              }}
              onChange={(e) => wizard.setSecret(e.target.value)}
              disabled={isSubmitting}
              data-testid="wizard-secret-input"
              placeholder={t("admin-ai:modelsNew.fields.secretPlainPlaceholder")}
            />
            <button
              type="button"
              aria-label={showSecret
                ? t("admin-ai:modelsNew.fields.secretHide")
                : t("admin-ai:modelsNew.fields.secretShow")}
              style={SHOW_HIDE_BUTTON}
              onClick={onToggleShowSecret}
              tabIndex={0}
              data-testid="wizard-secret-toggle"
            >
              {showSecret ? t("admin-ai:modelsNew.fields.secretHide") : t("admin-ai:modelsNew.fields.secretShow")}
            </button>
          </div>
          <span id="wizard-secret-hint" style={{ ...ERROR_TEXT, opacity: 0.55 }}>
            {t("admin-ai:modelsNew.fields.secretPlainHint")}
          </span>
          {wizard.fieldErrors.secret_plain && (
            <span id="wizard-secret-error" role="alert" style={ERROR_TEXT}>
              {t(wizard.fieldErrors.secret_plain)}
            </span>
          )}
        </div>

        <div style={FORM_ACTIONS}>
          <SolidCTA
            onClick={wizard.goBack}
            aria-label={t("admin-ai:modelsNew.actions.back")}
            data-testid="wizard-back-btn"
            width="auto"
            style={{
              padding: "0.75rem 1.5rem",
              minHeight: "44px",
              background: "transparent",
              color: "var(--color-ink)",
              border: "var(--hairline)",
            }}
            disabled={isSubmitting}
          >
            {t("admin-ai:modelsNew.actions.back")}
          </SolidCTA>
          <SolidCTA
            onClick={wizard.goNext}
            aria-label={t("admin-ai:modelsNew.actions.submit")}
            data-testid="wizard-submit-btn"
            width="auto"
            style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
            disabled={isSubmitting || !wizard.hasSecret}
          >
            {isSubmitting
              ? t("admin-ai:modelsNew.actions.submitting")
              : t("admin-ai:modelsNew.actions.submit")}
          </SolidCTA>
        </div>
      </div>
    </section>
  );
}
