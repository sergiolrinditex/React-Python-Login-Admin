/**
 * Hilo People — Admin AI feature barrel exports.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-ADMINAI-FEATURE-BARREL
 *
 * Responsibility: Public API surface for the admin-ai feature module.
 *   Re-exports types, errors, repository functions, and hooks so downstream slices
 *   (P04-S01-T002 AdminAiModelsPage, T003 ModelWizardPage, T004 ModelTestDrawer)
 *   can import cleanly without reaching into internal subdirectories.
 *
 * Design: barrel is additive-only. Future slices add exports here;
 *   they MUST NOT remove or rename existing exports (would break T001 consumers).
 */

// Domain types
export type {
  UsageRow,
  UsageTotals,
  UsageSummary,
  GetUsageRequest,
} from "./domain/types";

// Error classes and union
export {
  AdminAiAuthExpiredError,
  AdminAiForbiddenError,
  AdminAiValidationError,
  AdminAiNetworkError,
  AdminAiInternalError,
  mapAdminAiError,
} from "./data/errors";
export type { AdminAiError } from "./data/errors";

// Repository
export { getUsage } from "./data/adminAiRepository";

// Presentation hook
export { useDashboardUsage, computeUsageWindow } from "./presentation/useDashboardUsage";
export type { UseDashboardUsageResult } from "./presentation/useDashboardUsage";
