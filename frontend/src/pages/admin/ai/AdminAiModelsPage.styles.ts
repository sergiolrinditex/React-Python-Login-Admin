/**
 * Hilo People — AdminAiModelsPage token-only inline style constants.
 *
 * Slice/Phase: P04-S01-T002 — AdminAiModelsPage / Phase 4.
 * Write-set anchor: §D-T002-FILESIZE-SPLIT-STYLES
 *
 * Responsibility: Extracts inline CSSProperties constants from AdminAiModelsPage.tsx
 *   to stay within the ~300-line file-size cap.
 *   ALL values are CSS custom properties or unitless/token references —
 *   NO hardcoded colors, pixel values, or font names.
 *
 * Consumers: AdminAiModelsPage.tsx only.
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

export const TABLE_SECTION: CSSProperties = {
  marginBottom: "2rem",
};

export const CTA_WRAPPER: CSSProperties = {
  display: "inline-block",
  marginTop: "1.5rem",
};

// ---------------------------------------------------------------------------
// Status dot wrapper (ensures accessible min tap target for inline usage)
// ---------------------------------------------------------------------------

export const STATUS_DOT_CELL: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
};
