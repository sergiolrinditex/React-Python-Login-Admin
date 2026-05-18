/**
 * Hilo People — AccountPage style constants.
 *
 * Slice/Phase: P03-S02-T007 — AccountPage (profile + language + logout) / Phase 3.
 *
 * Responsibility: CSSProperties constants for AccountPage layout.
 *   Extracted to honor file-size cap (§D-T007-R7-PREAUTHORIZED-SPLIT,
 *   §D-T004-FILESIZE-EXTRACT-STYLES precedent).
 *
 * Design tokens ONLY. No hardcoded colors, radii, shadows, font-family strings.
 * All values reference CSS custom properties from tokens.css.
 *
 * Prohibitions enforced by design_tokens_v1 enforcer:
 *   - NO border-radius > 0
 *   - NO box-shadow for decoration
 *   - NO hardcoded hex/rgb/hsl
 *   - NO hardcoded font-family strings (use var(--font-sans) / var(--font-display))
 *
 * Key deps: None — pure CSSProperties constants.
 */

import type { CSSProperties } from "react";

// ---------------------------------------------------------------------------
// Page layout
// ---------------------------------------------------------------------------

export const PAGE_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  minHeight: "100%",
};

export const CONTENT_WRAPPER_STYLE: CSSProperties = {
  flex: 1,
  display: "flex",
  flexDirection: "column",
  padding: "1.5rem 1.25rem",
  gap: "0",
};

// ---------------------------------------------------------------------------
// Page header
// ---------------------------------------------------------------------------

export const PAGE_HEADER_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  paddingBottom: "1rem",
  marginBottom: "1.5rem",
};

export const PAGE_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1.5rem",
  fontWeight: 400,
  letterSpacing: "-0.01em",
  color: "var(--color-ink)",
  margin: 0,
};

// ---------------------------------------------------------------------------
// Profile section
// ---------------------------------------------------------------------------

export const SECTION_STYLE: CSSProperties = {
  marginBottom: "1.75rem",
};

export const SECTION_LABEL_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  fontWeight: 500,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase" as const,
  color: "var(--color-ink)",
  opacity: 0.55,
  margin: "0 0 0.75rem 0",
};

export const HAIRLINE_STYLE: CSSProperties = {
  border: "none",
  borderTop: "var(--hairline)",
  margin: 0,
};

export const PROFILE_ROW_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "space-between",
  alignItems: "flex-start",
  padding: "0.625rem 0",
  borderBottom: "var(--hairline)",
};

export const PROFILE_LABEL_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 500,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase" as const,
  color: "var(--color-ink)",
  opacity: 0.55,
  flexShrink: 0,
  marginRight: "1rem",
};

export const PROFILE_VALUE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  textAlign: "right" as const,
  wordBreak: "break-word" as const,
};

// ---------------------------------------------------------------------------
// Language picker
// ---------------------------------------------------------------------------

export const LANGUAGE_PICKER_STYLE: CSSProperties = {
  display: "flex",
  gap: "0",
  borderTop: "var(--hairline)",
  borderLeft: "var(--hairline)",
  borderRight: "var(--hairline)",
};

export const LANGUAGE_OPTION_STYLE: CSSProperties = {
  flex: 1,
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  padding: "0.75rem 0.5rem",
  cursor: "pointer",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 500,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase" as const,
  color: "var(--color-ink)",
  borderBottom: "var(--hairline)",
  borderRight: "var(--hairline)",
  background: "var(--color-bg)",
  minHeight: "44px",
  userSelect: "none" as const,
};

export const LANGUAGE_OPTION_SELECTED_STYLE: CSSProperties = {
  ...LANGUAGE_OPTION_STYLE,
  background: "var(--color-ink)",
  color: "var(--color-paper)",
};

export const LANGUAGE_OPTION_PENDING_STYLE: CSSProperties = {
  ...LANGUAGE_OPTION_STYLE,
  opacity: 0.45,
  cursor: "wait",
};

// ---------------------------------------------------------------------------
// Logout section
// ---------------------------------------------------------------------------

export const LOGOUT_SECTION_STYLE: CSSProperties = {
  marginTop: "auto",
  paddingTop: "1.5rem",
};
