/**
 * Hilo People — AccountPage styles.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3 (debugger cycle 1).
 *
 * Responsibility: CSSProperties style constants extracted from AccountPage.tsx
 *   to honor the file-size non-negotiable (`.claude/rules/01-non-negotiables.md §File size`).
 *   Pure presentational data — no business logic, no React state, no hooks.
 *
 * Anchor: §D-T004-FILESIZE-EXTRACT-STYLES (debugger cycle 1).
 *
 * Constraints preserved verbatim from origin:
 *   - Design tokens only — no hardcoded color/spacing/font literals.
 *   - All constants are imported by name from AccountPage.tsx.
 */

import { type CSSProperties } from "react";

export const PAGE_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "2rem",
};

export const SECTION_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
};

export const PROFILE_ROW_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "row",
  justifyContent: "space-between",
  alignItems: "baseline",
  borderBottom: "var(--hairline)",
  paddingBottom: "0.5rem",
};

export const PROFILE_VALUE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
};

export const LANG_PICKER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "row",
  gap: "0.5rem",
};

export const LANG_BTN_BASE: CSSProperties = {
  flex: 1,
  minHeight: "44px",
  backgroundColor: "transparent",
  border: "var(--hairline)",
  borderRadius: 0,
  cursor: "pointer",
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  fontWeight: 500,
  color: "var(--color-ink)",
  letterSpacing: "var(--tracking-label)",
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  gap: "0.25rem",
};

export const LANG_BTN_ACTIVE: CSSProperties = {
  ...LANG_BTN_BASE,
  backgroundColor: "var(--color-ink)",
  color: "var(--color-paper)",
};

export const LOGOUT_BTN_STYLE: CSSProperties = {
  background: "none",
  border: "none",
  padding: 0,
  cursor: "pointer",
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  textDecoration: "underline",
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  minHeight: "44px",
  display: "inline-flex",
  alignItems: "center",
};

export const ERROR_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.75rem",
  padding: "0.5rem 0",
};

export const ERROR_TEXT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.85,
};

export const INLINE_ERROR_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.8,
  marginTop: "0.25rem",
};

export const LOADING_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  opacity: 0.5,
};

export const SKELETON_LINE_STYLE: CSSProperties = {
  height: "1rem",
  backgroundColor: "var(--color-ink)",
  opacity: 0.12,
};
