/**
 * Vite build and dev-server configuration for Hilo People frontend.
 *
 * What: Configures Vite 8 with the React plugin, path alias @→src/,
 * reads the dev-server port from FRONT_PORT env var (default 5173),
 * and proxies `/api/v1` requests to the FastAPI backend during dev so
 * relative URLs from feature data layers (e.g. discoverModels.ts) reach
 * the real uvicorn process at :8000 instead of falling back to Vite's
 * SPA 404. In production the reverse proxy (nginx) handles this routing,
 * so the proxy block is dev-tooling only and never enters the bundle.
 *
 * Vitest config lives in vitest.config.ts (created P00-S01-T002) — Vite
 * does NOT duplicate the test block here to avoid double-config issues.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system.
 *              `server.proxy` added in P00-S02-T007 debugger fix #2 to unblock
 *              the wizard human-verify flow against FU-X1 (was reaching Vite
 *              instead of uvicorn).
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
 *
 * Backend proxy resolution:
 *   BACKEND_URL env var (default http://127.0.0.1:8000). Allows overriding
 *   the dev-proxy target without editing the file (e.g. when running the
 *   backend on a different host/port for QA). `changeOrigin: true` rewrites
 *   the `Host` header so FastAPI/CORS sees the backend origin.
 */

import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

const BACKEND_URL = process.env.BACKEND_URL || 'http://127.0.0.1:8000';

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
    proxy: {
      '/api/v1': {
        target: BACKEND_URL,
        changeOrigin: true,
      },
    },
  },
});
