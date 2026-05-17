/**
 * Hilo People — McpWizardPage SelectField helper.
 *
 * Slice/Phase: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: Reusable native <select> field for McpWizardPage.tsx.
 *   Deduplicates the two near-identical transport + authType select blocks
 *   (label + native <select> + error message + a11y wiring) that previously
 *   lived inline in McpWizardPage.tsx. Single responsibility: render one
 *   labelled, validated, design-token-styled native <select>.
 *
 * §D-T004-PAGE-SPLIT-STYLES (R-6 mitigation): proactive helper split to honor
 *   the ~300-line file-size non-negotiable. R-6 in the task pack §11
 *   pre-authorizes `_McpWizardPage.<helper>.tsx` extraction when inline blocks
 *   grow beyond ~50 LOC; the duplicated select blocks were ~74 LOC combined.
 * §D-T004-SELECT-STYLE: hairline bottom border, no radius, no shadow —
 *   inherited from the shared SELECT_*_STYLE constants.
 *
 * a11y: native <select> is fully keyboard-accessible by default. The label
 *   is wired via TrackedLabel `as="label" htmlFor=...`. Error messages use
 *   aria-invalid + aria-describedby + role="alert". Min height 44px enforced
 *   through SELECT_BASE_STYLE.
 *
 * Key deps: TrackedLabel (shared design system); style constants from
 *   _McpWizardPage.styles.ts; react-hook-form register return type.
 */

import type { ReactNode } from "react";
import type { UseFormRegisterReturn } from "react-hook-form";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import {
  FIELD_GROUP_STYLE,
  SELECT_BASE_STYLE,
  SELECT_ERROR_STYLE,
  SELECT_DISABLED_STYLE,
  FIELD_ERROR_STYLE,
} from "./_McpWizardPage.styles";

// ---------------------------------------------------------------------------
// SelectFieldOption
// ---------------------------------------------------------------------------

/** One <option> entry rendered inside the native <select>. */
export interface SelectFieldOption {
  /** Value attribute submitted by the form. */
  value: string;
  /** User-facing localized label rendered inside the option. */
  label: string;
}

// ---------------------------------------------------------------------------
// SelectFieldProps
// ---------------------------------------------------------------------------

/**
 * Props for the reusable McpWizardPage select field.
 *
 * @property id - DOM id used by both htmlFor on the label and aria-describedby.
 * @property label - Localized label text rendered through TrackedLabel.
 * @property options - Ordered list of <option> entries.
 * @property disabled - Whether the form is mid-submit / locked.
 * @property hasError - Whether the field currently has a validation error.
 * @property errorMessage - Localized error message rendered below the select.
 * @property testId - data-testid for RTL queries (also used to derive the
 *   error span id `<testId>-error`).
 * @property registration - react-hook-form `register("fieldName")` spread.
 */
export interface SelectFieldProps {
  id: string;
  label: string;
  options: ReadonlyArray<SelectFieldOption>;
  disabled: boolean;
  hasError: boolean;
  errorMessage?: string;
  testId: string;
  registration: UseFormRegisterReturn;
}

// ---------------------------------------------------------------------------
// SelectField component
// ---------------------------------------------------------------------------

/**
 * Native <select> wrapped with TrackedLabel + error region.
 *
 * Renders the exact DOM previously inlined for the transport + authType
 * selects in McpWizardPage.tsx. Behavior is byte-equivalent: same data-testid
 * attributes, same aria wiring, same conditional style selection between
 * disabled / error / base.
 *
 * @param props - SelectFieldProps describing the field instance.
 * @returns A field group containing label + native select + optional error.
 */
export function SelectField({
  id,
  label,
  options,
  disabled,
  hasError,
  errorMessage,
  testId,
  registration,
}: SelectFieldProps): ReactNode {
  const errorId = `${testId}-error`;
  const selectStyle = disabled
    ? SELECT_DISABLED_STYLE
    : hasError
    ? SELECT_ERROR_STYLE
    : SELECT_BASE_STYLE;

  return (
    <div style={FIELD_GROUP_STYLE}>
      <TrackedLabel
        as="label"
        htmlFor={id}
        variant={disabled ? "muted" : "default"}
      >
        {label}
      </TrackedLabel>
      <select
        id={id}
        disabled={disabled}
        aria-invalid={hasError ? "true" : undefined}
        aria-describedby={hasError ? errorId : undefined}
        style={selectStyle}
        data-testid={testId}
        {...registration}
      >
        {options.map((option) => (
          <option key={option.value} value={option.value}>
            {option.label}
          </option>
        ))}
      </select>
      {hasError && errorMessage !== undefined && (
        <span
          id={errorId}
          role="alert"
          style={FIELD_ERROR_STYLE}
          data-testid={errorId}
        >
          {errorMessage}
        </span>
      )}
    </div>
  );
}
