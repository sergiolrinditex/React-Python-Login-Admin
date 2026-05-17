/**
 * Hilo People — McpWizardPage style constants.
 *
 * Slice/Phase: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: CSSProperties constants and native select styles for McpWizardPage.tsx.
 *   Extracted to keep McpWizardPage.tsx within the ~300-line cap.
 *
 * §D-T004-PAGE-SPLIT-STYLES (P04-S02-T004 task pack §6)
 * §D-T004-SELECT-STYLE (R-5 mitigation): native <select> styled with hairline bottom
 *   border to match EditorialInput. No border-radius, no shadow, no rounded corners.
 *
 * All values use design tokens — no hardcoded colors or dimensions.
 * See frontend/src/shared/styles/tokens.css for token definitions.
 *
 * Key deps: React CSSProperties only; no runtime imports.
 */

import type { CSSProperties } from "react";

// ---------------------------------------------------------------------------
// Page layout
// ---------------------------------------------------------------------------

/** Main page header area with bottom margin. */
export const WIZARD_HEADER_STYLE: CSSProperties = {
  marginBottom: "2rem",
};

/** Page title — display font, editorial weight. */
export const WIZARD_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1.5rem",
  fontWeight: 400,
  color: "var(--color-ink)",
  margin: 0,
  marginBottom: "0.25rem",
  letterSpacing: "-0.02em",
};

/** Page subtitle — muted paragraph. */
export const WIZARD_SUBTITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.6,
  margin: 0,
};

// ---------------------------------------------------------------------------
// Form layout
// ---------------------------------------------------------------------------

/** Max-width single-column form container. */
export const FORM_STYLE: CSSProperties = {
  maxWidth: "480px",
  display: "flex",
  flexDirection: "column",
  gap: "1.5rem",
};

/** Field group wrapper — used to group label + control + error. */
export const FIELD_GROUP_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.375rem",
};

// ---------------------------------------------------------------------------
// Native <select> styling — §D-T004-SELECT-STYLE
// Hairline bottom border only; no border-radius; no shadow.
// Matches EditorialInput visual contract exactly.
// ---------------------------------------------------------------------------

/** Label style for native <select> fields (uppercase tracked via TrackedLabel). */
export const SELECT_LABEL_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
};

/** Base native <select> style — hairline bottom border, no radius, no shadow. */
export const SELECT_BASE_STYLE: CSSProperties = {
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
  appearance: "auto", /* native arrow for accessibility */
  cursor: "pointer",
};

/** Disabled state overlay for native <select>. */
export const SELECT_DISABLED_STYLE: CSSProperties = {
  ...SELECT_BASE_STYLE,
  opacity: 0.4,
  cursor: "not-allowed",
};

/** Error variant for native <select> — thicker bottom border. */
export const SELECT_ERROR_STYLE: CSSProperties = {
  ...SELECT_BASE_STYLE,
  borderBottomWidth: "2px",
};

/** Error text below a field — matches EditorialInput error style. */
export const FIELD_ERROR_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  marginTop: "0.25rem",
};

// ---------------------------------------------------------------------------
// Inline feedback blocks
// ---------------------------------------------------------------------------

/** Form-level error block (network / server error) above submit button. */
export const FORM_ERROR_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  padding: "0.75rem 0",
  borderTop: "var(--hairline)",
};

/** Success block (post-201). */
export const SUCCESS_BLOCK_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  padding: "0.75rem 0",
  borderTop: "var(--hairline)",
};

/** Success title — display font, smaller. */
export const SUCCESS_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1rem",
  fontWeight: 400,
  color: "var(--color-ink)",
  margin: 0,
  marginBottom: "0.25rem",
};

/** Success subtitle — muted. */
export const SUCCESS_BODY_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.6,
  margin: 0,
};

/** Permission denied block. */
export const PERMISSION_DENIED_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  padding: "0.75rem 0",
  borderTop: "var(--hairline)",
};

/** Permission denied title. */
export const PERMISSION_DENIED_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1rem",
  fontWeight: 400,
  color: "var(--color-ink)",
  margin: 0,
  marginBottom: "0.5rem",
};

// ---------------------------------------------------------------------------
// Submit row
// ---------------------------------------------------------------------------

/** Submit row — horizontal buttons. */
export const SUBMIT_ROW_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "row",
  gap: "0.75rem",
  marginTop: "0.5rem",
};

/** Back/Cancel link button — ink text, no background. */
export const CANCEL_BTN_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
  background: "transparent",
  border: "none",
  borderRadius: 0,
  cursor: "pointer",
  opacity: 0.6,
  minHeight: "44px",
  padding: "0 0.75rem",
};
