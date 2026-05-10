/**
 * diffSummary — Pure domain function for discover-models diff counts.
 *
 * What: Derives summary counts from a DiscoverModelsData payload.
 *       Contains no side effects and no imports beyond types.
 *       This is the canonical entry point for any component that needs
 *       computed summary figures from the raw discover-models response.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   - ../data/types — DiscoverModelsData (type-only import)
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §11.1 (diffSummary.ts ≤60 lines)
 *   - instrucciones.md §3.1 (EL MOTOR — listar modelos sub-step)
 */

import type { DiscoverModelsData } from '../data/types';

/** Summary counts derived from a DiscoverModelsData payload. */
export interface DiffSummary {
  /** Models newly persisted (auto_discovered=true). */
  totalPersisted: number;
  /** Models already present — untouched. */
  totalExisting: number;
  /** Models seen but skipped. */
  totalSkipped: number;
  /** Total models reported by upstream provider. */
  totalSeen: number;
}

/**
 * Derives summary counts from a DiscoverModelsData payload.
 *
 * Pure function — no side effects. Safe to call in render.
 *
 * @param data - The data field from a DiscoverModelsResponse.
 * @returns DiffSummary counts.
 */
export function diffSummary(data: DiscoverModelsData): DiffSummary {
  return {
    totalPersisted: data.added.length,
    totalExisting: data.existing.length,
    totalSkipped: data.skipped.length,
    totalSeen: data.total_seen,
  };
}
