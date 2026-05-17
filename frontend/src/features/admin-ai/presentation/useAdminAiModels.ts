/**
 * Hilo People — useAdminAiModels hook.
 *
 * Slice/Phase: P04-S01-T002 — AdminAiModelsPage / Phase 4.
 * Write-set anchor: §D-T002-FEATURE-PRESENTATION
 *
 * Responsibility: TanStack Query v5 useQuery hook that fetches providers + models
 *   via Promise.all, joins them client-side (D-T002-FETCH-BOTH), and exposes
 *   a typed result for AdminAiModelsPage.
 *
 * Clean Architecture: presentation/ layer — depends on data/adminAiRepository.
 *   Page mounts this hook; never calls repositories directly.
 *
 * TanStack Query v5 pattern (mirrors useDashboardUsage):
 *   queryKey: ["admin","ai","models"]  (no params in v1)
 *   staleTime: 30_000ms (30s)
 *   gcTime: 300_000ms (5min)
 *   retry: false (retry CTA handles UX — D-T002-RETRY-INVALIDATES)
 *
 * Non-negotiables §logging: BEFORE + AFTER gated by VITE_ENABLE_VERBOSE_LOGGING.
 * PII-clean (§D-T002-LOGS-PII-CLEAN): logs only provider_count, model_count, error_class.
 *   NEVER logs provider names, model_ids, credentials, base_urls.
 *
 * Key deps: @tanstack/react-query v5, adminAiRepository, authFetch, AuthProvider.
 */

import { useQuery } from "@tanstack/react-query";
import { useCallback } from "react";
import { useAuth } from "../../auth/presentation/AuthProvider";
import { getProviders, getModels } from "../data/adminAiRepository";
import {
  AdminAiForbiddenError,
  AdminAiAuthExpiredError,
  type AdminAiError,
} from "../data/errors";
import type { AiProvider, AiModel } from "../domain/types";
import { logVerbose, logWarn, logError } from "../data/logger";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STALE_TIME_MS = 30_000;
const GC_TIME_MS = 300_000;

// ---------------------------------------------------------------------------
// Derived row type
// ---------------------------------------------------------------------------

/**
 * A single row in the AdminAiModelsPage table — provider + model joined.
 * Source: D-T002-STATUS-DOT derivation table + D-T002-COST-FORMAT.
 */
export interface AdminAiModelRow {
  id: string;
  model_id: string;
  model_type: string;
  enabled: boolean;
  is_default: boolean;
  pricing: Record<string, unknown>;
  latency_ms_avg: number | null;
  provider_id: string;
  /** Joined from providers list. "—" if provider missing (R-2 defensive). */
  providerName: string;
  providerStatus: "draft" | "active" | "inactive" | "unknown";
}

// ---------------------------------------------------------------------------
// Hook result type
// ---------------------------------------------------------------------------

export interface UseAdminAiModelsResult {
  /** True while the first fetch is in-flight (loading skeleton). */
  isLoading: boolean;
  /** True if the query succeeded. */
  isSuccess: boolean;
  /** True if the query errored. */
  isError: boolean;
  /** Typed error from the last failed query. */
  error: AdminAiError | null;
  /** Joined data (defined when isSuccess). */
  data:
    | {
        providers: AiProvider[];
        models: AiModel[];
        rows: AdminAiModelRow[];
      }
    | undefined;
  /** Trigger a manual refetch (D-T002-RETRY-INVALIDATES). */
  refetch: () => void;
}

// ---------------------------------------------------------------------------
// Internal join helper
// ---------------------------------------------------------------------------

/**
 * Builds AdminAiModelRow[] by joining models with their provider data.
 * Provider lookup uses a Map for O(1) access.
 * PII-clean: no names or IDs logged — counts only.
 *
 * @param providers - Provider list from GET /api/v1/admin/ai/providers.
 * @param models - Model list from GET /api/v1/admin/ai/models.
 * @returns Joined AdminAiModelRow[].
 */
function joinModels(providers: AiProvider[], models: AiModel[]): AdminAiModelRow[] {
  const providerMap = new Map<string, AiProvider>(
    providers.map((p) => [p.id, p]),
  );

  return models.map((m) => {
    const provider = providerMap.get(m.provider_id);
    return {
      id: m.id,
      model_id: m.model_id,
      model_type: m.model_type,
      enabled: m.enabled,
      is_default: m.is_default,
      pricing: m.pricing,
      latency_ms_avg: m.latency_ms_avg,
      provider_id: m.provider_id,
      providerName: provider?.name ?? "—",
      providerStatus: (provider?.status ?? "unknown") as AdminAiModelRow["providerStatus"],
    };
  });
}

// ---------------------------------------------------------------------------
// Hook
// ---------------------------------------------------------------------------

/**
 * Fetches and joins AI providers + models for AdminAiModelsPage.
 *
 * Uses Promise.all to fetch providers and models concurrently (D-T002-FETCH-BOTH).
 * If either Result is err, throws the FIRST error to surface the typed error.
 * Joins models with provider name + status client-side.
 *
 * @returns UseAdminAiModelsResult
 */
export function useAdminAiModels(): UseAdminAiModelsResult {
  const { logout } = useAuth();

  const onAuthFailure = useCallback(() => {
    logWarn("admin-ai.hook.useAdminAiModels.auth_failure");
    void logout();
  }, [logout]);

  logVerbose("admin-ai.hook.useAdminAiModels.render.start", {});

  const query = useQuery<
    { providers: AiProvider[]; models: AiModel[]; rows: AdminAiModelRow[] },
    AdminAiError
  >({
    queryKey: ["admin", "ai", "models"],
    queryFn: async () => {
      logVerbose("admin-ai.hook.useAdminAiModels.queryFn.start", {});

      const [providersResult, modelsResult] = await Promise.all([
        getProviders(onAuthFailure),
        getModels(undefined, onAuthFailure),
      ]);

      // Surface the FIRST error — preserves typed error semantics
      if (!providersResult.ok) {
        logError("admin-ai.hook.useAdminAiModels.queryFn.providers_error", {
          error_class: providersResult.error.constructor.name,
        });
        throw providersResult.error;
      }

      if (!modelsResult.ok) {
        logError("admin-ai.hook.useAdminAiModels.queryFn.models_error", {
          error_class: modelsResult.error.constructor.name,
        });
        throw modelsResult.error;
      }

      const providers = providersResult.value;
      const models = modelsResult.value;
      const rows = joinModels(providers, models);

      logVerbose("admin-ai.hook.useAdminAiModels.queryFn.ok", {
        provider_count: providers.length,
        model_count: models.length,
      });

      return { providers, models, rows };
    },
    staleTime: STALE_TIME_MS,
    gcTime: GC_TIME_MS,
    retry: false,
  });

  // Map TanStack error to AdminAiError
  const typedError: AdminAiError | null =
    query.error instanceof Error ? (query.error as AdminAiError) : null;

  if (typedError instanceof AdminAiAuthExpiredError) {
    logWarn("admin-ai.hook.useAdminAiModels.auth_expired_in_error");
  }
  if (typedError instanceof AdminAiForbiddenError) {
    logWarn("admin-ai.hook.useAdminAiModels.forbidden_in_error");
  }

  return {
    isLoading: query.isLoading,
    isSuccess: query.isSuccess,
    isError: query.isError,
    error: typedError,
    data: query.data,
    refetch: () => {
      logVerbose("admin-ai.hook.useAdminAiModels.refetch");
      void query.refetch();
    },
  };
}
