/**
 * Hilo People — AdminDashboardPage.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-PAGE (canonical Coverage Registry write target)
 *
 * Responsibility: Admin AI dashboard — "Vista resumen Admin AI" (TECHNICAL_GUIDE §6.1).
 *   Renders 5 required UX states: loading, empty, error_network,
 *   permission_denied, success (error_validation: N/A — read-only page).
 *   Orchestrates AdminShell nav + KPI tiles + HairlineTable by model.
 *
 * Decisions applied:
 *   D-T001-GUARD: reuses existing RequireRole in router (NO new RequireAdmin).
 *   D-T001-NAV-LINKS: renders all 11 admin nav links enabled.
 *   D-T001-NEXT-ACTION: SolidCTA "Manage models" → /admin/ai/models.
 *   D-T001-WINDOW-DEFAULT: 30-day window computed in useDashboardUsage.
 *   D-T001-GROUPBY-DEFAULT: group_by=model (dashboard default).
 *   D-T001-KPIS: 4 KPI tiles (invocations, tokens, cost, latency).
 *   D-T001-UX-STATES: 5 states, no error_validation (anti-enum for read-only).
 *   D-T001-401-VS-403: 401 handled by authFetch; 403 → ForbiddenView.
 *   D-T001-LOGS-PII-CLEAN: no email, no model keys, no prompt text in logs.
 *   D-T001-FILESIZE-SPLIT: error/empty/permission sub-views in sibling file.
 *
 * Route: /admin (RequireRole — people_admin|super_admin).
 * Journey refs: J103 (participates; does NOT close — P04-S01-T002..T004 remain).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 * Security: token never in DOM/logs. Uses authFetch via useDashboardUsage.
 */

import type { CSSProperties, ReactNode } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import AdminShell from "../../shared/design-system/AdminShell";
import type { AdminNavItem } from "../../shared/design-system/AdminShell";
import HairlineTable from "../../shared/design-system/HairlineTable";
import type { HairlineTableColumn } from "../../shared/design-system/HairlineTable";
import SolidCTA from "../../shared/design-system/SolidCTA";
import TrackedLabel from "../../shared/design-system/TrackedLabel";
import { useDashboardUsage } from "../../features/admin-ai/presentation/useDashboardUsage";
import { AdminAiForbiddenError } from "../../features/admin-ai/data/errors";
import type { UsageRow } from "../../features/admin-ai/domain/types";
import { logVerbose, logWarn } from "../../features/admin-ai/data/logger";
import {
  ROUTE_ADMIN,
  ROUTE_ADMIN_AI_MODELS,
  ROUTE_ADMIN_AI_MODELS_NEW,
  ROUTE_ADMIN_RAG_DOCUMENTS,
  ROUTE_ADMIN_RAG_COLLECTIONS,
  ROUTE_ADMIN_AI_MCP,
  ROUTE_ADMIN_AI_MCP_NEW,
  ROUTE_ADMIN_AI_AGENTS,
  ROUTE_ADMIN_AUDIT,
  ROUTE_ADMIN_USAGE,
} from "../../app/router";
import {
  LoadingView,
  EmptyView,
  NetworkErrorView,
  ForbiddenView,
} from "./_AdminDashboardPage.error-views";

// ---------------------------------------------------------------------------
// Styles (token-only — no hardcoded colors, px, or fonts outside tokens)
// ---------------------------------------------------------------------------

const KPI_GRID: CSSProperties = {
  display: "grid",
  gridTemplateColumns: "repeat(4, 1fr)",
  gap: "1rem",
  marginBottom: "2rem",
};

const KPI_TILE: CSSProperties = {
  border: "var(--hairline)",
  padding: "1rem",
  backgroundColor: "var(--color-paper)",
};

const KPI_VALUE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1.75rem",
  color: "var(--color-ink)",
  margin: "0.25rem 0 0",
  lineHeight: 1.1,
};

const PAGE_TITLE: CSSProperties = {
  fontFamily: "var(--font-display)",
  fontSize: "1.5rem",
  color: "var(--color-ink)",
  margin: "0 0 0.25rem",
};

const WINDOW_RANGE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.8125rem",
  color: "var(--color-ink)",
  opacity: 0.55,
  margin: "0 0 2rem",
};

const TABLE_SECTION: CSSProperties = {
  marginBottom: "2rem",
};

const CTA_WRAPPER: CSSProperties = {
  display: "inline-block",
  marginTop: "1.5rem",
};

