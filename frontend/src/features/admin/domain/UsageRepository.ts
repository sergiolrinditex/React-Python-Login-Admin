/**
 * Hilo People — IUsageRepository port (interface).
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Port (interface) for the admin usage data layer.
 *   Defines what the domain needs; the data layer implements this.
 *   No imports of external libs, no React, no fetch calls here.
 *
 * Clean Architecture: presentation/ depends on this port, NOT on
 *   usageRepository.ts directly. Decouples UI from fetch implementation.
 *
 * D-T002-DOMAIN-PORT: Canonical write_set anchor for this file.
 * Source ref: §D-T002-DOMAIN-PORT, task pack §7 Front→Back→DB contract.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type { UsageSummary, UsageQuery } from "./types";

// ---------------------------------------------------------------------------
// Usage error union (re-exported for convenience)
// ---------------------------------------------------------------------------

/**
 * Re-export Result from auth domain for use in usage layer.
 * Avoids circular imports while keeping a single Result<T,E> definition.
 */
export type { Result };

// ---------------------------------------------------------------------------
// Usage errors (forward declaration for the port)
// ---------------------------------------------------------------------------

/**
 * Union type for all usage repository errors.
 * Concrete classes live in data/errors.ts.
 */
export type UsageError =
  | { readonly code: "USAGE_VALIDATION_ERROR"; message: string }
  | { readonly code: "USAGE_FORBIDDEN" }
  | { readonly code: "USAGE_AUTH_EXPIRED" }
  | { readonly code: "USAGE_NETWORK_ERROR"; message: string; cause?: unknown }
  | { readonly code: "USAGE_SERVER_ERROR"; status: number };

// ---------------------------------------------------------------------------
// Repository port
// ---------------------------------------------------------------------------

/**
 * Port interface for admin usage operations.
 * Implemented by data/usageRepository.ts.
 *
 * Contract:
 *   - getUsage(query, onAuthFailure?, signal?): fetches aggregated usage data.
 *     Returns Result<UsageSummary, UsageError>.
 *
 * @remarks
 *   All methods return typed Results — they never throw to the caller.
 *   Auth failures are surfaced via onAuthFailure callback (matches authFetch contract).
 */
export interface IUsageRepository {
  /**
   * Calls GET /api/v1/admin/usage with from, to, groupBy parameters.
   *
   * Returns Result.ok(UsageSummary) on 200.
   * Returns typed Result.err for all failure paths (403, 422, 5xx, network).
   *
   * @param query - UsageQuery with from, to, groupBy (validated by caller).
   * @param onAuthFailure - Called when session expires and cannot be refreshed.
   * @param signal - Optional AbortSignal for request cancellation (TanStack v5).
   * @returns Promise<Result<UsageSummary, UsageError>>
   */
  getUsage(
    query: UsageQuery,
    onAuthFailure?: () => void,
    signal?: AbortSignal,
  ): Promise<Result<UsageSummary, UsageError>>;
}
