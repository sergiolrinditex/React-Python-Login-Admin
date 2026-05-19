/**
 * Hilo People — UsagePage.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Admin usage metrics page — cost, tokens, latency by model/day.
 *   Deep-link route /admin/usage (RequireRole people_admin|super_admin).
 *   No left-nav v1 — AdminDashboardPage (P04-S01-T001) not yet built.
 *
 * Decisions applied (D-T002-*):
 *   D-T002-DEFAULT-RANGE: últimos 30 días, group_by=model_day (hardcoded v1).
 *   D-T002-NO-FORMS-V1: no date pickers; range is fixed.
 *   D-T002-RANGE-INVARIANT: useUsage.isRangeInvalid triggers ValidationErrorView.
 *   D-T002-DESKTOP-SHELL: no MobileFrame, no left-nav v1.
 *   D-T002-TABLE-A11Y: <table>+<caption>(sr-only)+<th scope="col">+<th scope="row">.
 *   D-T002-NUMBER-FORMAT: Intl.NumberFormat(i18n.language) for cost/tokens.
 *   D-T002-NEXT-ACTION: link to /admin/ai/models below the table.
 *   D-T002-EMPTY-STATE: Wordmark Hilo + body + CTA on empty rows.
 *   D-T002-RBAC-GUARD: RequireRole in router.tsx (not duplicated here).
 *   D-T002-GROUP-BY-PICKER: only model_day v1 — KISS.
 *
 * UX states implemented (AC1–AC9):
 *   loading     → LoadingView (aria-busy skeleton)
 *   empty       → EmptyView (Wordmark + body + CTA)
 *   error_network → NetworkErrorView (Retry CTA)
 *   permission_denied → ForbiddenView (back link)
 *   error_validation → ValidationErrorView (inline)
 *   success     → <table> with rows + totals
 *
 * Route: /admin/usage (RequireRole ["people_admin","super_admin"]).
 * Journey refs: J103 (participates; does NOT close J103 — P05-S01-T004 is terminal).
 *
 * D-T002-PAGE: Canonical write_set anchor for this file.
 * Source ref: §D-T002-PAGE, TECHNICAL_GUIDE §6.1, UX_CONTRACT line 38.
 */

import { type ReactNode, useMemo, useCallback } from "react";
import { useNavigate, Link } from "react-router";
import { useTranslation } from "react-i18next";
import { useUsage } from "../../../features/admin/presentation/useUsage";
import {
  UsageForbiddenError,
  UsageNetworkError,
  UsageServerError,
} from "../../../features/admin/data/errors";
import { logVerbose, logError } from "../../../features/admin/data/logger";
import { LoadingView, EmptyView, ForbiddenView, NetworkErrorView, ValidationErrorView }
  from "./_UsagePage.error-views";
import {
  PAGE_STYLE,
  CONTENT_STYLE,
  HEADER_STYLE,
  TITLE_STYLE,
  SUBTITLE_STYLE,
  TABLE_WRAPPER_STYLE,
  TABLE_STYLE,
  THEAD_TR_STYLE,
  TH_STYLE,
  TH_RIGHT_STYLE,
  TD_STYLE,
  TD_RIGHT_STYLE,
  TOTALS_TR_STYLE,
  TOTALS_TD_STYLE,
  TOTALS_TD_RIGHT_STYLE,
  NEXT_ACTION_STYLE,
  LINK_CTA_STYLE,
  SR_ONLY_STYLE,
} from "./UsagePage.styles";
import type { UsageSummary } from "../../../features/admin/domain/types";

// ---------------------------------------------------------------------------
// Date helpers (D-T002-DEFAULT-RANGE)
// ---------------------------------------------------------------------------

/**
 * Computes the default query range: last 30 days (from=now-30d, to=now).
 * Called once at component mount — not reactive.
 */
function computeDefaultRange(): { from: Date; to: Date } {
  const to = new Date();
  const from = new Date(to.getTime() - 30 * 24 * 60 * 60 * 1_000);
  return { from, to };
}

