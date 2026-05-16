/**
 * Hilo People — McpServersPage.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 * Route: /admin/ai/mcp
 *
 * Responsibility: Admin page listing MCP servers with per-row sync mutation.
 *   Consumes GET /api/v1/admin/ai/mcp/servers (list) and
 *   POST /api/v1/admin/ai/mcp/servers/{id}/sync (per-row action).
 *   Protected by RequireRole(['people_admin','super_admin']) at router level.
 *
 * §D-T003-PAGE (P04-S02-T003 task pack §5)
 *
 * UX states: loading, empty, syncing (per-row), error_network, permission_denied, success.
 * error_validation = N/A (no form input on this read-only list page).
 *
 * Design tokens: --color-bg, --color-ink, --color-paper, --font-display,
 *   --font-sans, --hairline, --tracking-label, --radius 0.
 * Components: AdminShell, HairlineTable, TrackedLabel, StatusDot, SolidCTA.
 *
 * Split files (pre-authorized per §D-T003-PAGE-SPLIT-STYLES + §D-T003-PAGE-SPLIT-ROWS):
 *   _McpServersPage.styles.ts — CSSProperties constants
 *   _McpServersPage.row.tsx — McpServerRow component
 *
 * §D-T003-TOOL-COUNT-TRANSIENT: tool_count is not in the list response.
 *   Shows em-dash on cold load; transient value from sync response shown post-sync.
 * §D-T003-RISK-LABELS-DERIVED-OR-OMITTED: risk per server not a backend concept.
 *   Shows em-dash + footnote pointing to P04-S02-T004.
 * §D-T003-WIZARD-LINK-PRE-T004: empty CTA links to /admin/ai/mcp/new (404 until T004).
 *
 * Security: React auto-escapes all server.name renders via McpServerRow.
 *   Never use dangerouslySetInnerHTML here.
 *
 * a11y: <table> has accessible caption (sr-only); sync buttons have per-server aria-label;
 *   syncing rows have aria-busy="true"; aria-live region for dynamic status changes.
 *
 * Non-negotiables §logging: BEFORE + AFTER on page render (verbose-gated).
 * Key deps: useMcpServers, useMcpSync, AdminShell, HairlineTable, i18n.
 */

import type { ReactNode } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import AdminShell from "../../../shared/design-system/AdminShell";
import HairlineTable from "../../../shared/design-system/HairlineTable";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import { useAuth } from "../../../features/auth/presentation/AuthProvider";
import { useMcpServers } from "../../../features/mcp/presentation/useMcpServers";
import { useMcpSync } from "../../../features/mcp/presentation/useMcpSync";
import {
  McpForbiddenError,
  McpServerUnreachableError,
  McpServerNotFoundError,
  McpRateLimitedError,
} from "../../../features/mcp/data/errors";
import type { McpServer, McpSyncResult } from "../../../features/mcp/domain/types";
import { McpServerRow } from "./_McpServersPage.row";
import {
  PAGE_HEADER_STYLE,
  PAGE_TITLE_STYLE,
  PAGE_SUBTITLE_STYLE,
  LOADING_STYLE,
  FOOTNOTE_STYLE,
  TABLE_STYLE,
  TH_STYLE,
  TH_FIRST_STYLE,
  TH_LAST_STYLE,
} from "./_McpServersPage.styles";

// ---------------------------------------------------------------------------
// Nav items for AdminShell
// ---------------------------------------------------------------------------

const ADMIN_NAV_ITEMS = [
  { key: "mcp", label: "MCP Servers", active: true },
];

// ---------------------------------------------------------------------------
// McpServersPage
// ---------------------------------------------------------------------------

/**
 * Admin page for MCP server management.
 *
 * Protected by RequireRole(['people_admin','super_admin']) at router level.
 * Implements: loading, empty, syncing (per-row), error_network, permission_denied, success.
 *
 * §D-T003-PAGE, §D-T003-TOOL-COUNT-TRANSIENT, §D-T003-RISK-LABELS-DERIVED-OR-OMITTED
 *
 * @returns The MCP servers admin page.
 */
