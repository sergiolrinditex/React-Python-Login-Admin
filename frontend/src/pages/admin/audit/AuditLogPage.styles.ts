/**
 * Hilo People — AuditLogPage inline styles.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: CSSProperties style constants for AuditLogPage.
 *   Split from AuditLogPage.tsx to stay within the 300 LoC cap.
 *   All values reference CSS custom properties from tokens.css — NO hardcoded hex/px literals.
 *
 * Design tokens used (from frontend/src/shared/styles/tokens.css):
 *   --color-bg, --color-ink, --color-paper, --font-display, --font-sans,
 *   --hairline, --tracking-label, --radius
 *
 * Editorial tone: Inditex/Zara — fondo crudo, tinta negra, serif alto contraste,
 *   hairlines, etiquetas uppercase tracked, cero esquinas redondeadas.
 *   D-T001-NO-COLOR: monochrome only (audit rows have no status color).
 *
 * §D-T001-PAGE: Conditional write_set anchor for this file.
 * Source ref: §D-T001-PAGE, UX_CONTRACT §5 Visual Implementation Contract.
 */

import type { CSSProperties } from "react";

/** Top-level page wrapper — desktop admin shell. */
export const PAGE_STYLE: CSSProperties = {
  minHeight: "100vh",
  backgroundColor: "var(--color-bg)",
  fontFamily: "var(--font-sans)",
};

/** Inner content column — max-width container, centered. */
export const CONTENT_STYLE: CSSProperties = {
  maxWidth: "1200px",
  margin: "0 auto",
  padding: "3rem 2rem",
};

/** Page header block — title + subtitle above filters. */
export const HEADER_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  paddingBottom: "2rem",
  marginBottom: "2.5rem",
};

/** Page title — display serif, editorial weight. */
export const TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "2rem",
  fontWeight: 700,
  color: "var(--color-ink)",
  margin: 0,
  letterSpacing: "-0.02em",
};

/** Subtitle / range description — uppercase tracked sans. */
export const SUBTITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 400,
  color: "var(--color-ink)",
  opacity: 0.6,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  marginTop: "0.5rem",
};

/** Filters form container. */
export const FILTERS_STYLE: CSSProperties = {
  display: "flex",
  flexWrap: "wrap",
  gap: "1rem",
  alignItems: "flex-end",
  marginBottom: "2rem",
  paddingBottom: "1.5rem",
  borderBottom: "var(--hairline)",
};

/** Individual filter field wrapper. */
export const FILTER_FIELD_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.25rem",
  minWidth: "180px",
};

/** Filter label — uppercase tracked. */
export const FILTER_LABEL_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  fontWeight: 600,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
  opacity: 0.6,
};

/** Filter input — hairline border, no radius. */
export const FILTER_INPUT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  backgroundColor: "var(--color-bg)",
  border: "var(--hairline)",
  padding: "0.5rem 0.75rem",
  outline: "none",
  minHeight: "44px",
  minWidth: "180px",
};

/** Filter submit button — solid CTA. */
export const FILTER_SUBMIT_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  backgroundColor: "var(--color-ink)",
  color: "var(--color-bg)",
  border: "none",
  padding: "0.875rem 1.75rem",
  cursor: "pointer",
  minHeight: "44px",
};

/** Filter reset button — ghost style. */
export const FILTER_RESET_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  backgroundColor: "transparent",
  color: "var(--color-ink)",
  border: "var(--hairline)",
  padding: "0.875rem 1.75rem",
  cursor: "pointer",
  minHeight: "44px",
};

/** Inline validation error for filters. */
export const VALIDATION_MSG_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.8125rem",
  color: "var(--color-ink)",
  opacity: 0.8,
  marginBottom: "1rem",
};

/** Loading skeleton container. */
export const SKELETON_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
};

/** Single skeleton row bar. */
export const SKELETON_ROW_STYLE: CSSProperties = {
  height: "2.5rem",
  backgroundColor: "var(--color-ink)",
  opacity: 0.06,
};

/** Empty state wrapper — aligned left. */
export const EMPTY_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "flex-start",
  gap: "1rem",
  padding: "3rem 0",
};

/** Wordmark in empty state. */
export const EMPTY_WORDMARK_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "3rem",
  fontWeight: 700,
  color: "var(--color-ink)",
  margin: 0,
};

/** Body text in empty / error states. */
export const BODY_TEXT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  color: "var(--color-ink)",
  opacity: 0.75,
  maxWidth: "40ch",
};

/** CTA link in empty / error states. */
export const LINK_CTA_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  fontWeight: 600,
  color: "var(--color-ink)",
  textDecoration: "underline",
  textUnderlineOffset: "3px",
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  cursor: "pointer",
};

/** Error container wrapper. */
export const ERROR_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  padding: "2rem 0",
};

/** Retry / back button — solid CTA black. */
export const SOLID_BTN_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  backgroundColor: "var(--color-ink)",
  color: "var(--color-bg)",
  border: "none",
  padding: "0.875rem 1.75rem",
  cursor: "pointer",
  minHeight: "44px",
};

/** Table wrapper with hairline border. */
export const TABLE_WRAPPER_STYLE: CSSProperties = {
  overflowX: "auto",
  border: "var(--hairline)",
};

/** The data table itself. */
export const TABLE_STYLE: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
};

/** Table header row. */
export const THEAD_TR_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
};

/** Table header cell — uppercase tracked label. */
export const TH_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  fontWeight: 600,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
  opacity: 0.6,
  textAlign: "left",
  padding: "0.75rem 1rem",
  whiteSpace: "nowrap",
};

/** Table data cell. */
export const TD_STYLE: CSSProperties = {
  padding: "0.75rem 1rem",
  color: "var(--color-ink)",
  borderBottom: "var(--hairline)",
  whiteSpace: "nowrap",
  maxWidth: "200px",
  overflow: "hidden",
  textOverflow: "ellipsis",
};

/** Monospace cell for IDs / UUIDs. */
export const TD_MONO_STYLE: CSSProperties = {
  ...TD_STYLE,
  fontVariantNumeric: "tabular-nums",
  fontFamily: "monospace",
};

/** Next action area below table. */
export const NEXT_ACTION_STYLE: CSSProperties = {
  marginTop: "2rem",
  paddingTop: "1.5rem",
  borderTop: "var(--hairline)",
  display: "flex",
  gap: "1rem",
  alignItems: "center",
};

/** Load-more button. */
export const LOAD_MORE_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  justifyContent: "center",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  backgroundColor: "var(--color-ink)",
  color: "var(--color-bg)",
  border: "none",
  padding: "0.875rem 1.75rem",
  cursor: "pointer",
  minHeight: "44px",
};

/** Disabled next-action CTA (coming soon). */
export const DISABLED_CTA_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 600,
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
  opacity: 0.4,
  cursor: "not-allowed",
};

/** sr-only utility for screen-reader-only content (table caption). */
export const SR_ONLY_STYLE: CSSProperties = {
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0,0,0,0)",
  whiteSpace: "nowrap",
  borderWidth: 0,
};
