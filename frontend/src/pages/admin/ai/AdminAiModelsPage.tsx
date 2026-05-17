/**
 * Hilo People — AdminAiModelsPage.
 *
 * Slice/Phase: P04-S01-T002 — AdminAiModelsPage / Phase 4.
 * Write-set anchor: §D-T002-PAGE (canonical Coverage Registry write target)
 *
 * Responsibility: Admin AI models list — "Tabla modelos LiteLLM" (TECHNICAL_GUIDE §6.1).
 *   Renders 5 required UX states: loading, empty, error_network,
 *   permission_denied, success (error_validation: N/A — read-only page).
 *   Orchestrates AdminShell nav + HairlineTable with status dot, cost, latency.
 *
 * Decisions applied:
 *   D-T002-GUARD: reuses RequireRole in router (NO new RequireAdmin).
 *   D-T002-FETCH-BOTH: hook fetches providers + models via Promise.all, joins client-side.
 *   D-T002-STATUS-DOT: derivation table in task pack §6.4.
 *   D-T002-COST-FORMAT: EUR per 1k tokens with Intl.NumberFormat, em-dash on empty.
 *   D-T002-LATENCY-FORMAT: ms with locale-aware grouping; em-dash on null.
 *   D-T002-EMPTY-STATE: empty when providers=[] OR models=[].
 *   D-T002-PERMISSION-DENIED: defensive 403 (RequireRole gates upstream).
 *   D-T002-ERROR-NETWORK: covers AdminAiNetworkError + AdminAiInternalError.
 *   D-T002-NEXT-ACTION: SolidCTA "New model" → /admin/ai/models/new (T003 future).
 *   D-T002-UX-STATES: 5 states, error_validation: N/A (read-only).
 *   D-T002-LOGS-PII-CLEAN: counts + class names only — no names/IDs/credentials.
 *   D-T002-ACCESSIBILITY: sr-only caption, th scope, aria-label on dots, aria-busy.
 *   D-T002-NO-MOBILE-FRAME: admin pages are desktop-only (AdminShell direct).
 *
 * Route: /admin/ai/models (RequireRole — people_admin|super_admin).
 * Journey refs: J103 (participates; does NOT close — T003/T004 and e2e remain).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 * Security: token never in DOM/logs. Uses authFetch via useAdminAiModels.
 */

import type { ReactNode } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import AdminShell from "../../../shared/design-system/AdminShell";
import type { AdminNavItem } from "../../../shared/design-system/AdminShell";
import HairlineTable from "../../../shared/design-system/HairlineTable";
import type { HairlineTableColumn } from "../../../shared/design-system/HairlineTable";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import StatusDot from "../../../shared/design-system/StatusDot";
import type { StatusDotState } from "../../../shared/design-system/StatusDot";
import { useAdminAiModels } from "../../../features/admin-ai/presentation/useAdminAiModels";
import type { AdminAiModelRow } from "../../../features/admin-ai/presentation/useAdminAiModels";
import { AdminAiForbiddenError, AdminAiNetworkError, AdminAiInternalError } from "../../../features/admin-ai/data/errors";
import { logVerbose, logWarn } from "../../../features/admin-ai/data/logger";
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
} from "../../../app/router";
import {
  LoadingView,
  EmptyView,
  NetworkErrorView,
  ForbiddenView,
} from "./_AdminAiModelsPage.error-views";
import {
  PAGE_TITLE,
  PAGE_SUBTITLE,
  TABLE_SECTION,
  CTA_WRAPPER,
  STATUS_DOT_CELL,
} from "./AdminAiModelsPage.styles";

// ---------------------------------------------------------------------------
// Formatters — D-T002-COST-FORMAT, D-T002-LATENCY-FORMAT
// ---------------------------------------------------------------------------

/**
 * Formats pricing from the opaque JSONB dict.
 * Rule (D-T002-COST-FORMAT):
 *   1. input_per_1k_tokens + output_per_1k_tokens → "${in} / ${out} €/1k"
 *   2. input + output → same format
 *   3. else → em-dash
 *
 * @param pricing - Opaque pricing dict (ASSUMPTION-1: may be {}).
 * @param locale - i18n language code for Intl.NumberFormat.
 * @returns Formatted cost string or em-dash.
 */
