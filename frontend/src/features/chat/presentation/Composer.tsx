/**
 * Hilo People — Composer component.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *   Updated: P03-S02-T005 — dedicated i18n key for over-limit error message.
 *
 * Responsibility: Controlled text input + send CTA for ChatHomePage.
 *   Enforces D-T001-COMPOSER-MAX: max 4000 characters.
 *   Shows error_validation state when input is empty (trimmed) or over max.
 *   Over-limit message uses dedicated key chat:composer.errors.tooLong (D-T005-I18N-KEY).
 *   aria-busy on the form during submission per §a11y.
 *   Accessible label on send button.
 *
 * Token usage: --font-sans, --color-ink, --color-paper, --hairline.
 * A11y: keyboard nav — textarea → send button via Tab. visible focus ring via global.css.
 *
 * Non-negotiables §logging: BEFORE/AFTER/ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 */

import {
  type CSSProperties,
  type ReactNode,
  type ChangeEvent,
  type FormEvent,
  useState,
} from "react";
import { useTranslation } from "react-i18next";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import { logVerbose, logWarn } from "../data/logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

/**
 * Maximum composer input length (characters).
 * D-T001-COMPOSER-MAX: 4000 chars. Reasonable for an LLM prompt.
 * Not declared in source-of-truth; documented here per task pack §9.
 */
export const COMPOSER_MAX_LENGTH = 4000;

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface ComposerProps {
  /** Called on valid submit with the trimmed message text. */
  onSubmit: (message: string) => void;
  /** Disable the composer while a mutation is in-flight. */
  disabled?: boolean;
  /** True while a mutation is pending — shows loading state on CTA. */
  loading?: boolean;
  /** Controlled value (allows parent to pre-fill from chip click). */
  value?: string;
  /** Controlled onChange. */
  onChange?: (value: string) => void;
}

// ---------------------------------------------------------------------------
// Styles (tokens only)
// ---------------------------------------------------------------------------

const FORM_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
  width: "100%",
};

const TEXTAREA_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.375rem",
  width: "100%",
};

const TEXTAREA_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "1rem",
  color: "var(--color-ink)",
  background: "transparent",
  border: "none",
  borderBottom: "var(--hairline)",
  borderRadius: 0,
  padding: "0.625rem 0",
  width: "100%",
  minHeight: "44px",
  resize: "vertical",
  outline: "none",
  lineHeight: 1.4,
};

const TEXTAREA_ERROR_STYLE: CSSProperties = {
  ...TEXTAREA_STYLE,
  borderBottomWidth: "2px",
  borderBottomColor: "var(--color-ink)",
};

const ERROR_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.85,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Chat composer: textarea + send CTA with validation.
 *
 * @param props - {@link ComposerProps}
 * @returns The composer form element.
 */
export default function Composer({
  onSubmit,
  disabled = false,
  loading = false,
  value: externalValue,
  onChange: externalOnChange,
}: ComposerProps): ReactNode {
  const { t } = useTranslation(["chat", "common"]);
  const [internalValue, setInternalValue] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  // Support both controlled (from chip click) and uncontrolled usage.
  const isControlled = externalValue !== undefined;
  const value = isControlled ? externalValue : internalValue;

  logVerbose("chat.Composer.render.start", {
    has_value: value.trim().length > 0,
    loading,
    disabled,
  });

  const handleChange = (e: ChangeEvent<HTMLTextAreaElement>): void => {
    const newValue = e.target.value;
    if (isControlled) {
      externalOnChange?.(newValue);
    } else {
      setInternalValue(newValue);
    }
    // Clear validation error as user types
    if (validationError !== null) {
      setValidationError(null);
    }
  };

  const handleSubmit = (e: FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    const trimmed = value.trim();

    logVerbose("chat.Composer.submit.start", { prompt_len: trimmed.length });

    if (trimmed.length === 0) {
      logWarn("chat.Composer.submit.validation.empty");
      // Empty input: disable prevents this path typically, but guard for keyboard submit
      setValidationError(t("common:states.empty"));
      return;
    }

    if (trimmed.length > COMPOSER_MAX_LENGTH) {
      logWarn("chat.Composer.submit.validation.too_long", {
        len: trimmed.length,
        max: COMPOSER_MAX_LENGTH,
      });
      setValidationError(
        t("chat:composer.errors.tooLong", { max: COMPOSER_MAX_LENGTH }),
      );
      return;
    }

    setValidationError(null);
    logVerbose("chat.Composer.submit.ok", { prompt_len: trimmed.length });
    onSubmit(trimmed);
  };

  const isDisabled = disabled || loading;
  const isSendDisabled = isDisabled || value.trim().length === 0;
  const hasValidationError = validationError !== null;
  const errorId = "composer-error";

  return (
    <form
      onSubmit={handleSubmit}
      style={FORM_STYLE}
      aria-busy={loading ? "true" : undefined}
      data-testid="composer-form"
    >
      <div style={TEXTAREA_CONTAINER_STYLE}>
        <textarea
          id="composer-input"
          value={value}
          onChange={handleChange}
          placeholder={t("chat:composer.placeholder")}
          maxLength={COMPOSER_MAX_LENGTH + 1}
          disabled={isDisabled}
          aria-label={t("chat:composer.placeholder")}
          aria-invalid={hasValidationError ? "true" : undefined}
          aria-describedby={hasValidationError ? errorId : undefined}
          style={hasValidationError ? TEXTAREA_ERROR_STYLE : TEXTAREA_STYLE}
          rows={2}
          data-testid="composer-textarea"
        />
        {hasValidationError && (
          <span
            id={errorId}
            role="alert"
            aria-live="assertive"
            style={ERROR_STYLE}
            data-testid="composer-validation-error"
          >
            {validationError}
          </span>
        )}
      </div>

      <SolidCTA
        type="submit"
        disabled={isSendDisabled}
        loading={loading}
        loadingLabel="…"
        aria-label={t("chat:composer.send")}
        data-testid="composer-send"
      >
        {t("chat:composer.send")}
      </SolidCTA>
    </form>
  );
}
