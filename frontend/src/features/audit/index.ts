/**
 * Hilo People — Audit feature barrel exports.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Public API surface of the audit feature module.
 *   Downstream consumers import from this barrel, not from internal paths.
 *
 * §D-T001-BARREL: Canonical write_set anchor for this file.
 * Source ref: §D-T001-BARREL, task pack §6 write-set.
 */

// Domain types
export type { AuditLog, AuditQuery, AuditPage } from "./domain/types";
export { AUDIT_MAX_WINDOW_DAYS, AUDIT_DEFAULT_WINDOW_DAYS, AUDIT_KNOWN_ACTIONS } from "./domain/types";

// Domain port
export type { IAuditRepository } from "./domain/IAuditRepository";

// Data errors
export {
  AuditValidationError,
  AuditForbiddenError,
  AuditAuthExpiredError,
  AuditNetworkError,
  AuditServerError,
  mapAuditError,
} from "./data/errors";
export type { AuditError } from "./data/errors";

// Data repository
export { getAuditPage } from "./data/auditRepository";

// Presentation hook
export { useAuditQuery, isAuditRangeValid, isActorValid } from "./presentation/useAuditQuery";
export type { UseAuditQueryProps, UseAuditQueryResult } from "./presentation/useAuditQuery";
