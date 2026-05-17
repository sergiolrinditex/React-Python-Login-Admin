/**
 * Hilo People — McpWizardPage form body.
 *
 * Slice/Phase: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: Presentational `<form>` body for McpWizardPage.tsx — renders
 *   the name + transport + endpoint + authType fields, the conditional secret
 *   and refreshToken fields, the optional form-level error block, and the
 *   submit/cancel row. Single responsibility: render the form. No data
 *   fetching, no business logic, no state — every prop is supplied by the
 *   parent page. Behavior is byte-equivalent to the previously inlined form.
 *
 * §D-T004-PAGE-SPLIT-STYLES (R-6 mitigation, cycle 2): proactive helper split
 *   to honor the ~300-line file-size non-negotiable. Pre-authorized by R-6 in
 *   the task pack §11 (`_McpWizardPage.<helper>.tsx`).
 * §D-T004-SECRET-FIELD / §D-T004-SECRET-NEVER-PERSISTED: secret +
 *   refreshToken stay `type="password" autoComplete="off" spellCheck={false}`.
 *
 * Key deps beyond imports: react-hook-form ^7 types (register + errors +
 *   handleSubmit); EditorialInput + SolidCTA shared design-system primitives;
 *   sibling SelectField and FormLevelErrorBlock helpers; style constants from
 *   _McpWizardPage.styles.
 */

import type { ReactNode } from "react";
import type {
  FieldErrors,
  UseFormRegister,
  UseFormHandleSubmit,
} from "react-hook-form";
import EditorialInput from "../../../shared/design-system/EditorialInput";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import { SelectField } from "./_McpWizardPage.select-field";
import { FormLevelErrorBlock } from "./_McpWizardPage.feedback";
import {
  FORM_STYLE,
  SUBMIT_ROW_STYLE,
  CANCEL_BTN_STYLE,
} from "./_McpWizardPage.styles";

/**
 * Form values shape — kept structural rather than imported so this helper
 * stays decoupled from the parent's Zod schema generic.
 */
export interface WizardFormValues {
  name: string;
  transport: "http" | "sse";
  endpoint: string;
  authType: "none" | "api_key" | "bearer" | "oauth2";
  secret?: string;
  refreshToken?: string;
}

/** i18n lookup narrowed to what this form needs. */
export type WizardTranslator = (key: string) => string;

/**
 * Props for the McpWizardPage form body.
 *
 * @property formAriaLabelId - id of the page H1, used as aria-labelledby.
 * @property isLoading - mutation in-flight; disables fields + sets aria-busy.
 * @property onSubmit - react-hook-form bound submit handler.
 * @property register - react-hook-form register fn.
 * @property errors - react-hook-form error state.
 * @property showSecret - true when authType !== "none".
 * @property showRefreshToken - true when authType === "oauth2".
 * @property isFormLevelError - true when the mutation error renders form-level
 *   (parent already excludes McpValidationError + McpForbiddenError).
 * @property formLevelErrorMessage - localized message for the error block.
 * @property t - i18n translator for labels and option labels.
 * @property onCancel - click handler for the cancel button.
 */
export interface WizardFormProps {
  formAriaLabelId: string;
  isLoading: boolean;
  onSubmit: ReturnType<UseFormHandleSubmit<WizardFormValues>>;
  register: UseFormRegister<WizardFormValues>;
  errors: FieldErrors<WizardFormValues>;
  showSecret: boolean;
  showRefreshToken: boolean;
  isFormLevelError: boolean;
  formLevelErrorMessage: string;
  t: WizardTranslator;
  onCancel: () => void;
}

/**
 * Form body of McpWizardPage. Renders the exact same DOM as the previously
 * inlined `<form>` — name + transport + endpoint + authType + optional secret
 * + optional refreshToken + optional form-level error + submit row.
 *
 * @param props - WizardFormProps describing the current form state.
 * @returns The form element.
 */
