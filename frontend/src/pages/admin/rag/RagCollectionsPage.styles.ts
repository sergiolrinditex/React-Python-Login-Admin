/**
 * Hilo People — RagCollectionsPage CSSProperties constants.
 *
 * Slice/Phase: P04-S02-T002 — RagCollectionsPage / Phase 4 Complete Features.
 *
 * Responsibility: Style constants for RagCollectionsPage and its sub-components.
 *   All values use design tokens (CSS custom props) only.
 *
 * §D-T002-FILESIZE-STYLES: mirrors RagDocumentsPage.styles.ts split pattern.
 *
 * Token compliance: NO hex literals, NO border-radius > 0, NO decorative shadows.
 *   All colors via var(--color-*), all fonts via var(--font-*).
 */

import type { CSSProperties } from "react";

// ---------------------------------------------------------------------------
// Page layout
// ---------------------------------------------------------------------------

export const PAGE_HEADER_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  paddingBottom: "1.5rem",
  marginBottom: "2rem",
};

export const PAGE_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1.5rem",
  fontWeight: 400,
  color: "var(--color-ink)",
  margin: 0,
  marginBottom: "0.25rem",
};

export const PAGE_SUBTITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.6,
  margin: 0,
};

/** Back-link button to documents page. Mirrors COLLECTIONS_LINK_STYLE from T001. */
export const DOCUMENTS_LINK_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  minHeight: "44px",
  fontFamily: "var(--font-sans)",
  fontSize: "0.8125rem",
  color: "var(--color-ink)",
  opacity: 0.7,
  textDecoration: "underline",
  cursor: "pointer",
  background: "none",
  border: "none",
  padding: 0,
  marginTop: "0.75rem",
};

// ---------------------------------------------------------------------------
// Collection list section
// ---------------------------------------------------------------------------

export const LIST_SECTION_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  fontWeight: 500,
  color: "var(--color-ink)",
  marginBottom: "1rem",
};

// ---------------------------------------------------------------------------
// Table styles
// ---------------------------------------------------------------------------

export const TABLE_STYLE: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontFamily: "var(--font-sans)",
};

export const TH_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.5rem 0",
  textAlign: "left",
  fontWeight: "inherit",
};

export const TD_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.75rem 0",
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  verticalAlign: "middle",
};

// ---------------------------------------------------------------------------
// Inline edit controls
// ---------------------------------------------------------------------------

/** Text input for vertical field (free text). */
export const FIELD_INPUT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  background: "var(--color-paper)",
  border: "var(--hairline)",
  borderRadius: 0,
  padding: "0.375rem 0.5rem",
  width: "100%",
  maxWidth: "14rem",
  outline: "none",
};

/** Select for language field. */
export const FIELD_SELECT_STYLE: CSSProperties = {
  ...FIELD_INPUT_STYLE,
  appearance: "none",
  cursor: "pointer",
};

/** Toggle button for enabled field. §D-T002-INLINE-EDIT tap-target ≥44px. */
export const TOGGLE_BTN_STYLE: CSSProperties = {
  background: "transparent",
  border: "var(--hairline)",
  borderRadius: 0,
  padding: "0.25rem 0.75rem",
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
  cursor: "pointer",
  minHeight: "44px",
  minWidth: "44px",
};

// ---------------------------------------------------------------------------
// Live region (aria-live)
// ---------------------------------------------------------------------------

export const LIVE_REGION_STYLE: CSSProperties = {
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0,0,0,0)",
  whiteSpace: "nowrap",
  border: 0,
};
