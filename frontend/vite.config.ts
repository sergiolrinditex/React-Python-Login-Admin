/**
 * Vite build and dev-server configuration for Hilo People frontend.
 *
 * What: Configures Vite 8 with the React plugin (Oxc transforms),
 * a path alias @→src/, and reads FRONT_PORT for the dev-server port.
 * Vitest configuration lives in vitest.config.ts to avoid double-config.
 *
 * Phase/Slice: P00 / P00-S01-T001 (scaffold) — created in T002 as T001
 * scaffold completion (T001 only committed package.json; vite.config.ts
 * was declared in the TECHNICAL_GUIDE §4 structure but not written).
 *
 * Dependencies:
 *   - @vitejs/plugin-react 6.0.1 (peerDeps: vite ^8)
 *   - vite 8.x
 *   - typescript 6.0 (referenced via tsconfig.json)
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, 'src'),
    },
  },
  server: {
    host: '0.0.0.0',
    port: Number(process.env.FRONT_PORT) || 5173,
  },
});
