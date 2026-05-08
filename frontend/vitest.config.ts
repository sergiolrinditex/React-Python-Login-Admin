/**
 * Vitest configuration for the Hilo People frontend.
 *
 * What: Configures Vitest to run in jsdom environment so React components
 * can be mounted via @testing-library/react without "document is not defined"
 * errors (which occur with the default 'node' environment).
 *
 * Phase/Slice: P00 / P00-S01-T002 — Frontend dependency pack
 *
 * Notes:
 *   - `globals: false` — tests must import describe/it/expect from 'vitest'.
 *   - `environment: 'jsdom'` — required for React DOM mounting in Vitest 4.
 *   - This file supersedes any vitest configuration in vite.config.ts (none
 *     exists yet; vite.config.ts is added in P00-S01-T004 design tokens).
 */

import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    globals: false,
  },
});