export default function McpServersPage(): ReactNode {
  const { t } = useTranslation("mcp");
  const { t: tErrors } = useTranslation("errors");
  const navigate = useNavigate();
  const { logout } = useAuth();

  /* BEFORE render log — §D-T003-PAGE */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("McpServersPage.render.start", {
      phase: "P04",
      slice: "P04-S02-T003",
      route: "/admin/ai/mcp",
    });
  }

  // Per-row transient tool counts — §D-T003-TOOL-COUNT-TRANSIENT
  const [toolCounts, setToolCounts] = useState<Record<string, number>>({});
  // Per-row sync error messages — §D-T003-PER-ROW-ERROR
  const [syncErrors, setSyncErrors] = useState<Record<string, string | null>>({});
  // Per-row syncing state — §D-T003-PER-ROW-SYNCING
  const [syncingRows, setSyncingRows] = useState<Record<string, boolean>>({});

  const onAuthFailure = logout;

  const { data: servers, isLoading, isError, error, refetch } = useMcpServers(onAuthFailure);
  const { mutate: syncServer } = useMcpSync(onAuthFailure);

  /** Derive table state from query results. */
  function getTableState() {
    if (isLoading) return "loading";
    if (isError) {
      if (error instanceof McpForbiddenError) return "permission_denied";
      return "error_network";
    }
    if (!servers || servers.length === 0) return "empty";
    return "populated";
  }

  const tableState = getTableState();

  /** Handle per-row sync action. §D-T003-PER-ROW-SYNCING, §D-T003-INVALIDATE-ON-SUCCESS */
  function handleSync(server: McpServer): void {
    setSyncErrors((prev) => ({ ...prev, [server.id]: null }));
    setSyncingRows((prev) => ({ ...prev, [server.id]: true }));

    syncServer(
      { id: server.id },
      {
        onSuccess: (result: McpSyncResult) => {
          // §D-T003-TOOL-COUNT-TRANSIENT: store transient count from sync response
          setToolCounts((prev) => ({ ...prev, [server.id]: result.tools_count }));
          setSyncingRows((prev) => ({ ...prev, [server.id]: false }));
        },
        onError: (err: unknown) => {
          let message: string;
          if (err instanceof McpServerUnreachableError) {
            message = tErrors("MCP_SERVER_UNREACHABLE");
          } else if (err instanceof McpServerNotFoundError) {
            message = t("servers.errors.sync_not_found");
          } else if (err instanceof McpRateLimitedError) {
            message = t("servers.errors.sync_rate_limited");
          } else {
            message = t("servers.errors.sync_internal");
          }
          setSyncErrors((prev) => ({ ...prev, [server.id]: message }));
          setSyncingRows((prev) => ({ ...prev, [server.id]: false }));
        },
      },
    );
  }

  /* AFTER render log — verbose only */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("McpServersPage.render.state", {
      tableState,
      serverCount: servers?.length ?? 0,
      isLoading,
      isError,
    });
  }

  return (
    <AdminShell navItems={ADMIN_NAV_ITEMS} navAriaLabel={t("servers.title")}>
      {/* aria-live region for sync status — §D-T003-PER-ROW-SYNCING a11y */}
      <div aria-live="polite" aria-atomic="false" className="sr-only" data-testid="mcp-aria-live" />

      {/* Page header */}
      <header style={PAGE_HEADER_STYLE}>
        <h1 style={PAGE_TITLE_STYLE}>{t("servers.title")}</h1>
        <p style={PAGE_SUBTITLE_STYLE}>{t("servers.subtitle")}</p>
      </header>

      {/* Loading state — §D-T003-LOADING-STYLE: aria-busy section */}
      {tableState === "loading" && (
        <div
          aria-busy="true"
          aria-label={t("servers.title")}
          data-testid="mcp-loading"
          style={LOADING_STYLE}
        >
          <TrackedLabel variant="muted">Cargando…</TrackedLabel>
        </div>
      )}

      {/* Permission denied — uses HairlineTable built-in state */}
      {tableState === "permission_denied" && (
        <HairlineTable
          columns={[]}
          rows={[]}
          state="permission_denied"
          caption={t("servers.title")}
        />
      )}

      {/* Error network — uses HairlineTable built-in state with retry */}
      {tableState === "error_network" && (
        <HairlineTable
          columns={[]}
          rows={[]}
          state="error_network"
          caption={t("servers.title")}
          errorMessage={tErrors("NETWORK")}
          onRetry={() => void refetch()}
        />
      )}

      {/* Empty state */}
      {tableState === "empty" && (
        <>
          <HairlineTable
            columns={[]}
            rows={[]}
            state="empty"
            caption={t("servers.title")}
            emptyMessage={t("servers.empty")}
          />
          {/* §D-T003-WIZARD-LINK-PRE-T004: honest stub until T004 ships */}
          <div style={{ marginTop: "1.5rem" }}>
            <SolidCTA
              onClick={() => navigate("/admin/ai/mcp/new")}
              aria-label={t("servers.actions.connectFirst")}
              width="auto"
              style={{ padding: "0.5rem 1.25rem" }}
              data-testid="mcp-connect-cta"
            >
              {t("servers.actions.connectFirst")}
            </SolidCTA>
          </div>
        </>
      )}

      {/* Populated table with server rows */}
      {tableState === "populated" && servers && (
        <>
          <table style={TABLE_STYLE} aria-label={t("servers.title")}>
            <caption className="sr-only">{t("servers.title")}</caption>
            <thead>
              <tr>
                <th scope="col" style={TH_FIRST_STYLE}>
                  <TrackedLabel variant="muted">{t("servers.columns.name")}</TrackedLabel>
                </th>
                <th scope="col" style={TH_STYLE}>
                  <TrackedLabel variant="muted">{t("servers.columns.status")}</TrackedLabel>
                </th>
                <th scope="col" style={TH_STYLE}>
                  <TrackedLabel variant="muted">{t("servers.columns.transport")}</TrackedLabel>
                </th>
                <th scope="col" style={TH_STYLE}>
                  <TrackedLabel variant="muted">{t("servers.columns.lastSync")}</TrackedLabel>
                </th>
                <th scope="col" style={TH_STYLE}>
                  <TrackedLabel variant="muted">{t("servers.columns.toolCount")}</TrackedLabel>
                </th>
                <th scope="col" style={TH_STYLE}>
                  <TrackedLabel variant="muted">{t("servers.columns.risk")}</TrackedLabel>
                </th>
                <th scope="col" style={TH_LAST_STYLE}>
                  <TrackedLabel variant="muted">{t("servers.columns.actions")}</TrackedLabel>
                </th>
              </tr>
            </thead>
            <tbody>
              {servers.map((server) => (
                <McpServerRow
                  key={server.id}
                  server={server}
                  isSyncing={syncingRows[server.id] === true}
                  syncError={syncErrors[server.id] ?? null}
                  transientToolCount={toolCounts[server.id] ?? null}
                  onSync={() => handleSync(server)}
                />
              ))}
            </tbody>
          </table>

          {/* §D-T003-RISK-LABELS-DERIVED-OR-OMITTED: footnote about risk curation */}
          <p style={FOOTNOTE_STYLE} data-testid="mcp-risk-footnote">
            {t("servers.notes.risk_per_tool")}
          </p>
        </>
      )}
    </AdminShell>
  );
}
