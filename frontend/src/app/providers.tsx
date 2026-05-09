/**
 * App-level React context providers.
 *
 * What: Wraps the application component tree with QueryClientProvider
 * (TanStack Query) and I18nextProvider (react-i18next). No Router here —
 * BrowserRouter lives in app/router.tsx, added in P01-S03-T001.
 *
 * Phase/Slice: P00 / P00-S01-T002 — Frontend dependency pack
 * Updated:     P00 / P00-S01-T005 — i18n resources ES/EN/FR
 *
 * Dependencies (non-obvious):
 *   - @tanstack/react-query 5.100.9 — QueryClient, QueryClientProvider
 *   - i18next 26.0.10 — i18n singleton instance
 *   - react-i18next 17.0.7 — I18nextProvider
 *   - ../i18n/index.ts — i18n singleton (P00-S01-T005)
 *
 * i18n bootstrap notes:
 *   - Resources loaded from `../i18n` (P00-S01-T005). The side-effect import
 *     below triggers eager initialisation of all 8 namespaces in es/en/fr
 *     per instrucciones.md §6 and §1.4.
 *   - lng + fallbackLng = 'es' per instrucciones.md §6 + §1.4 (locale list, line 42).
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
import i18n from '../i18n';

// Side-effect import ensures i18next is initialised before the provider mounts.
// The singleton is configured in ../i18n/index.ts (P00-S01-T005):
//   - 8 namespaces: common, auth, chat, account, admin-ai, rag, mcp, errors
//   - 3 locales: es (default), en, fr  — fallbackLng: 'es'
//   - Eager loading: all 24 JSON bundles preloaded at module import time

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
