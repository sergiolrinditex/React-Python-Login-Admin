/**
 * Hilo People — StatusDot component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: monochrome dot + tracked label combo for status indication.
 *   NOT color-only — the label always accompanies the dot (WCAG 1.4.1).
 *   Used on: McpServersPage (server health), AdminDashboard (provider status),
 *   UsagePage (service status).
 *   Journey refs: J103 (admin — provider status), J104 (MCP config health).
 *
 * Token usage: --color-ink, --tracking-label.
 * Prohibitions: NO colored badges, NO border-radius > 0, NO box-shadow.
 *
 * Accessibility: never conveys state through color alone — the label text
 *   is always visible and the dot opacity/pattern varies for distinction.
 *
 * Key deps: React 19, TrackedLabel, CSS custom properties from tokens.css.
 */

import type { CSSProperties, ReactNode } from "react";
import TrackedLabel from "./TrackedLabel";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type StatusDotState = "active" | "inactive" | "syncing" | "error";

export interface StatusDotProps {
  state: StatusDotState;
  /** Optional override for the label text — defaults to state name. */
  label?: string;
  className?: string;
  style?: CSSProperties;
  /** Aria label for the container when used outside a table cell. */
  "aria-label"?: string;
}

// ---------------------------------------------------------------------------
// Config
// ---------------------------------------------------------------------------

const STATE_CONFIG: Record<
  StatusDotState,
  { label: string; opacity: number; variant: "default" | "active" | "muted" }
> = {
  active:   { label: "Active",   opacity: 1,    variant: "active"  },
  inactive: { label: "Inactive", opacity: 0.38, variant: "muted"   },
  syncing:  { label: "Syncing",  opacity: 0.65, variant: "default" },
  error:    { label: "Error",    opacity: 0.85, variant: "active"  },
};

const CONTAINER_STYLE: CSSProperties = {
  display: "inline-flex",
  alignItems: "center",
  gap: "0.5rem",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Status dot with accessible label — monochrome only.
 *
 * @param props - {@link StatusDotProps}
 * @returns The dot + label combination.
 */
export default function StatusDot({
  state,
  label: labelOverride,
  className,
  style,
  "aria-label": ariaLabel,
}: StatusDotProps): ReactNode {
  const config = STATE_CONFIG[state];
  const labelText = labelOverride ?? config.label;

  /* dot pattern: syncing uses hollow circle, error uses "×", others use filled dot */
  const dotChar =
    state === "error" ? "×" : state === "syncing" ? "○" : "●";

  /* BEFORE render log */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("StatusDot.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      state,
    });
  }

  const dotStyle: CSSProperties = {
    display: "inline-block",
    fontSize: state === "error" ? "0.875rem" : "0.625rem",
    lineHeight: 1,
    color: "var(--color-ink)",
    opacity: config.opacity,
    userSelect: "none",
    fontFamily: "var(--font-sans)",
  };

  return (
    <span
      className={className}
      style={{ ...CONTAINER_STYLE, ...style }}
      aria-label={ariaLabel ?? `Status: ${labelText}`}
    >
      <span aria-hidden="true" style={dotStyle}>
        {dotChar}
      </span>
      <TrackedLabel variant={config.variant}>
        {labelText}
      </TrackedLabel>
    </span>
  );
}
