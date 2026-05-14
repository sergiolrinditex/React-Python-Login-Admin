/**
 * Hilo People — ConversationPage style constants (§D-T002-PAGE-SPLIT-STYLES).
 *
 * Slice/Phase: P03-S02-T002 — ConversationPage / Phase 3.
 *
 * Responsibility: CSSProperties constants for ConversationPage.tsx.
 *   Split out per §D-T002-FILE-SIZE-DISCIPLINE to keep the main page under the
 *   ~300 substantive-lines cap.
 *
 * Token usage: --color-ink, --color-paper, --color-bg, --font-display,
 *   --font-sans, --hairline. No hardcoded color literals.
 */

import type { CSSProperties } from "react";

export const PAGE_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1.5rem",
  paddingBottom: "2rem",
};

export const HEADER_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  paddingBottom: "0.75rem",
};

export const TRANSCRIPT_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1.5rem",
};

export const MESSAGE_BLOCK_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.375rem",
};

export const USER_TEXT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  color: "var(--color-ink)",
  lineHeight: 1.5,
  margin: 0,
};

export const ASSISTANT_TEXT_STYLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1rem",
  color: "var(--color-ink)",
  lineHeight: 1.6,
  margin: 0,
};

export const CITATIONS_ROW_STYLE: CSSProperties = {
  display: "inline-flex",
  flexWrap: "wrap",
  gap: "0.25rem",
  marginTop: "0.25rem",
};

export const LOADING_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.6,
};

/** CSS animation for streaming cursor blink */
export const CURSOR_STYLE: CSSProperties = {
  display: "inline-block",
  animation: "blink 1s step-end infinite",
  fontFamily: "var(--font-display)",
  fontSize: "1rem",
  color: "var(--color-ink)",
};
