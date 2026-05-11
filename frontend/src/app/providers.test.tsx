/**
 * providers.test.tsx — Smoke tests for the Providers root context tree.
 *
 * What: Verifies that BrowserRouter, QueryClientProvider, and I18nextProvider
 * mount without throwing and that children render correctly inside them.
 * Tests use REAL providers (no mocks) — the providers wiring IS the unit
 * under test (per 01-non-negotiables.md § Tests are REAL).
 *
 * Phase/Slice: P00 / P00-S01-T002 — Frontend dependency pack
 *
 * jest-dom matchers are imported directly (single-file scope) to avoid
 * modifying vitest.config.ts setupFiles in this slice.
 */

import '@testing-library/jest-dom/vitest';
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { Providers, queryClient, i18n } from './providers';

// ---------------------------------------------------------------------------
// Test 1 — mount-smoke
// Renders a child probe and verifies it is in the DOM.
// Confirms BrowserRouter + QueryClientProvider + I18nextProvider all mount.
// ---------------------------------------------------------------------------

describe('Providers', () => {
  it('mount-smoke: children render inside <Providers> without error', () => {
    render(
      <Providers>
        <div data-testid="probe">ok</div>
      </Providers>
    );
    expect(screen.getByTestId('probe')).toBeInTheDocument();
  });

  // -------------------------------------------------------------------------
  // Test 2 — query-client-shared
  // Two separate components rendered inside one Providers tree both receive
  // the same module-level queryClient singleton via useQueryClient().
  // -------------------------------------------------------------------------

  it('query-client-shared: useQueryClient() returns the module-level singleton', () => {
    let capturedClient: ReturnType<typeof useQueryClient> | null = null;

    function Inspector(): null {
      capturedClient = useQueryClient();
      return null;
    }

    render(
      <Providers>
        <Inspector />
      </Providers>
    );

    expect(capturedClient).toBe(queryClient);
    expect(queryClient.getDefaultOptions().queries?.staleTime).toBe(60_000);
  });

  // -------------------------------------------------------------------------
  // Test 3 — i18n-ready
  // Verifies that i18next.isInitialized is true after the init() promise
  // resolves. Since init() is synchronous when no async backend is used
  // (empty resources object), isInitialized should be true immediately after
  // mount. Also checks useTranslation() does not throw inside Providers.
  // -------------------------------------------------------------------------

  it('i18n-ready: i18n.isInitialized is true and useTranslation works', () => {
    let initialized = false;

    function I18nProbe(): React.JSX.Element {
      const { i18n: localI18n } = useTranslation();
      initialized = localI18n.isInitialized;
      return <span data-testid="i18n-probe">{String(initialized)}</span>;
    }

    render(
      <Providers>
        <I18nProbe />
      </Providers>
    );

    expect(screen.getByTestId('i18n-probe')).toBeInTheDocument();
    expect(i18n.isInitialized).toBe(true);
  });
});
