/**
 * Hilo People — Admin feature barrel exports.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Public API surface of the admin feature module.
 *   Downstream consumers import from this barrel, not from internal paths.
 *
 * D-T002-BARREL: Canonical write_set anchor for this file.
 * Source ref: §D-T002-BARREL, task pack §9 Impact analysis.
 */

// Domain types
export type { UsageQuery, UsageRow, UsageTotals, UsageSummary, UsageGroupBy } from "./domain/types";

// Domain port
export type { IUsageRepository } from "./domain/UsageRepository";

// Data errors
export {
  UsageValidationError,
  UsageForbiddenError,
  UsageAuthExpiredError,
  UsageNetworkError,
  UsageServerError,
  mapUsageError,
} from "./data/errors";
export type { UsageError } from "./data/errors";

// Data repository
export { getUsage } from "./data/usageRepository";

// Presentation hook
export { useUsage, isRangeValid } from "./presentation/useUsage";
export type { UseUsageProps, UseUsageResult } from "./presentation/useUsage";
