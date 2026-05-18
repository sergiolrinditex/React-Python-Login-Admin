/**
 * Hilo People — Admin feature domain types.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Pure domain types for the admin usage feature.
 *   No external imports — domain layer is framework-agnostic.
 *   Types mirror the backend response shape from:
 *     - backend/app/admin/usage.py (endpoint handler)
 *     - backend/app/admin/_usage_aggregator.py (SQL aggregation shape)
 *
 * Backend canonical response shape (GET /api/v1/admin/usage):
 *   { data: { from, to, group_by, rows[], totals }, meta: { request_id } }
 *
 * Row fields present based on group_by:
 *   - group_by=model:     model_id, model_name, provider_type, tokens_in, tokens_out,
 *                          estimated_cost, latency_ms_avg, invocations
 *   - group_by=day:       day, tokens_in, tokens_out, estimated_cost, latency_ms_avg, invocations
 *   - group_by=model_day: model_id, model_name, provider_type, day + above
 *
 * D-T002-DOMAIN-TYPES: Canonical write_set anchor for this file.
 * Source ref: §D-T002-DOMAIN-TYPES, TECHNICAL_GUIDE §6.1#/admin/usage.
 */

// ---------------------------------------------------------------------------
// Query input types
// ---------------------------------------------------------------------------

/**
 * Valid group_by dimensions for the usage aggregation.
 * Mirrors backend _VALID_GROUP_BY = {"model", "day", "model_day"}.
 */
export type UsageGroupBy = "model" | "day" | "model_day";

/**
 * Input query parameters for usage aggregation.
 * Validated client-side before fetching (D-T002-RANGE-INVARIANT).
 */
export interface UsageQuery {
  /** Window start (inclusive). */
  from: Date;
  /** Window end (exclusive). */
  to: Date;
  /** Aggregation dimension. Default: "model_day" (D-T002-DEFAULT-RANGE). */
  groupBy: UsageGroupBy;
}

// ---------------------------------------------------------------------------
// Response row type
// ---------------------------------------------------------------------------

/**
 * A single aggregated usage row from the backend.
 * Fields are conditional based on group_by dimension.
 *
 * Present for group_by=model and group_by=model_day:
 *   model_id, model_name, provider_type
 *
 * Present for group_by=day and group_by=model_day:
 *   day (ISO date string "YYYY-MM-DD")
 *
 * Always present:
 *   tokens_in, tokens_out, estimated_cost, latency_ms_avg, invocations
 */
export interface UsageRow {
  /** Model UUID string (only for group_by=model|model_day). */
  model_id?: string | null;
  /** Model name/identifier (only for group_by=model|model_day). */
  model_name?: string | null;
  /** Provider type identifier (only for group_by=model|model_day). */
  provider_type?: string | null;
  /** ISO date string "YYYY-MM-DD" (only for group_by=day|model_day). */
  day?: string | null;
  /** Prompt token count for the period. */
  tokens_in: number;
  /** Completion token count for the period. */
  tokens_out: number;
  /** Estimated cost in USD (float). */
  estimated_cost: number;
  /** Average latency in milliseconds (null if no data). */
  latency_ms_avg: number | null;
  /** Total invocation count for the period. */
  invocations: number;
}

// ---------------------------------------------------------------------------
// Response totals type
// ---------------------------------------------------------------------------

/**
 * Aggregated totals across all rows in the response.
 * Always present in the backend response.
 */
export interface UsageTotals {
  /** Total prompt tokens across all rows. */
  tokens_in: number;
  /** Total completion tokens across all rows. */
  tokens_out: number;
  /** Total estimated cost in USD. */
  estimated_cost: number;
  /** Total invocations across all rows. */
  invocations: number;
  /** Weighted average latency in ms across all rows (null if no data). */
  latency_ms_avg: number | null;
}

// ---------------------------------------------------------------------------
// Response summary type
// ---------------------------------------------------------------------------

/**
 * Full usage summary as returned by the backend.
 * Wraps rows[] + totals + metadata about the query window.
 *
 * Mirrors backend: data: { from, to, group_by, rows, totals }
 */
export interface UsageSummary {
  /** ISO 8601 window start string from the backend. */
  from: string;
  /** ISO 8601 window end string from the backend. */
  to: string;
  /** The group_by dimension used in the query. */
  group_by: UsageGroupBy;
  /** Aggregated rows (may be empty). */
  rows: UsageRow[];
  /** Cross-row totals. */
  totals: UsageTotals;
}
