/**
 * Smoke test for AppProviders.
 *
 * What: Renders the AppProviders tree and asserts that both QueryClient
 * (TanStack Query) and i18n (react-i18next) are accessible from a child
 * component without throwing. Validates the bootstrap language is 'es'.
 *
 * Phase/Slice: P00 / P00-S01-T002 — Frontend dependency pack
 *
 * Dependencies:
 *   - vitest 4.1.5 + jsdom env (configured in vitest.config.ts)
 *   - @testing-library/react 16.3.2
 *   - @tanstack/react-query 5.100.9 (useQueryClient)
 *   - react-i18next 17.0.7 (useTranslation)
 *
 * Test is intentionally minimal — it only verifies provider wiring, not
 * application behaviour. No mocks; real QueryClient and real i18next instance.
 */

import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { useQueryClient } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';
import { AppProviders } from './providers';

/**
 * Probe component — reads from both providers and renders their values
 * into the DOM so the test can assert on them.
 */
function Probe() {
  const qc = useQueryClient();
  const { i18n } = useTranslation();
  return (
    <div>
      <span data-testid="qc">{qc ? 'qc-ok' : 'qc-null'}</span>
      <span data-testid="i18n">{i18n?.language ?? 'no-lng'}</span>
    </div>
  );
}

describe('AppProviders smoke', () => {
  it('mounts and exposes QueryClient + i18n to children', () => {
    const { getByTestId } = render(
      <AppProviders>
        <Probe />
      </AppProviders>,
    );

    // TanStack Query context is reachable.
    expect(getByTestId('qc').textContent).toBe('qc-ok');

    // i18next is initialized with fallback language 'es' per instrucciones.md §3.3.
    expect(getByTestId('i18n').textContent).toBe('es');
  });
});
