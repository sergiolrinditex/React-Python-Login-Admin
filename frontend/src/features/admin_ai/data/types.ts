/**
 * TypeScript type mirrors of the discover-models API contracts.
 *
 * What: Defines the response and error types for the
 *       POST /api/v1/admin/ai/providers/{id}/discover-models endpoint (FU-X1).
 *       Field names mirror the backend Pydantic schemas verbatim.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   none — pure type definitions, no runtime imports.
 *
 * Source-of-truth refs:
 *   - backend/app/features/admin_ai/schemas.py — AiModelOut, SkippedModel,
 *     DiscoverModelsData, DiscoverModelsResponse
 *   - task-pack P00-S02-T007.md §3.2 (Response shape)
 *   - task-pack P00-S02-T007.md §3.3 (Error codes)
 *
 * Downstream consumers:
 *   - discoverModels.ts (API client)
 *   - DiffReviewTable.tsx (presentation)
 *   - diffSummary.ts (domain)
 *   - P04-S01-T002 reuses AiModelOut for the canonical models table
 */

/** A discovered or existing AI model row (mirrors backend AiModelOut). */
export interface AiModelOut {
  id: string;
  provider_id: string;
  model_id: string;
  model_type: 'chat' | 'embedding' | 'unknown';
  capabilities: string[];
  enabled: boolean;
  is_default: boolean;
  auto_discovered: boolean;
}

/** A model skipped during discovery, with the reason (mirrors backend SkippedModel). */
export interface SkippedModel {
  model_id: string;
  reason: 'unsupported_model_type' | 'parse_error' | 'empty_model_id';
}

/** The payload inside data.* of the discover-models 200 response. */
export interface DiscoverModelsData {
  /** Newly persisted models (auto_discovered=true). */
  added: AiModelOut[];
  /** Models already present in the DB, untouched. */
  existing: AiModelOut[];
  /** Models seen from the upstream provider but not persisted. */
  skipped: SkippedModel[];
  /** Total models seen from the upstream provider (added + existing + skipped). */
  total_seen: number;
}

/**
 * Top-level response envelope for the discover-models endpoint.
 * Backend returns { "data": { ... } }.
 */
export interface DiscoverModelsResponse {
  data: DiscoverModelsData;
}

// ── Error types ──────────────────────────────────────────────────────────────

/** Discriminated union of error codes the API client produces. */
export type AdminAiErrorCode =
  | 'network_error'        // transport failure, fetch throws
  | 'unauthorized'         // 401 — header absent or malformed
  | 'forbidden'            // 403 — token does not start with dev-admin-
  | 'provider_not_found'   // 404 — provider_id not in ai_providers
  | 'validation_error'     // 422 — unsupported provider or malformed UUID
  | 'upstream_error'       // 502 — MissingCredentialError / CryptoError / UpstreamProviderError
  | 'server_error';        // any other 5xx

/** Typed error returned by the API client (never thrown across layers). */
export interface AdminAiError {
  code: AdminAiErrorCode;
  /** Human-readable message for logging (never shown raw in UI). */
  message: string;
  /** Raw HTTP status code, if available. */
  httpStatus?: number;
}

/** Result type — either a success value or a typed error. */
export type Result<T, E> =
  | { ok: true; value: T }
  | { ok: false; error: E };
