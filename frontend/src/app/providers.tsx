/**
 * Hilo People — Application providers composition root.
 *
 * Slice/Phase: P00-S01-T002 — Frontend dependency pack / Phase 0 Scaffold.
 *
 * Responsibility: single mount point for ALL React context providers used
 *   app-wide. Every screen in the application must be mounted inside
 *   <Providers> so that TanStack Query, i18n, and (downstream) auth context
 *   are always available.
 *
 * Composition order (outer → inner, fixed — downstream slices rely on this):
 *   1. <I18nextProvider>       — T005 wires real locale resources.
 *   2. <QueryClientProvider>   — P01-S03-T001 and all feature hooks rely on this.
 *   3. {children}
 *
 * NOT included here intentionally:
 *   - <BrowserRouter> — mounted by T004 in App.tsx / router.tsx, OUTSIDE
 *     Providers. This keeps providers.tsx route-unaware and easier to test.
 *   - <AuthProvider>  — P01-S03-T001 adds it INSIDE <Providers> composition.
 *   - persistQueryClient — localStorage persistence is PROHIBITED per
 *     instrucciones.md §11.2 (tokens must not touch localStorage).
 *
 * Key deps:
 *   - @tanstack/react-query ^5.100.9 (React 19 compatible, memory-only cache).
 *   - i18next ^26.1.0 + react-i18next ^17.0.7 (React 19, TS 6 compatible).
 *   - i18n bootstrap from src/i18n/index.ts (minimal, resource-less — T005 fills).
 *
 * Logging: BEFORE/AFTER QueryClient init, gated by
 *   `import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true"`.
 *   ERROR path re-throws — never swallows errors.
 *   No PII, no secrets, no tokens in any log statement.
 */

import type { ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import type { i18n as I18nType } from "i18next";
import defaultI18n from "../i18n/index";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/**
 * Props for the Providers composition root.
 *
 * Both seams are optional for production use (defaults are fine).
 * They are mandatory for unit/integration tests to inject pre-built instances
 * and avoid re-initialising singletons across test renders.
 */
export interface ProvidersProps {
  /** Child tree — typically App → Router → pages. */
  children: ReactNode;
  /**
   * Injectable QueryClient — defaults to a new instance with `retry: 1`.
   * Tests SHOULD pass a fresh QueryClient to avoid cross-test cache bleed.
   */
  queryClient?: QueryClient;
  /**
   * Injectable i18n instance — defaults to the bootstrap singleton from
   * src/i18n/index.ts (resource-less, lng="es"). T005 passes the full instance.
   */
  i18n?: I18nType;
}

// ---------------------------------------------------------------------------
// Logging helper
// ---------------------------------------------------------------------------

/**
 * Emits a console.info message only when VITE_ENABLE_VERBOSE_LOGGING === "true".
 * Always safe to call — if the env var is absent or false, the call is a no-op.
 *
 * @param msg - Log message (no PII, no secrets, no tokens).
 * @param rest - Additional structured fields.
 */
function verboseLog(msg: string, ...rest: unknown[]): void {
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info(msg, ...rest);
  }
}

// ---------------------------------------------------------------------------
// Default QueryClient factory
// ---------------------------------------------------------------------------

/**
 * Creates the application-default QueryClient.
 * Kept outside the component so tests that don't inject a custom client
 * can call this factory directly.
 *
 * Policy (instrucciones.md §11.2):
 *   - NO persistQueryClient — cache lives in memory only.
 *   - retry: 1 — one automatic retry on transient failures.
 */
export function createDefaultQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        staleTime: 0,
      },
    },
  });
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Application-wide provider composition root.
 *
 * Business rule: ALL context that features depend on is provided here, in
 * a fixed order, so feature components never need to re-wrap themselves.
 *
 * Side effects:
 *   - Instantiates a QueryClient (or uses the injected one).
 *   - Attaches i18n to the React tree via I18nextProvider.
 *   - Emits BEFORE/AFTER init console.info messages when verbose logging is on.
 *
 * @param props - {@link ProvidersProps}
 * @returns The composed provider tree wrapping `children`.
 */
export function Providers({
  children,
  queryClient,
  i18n = defaultI18n,
}: ProvidersProps): import("react").ReactElement {
  // BEFORE init log
  verboseLog(
    "providers.init.start phase=P00 slice=P00-S01-T002",
    "queryClient=injected:" + String(queryClient !== undefined),
    "i18n=injected:" + String(i18n !== defaultI18n),
  );

  let resolvedClient: QueryClient;
  try {
    resolvedClient = queryClient ?? createDefaultQueryClient();
  } catch (err: unknown) {
    // ERROR path — QueryClient constructor failed (should never happen, but
    // the contract is the contract: log with full context and re-throw).
    console.error("providers.init.error", {
      phase: "P00",
      slice: "P00-S01-T002",
      error: err,
    });
    throw err;
  }

  const i18nReady = i18n.isInitialized;

  // AFTER init log
  verboseLog(
    "providers.init.ok",
    "queryClient=ready",
    "i18n=" + (i18nReady ? "ready" : "deferred"),
  );

  return (
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={resolvedClient}>
        {children}
      </QueryClientProvider>
    </I18nextProvider>
  );
}