export function WizardForm({
  formAriaLabelId,
  isLoading,
  onSubmit,
  register,
  errors,
  showSecret,
  showRefreshToken,
  isFormLevelError,
  formLevelErrorMessage,
  t,
  onCancel,
}: WizardFormProps): ReactNode {
  return (
    <form
      onSubmit={onSubmit}
      style={FORM_STYLE}
      aria-labelledby={formAriaLabelId}
      aria-busy={isLoading ? "true" : undefined}
      noValidate
      data-testid="wizard-form"
    >
      {/* Name field */}
      <EditorialInput
        label={t("wizard.fields.name")}
        errorMessage={errors.name?.message ? t(errors.name.message) : undefined}
        disabled={isLoading}
        data-testid="wizard-name"
        {...register("name")}
      />

      {/* Transport field — native <select> §D-T004-SELECT-STYLE */}
      <SelectField
        id="wizard-transport"
        label={t("wizard.fields.transport")}
        options={[
          { value: "http", label: t("wizard.fields.transport.http") },
          { value: "sse", label: t("wizard.fields.transport.sse") },
        ]}
        disabled={isLoading}
        hasError={Boolean(errors.transport)}
        errorMessage={
          errors.transport ? t(errors.transport.message ?? "") : undefined
        }
        testId="wizard-transport"
        registration={register("transport")}
      />

      {/* Endpoint field */}
      <EditorialInput
        label={t("wizard.fields.endpoint")}
        errorMessage={errors.endpoint?.message ? t(errors.endpoint.message) : undefined}
        disabled={isLoading}
        type="url"
        inputMode="url"
        autoComplete="off"
        placeholder="https://your-mcp-server.example.com/mcp"
        data-testid="wizard-endpoint"
        {...register("endpoint")}
      />

      {/* Auth type field — native <select> §D-T004-SELECT-STYLE */}
      <SelectField
        id="wizard-auth-type"
        label={t("wizard.fields.authType")}
        options={[
          { value: "none", label: t("wizard.fields.authType.none") },
          { value: "api_key", label: t("wizard.fields.authType.api_key") },
          { value: "bearer", label: t("wizard.fields.authType.bearer") },
          { value: "oauth2", label: t("wizard.fields.authType.oauth2") },
        ]}
        disabled={isLoading}
        hasError={Boolean(errors.authType)}
        errorMessage={
          errors.authType ? t(errors.authType.message ?? "") : undefined
        }
        testId="wizard-auth-type"
        registration={register("authType")}
      />

      {/* Secret field — conditional, type="password" §D-T004-SECRET-FIELD */}
      {showSecret && (
        <EditorialInput
          label={t("wizard.fields.secret")}
          errorMessage={errors.secret?.message ? t(errors.secret.message) : undefined}
          disabled={isLoading}
          type="password"
          autoComplete="off"
          spellCheck={false}
          data-testid="wizard-secret"
          {...register("secret")}
        />
      )}

      {/* Refresh token — oauth2 only */}
      {showRefreshToken && (
        <EditorialInput
          label={t("wizard.fields.refreshToken")}
          errorMessage={
            errors.refreshToken?.message
              ? t(errors.refreshToken.message)
              : undefined
          }
          disabled={isLoading}
          type="password"
          autoComplete="off"
          spellCheck={false}
          data-testid="wizard-refresh-token"
          {...register("refreshToken")}
        />
      )}

      {isFormLevelError && (
        <FormLevelErrorBlock message={formLevelErrorMessage} />
      )}

      {/* Submit row */}
      <div style={SUBMIT_ROW_STYLE}>
        <SolidCTA
          type="submit"
          loading={isLoading}
          loadingLabel={t("wizard.actions.submitting")}
          width="auto"
          style={{ padding: "0.5rem 1.5rem" }}
          data-testid="wizard-submit"
        >
          {t("wizard.actions.submit")}
        </SolidCTA>
        <button
          type="button"
          style={CANCEL_BTN_STYLE}
          onClick={onCancel}
          disabled={isLoading}
          data-testid="wizard-cancel"
        >
          {t("wizard.actions.cancel")}
        </button>
      </div>
    </form>
  );
}
