/**
 * Providers — root React context providers for Hilo People.
 *
 * What: Wires BrowserRouter, QueryClientProvider and I18nextProvider so all
 * child trees have access to routing, server-state cache and i18n without
 * prop-drilling. This is the providers shell; full i18n resource namespaces
 * (ES/EN/FR) are added in P00-S01-T005. Auth provider arrives in P01-S03-T001.
 *
 * Phase/Slice: P00 / P00-S01-T002 — Frontend dependency pack
 *
 * Key dependencies (non-obvious):
 *   - i18next: initialized inline with empty resources; T005 replaces this
 *     with the real namespace loader (i18n/index.ts).
 *   - QueryClient: module-level singleton — one shared client for the app.
 *   - BrowserRouter: must wrap QueryClientProvider so route hooks work inside
 *     query-aware components (e.g. useNavigate inside a mutation callback).
 *
 * Logging: controlled by VITE_ENABLE_VERBOSE_LOGGING env var.
 *   true  → console.info shows full flow (module init + provider mount)
 *   false → only console.warn / console.error appear
 *   Note: .env.example maps ENABLE_VERBOSE_LOGGING (backend) →
 *   VITE_ENABLE_VERBOSE_LOGGING (frontend Vite prefix).
 */

import { type ReactNode } from 'react';
import { BrowserRouter } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { I18nextProvider } from 'react-i18next';
import i18next from 'i18next';
import { initReactI18next } from 'react-i18next';

// ---------------------------------------------------------------------------
// Minimal inline logger — reads VITE_ENABLE_VERBOSE_LOGGING.
// Inlined here (≤20 lines) because a shared logger module is not yet created
// (YAGNI for single-file use; shared/ is only for code used by 2+ features).
// ---------------------------------------------------------------------------

const isVerbose = (): boolean =>
  import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === 'true';

const logger = {
  info: (msg: string, data?: unknown): void => {
    if (isVerbose()) {
      if (data !== undefined) {
        console.info(`[providers] ${msg}`, data);
      } else {
        console.info(`[providers] ${msg}`);
      }
    }
  },
  warn: (msg: string, data?: unknown): void => {
    if (data !== undefined) {
      console.warn(`[providers] ${msg}`, data);
    } else {
      console.warn(`[providers] ${msg}`);
    }
  },
  error: (msg: string, err?: unknown): void => {
    console.error(`[providers] ${msg}`, err);
  },
};

// ---------------------------------------------------------------------------
// QueryClient — module-level singleton with production-sane defaults.
// staleTime 60 000ms: data is fresh for 1 min before background refetch.
// retry 1: one automatic retry on transient network errors; avoids hammering
// the backend on hard failures.
// ---------------------------------------------------------------------------

logger.info('BEFORE queryClient.create');

export const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      retry: 1,
    },
  },
});

logger.info('AFTER queryClient.create', {
  staleTime: 60_000,
  retry: 1,
});

// ---------------------------------------------------------------------------
// i18n singleton — minimal bootstrap with empty resources.
// T005 (P00-S01-T005) will replace this with the real ES/EN/FR loader from
// frontend/src/i18n/index.ts. The init call here is intentionally fire-and-
// forget (returns a promise); i18next sets isInitialized synchronously in
// v23+ when no async backends are used. We pass void to suppress lint.
// ---------------------------------------------------------------------------

logger.info('BEFORE i18n.init');

void i18next
  .use(initReactI18next)
  .init({
    resources: {
      en: {},
      es: {},
      fr: {},
    },
    fallbackLng: 'es',
    lng: 'es',
    interpolation: {
      escapeValue: false, // React already escapes output
    },
  })
  .then(() => {
    logger.info('AFTER i18n.init', { isInitialized: i18next.isInitialized });
  })
  .catch((err: unknown) => {
    logger.error('i18n.init failed', err);
  });

// Export the i18n instance for use in tests and I18nextProvider
export { i18next as i18n };

// ---------------------------------------------------------------------------
// Providers component
// ---------------------------------------------------------------------------

interface ProvidersProps {
  /** Child components that require router / query / i18n context */
  children: ReactNode;
}

/**
 * Root provider tree for Hilo People.
 *
 * Wrapping order (outer → inner):
 *   I18nextProvider → BrowserRouter → QueryClientProvider → children
 *
 * Rationale: BrowserRouter must be above QueryClientProvider so that
 * route-aware callbacks inside mutations/queries can call useNavigate.
 * I18nextProvider is outermost because t() is needed everywhere including
 * in error boundaries that may wrap the Router.
 *
 * @param props.children - The application tree to render.
 */
export function Providers({ children }: ProvidersProps): React.JSX.Element {
  logger.info('BEFORE Providers.render');

  const element = (
    <I18nextProvider i18n={i18next}>
      <BrowserRouter>
        <QueryClientProvider client={queryClient}>
          {children}
        </QueryClientProvider>
      </BrowserRouter>
    </I18nextProvider>
  );

  logger.info('AFTER Providers.render');

  return element;
}
