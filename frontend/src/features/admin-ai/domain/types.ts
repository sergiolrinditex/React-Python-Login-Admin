/**
 * Hilo People — Admin AI domain types.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-ADMINAI-FEATURE
 *
 * Responsibility: Pure domain types for the admin-ai feature module.
 *   No framework imports. No external lib imports. Domain-only.
 *   Consumed by adminAiRepository, useDashboardUsage, and downstream slices
 *   (P04-S01-T002 AdminAiModelsPage, T003 ModelWizardPage, T004 ModelTestDrawer).
 *
 * Source: TECHNICAL_GUIDE §6.2 backend response shape (read from HEAD
 *   backend/app/admin/usage.py + _usage_aggregator.py).
 *
 * Clean Architecture: domain imports nothing external.
 */

// ---------------------------------------------------------------------------
// Usage domain types
// ---------------------------------------------------------------------------

/**
 * A single row in the usage summary — represents one model (or one day, or
 * one model-day combination depending on group_by).
 *
 * group_by=model: model_name present, day absent.
 * group_by=day:   day present, model_name absent.
 * group_by=model_day: both present.
 *
 * Source: backend/app/admin/_usage_aggregator.py shape.
 */
export interface UsageRow {
  /** Total input tokens. */
  tokens_in: number;
  /** Total output tokens. */
  tokens_out: number;
  /** Estimated cost in USD. */
  estimated_cost: number;
  /** Average latency in milliseconds. */
  latency_ms_avg: number;
  /** Number of invocations in the window. */
  invocations: number;
  /** Model display name — present when group_by in {model, model_day}. */
  model_name?: string;
  /** ISO-8601 date string — present when group_by in {day, model_day}. */
  day?: string;
}

/**
 * Aggregated totals across all rows in the window.
 * Source: backend UsageSummary.totals schema.
 */
export interface UsageTotals {
  tokens_in: number;
  tokens_out: number;
  estimated_cost: number;
  invocations: number;
  latency_ms_avg: number;
}

/**
 * Full usage summary returned by GET /api/v1/admin/usage.
 * Source: backend UsageSummary schema (data envelope).
 */
export interface UsageSummary {
  /** ISO-8601 start of the window. */
  from: string;
  /** ISO-8601 end of the window. */
  to: string;
  /** Grouping mode used for this query. */
  group_by: "model" | "day" | "model_day";
  /** Per-group rows. Empty array when no usage in the window. */
  rows: UsageRow[];
  /** Cross-row totals. All zeros when rows is empty. */
  totals: UsageTotals;
}

/**
 * Request parameters for getUsage.
 * Source: TECHNICAL_GUIDE §6.2 query params for GET /api/v1/admin/usage.
 */
export interface GetUsageRequest {
  /** ISO-8601 start datetime (inclusive). */
  from: string;
  /** ISO-8601 end datetime (exclusive). */
  to: string;
  /** Grouping mode. Default: "model". */
  group_by?: "model" | "day" | "model_day";
  /** Optional UUID to filter by a specific AI model. */
  model_id?: string;
  /** Optional UUID to filter by a specific provider. */
  provider_id?: string;
}
