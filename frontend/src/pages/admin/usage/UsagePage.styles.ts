/**
 * Hilo People — UsagePage inline styles.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: CSSProperties style constants for UsagePage.
 *   Split from UsagePage.tsx to stay within the 300 LoC cap.
 *   All values reference CSS custom properties from tokens.css — NO hardcoded hex/px literals.
 *
 * Design tokens used (from frontend/src/shared/styles/tokens.css):
 *   --color-bg, --color-ink, --color-paper, --font-display, --font-sans,
 *   --hairline, --tracking-label, --radius
 *
 * Editorial tone: Inditex/Zara — fondo crudo, tinta negra, serif alto contraste,
 *   hairlines, etiquetas uppercase tracked, cero esquinas redondeadas.
 *
 * D-T002-PAGE-SPLIT-STYLES: Conditional write_set anchor for this file.
 * Source ref: §D-T002-PAGE-SPLIT-STYLES, task pack §10 allowed_paths.
 */

import type { CSSProperties } from "react";

/** Top-level page wrapper — desktop admin shell (D-T002-DESKTOP-SHELL). */
export const PAGE_STYLE: CSSProperties = {
  minHeight: "100vh",
  backgroundColor: "var(--color-bg)",
  fontFamily: "var(--font-sans)",
};

/** Inner content column — max-width container, centered. */
export const CONTENT_STYLE: CSSProperties = {
  maxWidth: "1100px",
  margin: "0 auto",
  padding: "3rem 2rem",
};

/** Page header block — title + subtitle above the table. */
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

/** Empty state wrapper — centered wordmark + body. */
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

/** Table header cell — numeric columns aligned right. */
export const TH_RIGHT_STYLE: CSSProperties = {
  ...TH_STYLE,
  textAlign: "right",
};

/** Table data cell. */
export const TD_STYLE: CSSProperties = {
  padding: "0.75rem 1rem",
  color: "var(--color-ink)",
  borderBottom: "var(--hairline)",
  whiteSpace: "nowrap",
};

/** Table data cell — numeric columns aligned right. */
export const TD_RIGHT_STYLE: CSSProperties = {
  ...TD_STYLE,
  textAlign: "right",
  fontVariantNumeric: "tabular-nums",
};

/** Totals row — slightly distinct styling. */
export const TOTALS_TR_STYLE: CSSProperties = {
  borderTop: "var(--hairline)",
  backgroundColor: "var(--color-ink)",
};

/** Totals row cell. */
export const TOTALS_TD_STYLE: CSSProperties = {
  ...TD_STYLE,
  color: "var(--color-bg)",
  fontWeight: 600,
  borderBottom: "none",
};

/** Totals row cell — numeric right-aligned. */
export const TOTALS_TD_RIGHT_STYLE: CSSProperties = {
  ...TD_RIGHT_STYLE,
  color: "var(--color-bg)",
  fontWeight: 600,
  borderBottom: "none",
};

/** Next action link below the table. */
export const NEXT_ACTION_STYLE: CSSProperties = {
  marginTop: "2rem",
  paddingTop: "1.5rem",
  borderTop: "var(--hairline)",
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
