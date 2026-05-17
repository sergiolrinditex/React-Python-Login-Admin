/**
 * Hilo People — ModelWizardPage provider step.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-FILESIZE-SPLIT-STEPS
 *
 * Responsibility: Step 1 of the model wizard — pick provider_type, enter a
 *   display name, and optionally a base_url. Presentational only; all state
 *   lives in the `wizard` hook passed in as a prop.
 *
 * Consumers: ModelWizardPage.tsx only.
 * Design: token-only styles from ./ModelWizardPage.styles.ts.
 * Accessibility: labels + aria-required/aria-invalid/aria-describedby per
 *   UX_CONTRACT §7 / §D-T003-ACCESSIBILITY.
 *
 * Key deps: useModelWizard (hook result type), shared/design-system primitives,
 *   react-i18next.
 */

import type { ReactNode } from "react";
import type { TFunction } from "i18next";
import EditorialInput from "../../../shared/design-system/EditorialInput";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import type { UseModelWizardResult } from "../../../features/admin-ai/presentation/useModelWizard";
import {
  FORM_SECTION,
  FIELD_ROW,
  FORM_ACTIONS,
  SELECT_STYLE,
  SELECT_ERROR_STYLE,
  ERROR_TEXT,
  STEP_HEADING,
} from "./ModelWizardPage.styles";

// Provider options — must match backend ProviderType enum + i18n.
export const PROVIDER_OPTIONS = [
  "openai",
  "anthropic",
  "azure",
  "litellm",
  "ollama",
  "google",
  "custom",
] as const;

interface ProviderStepProps {
  wizard: UseModelWizardResult;
  t: TFunction;
}

/**
 * Renders step 1: pick provider type, name, optional base URL.
 */
export function ProviderStep({ wizard, t }: ProviderStepProps): ReactNode {
  return (
    <section
      aria-labelledby="wizard-provider-heading"
      data-testid="wizard-step-provider"
    >
      <h2 id="wizard-provider-heading" style={STEP_HEADING}>
        {t("admin-ai:modelsNew.steps.provider.title")}
      </h2>
      <div style={FORM_SECTION}>
        {/* Provider type select */}
        <div style={FIELD_ROW}>
          <TrackedLabel
            as="label"
            htmlFor="wizard-provider-type"
            variant={wizard.fieldErrors.provider_type ? "default" : "muted"}
          >
            {t("admin-ai:modelsNew.fields.providerType")}
          </TrackedLabel>
          <select
            id="wizard-provider-type"
            value={wizard.form.provider_type}
            onChange={(e) => wizard.setField("provider_type", e.target.value)}
            aria-required="true"
            aria-invalid={Boolean(wizard.fieldErrors.provider_type)}
            aria-describedby={wizard.fieldErrors.provider_type ? "wizard-provider-type-error" : undefined}
            style={wizard.fieldErrors.provider_type ? SELECT_ERROR_STYLE : SELECT_STYLE}
            data-testid="wizard-provider-type-select"
          >
            <option value="">{t("admin-ai:modelsNew.fields.providerTypePlaceholder")}</option>
            {PROVIDER_OPTIONS.map((pt) => (
              <option key={pt} value={pt}>
                {t(`admin-ai:modelsNew.providerOptions.${pt}`)}
              </option>
            ))}
          </select>
          {wizard.fieldErrors.provider_type && (
            <span id="wizard-provider-type-error" role="alert" style={ERROR_TEXT}>
              {t(wizard.fieldErrors.provider_type)}
            </span>
          )}
        </div>

        {/* Provider name */}
        <EditorialInput
          id="wizard-provider-name"
          label={t("admin-ai:modelsNew.fields.name")}
          value={wizard.form.name}
          onChange={(e) => wizard.setField("name", e.target.value)}
          placeholder={t("admin-ai:modelsNew.fields.namePlaceholder")}
          aria-required="true"
          errorMessage={wizard.fieldErrors.name ? t(wizard.fieldErrors.name) : undefined}
          autoComplete="off"
          data-testid="wizard-provider-name-input"
        />

        {/* Base URL (optional) */}
        <EditorialInput
          id="wizard-provider-base-url"
          label={t("admin-ai:modelsNew.fields.baseUrl")}
          value={wizard.form.base_url}
          onChange={(e) => wizard.setField("base_url", e.target.value)}
          placeholder={t("admin-ai:modelsNew.fields.baseUrlPlaceholder")}
          autoComplete="off"
          data-testid="wizard-provider-base-url-input"
        />

        <div style={FORM_ACTIONS}>
          <SolidCTA
            onClick={wizard.goNext}
            aria-label={t("admin-ai:modelsNew.actions.next")}
            data-testid="wizard-next-btn"
            width="auto"
            style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
          >
            {t("admin-ai:modelsNew.actions.next")}
          </SolidCTA>
        </div>
      </div>
    </section>
  );
}
