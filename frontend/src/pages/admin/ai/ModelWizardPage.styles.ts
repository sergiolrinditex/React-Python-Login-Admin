/**
 * Hilo People — ModelWizardPage token-only inline style constants.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-WIZARD-STYLES
 *
 * Responsibility: Extracts inline CSSProperties constants from ModelWizardPage.tsx
 *   to stay within the ~300-line file-size cap (mirrors AdminAiModelsPage.styles.ts).
 *   ALL values are CSS custom properties or unitless/token references —
 *   NO hardcoded colors, pixel values, or font names.
 *
 * Consumers: ModelWizardPage.tsx only.
 * Source: §3.7 Theme & Design System, UX_CONTRACT §5 Visual Implementation Contract.
 */

import type { CSSProperties } from "react";

// ---------------------------------------------------------------------------
// Page layout
// ---------------------------------------------------------------------------

export const PAGE_TITLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1.5rem",
  color: "var(--color-ink)",
  margin: "0 0 0.25rem",
};

export const PAGE_SUBTITLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.8125rem",
  color: "var(--color-ink)",
  opacity: 0.55,
  margin: "0 0 2rem",
};

// ---------------------------------------------------------------------------
// Form layout
// ---------------------------------------------------------------------------

export const FORM_SECTION: CSSProperties = {
  maxWidth: "480px",
  display: "flex",
  flexDirection: "column",
  gap: "1.5rem",
};

export const FIELD_ROW: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.375rem",
  width: "100%",
};

export const FORM_ACTIONS: CSSProperties = {
  display: "flex",
  gap: "1rem",
  alignItems: "center",
  marginTop: "0.5rem",
  flexWrap: "wrap",
};

// ---------------------------------------------------------------------------
// Select field — matches EditorialInput visual style
// ---------------------------------------------------------------------------

export const SELECT_STYLE: CSSProperties = {
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
  outline: "none",
  lineHeight: 1.4,
  cursor: "pointer",
  appearance: "none",
  WebkitAppearance: "none",
};

export const SELECT_ERROR_STYLE: CSSProperties = {
  ...SELECT_STYLE,
  borderBottomWidth: "2px",
};

export const ERROR_TEXT: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  marginTop: "0.25rem",
};

// ---------------------------------------------------------------------------
// Secret field wrapper (relative for show/hide button placement)
// ---------------------------------------------------------------------------

export const SECRET_WRAPPER: CSSProperties = {
  position: "relative",
};

export const SHOW_HIDE_BUTTON: CSSProperties = {
  position: "absolute",
  right: 0,
  top: "0.625rem",
  background: "none",
  border: "none",
  cursor: "pointer",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.6,
  padding: "0.25rem",
  minHeight: "44px",
  minWidth: "44px",
  display: "flex",
  alignItems: "center",
  justifyContent: "flex-end",
};

// ---------------------------------------------------------------------------
// State views (loading, error, success, models)
// ---------------------------------------------------------------------------

export const CENTER_BLOCK: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  gap: "1.25rem",
  maxWidth: "480px",
};

export const BODY_TEXT: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  color: "var(--color-ink)",
  opacity: 0.75,
  lineHeight: 1.6,
  margin: 0,
};

export const SUCCESS_SECTION: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1.5rem",
  maxWidth: "600px",
};

export const MODELS_TABLE_WRAPPER: CSSProperties = {
  marginTop: "1rem",
};

export const STEP_INDICATOR: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.5,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase" as const,
  marginBottom: "1.5rem",
};

// ---------------------------------------------------------------------------
// Step heading (shared across provider/credentials/models steps)
// ---------------------------------------------------------------------------

export const STEP_HEADING: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1.125rem",
  color: "var(--color-ink)",
  margin: "0 0 1.5rem",
};

export const STEP_HEADING_TIGHT: CSSProperties = {
  ...STEP_HEADING,
  margin: "0 0 0.5rem",
};
