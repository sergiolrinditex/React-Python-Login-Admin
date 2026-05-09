/**
 * App-level React context providers.
 *
 * What: Wraps the application component tree with QueryClientProvider
 * (TanStack Query) and I18nextProvider (react-i18next). No Router here —
 * BrowserRouter lives in app/router.tsx, added in P01-S03-T001.
 *
 * Phase/Slice: P00 / P00-S01-T002 — Frontend dependency pack
 *
 * Dependencies (non-obvious):
 *   - @tanstack/react-query 5.100.9 — QueryClient, QueryClientProvider
 *   - i18next 26.0.10 — i18n singleton instance
 *   - react-i18next 17.0.7 — I18nextProvider
 *
 * i18n bootstrap notes:
 *   - Resources are intentionally empty here. Namespaces (common, auth, chat,
 *     account, admin-ai, rag, mcp, errors) and translations land in P00-S01-T005.
 *   - `i18n.isInitialized` guard prevents re-init on hot reload.
 *   - lng + fallbackLng = 'es' per instrucciones.md §3.3.
 *
 * Logging decision:
 *   This file is purely declarative component composition with no action
 *   (no fetch, no mutation, no side effect). Per 01-non-negotiables.md §Logging,
 *   BEFORE/AFTER logs are added when the provider gains runtime behavior
 *   (auth refresh interceptor, language detector callback, etc.).
 *
 * Export shape (stable — DO NOT change without updating downstream slices):
 *   export function AppProviders({ children }: { children: ReactNode }): JSX.Element
 */

import { type ReactNode, useState } from 'react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { I18nextProvider } from 'react-i18next';
import i18n from 'i18next';

// Bootstrap i18next at module load — runs once at import, idempotent guard below.
// Resources empty: namespaces and translations land in P00-S01-T005.
// fallbackLng=es per instrucciones.md §3.3 (español, inglés, francés; fallback español).
if (!i18n.isInitialized) {
  i18n.init({
    lng: 'es',
    fallbackLng: 'es',
    resources: {},
    interpolation: { escapeValue: false },
  });
}

/**
 * Root provider tree for the Hilo People frontend.
 *
 * Renders `QueryClientProvider` (TanStack Query) wrapping `I18nextProvider`
 * (react-i18next), then renders `children` inside both.
 *
 * @param children - The full application component subtree.
 * @returns JSX element with provider tree.
 */
export function AppProviders({ children }: { children: ReactNode }) {
  // useState initializer ensures one QueryClient per React tree lifecycle,
  // not recreated on every render. Pattern recommended for React 19 + StrictMode.
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          // Disable refetch-on-window-focus to avoid spurious requests in tests
          // and development. Can be overridden per-query when needed.
          queries: { refetchOnWindowFocus: false },
        },
      }),
  );

  return (
    <QueryClientProvider client={queryClient}>
      <I18nextProvider i18n={i18n}>{children}</I18nextProvider>
    </QueryClientProvider>
  );
}