// ---------------------------------------------------------------------------
// Number formatters (D-T002-NUMBER-FORMAT)
// ---------------------------------------------------------------------------

/**
 * Formats cost as USD currency using i18n.language locale.
 * @param value - Cost in USD float.
 * @param lng - i18n language code (es/en/fr).
 * @returns Formatted currency string.
 */
function formatCost(value: number, lng: string): string {
  return new Intl.NumberFormat(lng, {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 4,
    maximumFractionDigits: 6,
  }).format(value);
}

/**
 * Formats token/invocation counts using i18n.language locale.
 * @param value - Integer count.
 * @param lng - i18n language code.
 * @returns Formatted number string.
 */
function formatNumber(value: number, lng: string): string {
  return new Intl.NumberFormat(lng).format(value);
}

/**
 * Formats latency in milliseconds (direct string, no currency).
 * @param ms - Latency in milliseconds, or null.
 * @returns Formatted string "n ms" or "—" for null.
 */
function formatLatency(ms: number | null): string {
  if (ms === null) return "—";
  return `${ms} ms`;
}

// ---------------------------------------------------------------------------
// UsageTable sub-component (success state)
// ---------------------------------------------------------------------------

interface UsageTableProps {
  summary: UsageSummary;
  lng: string;
}

/**
 * Renders the usage data table with rows and totals.
 * D-T002-TABLE-A11Y: <table>+<caption>(sr-only)+<th scope="col">+<th scope="row">.
 */
function UsageTable({ summary, lng }: UsageTableProps): ReactNode {
  const { t } = useTranslation("usage");
  const showModel = summary.group_by === "model" || summary.group_by === "model_day";
  const showDay = summary.group_by === "day" || summary.group_by === "model_day";

  return (
    <div style={TABLE_WRAPPER_STYLE}>
      <table style={TABLE_STYLE} data-testid="usage-table">
        {/* sr-only caption for screen readers (D-T002-TABLE-A11Y) */}
        <caption style={SR_ONLY_STYLE}>{t("table.caption")}</caption>

        <thead>
          <tr style={THEAD_TR_STYLE}>
            {showModel && (
              <th scope="col" style={TH_STYLE}>{t("table.col.model")}</th>
            )}
            {showDay && (
              <th scope="col" style={TH_STYLE}>{t("table.col.day")}</th>
            )}
            <th scope="col" style={TH_RIGHT_STYLE}>{t("table.col.tokens")}</th>
            <th scope="col" style={TH_RIGHT_STYLE}>{t("table.col.cost")}</th>
            <th scope="col" style={TH_RIGHT_STYLE}>{t("table.col.latency")}</th>
            <th scope="col" style={TH_RIGHT_STYLE}>{t("table.col.invocations")}</th>
          </tr>
        </thead>

        <tbody>
          {summary.rows.map((row, i) => (
            <tr key={i}>
              {showModel && (
                <th scope="row" style={TD_STYLE}>
                  {row.model_name ?? row.model_id ?? "—"}
                </th>
              )}
              {showDay && (
                <td style={TD_STYLE}>{row.day ?? "—"}</td>
              )}
              <td style={TD_RIGHT_STYLE}>
                {formatNumber(row.tokens_in + row.tokens_out, lng)}
              </td>
              <td style={TD_RIGHT_STYLE}>{formatCost(row.estimated_cost, lng)}</td>
              <td style={TD_RIGHT_STYLE}>{formatLatency(row.latency_ms_avg)}</td>
              <td style={TD_RIGHT_STYLE}>{formatNumber(row.invocations, lng)}</td>
            </tr>
          ))}
        </tbody>

        {/* Totals row */}
        <tfoot>
          <tr style={TOTALS_TR_STYLE}>
            {showModel && (
              <th scope="row" style={TOTALS_TD_STYLE}>Total</th>
            )}
            {showDay && !showModel && (
              <th scope="row" style={TOTALS_TD_STYLE}>Total</th>
            )}
            <td style={TOTALS_TD_RIGHT_STYLE}>
              {formatNumber(
                summary.totals.tokens_in + summary.totals.tokens_out,
                lng,
              )}
            </td>
            <td style={TOTALS_TD_RIGHT_STYLE}>
              {formatCost(summary.totals.estimated_cost, lng)}
            </td>
            <td style={TOTALS_TD_RIGHT_STYLE}>
              {formatLatency(summary.totals.latency_ms_avg)}
            </td>
            <td style={TOTALS_TD_RIGHT_STYLE}>
              {formatNumber(summary.totals.invocations, lng)}
            </td>
          </tr>
        </tfoot>
      </table>
    </div>
  );
}

