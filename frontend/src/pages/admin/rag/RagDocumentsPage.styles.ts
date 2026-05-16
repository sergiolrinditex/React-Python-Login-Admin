/**
 * Hilo People — RagDocumentsPage CSSProperties constants.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Extracted style constants for RagDocumentsPage and its
 *   sub-components. All values use design tokens (CSS custom props) only.
 *
 * §D-RAGDOC-FILESIZE-STYLES: proactive split to keep RagDocumentsPage.tsx under cap.
 *   Pattern from AccountPage.styles.ts (P03-S02-T004 §D-T004-FILESIZE-EXTRACT-STYLES).
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

// §D-T001-DEBUG-C2-TAP-TARGET — Cycle 2 debugger fix:
//   "Ver colecciones →" button measured 36px height in browser (display:inline-block
//   + padding:0). UX_CONTRACT §7 and task pack §Accessibility require tap targets
//   ≥44×44px. Switched to inline-flex with alignItems:center + minHeight:44px so
//   the rendered control meets the WCAG/AA tap target invariant. Padding and
//   tokens are intentionally untouched; copy and i18n keys unchanged.
export const COLLECTIONS_LINK_STYLE: CSSProperties = {
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
// Upload form section
// ---------------------------------------------------------------------------

export const UPLOAD_SECTION_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  paddingBottom: "2rem",
  marginBottom: "2rem",
};

export const UPLOAD_SECTION_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  fontWeight: 500,
  color: "var(--color-ink)",
  marginBottom: "1.25rem",
};

export const UPLOAD_FIELDS_GRID_STYLE: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "1fr 1fr 1fr",
  gap: "1rem",
  marginBottom: "1rem",
};

export const FIELD_GROUP_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.375rem",
};

export const FIELD_LABEL_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  fontWeight: 500,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
  opacity: 0.7,
};

export const FIELD_INPUT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  background: "var(--color-paper)",
  border: "var(--hairline)",
  borderRadius: 0,
  padding: "0.5rem 0.625rem",
  width: "100%",
  outline: "none",
};

export const FIELD_SELECT_STYLE: CSSProperties = {
  ...FIELD_INPUT_STYLE,
  appearance: "none",
  cursor: "pointer",
};

export const FIELD_ERROR_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.85,
  marginTop: "0.25rem",
};

export const SUBMIT_ROW_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "1rem",
  marginTop: "1rem",
};

// ---------------------------------------------------------------------------
// Document list section
// ---------------------------------------------------------------------------

export const LIST_SECTION_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  fontWeight: 500,
  color: "var(--color-ink)",
  marginBottom: "1rem",
};

// ---------------------------------------------------------------------------
// Dedup toast
// ---------------------------------------------------------------------------

export const DEDUP_NOTICE_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  gap: "0.5rem",
  padding: "0.75rem 1rem",
  background: "var(--color-paper)",
  border: "var(--hairline)",
  marginBottom: "1rem",
  fontFamily: "var(--font-sans)",
  fontSize: "0.8125rem",
  color: "var(--color-ink)",
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
