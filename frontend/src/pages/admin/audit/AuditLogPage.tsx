/**
 * Hilo People — AuditLogPage.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Admin audit log page — audit events with filters.
 *   Deep-link route /admin/audit (RequireRole people_auditor|super_admin).
 *   Composes AuditFilters (_AuditFilters.tsx) + AuditTable (_AuditTable.tsx)
 *   + error views (_AuditLogPage.error-views.tsx).
 *
 * Decisions applied (D-T001-*):
 *   RBAC-SCOPE, FILTER-UX, PAGINATION, METADATA-RENDER, ACTOR-RENDER,
 *   ACTION-FILTER, NEXT-ACTION (disabled), RANGE-INVARIANT, NO-COLOR, A11Y.
 *
 * UX states (AC1–AC3): loading, empty, error_network, permission_denied,
 *   error_validation, success.
 *
 * Route: /admin/audit (RequireRole ["people_auditor","super_admin"]).
 * Journey refs: J103, J104, J105 (participates; closes none — P05-S01-T004/T005/T006 are terminal).
 *
 * §D-T001-PAGE: Canonical write_set anchor for this file.
 * Source ref: §D-T001-PAGE, TECHNICAL_GUIDE §6.1, UX_CONTRACT line 37.
 */

import { type ReactNode, useState, useCallback, useRef, useEffect } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import {
  useAuditQuery,
  AUDIT_DEFAULT_WINDOW_DAYS,
  AuditForbiddenError,
  AuditNetworkError,
  AuditServerError,
} from "../../../features/audit/index";
import { logVerbose, logError } from "../../../features/audit/data/logger";
import type { AuditLog, AuditPage } from "../../../features/audit/domain/types";
import {
  LoadingView,
  EmptyView,
  ForbiddenView,
  NetworkErrorView,
  ValidationErrorView,
} from "./_AuditLogPage.error-views";
import { AuditTable } from "./_AuditTable";
import { AuditFilters } from "./_AuditFilters";
import {
  PAGE_STYLE,
  CONTENT_STYLE,
  HEADER_STYLE,
  TITLE_STYLE,
  SUBTITLE_STYLE,
  NEXT_ACTION_STYLE,
  LOAD_MORE_STYLE,
  DISABLED_CTA_STYLE,
} from "./AuditLogPage.styles";

// ---------------------------------------------------------------------------
// Date helpers (D-T001-FILTER-UX)
// ---------------------------------------------------------------------------

/** Returns a Date object n days before `from`. */
function daysAgo(n: number, from: Date = new Date()): Date {
  return new Date(from.getTime() - n * 24 * 60 * 60 * 1_000);
}

/** Formats a Date as "YYYY-MM-DD" for <input type="date"> value. */
function toDateInputValue(d: Date): string {
  return d.toISOString().slice(0, 10);
}

/** Parses "YYYY-MM-DD" from <input type="date"> to Date at start-of-day UTC. */
function fromDateInputValue(s: string): Date | null {
  if (!s) return null;
  const d = new Date(`${s}T00:00:00.000Z`);
  return isNaN(d.getTime()) ? null : d;
}

/**
 * AuditLogPage — desktop shell, deep-link /admin/audit.
 * Renders 5 UX states + error_validation. @returns the page element.
 */
