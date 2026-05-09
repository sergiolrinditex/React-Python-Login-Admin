/**
 * Vite build and dev-server configuration for Hilo People frontend.
 *
 * What: Configures Vite 8 with the React plugin, path alias @→src/,
 * and reads the dev-server port from FRONT_PORT env var (default 5173).
 * Vitest config lives in vitest.config.ts (created P00-S01-T002) — Vite
 * does NOT duplicate the test block here to avoid double-config issues.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Dependencies:
 *   - @vitejs/plugin-react 6.0.1
 *   - vite 8.0.11
 *   - typescript 6.0.3 (referenced via tsconfig.json)
 *
 * Port resolution:
 *   FRONT_PORT env var → used by scripts/dev-restart.sh and .env.
 *   .env sets FRONT_PORT=5174 to avoid collision with a parallel Vite instance
 *   on the default 5173. The Number() cast returns NaN for unset strings, so
 *   the fallback 5173 kicks in only when FRONT_PORT is absent.
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
