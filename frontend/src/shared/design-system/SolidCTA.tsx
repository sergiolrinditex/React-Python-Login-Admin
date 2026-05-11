/**
 * Hilo People — SolidCTA component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: solid black call-to-action button with no border-radius
 *   and uppercase tracked text. Used on: SignInPage ("Sign In"), SignUpPage
 *   ("Create Account"), ForgotPasswordPage ("Send Reset Link"), AdminDashboard
 *   bulk actions, RAG upload triggers.
 *   Journey refs: J100 (login submit), J101 (send message), J102 (upload),
 *                 J103 (admin save), J104 (onboard), J105 (usage report).
 *
 * Token usage: --color-ink (bg), --color-paper (fg), --tracking-label.
 * Prohibitions: NO border-radius, NO box-shadow, NO color variants (ink bg only).
 *
 * Accessibility:
 *   - Minimum 44px height tap target.
 *   - aria-disabled matches disabled state.
 *   - aria-busy for loading state.
 *   - Keyboard activation via native button element.
 *
 * Key deps: React 19, CSS custom properties from tokens.css.
 */

import type { ButtonHTMLAttributes, CSSProperties, ReactNode } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type SolidCTAVariant = "default" | "disabled" | "loading";

export interface SolidCTAProps extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "style"> {
  /** Loading state — shows loading label and aria-busy. */
  loading?: boolean;
  /** Text shown while loading. Defaults to "…". */
  loadingLabel?: string;
  /** Container width — defaults to "100%". */
  width?: string;
  /** Extra class. */
  className?: string;
  style?: CSSProperties;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const BASE_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  width: "100%",
  minHeight: "44px",
  padding: "0.75rem 1.5rem",
  backgroundColor: "var(--color-ink)",
  color: "var(--color-paper)",
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  fontWeight: 500,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  border: "none",
  borderRadius: 0, /* Hard rule */
  cursor: "pointer",
  userSelect: "none",
  WebkitTapHighlightColor: "transparent",
};

const DISABLED_OVERRIDES: CSSProperties = {
  opacity: 0.38,
  cursor: "not-allowed",
};

const LOADING_OVERRIDES: CSSProperties = {
  opacity: 0.65,
  cursor: "wait",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Solid black CTA button — no radius, uppercase tracking.
 *
 * @param props - {@link SolidCTAProps}
 * @returns The button element.
 */
export default function SolidCTA({
  children,
  disabled,
  loading = false,
  loadingLabel = "…",
  width = "100%",
  className,
  style,
  onClick,
  type = "button",
  ...rest
}: SolidCTAProps): ReactNode {
  const isDisabled = disabled || loading;

  /* BEFORE render log */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("SolidCTA.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      loading,
      disabled,
    });
  }

  const computedStyle: CSSProperties = {
    ...BASE_STYLE,
    width,
    ...(loading ? LOADING_OVERRIDES : {}),
    ...(disabled ? DISABLED_OVERRIDES : {}),
    ...style,
  };

  return (
    <button
      type={type}
      disabled={isDisabled}
      aria-disabled={isDisabled ? "true" : undefined}
      aria-busy={loading ? "true" : undefined}
      className={className}
      style={computedStyle}
      onClick={!isDisabled ? onClick : undefined}
      {...rest}
    >
      {loading ? loadingLabel : children}
    </button>
  );
}