export function formatCost(pricing: Record<string, unknown>, locale: string): string {
  const fmt = new Intl.NumberFormat(locale, {
    style: "currency",
    currency: "EUR",
    maximumFractionDigits: 4,
  });

  const inKey1 = pricing["input_per_1k_tokens"];
  const outKey1 = pricing["output_per_1k_tokens"];
  if (typeof inKey1 === "number" && typeof outKey1 === "number") {
    return `${fmt.format(inKey1)} / ${fmt.format(outKey1)} /1k`;
  }

  const inKey2 = pricing["input"];
  const outKey2 = pricing["output"];
  if (typeof inKey2 === "number" && typeof outKey2 === "number") {
    return `${fmt.format(inKey2)} / ${fmt.format(outKey2)} /1k`;
  }

  return "—";
}

/**
 * Formats latency from integer ms.
 * Rule (D-T002-LATENCY-FORMAT):
 *   - null → "—"
 *   - number → locale-formatted integer + " ms" (e.g. "1 234 ms" in FR)
 *
 * @param ms - Latency in milliseconds or null.
 * @param locale - i18n language code for Intl.NumberFormat.
 * @returns Formatted latency string.
 */
export function formatLatency(ms: number | null, locale: string): string {
  if (ms === null) return "—";
  return `${new Intl.NumberFormat(locale).format(ms)} ms`;
}

// ---------------------------------------------------------------------------
// D-T002-STATUS-DOT derivation
// ---------------------------------------------------------------------------

/**
 * Derives StatusDotState from provider status + model enabled flag.
 * Source: task pack §6.4 D-T002-STATUS-DOT derivation table.
 *
 * | provider.status | model.enabled | result     |
 * |-----------------|---------------|------------|
 * | active          | true          | active     |
 * | active          | false         | inactive   |
 * | draft/inactive  | true          | inactive   |
 * | draft/inactive  | false         | inactive   |
 * | unknown         | -             | error      |
 */
export function deriveStatusDotState(
  providerStatus: AdminAiModelRow["providerStatus"],
  enabled: boolean,
): StatusDotState {
  if (providerStatus === "unknown") return "error";
  if (providerStatus === "active" && enabled) return "active";
  return "inactive";
}

/**
 * Returns the i18n key for the status label (D-T002-STATUS-DOT).
 */
