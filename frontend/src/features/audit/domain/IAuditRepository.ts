/**
 * Hilo People — Audit feature domain repository port (interface).
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Port (interface) for the audit data layer.
 *   Defines what operations the domain needs; the data layer implements them.
 *   No imports of external libs, no React, no fetch calls here.
 *
 * Clean Architecture: presentation/ hooks depend on this port, NOT on
 *   auditRepository.ts directly. This decouples the UI from fetch internals.
 *
 * §D-T001-DOMAIN: Canonical write_set anchor for this file.
 * Source ref: §D-T001-DOMAIN, task pack §7 Front→Back→DB contract.
 */

import type { Result } from "../../auth/domain/AuthRepository";
import type { AuditQuery, AuditPage } from "./types";
import type { AuditError } from "../data/errors";

// ---------------------------------------------------------------------------
// Audit repository port
// ---------------------------------------------------------------------------

/**
 * Port interface for the audit log data operations.
 * Implemented by data/auditRepository.ts; consumed by presentation/useAuditQuery.ts.
 *
 * Contract:
 *   - getAuditPage(query): calls GET /api/v1/admin/audit; returns AuditPage or typed error.
 *
 * Error handling: returns Result<AuditPage, AuditError> — never throws to presentation layer.
 */
export interface IAuditRepository {
  /**
   * Fetches a page of audit log rows from the backend.
   *
   * Maps the standard backend envelope {data:[], meta:{next_cursor, has_more, count}} to AuditPage.
   *
   * @param query - Validated AuditQuery (from, to, optional actor/action/cursor/limit).
   * @param onAuthFailure - Called when session expires and refresh fails (triggers logout).
   * @param signal - Optional AbortSignal for TanStack v5 cancellation.
   * @returns Result<AuditPage, AuditError>
   */
  getAuditPage(
    query: AuditQuery,
    onAuthFailure?: () => void,
    signal?: AbortSignal,
  ): Promise<Result<AuditPage, AuditError>>;
}
