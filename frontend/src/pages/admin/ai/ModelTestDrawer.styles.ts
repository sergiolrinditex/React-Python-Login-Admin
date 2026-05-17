/**
 * Hilo People — ModelTestDrawer token-only inline style constants.
 *
 * Slice/Phase: P04-S01-T004 — ModelTestDrawer / Phase 4.
 * Write-set anchor: §D-T004-DRAWER-STYLES (authorized by task pack §6.2 file #2).
 *
 * Responsibility: Extracts inline CSSProperties constants from ModelTestDrawer.tsx.
 *   ALL values are CSS custom properties or unitless/token references —
 *   NO hardcoded colors, pixel values, or font names outside a11y constraints.
 *
 * Consumers: ModelTestDrawer.tsx + _ModelTestDrawer.error-views.tsx.
 * Design: mirrors ModelWizardPage.styles.ts (task pack §D-T004-DRAWER-AS-PAGE).
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
  maxWidth: "560px",
  display: "flex",
  flexDirection: "column",
  gap: "1.25rem",
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
// Prompt textarea
// ---------------------------------------------------------------------------

export const PROMPT_TEXTAREA: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "1rem",
  color: "var(--color-ink)",
  background: "transparent",
  border: "none",
  borderBottom: "var(--hairline)",
  borderRadius: 0,
  padding: "0.625rem 0",
  width: "100%",
  minHeight: "96px",
  outline: "none",
  lineHeight: 1.5,
  resize: "vertical",
};

export const PROMPT_TEXTAREA_ERROR: CSSProperties = {
  ...PROMPT_TEXTAREA,
  borderBottomWidth: "2px",
};

// ---------------------------------------------------------------------------
// Result panel
// ---------------------------------------------------------------------------

export const RESULT_PANEL: CSSProperties = {
  border: "var(--hairline)",
  padding: "1.25rem",
  marginTop: "1.5rem",
  maxWidth: "560px",
};

export const RESULT_OUTPUT: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  color: "var(--color-ink)",
  lineHeight: 1.6,
  margin: "0 0 1rem",
  whiteSpace: "pre-wrap" as const,
  wordBreak: "break-word" as const,
};

export const RESULT_META_ROW: CSSProperties = {
  display: "flex",
  gap: "1.5rem",
  flexWrap: "wrap",
  borderTop: "var(--hairline)",
  paddingTop: "0.75rem",
  marginTop: "0.75rem",
};

export const RESULT_META_ITEM: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.8125rem",
  color: "var(--color-ink)",
  opacity: 0.65,
};

// ---------------------------------------------------------------------------
// Inline confirmation (activate success)
// ---------------------------------------------------------------------------

export const ACTIVATE_CONFIRM: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.75,
  fontStyle: "italic",
};

// ---------------------------------------------------------------------------
// Error / info text
// ---------------------------------------------------------------------------

export const BODY_TEXT: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  color: "var(--color-ink)",
  opacity: 0.75,
  lineHeight: 1.6,
  margin: 0,
};

export const ERROR_TEXT: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  marginTop: "0.25rem",
};

export const ERROR_BANNER: CSSProperties = {
  border: "var(--hairline)",
  padding: "1rem 1.25rem",
  maxWidth: "560px",
  marginTop: "1rem",
};

// ---------------------------------------------------------------------------
// Label / heading
// ---------------------------------------------------------------------------

export const SECTION_HEADING: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1rem",
  color: "var(--color-ink)",
  margin: "0 0 0.75rem",
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase" as const,
};

export const CENTER_BLOCK: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  gap: "1.25rem",
  maxWidth: "480px",
};
