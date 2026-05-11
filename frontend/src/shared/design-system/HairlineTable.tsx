/**
 * Hilo People — HairlineTable component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: editorial table with hairline row separators. No zebra
 *   striping, no colored headers, no rounded corners. Used on:
 *   AdminDashboardPage (usage summary), RagDocumentsPage (document list),
 *   McpServersPage (server list), AuditLogPage (log entries), UsagePage (stats).
 *   Journey refs: J103 (admin document management), J104 (MCP configuration).
 *
 * Token usage: --hairline, --font-sans, --color-ink.
 * Prohibitions: NO border-radius, NO box-shadow, NO zebra/colored rows.
 *
 * States:
 *   - populated: rows with data.
 *   - empty: "No results" row spanning all columns.
 *   - error_network: error message row with retry CTA.
 *   - permission_denied: access denied row.
 *
 * Accessibility:
 *   - <table> with <caption> (sr-only if empty string).
 *   - <th scope="col"> for column headers.
 *   - role="alert" on error state.
 *
 * Key deps: React 19, CSS custom properties from tokens.css, SolidCTA.
 */

import type { CSSProperties, ReactNode } from "react";
import SolidCTA from "./SolidCTA";
import TrackedLabel from "./TrackedLabel";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export type HairlineTableState = "populated" | "empty" | "error_network" | "permission_denied";

export interface HairlineTableColumn<T = Record<string, unknown>> {
  /** Column header text (TrackedLabel). */
  header: string;
  /** Key in row data or render function. */
  accessor: keyof T | ((row: T) => ReactNode);
}

export interface HairlineTableProps<T = Record<string, unknown>> {
  columns: HairlineTableColumn<T>[];
  rows: T[];
  /** Explicit state override — inferred from rows/error if not provided. */
  state?: HairlineTableState;
  /** Caption for accessibility. Pass "" for purely decorative tables. */
  caption?: string;
  /** Message for empty state. */
  emptyMessage?: string;
  /** Error message for error_network state. */
  errorMessage?: string;
  /** Retry callback for error_network state. */
  onRetry?: () => void;
  className?: string;
  style?: CSSProperties;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const TABLE_STYLE: CSSProperties = {
  width: "100%",
  borderCollapse: "collapse",
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
};

const TH_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.5rem 0",
  textAlign: "left",
  fontWeight: "inherit",
};

const TD_STYLE: CSSProperties = {
  borderBottom: "var(--hairline)",
  padding: "0.75rem 0",
  verticalAlign: "top",
};

const SPAN_CELL_STYLE: CSSProperties = {
  padding: "1.5rem 0",
  textAlign: "center",
  opacity: 0.6,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Editorial hairline table — no zebra, no radius, no shadows.
 *
 * @param props - {@link HairlineTableProps}
 * @returns The table element.
 */
export default function HairlineTable<T = Record<string, unknown>>({
  columns,
  rows,
  state: stateProp,
  caption = "",
  emptyMessage = "No results.",
  errorMessage = "Failed to load data.",
  onRetry,
  className,
  style,
}: HairlineTableProps<T>): ReactNode {
  /* Infer state from rows/error if not explicit */
  const state: HairlineTableState =
    stateProp ??
    (rows.length === 0 ? "empty" : "populated");

  /* BEFORE render log */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("HairlineTable.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      state,
      rowCount: rows.length,
    });
  }

  const colSpan = columns.length;

  return (
    <table className={className} style={{ ...TABLE_STYLE, ...style }}>
      {caption && (
        <caption className="sr-only">{caption}</caption>
      )}
      <thead>
        <tr>
          {columns.map((col) => (
            <th key={String(col.header)} scope="col" style={TH_STYLE}>
              <TrackedLabel variant="muted">{col.header}</TrackedLabel>
            </th>
          ))}
        </tr>
      </thead>
      <tbody>
        {state === "populated" &&
          rows.map((row, i) => (
            <tr key={i}>
              {columns.map((col) => {
                const cellContent =
                  typeof col.accessor === "function"
                    ? col.accessor(row)
                    : (row[col.accessor] as ReactNode);
                return (
                  <td key={String(col.header)} style={TD_STYLE}>
                    {cellContent}
                  </td>
                );
              })}
            </tr>
          ))}

        {state === "empty" && (
          <tr>
            <td colSpan={colSpan} style={{ ...TD_STYLE, ...SPAN_CELL_STYLE }}>
              {emptyMessage}
            </td>
          </tr>
        )}

        {state === "error_network" && (
          <tr>
            <td
              colSpan={colSpan}
              style={{ ...TD_STYLE, ...SPAN_CELL_STYLE }}
              role="alert"
            >
              <span style={{ display: "block", marginBottom: "0.75rem" }}>
                {errorMessage}
              </span>
              {onRetry && (
                <SolidCTA
                  onClick={onRetry}
                  width="auto"
                  style={{ display: "inline-flex", padding: "0.5rem 1rem" }}
                >
                  Retry
                </SolidCTA>
              )}
            </td>
          </tr>
        )}

        {state === "permission_denied" && (
          <tr>
            <td
              colSpan={colSpan}
              style={{ ...TD_STYLE, ...SPAN_CELL_STYLE }}
              role="alert"
            >
              You do not have permission to view this content.
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
