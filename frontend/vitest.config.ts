/**
 * Vitest configuration for the Hilo People frontend.
 *
 * What: Configures Vitest 4 with jsdom environment so React components
 * render correctly via @testing-library/react without DOM errors.
 * Kept separate from vite.config.ts to avoid double-config issues.
 *
 * Phase/Slice: P00 / P00-S01-T002 — Frontend dependency pack
 *
 * Notes:
 *   - globals: false → tests must import describe/it/expect from 'vitest'.
 *   - environment: 'jsdom' → required for React DOM mounting in Vitest 4.
 *   - No setupFiles here; providers.test.tsx imports jest-dom matchers
 *     directly using '@testing-library/jest-dom/vitest' (single-file scope,
 *     avoids touching this config in T002).
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
  },
});