// ---------------------------------------------------------------------------
// UsagePage
// ---------------------------------------------------------------------------

/**
 * Admin usage metrics page — desktop shell, deep-link /admin/usage.
 * Renders 5 UX states: loading, empty, error_network, permission_denied, success.
 * Additionally renders error_validation when client-side range invariant fails.
 *
 * @returns The admin usage page element.
 */
export default function UsagePage(): ReactNode {
  const { t, i18n } = useTranslation(["usage", "common"]);
  const navigate = useNavigate();

  // D-T002-DEFAULT-RANGE: fixed 30-day window, memoized at mount
  const { from, to } = useMemo(() => computeDefaultRange(), []);

  logVerbose("usage.page.render.start", {
    from: from.toISOString(),
    to: to.toISOString(),
    group_by: "model_day",
  });

  const { data, error, isPending, isFetching, refetch, isRangeInvalid } = useUsage({
    from,
    to,
    groupBy: "model_day",
  });

  // Classify error type for UX state routing
  const isForbidden = error instanceof UsageForbiddenError;
  const isNetworkError =
    error !== null &&
    !isForbidden &&
    (error instanceof UsageNetworkError || error instanceof UsageServerError);

  const handleRetry = useCallback((): void => {
    logVerbose("usage.page.retry.triggered");
    refetch();
  }, [refetch]);

  const handleBack = useCallback((): void => {
    logVerbose("usage.page.back.triggered");
    void navigate(-1);
  }, [navigate]);

  // Log error state transitions
  if (error !== null) {
    logError("usage.page.error.state", { error_code: error.code });
  }

  // Determine content to render
  const showLoading = isPending && !isRangeInvalid;
  const showEmpty = !isPending && !error && data !== undefined && data.rows.length === 0;
  const showSuccess = !isPending && !error && data !== undefined && data.rows.length > 0;

  return (
    <main style={PAGE_STYLE} data-testid="usage-page">
      <div style={CONTENT_STYLE}>
        {/* Page header */}
        <header style={HEADER_STYLE}>
          <h1 style={TITLE_STYLE}>{t("usage:title")}</h1>
          <p style={SUBTITLE_STYLE}>{t("usage:subtitle")}</p>
        </header>

        {/* error_validation — range invariant (no fetch) */}
        {isRangeInvalid && <ValidationErrorView />}

        {/* loading state */}
        {showLoading && <LoadingView />}

        {/* permission_denied state */}
        {isForbidden && <ForbiddenView onBack={handleBack} />}

        {/* error_network state (5xx, fetch failure) */}
        {isNetworkError && (
          <NetworkErrorView onRetry={handleRetry} loading={isFetching} />
        )}

        {/* empty state */}
        {showEmpty && <EmptyView />}

        {/* success state */}
        {showSuccess && data !== undefined && (
          <>
            <UsageTable summary={data} lng={i18n.language} />
            <nav style={NEXT_ACTION_STYLE} aria-label={t("usage:nextAction")}>
              <Link
                to="/admin/ai/models"
                style={LINK_CTA_STYLE}
                data-testid="usage-next-action"
              >
                {t("usage:nextAction")} →
              </Link>
            </nav>
          </>
        )}
      </div>
    </main>
  );
}
