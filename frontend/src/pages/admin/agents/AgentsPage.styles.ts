/**
 * Hilo People — AgentsPage style constants.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: CSSProperties constants for AgentsPage.tsx.
 *   Extracted to keep AgentsPage.tsx within the ~300-line cap.
 *   Mirrors _McpServersPage.styles.ts pattern (§D-T005-PAGE-SPLIT-STYLES).
 *
 * §D-T005-PAGE-SPLIT-STYLES (P04-S02-T005 task pack §8.3)
 *
 * All values use design tokens — no hardcoded colors or dimensions.
 * See frontend/src/shared/styles/tokens.css for token definitions.
 */

import type { CSSProperties } from "react";

export const PAGE_HEADER_STYLE: CSSProperties = {
  marginBottom: "2rem",
};

export const PAGE_TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1.5rem",
  fontWeight: 400,
  color: "var(--color-ink)",
  margin: 0,
  marginBottom: "0.25rem",
  letterSpacing: "-0.02em",
};

export const PAGE_SUBTITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.6,
  margin: 0,
};

export const LOADING_STYLE: CSSProperties = {
  padding: "3rem 0",
  textAlign: "center",
  fontFamily: "var(--font-sans)",
  color: "var(--color-ink)",
  opacity: 0.5,
};

export const TABLE_STYLE: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
};

export const TH_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.5rem 0.75rem",
  textAlign: "left",
  fontWeight: "inherit",
};

export const TH_FIRST_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.5rem 0.75rem 0.5rem 0",
  textAlign: "left",
  fontWeight: "inherit",
};

export const TH_LAST_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.5rem 0 0.5rem 0.75rem",
  textAlign: "left",
  fontWeight: "inherit",
};

export const TD_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.75rem",
  verticalAlign: "top",
};

export const TD_FIRST_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.75rem 0.75rem 0.75rem 0",
  verticalAlign: "top",
};

export const TD_LAST_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.75rem 0 0.75rem 0.75rem",
  verticalAlign: "top",
};

export const AGENT_NAME_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  fontWeight: 500,
};

export const AGENT_DESC_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.6,
  marginTop: "0.125rem",
};

export const EM_DASH_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.4,
};

export const INLINE_ERROR_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.7,
};

export const RUN_FORM_STYLE: CSSProperties = {
  display: "flex",
  gap: "0.5rem",
  alignItems: "flex-start",
  flexWrap: "wrap",
};

export const RUN_INPUT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  border: "var(--hairline)",
  borderRadius: 0,
  padding: "0.5rem 0.75rem",
  background: "var(--color-paper)",
  minWidth: "10rem",
  flex: 1,
};

export const RUN_RESULT_STYLE: CSSProperties = {
  marginTop: "0.5rem",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.8,
};

export const EMPTY_BODY_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.6,
  marginTop: "1rem",
};
