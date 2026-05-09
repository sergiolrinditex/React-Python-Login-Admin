/**
 * Vitest configuration for the Hilo People frontend.
 *
 * What: Configures Vitest to run in jsdom environment so React components
 * can be mounted via @testing-library/react without "document is not defined"
 * errors (which occur with the default 'node' environment).
 *
 * Phase/Slice: P00 / P00-S01-T002 — Frontend dependency pack
 * Updated: P00 / P00-S01-T004 — Design tokens (added setupFiles for jest-dom)
 *
 * Notes:
 *   - `globals: false` — tests must import describe/it/expect from 'vitest'.
 *   - `environment: 'jsdom'` — required for React DOM mounting in Vitest 4.
 *   - `setupFiles` — adds @testing-library/jest-dom matchers for all tests.
 *     Per official-doc-notes/P00-S01-T004-testing-library-vitest-setup.md:
 *     the import must be '@testing-library/jest-dom/vitest' (v6 + Vitest form).
 */

import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    setupFiles: ['./src/test/setup.ts'],
  },
});
