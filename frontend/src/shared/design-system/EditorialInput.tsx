/**
 * Hilo People — EditorialInput component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: full-width text input with hairline bottom border only.
 *   No border-radius (hard rule). Label rendered above via TrackedLabel.
 *   Used on: SignInPage (email/password), SignUpPage (all fields),
 *   ForgotPasswordPage (email), AuditLogPage (filter row).
 *   Journey refs: J100 (login), J101 (chat upload/search), J103 (admin).
 *
 * Token usage: --hairline, --color-ink, --font-sans, --color-bg, --color-paper.
 * Prohibitions: NO border-radius, NO box-shadow, NO colored borders beyond hairline.
 *
 * Accessibility:
 *   - Label linked via htmlFor/id.
 *   - aria-invalid on error state.
 *   - aria-describedby linking to error message.
 *   - Minimum 44px touch target height.
 *
 * Key deps: React 19, TrackedLabel, CSS custom properties from tokens.css.
 */

import { useId, type CSSProperties, type InputHTMLAttributes, type ReactNode } from "react";
import TrackedLabel from "./TrackedLabel";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type EditorialInputVariant = "empty" | "filled" | "focused" | "error_validation" | "disabled";

export interface EditorialInputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "style"> {
  /** Field label — rendered above via TrackedLabel. Required for accessibility. */
  label: string;
  /** Error message — renders below input, sets aria-invalid. */
  errorMessage?: string;
  /** Controlled variant override — in practice state flows from value/disabled/error. */
  variant?: EditorialInputVariant;
  /** Container class. */
  containerClassName?: string;
  /** Container inline style. */
  containerStyle?: CSSProperties;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.375rem",
  width: "100%",
};

const INPUT_BASE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "1rem",
  color: "var(--color-ink)",
  background: "transparent",
  border: "none",
  borderBottom: "var(--hairline)",
  borderRadius: 0, /* Hard rule — always 0 */
  padding: "0.625rem 0",
  width: "100%",
  minHeight: "44px", /* WCAG tap target */
  outline: "none",
  lineHeight: 1.4,
};

const ERROR_TEXT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  marginTop: "0.25rem",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Editorial input with label above and optional error state.
 *
 * @param props - {@link EditorialInputProps}
 * @returns The labeled input field.
 */
export default function EditorialInput({
  label,
  errorMessage,
  variant: _variant,
  containerClassName,
  containerStyle,
  id: externalId,
  disabled,
  ...inputProps
}: EditorialInputProps): ReactNode {
  const generatedId = useId();
  const id = externalId ?? generatedId;
  const errorId = `${id}-error`;
  const hasError = Boolean(errorMessage);

  /* BEFORE log — respects VITE_ENABLE_VERBOSE_LOGGING */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("EditorialInput.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      id,
      hasError,
      disabled,
    });
  }

  const inputStyle: CSSProperties = {
    ...INPUT_BASE_STYLE,
    opacity: disabled ? 0.4 : 1,
    cursor: disabled ? "not-allowed" : "text",
    /* Focus ring via ::focus-visible is in global.css; here we keep outline:none */
    borderBottomColor: hasError
      ? "var(--color-ink)"
      : undefined /* hairline already sets rgba ink */,
    borderBottomWidth: hasError ? "2px" : "1px",
  };

  return (
    <div
      className={containerClassName}
      style={{ ...CONTAINER_STYLE, ...containerStyle }}
    >
      <TrackedLabel as="label" htmlFor={id} variant={disabled ? "muted" : "default"}>
        {label}
      </TrackedLabel>

      <input
        id={id}
        disabled={disabled}
        aria-invalid={hasError ? "true" : undefined}
        aria-describedby={hasError ? errorId : undefined}
        style={inputStyle}
        {...inputProps}
      />

      {hasError && (
        <span id={errorId} role="alert" style={ERROR_TEXT_STYLE}>
          {errorMessage}
        </span>
      )}
    </div>
  );
}
