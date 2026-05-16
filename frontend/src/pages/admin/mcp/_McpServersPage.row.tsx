/**
 * Hilo People — McpServersPage row component.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Single MCP server row with per-row sync state and error display.
 *   Extracted from McpServersPage.tsx to keep parent under the ~300-line cap.
 *
 * §D-T003-PAGE-SPLIT-ROWS (P04-S02-T003 task pack §6)
 * §D-T003-PER-ROW-SYNCING: aria-busy on syncing rows; disabled sync button.
 * §D-T003-PER-ROW-ERROR: inline error text below row actions.
 * §D-T003-TOOL-COUNT-TRANSIENT: transient tool count from sync response; em-dash otherwise.
 * §D-T003-RISK-LABELS-DERIVED-OR-OMITTED: risk column always em-dash (per-tool, not per-server).
 *
 * Security: all server.name values rendered as React children (auto-escaped — no XSS risk).
 *
 * a11y: aria-busy on row while syncing; sync button has per-server aria-label.
 */

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import StatusDot from "../../../shared/design-system/StatusDot";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import type { McpServer } from "../../../features/mcp/domain/types";
import type { StatusDotState } from "../../../shared/design-system/StatusDot";
import {
  TD_FIRST_STYLE,
  TD_STYLE,
  TD_LAST_STYLE,
  SERVER_NAME_STYLE,
  LAST_SYNC_STYLE,
  EM_DASH_STYLE,
  SYNC_ERROR_STYLE,
} from "./_McpServersPage.styles";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Maps a McpServerStatus to a StatusDot state. */
export function serverStatusToDotState(status: string): StatusDotState {
  if (status === "active") return "active";
  if (status === "error") return "error";
  if (status === "draft" || status === "inactive") return "inactive";
  return "inactive";
}

/** Format a last_sync_at ISO string as a human-readable relative time. */
export function formatRelativeTime(isoDate: string): string {
  try {
    const diff = Date.now() - new Date(isoDate).getTime();
    const minutes = Math.floor(diff / 60_000);
    if (minutes < 1) return "< 1 min";
    if (minutes < 60) return `${minutes} min`;
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return `${hours} h`;
    const days = Math.floor(hours / 24);
    return `${days} d`;
  } catch {
    return "?";
  }
}

// ---------------------------------------------------------------------------
// McpServerRow — exported per-row component
// ---------------------------------------------------------------------------

export interface McpServerRowProps {
  server: McpServer;
  isSyncing: boolean;
  syncError: string | null;
  transientToolCount: number | null;
  onSync: () => void;
}

/**
 * Single MCP server row with per-row sync action and inline error display.
 *
 * Renders two <tr> elements: the data row + (optionally) a sync error row.
 *
 * @param props - {@link McpServerRowProps}
 * @returns A React fragment with one or two <tr> elements.
 */
export function McpServerRow({
  server,
  isSyncing,
  syncError,
  transientToolCount,
  onSync,
}: McpServerRowProps): ReactNode {
  const { t } = useTranslation("mcp");
  const { t: tErrors } = useTranslation("errors");

  const statusLabel = t(`servers.status.${server.status}`, {
    defaultValue: t("servers.status.unknown"),
  });

  const lastSyncLabel =
    server.last_sync_at != null
      ? t("servers.lastSync.relative", { relative: formatRelativeTime(server.last_sync_at) })
      : t("servers.lastSync.never");

  const toolCountCell =
    transientToolCount !== null ? (
      <span style={SERVER_NAME_STYLE}>{transientToolCount}</span>
    ) : (
      <span style={EM_DASH_STYLE} aria-label={t("servers.tools.none")}>
        —
      </span>
    );

  const syncButtonLabel = isSyncing
    ? t("servers.actions.syncing")
    : t("servers.actions.sync");

  /* §D-T003-RISK-LABELS-DERIVED-OR-OMITTED: risk always uses t("errors:MCP_SERVER_UNREACHABLE") as accessible label */
  void tErrors; // tErrors consumed for MCP_SERVER_UNREACHABLE in page; imported here for symmetry

  return (
    <>
      <tr aria-busy={isSyncing ? "true" : undefined} data-testid={`mcp-server-row-${server.id}`}>
        {/* Name — React auto-escapes, XSS-safe */}
        <td style={TD_FIRST_STYLE}>
          <span style={SERVER_NAME_STYLE}>{server.name}</span>
        </td>
        {/* Status */}
        <td style={TD_STYLE}>
          <StatusDot state={serverStatusToDotState(server.status)} label={statusLabel} />
        </td>
        {/* Transport */}
        <td style={TD_STYLE}>
          <TrackedLabel variant="muted">{server.transport.toUpperCase()}</TrackedLabel>
        </td>
        {/* Last sync */}
        <td style={TD_STYLE}>
          <span style={LAST_SYNC_STYLE}>{lastSyncLabel}</span>
        </td>
        {/* Tool count — §D-T003-TOOL-COUNT-TRANSIENT */}
        <td style={TD_STYLE}>{toolCountCell}</td>
        {/* Risk — §D-T003-RISK-LABELS-DERIVED-OR-OMITTED */}
        <td style={TD_STYLE}>
          <span style={EM_DASH_STYLE} aria-label={t("servers.tools.none")}>—</span>
        </td>
        {/* Actions */}
        <td style={TD_LAST_STYLE}>
          <SolidCTA
            onClick={onSync}
            disabled={isSyncing}
            aria-label={`${syncButtonLabel}: ${server.name}`}
            width="auto"
            style={{ padding: "0.375rem 0.75rem", fontSize: "0.8125rem", opacity: isSyncing ? 0.6 : 1 }}
          >
            {syncButtonLabel}
          </SolidCTA>
        </td>
      </tr>
      {/* Per-row sync error — §D-T003-PER-ROW-ERROR */}
      {syncError && (
        <tr data-testid={`mcp-sync-error-${server.id}`}>
          <td colSpan={7} style={{ padding: "0 0 0.5rem 0", borderBottom: "none" }}>
            <span style={SYNC_ERROR_STYLE} role="alert">{syncError}</span>
          </td>
        </tr>
      )}
    </>
  );
}