// ---------------------------------------------------------------------------
// Helper: format date for the window range display (D-T001-WINDOW-DEFAULT)
// ---------------------------------------------------------------------------

/**
 * Formats an ISO-8601 datetime string to a locale-aware medium date string.
 * Uses Intl.DateTimeFormat with the active i18n language — never hardcodes locale.
 * Source: task pack §7 "use Intl.DateTimeFormat(language, {dateStyle:'medium'})".
 *
 * @param isoString - ISO-8601 datetime string (e.g. "2026-04-16T00:00:00.000Z").
 * @param language - Active i18n language code (e.g. "es", "en", "fr").
 * @returns Locale-formatted medium date string.
 */
function formatWindowDate(isoString: string, language: string): string {
  try {
    return new Intl.DateTimeFormat(language, { dateStyle: "medium" }).format(
      new Date(isoString),
    );
  } catch {
    return isoString.slice(0, 10); // fallback: YYYY-MM-DD
  }
}

// ---------------------------------------------------------------------------
// Helper: format numbers for KPI display
// ---------------------------------------------------------------------------

function formatNumber(value: number): string {
  return new Intl.NumberFormat().format(Math.round(value));
}

function formatCost(value: number): string {
  return `$${value.toFixed(4)}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AdminDashboardPage — Usage summary dashboard for admin role.
 *
 * Renders AdminShell with 11 nav items, 4 KPI tiles, and usage-by-model table.
 * Handles 5 UX states: loading, empty, error_network, permission_denied, success.
 *
 * @returns The admin dashboard page.
 */
export default function AdminDashboardPage(): ReactNode {
  const { t, i18n } = useTranslation(["admin-ai"]);
  const navigate = useNavigate();
  const { isLoading, isSuccess, isError, error, data, refetch, from, to } = useDashboardUsage();

  logVerbose("admin-ai.page.AdminDashboardPage.render.start", {
    is_loading: isLoading,
    is_success: isSuccess,
    is_error: isError,
  });

  // ---------------------------------------------------------------------------
  // Nav items — D-T001-NAV-LINKS: all 11 routes enabled
  // ---------------------------------------------------------------------------

  const navItems: AdminNavItem[] = [
    { key: "dashboard", label: t("admin-ai:nav.dashboard"), active: true, onClick: () => navigate(ROUTE_ADMIN) },
    { key: "models", label: t("admin-ai:nav.models"), onClick: () => navigate(ROUTE_ADMIN_AI_MODELS) },
    { key: "modelsNew", label: t("admin-ai:nav.modelsNew"), onClick: () => navigate(ROUTE_ADMIN_AI_MODELS_NEW) },
    { key: "ragDocuments", label: t("admin-ai:nav.ragDocuments"), onClick: () => navigate(ROUTE_ADMIN_RAG_DOCUMENTS) },
    { key: "ragCollections", label: t("admin-ai:nav.ragCollections"), onClick: () => navigate(ROUTE_ADMIN_RAG_COLLECTIONS) },
    { key: "mcpServers", label: t("admin-ai:nav.mcpServers"), onClick: () => navigate(ROUTE_ADMIN_AI_MCP) },
    { key: "mcpNew", label: t("admin-ai:nav.mcpNew"), onClick: () => navigate(ROUTE_ADMIN_AI_MCP_NEW) },
    { key: "agents", label: t("admin-ai:nav.agents"), onClick: () => navigate(ROUTE_ADMIN_AI_AGENTS) },
    { key: "audit", label: t("admin-ai:nav.audit"), onClick: () => navigate(ROUTE_ADMIN_AUDIT) },
    { key: "usage", label: t("admin-ai:nav.usage"), onClick: () => navigate(ROUTE_ADMIN_USAGE) },
  ];

  // ---------------------------------------------------------------------------
  // Table columns — D-T001-GROUPBY-DEFAULT: group_by=model
  // ---------------------------------------------------------------------------

  const tableColumns: HairlineTableColumn<UsageRow>[] = [
    {
      header: t("admin-ai:dashboard.table.headers.model"),
      accessor: (row) => row.model_name ?? "—",
    },
    {
      header: t("admin-ai:dashboard.table.headers.invocations"),
      accessor: (row) => formatNumber(row.invocations),
    },
    {
      header: t("admin-ai:dashboard.table.headers.tokensIn"),
      accessor: (row) => formatNumber(row.tokens_in),
    },
    {
      header: t("admin-ai:dashboard.table.headers.tokensOut"),
      accessor: (row) => formatNumber(row.tokens_out),
    },
    {
      header: t("admin-ai:dashboard.table.headers.cost"),
      accessor: (row) => formatCost(row.estimated_cost),
    },
    {
      header: t("admin-ai:dashboard.table.headers.latency"),
      accessor: (row) => formatNumber(row.latency_ms_avg),
    },
  ];

  // ---------------------------------------------------------------------------
  // Determine UX state
  // ---------------------------------------------------------------------------

  const isForbidden = isError && error instanceof AdminAiForbiddenError;

  const isEmpty = isSuccess
    && data !== undefined
    && data.rows.length === 0
    && data.totals.invocations === 0;

  const isPopulated = isSuccess && data !== undefined && !isEmpty;

  if (isForbidden) {
    logWarn("admin-ai.page.AdminDashboardPage.permission_denied");
  }

  // ---------------------------------------------------------------------------
  // Main content depending on state
  // ---------------------------------------------------------------------------

  function renderContent(): ReactNode {
    if (isLoading) {
      return <LoadingView />;
    }

    if (isForbidden) {
      return <ForbiddenView />;
    }

    if (isError) {
      return <NetworkErrorView onRetry={refetch} />;
    }

    if (isEmpty) {
      return <EmptyView />;
    }

    if (isPopulated && data !== undefined) {
      const { totals, rows } = data;
      const fromFormatted = formatWindowDate(from, i18n.language);
      const toFormatted = formatWindowDate(to, i18n.language);

      logVerbose("admin-ai.page.AdminDashboardPage.success.render", {
        row_count: rows.length,
        total_invocations: totals.invocations,
      });

      return (
        <>
          <h1 style={PAGE_TITLE} data-testid="dashboard-title">
            {t("admin-ai:dashboard.title")}
          </h1>
          <p style={WINDOW_RANGE} data-testid="dashboard-window-range">
            {t("admin-ai:dashboard.window.range", {
              from: fromFormatted,
              to: toFormatted,
            })}
          </p>

          {/* KPI tiles — D-T001-KPIS */}
          <div style={KPI_GRID} role="list" aria-label="KPI summary" data-testid="kpi-grid">
            <div style={KPI_TILE} role="listitem" data-testid="kpi-invocations">
              <TrackedLabel variant="muted">
                {t("admin-ai:dashboard.kpi.invocations")}
              </TrackedLabel>
              <p style={KPI_VALUE}>{formatNumber(totals.invocations)}</p>
            </div>
            <div style={KPI_TILE} role="listitem" data-testid="kpi-tokens">
              <TrackedLabel variant="muted">
                {t("admin-ai:dashboard.kpi.tokens")}
              </TrackedLabel>
              <p style={KPI_VALUE}>
                {formatNumber(totals.tokens_in + totals.tokens_out)}
              </p>
            </div>
            <div style={KPI_TILE} role="listitem" data-testid="kpi-cost">
              <TrackedLabel variant="muted">
                {t("admin-ai:dashboard.kpi.cost")}
              </TrackedLabel>
              <p style={KPI_VALUE}>{formatCost(totals.estimated_cost)}</p>
            </div>
            <div style={KPI_TILE} role="listitem" data-testid="kpi-latency">
              <TrackedLabel variant="muted">
                {t("admin-ai:dashboard.kpi.latency")}
              </TrackedLabel>
              <p style={KPI_VALUE}>{formatNumber(totals.latency_ms_avg)}</p>
            </div>
          </div>

          {/* Usage by model table */}
          <div style={TABLE_SECTION} data-testid="usage-table-section">
            <HairlineTable<UsageRow>
              columns={tableColumns}
              rows={rows}
              caption={t("admin-ai:dashboard.table.caption")}
              state="populated"
            />
          </div>

          {/* Next action CTA — D-T001-NEXT-ACTION */}
          <div style={CTA_WRAPPER}>
            <SolidCTA
              onClick={() => navigate(ROUTE_ADMIN_AI_MODELS)}
              aria-label={t("admin-ai:dashboard.actions.manageModels")}
              data-testid="manage-models-cta"
              width="auto"
              style={{ padding: "0.75rem 1.5rem" }}
            >
              {t("admin-ai:dashboard.actions.manageModels")}
            </SolidCTA>
          </div>
        </>
      );
    }

    // Fallback (shouldn't normally reach here — but be safe)
    return <LoadingView />;
  }

  return (
    <AdminShell
      navItems={navItems}
      navAriaLabel={t("admin-ai:dashboard.title")}
      data-testid="admin-shell"
    >
      {renderContent()}
    </AdminShell>
  );
}
