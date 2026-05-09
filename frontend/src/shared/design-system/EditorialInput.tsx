/**
 * EditorialInput — Hairline-bordered text input for the Hilo editorial system.
 *
 * What: A styled text input that applies the `--hairline` token for its border
 * and uses the `--font-sans` / `--font-display` type stack. Zero rounded corners.
 * Supports a visible label (paired via htmlFor / aria-describedby) and optional
 * error message for accessible form validation display.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: instrucciones.md §7, TECHNICAL_GUIDE §7, UX_CONTRACT §6
 *
 * Logging:
 *   This component forwards onChange to the parent consumer. The parent feature
 *   use-case is responsible for BEFORE/AFTER logging of form submission actions.
 *   No logging at the primitive component level (same pattern as SolidCTA).
 *
 * Accessibility:
 *   - `aria-label` or pairing with a <label htmlFor={id}> is required.
 *   - `aria-describedby` points to error message element when error is present.
 *   - :focus-visible ring is set globally in reset.css; not overridden here.
 */

import type { CSSProperties, ChangeEvent, InputHTMLAttributes } from 'react';

interface EditorialInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, 'className'> {
  /** Accessible label text (rendered as visible <label> above the input). */
  label?: string;
  /** Error message rendered below the input. Also sets aria-invalid. */
  errorMessage?: string;
  /** DOM id — required when using `label`. */
  id?: string;
  /** Additional class for outer wrapper. */
  wrapperClassName?: string;
}

const inputStyle: CSSProperties = {
  display:       'block',
  width:         '100%',
  padding:       'var(--space-3) var(--space-4)',
  fontFamily:    'var(--font-sans)',
  fontSize:      'var(--text-base)',
  color:         'var(--color-text-primary)',
  background:    'var(--color-paper)',
  border:        'var(--hairline)',
  borderRadius:  'var(--radius)',   /* = 0 */
  outline:       'none',            /* :focus-visible from reset.css handles the ring */
  transition:    `border-color var(--duration-fast) var(--ease-standard)`,
};

const inputErrorStyle: CSSProperties = {
  ...inputStyle,
  borderColor: 'var(--color-ink)',  /* stronger hairline for error state */
};

const errorTextStyle: CSSProperties = {
  display:       'block',
  marginTop:     'var(--space-1)',
  fontFamily:    'var(--font-sans)',
  fontSize:      'var(--text-xs)',
  color:         'var(--color-text-primary)',
  letterSpacing: 'var(--tracking-label)',
  textTransform: 'uppercase',
};

const wrapperStyle: CSSProperties = {
  display:       'flex',
  flexDirection: 'column',
  gap:           'var(--space-2)',
};

/**
 * Editorial text input with hairline border, optional label and error message.
 *
 * @param label - Visible label rendered above the input.
 * @param errorMessage - Validation error rendered below the input.
 * @param id - DOM id for label association.
 * @param wrapperClassName - Class on outer wrapper element.
 * @param rest - Passed to the native <input> element.
 */
export function EditorialInput({
  label,
  errorMessage,
  id,
  wrapperClassName,
  onChange,
  ...rest
}: EditorialInputProps) {
  const errorId = id !== undefined ? `${id}-error` : undefined;
  const hasError = errorMessage !== undefined && errorMessage.length > 0;

  const handleChange = (e: ChangeEvent<HTMLInputElement>) => {
    onChange?.(e);
  };

  return (
    <div className={wrapperClassName} style={wrapperStyle}>
      {label !== undefined && id !== undefined && (
        <label htmlFor={id}>
          <span
            style={{
              fontFamily:    'var(--font-sans)',
              fontSize:      'var(--text-xs)',
              fontWeight:    'var(--weight-semibold)' as string,
              letterSpacing: 'var(--tracking-label)',
              textTransform: 'uppercase',
              color:         'var(--color-text-secondary)',
            }}
          >
            {label}
          </span>
        </label>
      )}
      <input
        id={id}
        style={hasError ? inputErrorStyle : inputStyle}
        aria-invalid={hasError}
        aria-describedby={hasError ? errorId : undefined}
        onChange={handleChange}
        {...rest}
      />
      {hasError && errorId !== undefined && (
        <span id={errorId} role="alert" style={errorTextStyle}>
          {errorMessage}
        </span>
      )}
    </div>
  );
}