export function deriveStatusLabelKey(
  providerStatus: AdminAiModelRow["providerStatus"],
  enabled: boolean,
): string {
  if (providerStatus === "unknown") return "admin-ai:models.status.unknown";
  if (providerStatus === "active" && enabled) return "admin-ai:models.status.active";
  if (providerStatus === "active" && !enabled) return "admin-ai:models.status.modelDisabled";
  if (enabled) return "admin-ai:models.status.providerInactive";
  return "admin-ai:models.status.bothInactive";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * AdminAiModelsPage — LiteLLM model list for admin role.
 *
 * Renders AdminShell with 10 nav items and a HairlineTable of AI models.
 * Handles 5 UX states: loading, empty, error_network, permission_denied, success.
 *
 * @returns The admin AI models page.
 */
export default function AdminAiModelsPage(): ReactNode {
  const { t, i18n } = useTranslation(["admin-ai"]);
  const navigate = useNavigate();
  const { isLoading, isSuccess, isError, error, data, refetch } = useAdminAiModels();

  logVerbose("admin-ai.page.AdminAiModelsPage.render.start", {
    is_loading: isLoading,
    is_success: isSuccess,
    is_error: isError,
  });

  // ---------------------------------------------------------------------------
  // Nav items — matching AdminDashboardPage but highlighting /admin/ai/models
  // ---------------------------------------------------------------------------

  const navItems: AdminNavItem[] = [
    { key: "dashboard", label: t("admin-ai:nav.dashboard"), onClick: () => navigate(ROUTE_ADMIN) },
    { key: "models", label: t("admin-ai:nav.models"), active: true, onClick: () => navigate(ROUTE_ADMIN_AI_MODELS) },
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
  // Table columns
  // ---------------------------------------------------------------------------

  const tableColumns: HairlineTableColumn<AdminAiModelRow>[] = [
    {
      header: t("admin-ai:models.table.headers.model"),
      accessor: (row) => row.model_id,
    },
    {
      header: t("admin-ai:models.table.headers.type"),
      accessor: (row) => <TrackedLabel variant="muted">{row.model_type}</TrackedLabel>,
    },
    {
      header: t("admin-ai:models.table.headers.provider"),
      accessor: (row) => row.providerName,
    },
    {
      header: t("admin-ai:models.table.headers.status"),
      accessor: (row) => {
        const dotState = deriveStatusDotState(row.providerStatus, row.enabled);
        const labelKey = deriveStatusLabelKey(row.providerStatus, row.enabled);
        const label = t(labelKey);
        return (
          <span style={STATUS_DOT_CELL}>
            <StatusDot
              state={dotState}
              label={label}
              aria-label={`${t("admin-ai:models.table.headers.status")}: ${label}`}
            />
          </span>
        );
      },
    },
    {
      header: t("admin-ai:models.table.headers.default"),
      accessor: (row) => (row.is_default ? t("admin-ai:models.default.yes") : t("admin-ai:models.default.no")),
    },
    {
      header: t("admin-ai:models.table.headers.cost"),
      accessor: (row) => formatCost(row.pricing, i18n.language),
    },
    {
      header: t("admin-ai:models.table.headers.latency"),
      accessor: (row) => formatLatency(row.latency_ms_avg, i18n.language),
    },
  ];

  // ---------------------------------------------------------------------------
  // Determine UX state
  // ---------------------------------------------------------------------------

  const isForbidden = isError && error instanceof AdminAiForbiddenError;
  const isNetworkError = isError && (error instanceof AdminAiNetworkError || error instanceof AdminAiInternalError);

  // Empty: success but no providers OR no models (D-T002-EMPTY-STATE)
  const isEmpty = isSuccess
    && data !== undefined
    && (data.providers.length === 0 || data.models.length === 0);

  const isPopulated = isSuccess && data !== undefined && !isEmpty;

  if (isForbidden) {
    logWarn("admin-ai.page.AdminAiModelsPage.permission_denied");
  }

  // ---------------------------------------------------------------------------
  // Verbose log route (§D-T002-ROUTER)
  // ---------------------------------------------------------------------------

  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("AppRouter.render.start", {
      phase: "P04",
      slice: "P04-S01-T002",
      routes: [ROUTE_ADMIN_AI_MODELS],
    });
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

    if (isError || isNetworkError) {
      return <NetworkErrorView onRetry={refetch} />;
    }

    if (isEmpty) {
      return <EmptyView />;
    }

    if (isPopulated && data !== undefined) {
      logVerbose("admin-ai.page.AdminAiModelsPage.success.render", {
        provider_count: data.providers.length,
        model_count: data.models.length,
      });

      return (
        <div style={TABLE_SECTION} data-testid="models-table-section">
          <HairlineTable<AdminAiModelRow>
            columns={tableColumns}
            rows={data.rows}
            state="populated"
            caption={t("admin-ai:models.table.caption")}
            data-testid="models-table"
          />
          <div style={CTA_WRAPPER}>
            <SolidCTA
              onClick={() => navigate(ROUTE_ADMIN_AI_MODELS_NEW)}
              aria-label={t("admin-ai:models.actions.newModel")}
              data-testid="models-new-model-cta"
              width="auto"
              style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
            >
              {t("admin-ai:models.actions.newModel")}
            </SolidCTA>
          </div>
        </div>
      );
    }

    // Fallback (should never be reached)
    return null;
  }

  return (
    <AdminShell navItems={navItems} data-testid="admin-ai-models-shell">
      <h1 style={PAGE_TITLE} data-testid="models-page-title">
        {t("admin-ai:models.title")}
      </h1>
      <p style={PAGE_SUBTITLE} data-testid="models-page-subtitle">
        {t("admin-ai:nav.models")}
      </p>
      {renderContent()}
    </AdminShell>
  );
}