export default function AuditLogPage(): ReactNode {
  const { t } = useTranslation(["audit", "common"]);
  const navigate = useNavigate();

  // D-T001-FILTER-UX: default last AUDIT_DEFAULT_WINDOW_DAYS days
  const now = new Date();
  const defaultTo = toDateInputValue(now);
  const defaultFrom = toDateInputValue(daysAgo(AUDIT_DEFAULT_WINDOW_DAYS, now));

  const [fromValue, setFromValue] = useState<string>(defaultFrom);
  const [toValue, setToValue] = useState<string>(defaultTo);
  const [actorValue, setActorValue] = useState<string>("");
  const [actionValue, setActionValue] = useState<string>("");

  // Applied filter state (submitted values trigger query)
  const [appliedFrom, setAppliedFrom] = useState<Date>(
    fromDateInputValue(defaultFrom) ?? daysAgo(AUDIT_DEFAULT_WINDOW_DAYS, now),
  );
  const [appliedTo, setAppliedTo] = useState<Date>(now);
  const [appliedActor, setAppliedActor] = useState<string>("");
  const [appliedAction, setAppliedAction] = useState<string>("");
  const [appliedCursor, setAppliedCursor] = useState<string | undefined>(undefined);

  // Accumulated rows for load-more pagination (D-T001-PAGINATION)
  const [allRows, setAllRows] = useState<AuditLog[]>([]);
  const prevDataRef = useRef<AuditPage | undefined>(undefined);

  logVerbose("audit.page.render.start", {
    has_from: true,
    has_to: true,
    action_present: appliedAction !== "",
    actor_present: appliedActor !== "",
  });

  const { data, error, isPending, isFetching, refetch, isRangeInvalid, isActorInvalid } =
    useAuditQuery({
      from: appliedFrom,
      to: appliedTo,
      actor: appliedActor || undefined,
      action: appliedAction || undefined,
      cursor: appliedCursor,
    });

  // Accumulate rows on successful new page load
  useEffect(() => {
    if (data && data !== prevDataRef.current) {
      prevDataRef.current = data;
      if (appliedCursor) {
        // Load more: append to existing rows
        setAllRows((prev) => [...prev, ...data.rows]);
      } else {
        // Fresh query (filters changed): replace rows
        setAllRows(data.rows);
      }
    }
  }, [data, appliedCursor]);

  // Classify error type for UX state routing
  const isForbidden = error instanceof AuditForbiddenError;
  const isNetworkError =
    error !== null &&
    !isForbidden &&
    (error instanceof AuditNetworkError || error instanceof AuditServerError);

  const handleSubmit = useCallback((): void => {
    const fromDate = fromDateInputValue(fromValue);
    const toDate = fromDateInputValue(toValue);
    if (!fromDate || !toDate) return;
    logVerbose("audit.page.filter.submit", {
      action_present: actionValue !== "",
      actor_present: actorValue !== "",
    });
    // Reset pagination on new filter
    setAppliedCursor(undefined);
    prevDataRef.current = undefined;
    setAllRows([]);
    setAppliedFrom(fromDate);
    setAppliedTo(toDate);
    setAppliedActor(actorValue);
    setAppliedAction(actionValue);
  }, [fromValue, toValue, actorValue, actionValue]);

  const handleReset = useCallback((): void => {
    logVerbose("audit.page.filter.reset");
    setFromValue(defaultFrom);
    setToValue(defaultTo);
    setActorValue("");
    setActionValue("");
    setAppliedCursor(undefined);
    prevDataRef.current = undefined;
    setAllRows([]);
    setAppliedFrom(fromDateInputValue(defaultFrom) ?? daysAgo(AUDIT_DEFAULT_WINDOW_DAYS, new Date()));
    setAppliedTo(new Date());
    setAppliedActor("");
    setAppliedAction("");
  }, [defaultFrom, defaultTo]);

  const handleRetry = useCallback((): void => {
    logVerbose("audit.page.retry.triggered");
    refetch();
  }, [refetch]);

  const handleBack = useCallback((): void => {
    logVerbose("audit.page.back.triggered");
    void navigate(-1);
  }, [navigate]);

  const handleLoadMore = useCallback((): void => {
    if (data?.next_cursor) {
      logVerbose("audit.page.load_more.triggered", { has_cursor: true });
      setAppliedCursor(data.next_cursor);
    }
  }, [data]);

  // Log error state transitions
  if (error !== null) {
    logError("audit.page.error.state", { error_code: error.code });
  }

  // Derive UX states
  const showValidationError = isRangeInvalid || isActorInvalid;
  const validationSubCode = isActorInvalid ? "actor" : "range";
  const showLoading = isPending && !showValidationError;
  const showEmpty =
    !isPending && !error && !showValidationError && allRows.length === 0 && data !== undefined;
  const showSuccess =
    !isPending && !error && !showValidationError && allRows.length > 0;

  return (
    <main style={PAGE_STYLE} data-testid="audit-page">
      <div style={CONTENT_STYLE}>
        {/* Page header */}
        <header style={HEADER_STYLE}>
          <h1 style={TITLE_STYLE}>{t("audit:title")}</h1>
          <p style={SUBTITLE_STYLE}>{t("audit:subtitle")}</p>
        </header>

        {/* Filters */}
        <AuditFilters
          fromValue={fromValue}
          toValue={toValue}
          actorValue={actorValue}
          actionValue={actionValue}
          onFromChange={setFromValue}
          onToChange={setToValue}
          onActorChange={setActorValue}
          onActionChange={setActionValue}
          onSubmit={handleSubmit}
          onReset={handleReset}
        />

        {/* Validation error — filter invariant */}
        {showValidationError && (
          <ValidationErrorView subCode={validationSubCode} />
        )}

        {/* Loading state */}
        {showLoading && <LoadingView />}

        {/* Permission denied state */}
        {isForbidden && <ForbiddenView onBack={handleBack} />}

        {/* Network error state (5xx, fetch failure) */}
        {isNetworkError && (
          <NetworkErrorView onRetry={handleRetry} loading={isFetching} />
        )}

        {/* Empty state */}
        {showEmpty && <EmptyView />}

        {/* Success state — table + pagination + next action */}
        {showSuccess && (
          <>
            <div aria-live="polite" aria-atomic="false">
              <AuditTable rows={allRows} />
            </div>

            <nav style={NEXT_ACTION_STYLE} aria-label={t("audit:nextAction")}>
              {/* Load more CTA (D-T001-PAGINATION) */}
              {data?.has_more && (
                <button
                  type="button"
                  onClick={handleLoadMore}
                  disabled={isFetching}
                  style={LOAD_MORE_STYLE}
                  data-testid="audit-load-more"
                >
                  {isFetching ? "…" : t("audit:pagination.loadMore")}
                </button>
              )}

              {data && !data.has_more && allRows.length > 0 && (
                <span style={DISABLED_CTA_STYLE} aria-label={t("audit:pagination.noMore")}>
                  {t("audit:pagination.noMore")}
                </span>
              )}

              {/* Next action: open event detail — DISABLED in v1 (D-T001-NEXT-ACTION) */}
              <span
                style={DISABLED_CTA_STYLE}
                title={t("audit:nextAction")}
                aria-disabled="true"
                data-testid="audit-next-action-disabled"
              >
                {t("audit:nextAction")}
              </span>
            </nav>
          </>
        )}
      </div>
    </main>
  );
}
