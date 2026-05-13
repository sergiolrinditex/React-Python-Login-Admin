/**
 * Hilo People — Vite configuration.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *   Write set extension §B (human-approved in planner pack): Vite runtime config
 *   required for `npm run build` and `npm run dev` to succeed.
 *
 * Updated: P01-S03-T002 — cross-origin / reverse-proxy topology (ADR-002).
 *   Strategy A: vite dev server proxies /api → http://localhost:8000.
 *   The browser sees a SINGLE origin (:5173) for HTML/assets/API — no cross-origin
 *   XHR, no CORS preflight, SameSite=Lax cookie works natively.
 *   Matches prod topology (Nginx proxies /api → backend container).
 *   Ref: TECHNICAL_GUIDE §11.4 + ADR-002.
 *
 * Responsibility:
 *   - Register @vitejs/plugin-react (SWC-based JSX transform for React 19).
 *   - Declare path alias @/ → frontend/src/ (consumed by all downstream tasks).
 *   - Set dev server to port 5173 / host 0.0.0.0 (Docker-safe; STACK_PROFILE §frontend.dev_cmd).
 *   - Proxy /api → http://localhost:8000 in dev (ADR-002, P01-S03-T002).
 *   - Build output to dist/ (default; referenced by frontend/Dockerfile COPY).
 *
 * Key deps: vite ^8.0.12, @vitejs/plugin-react ^6.0.1.
 *
 * Q2 decision (§H): @/ alias IS wired here — conventional, low-cost, and downstream
 *   tasks (P03-S01-T001+) will use it. Declared in handoff.
 * Q1 decision (§H): tsconfig.node.json IS created — required for tsc -b composite builds
 *   when vite.config.ts is excluded from main tsconfig include. See tsconfig.node.json.
 */

import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import { fileURLToPath, URL } from "node:url";

export default defineConfig({
  plugins: [react()],

  resolve: {
    alias: {
      "@": fileURLToPath(new URL("./src", import.meta.url)),
    },
  },

  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: false,

    /**
     * Reverse-proxy all /api/** requests to the uvicorn backend at :8000.
     *
     * ADR-002 (P01-S03-T002): Strategy A — same-origin in dev (mirrors prod nginx).
     * The browser only knows :5173; no cross-origin XHR, no CORS preflight needed.
     *
     * changeOrigin: false — backend receives the original Host (:5173) which is fine
     *   for dev. No virtual-host routing on the backend relies on Host.
     * secure: false — backend is plain http in dev; no TLS cert to validate.
     *
     * Set-Cookie headers from the backend (HttpOnly; Secure; SameSite=Lax;
     * Path=/api/v1/auth) are forwarded untouched by vite/http-proxy (default
     * behavior; no cookieDomainRewrite or cookiePathRewrite configured).
     * Cookie is bound to :5173 (the browser's perceived origin).
     *
     * X-Request-ID and Authorization headers are forwarded unmodified.
     *
     * SSE / chunked-transfer (POST /api/v1/chat/conversations/{id}/stream — P02-S04):
     * http-proxy preserves chunked transfer by default. Explicit verification
     * required in P02-S04 slice; documented in handoff P01-S03-T002 risk K.4.
     *
     * WARNING: Do NOT set VITE_API_BASE_URL=http://localhost:8000 in dev.
     * That re-introduces cross-origin XHR. Keep VITE_API_BASE_URL="" (empty).
     * See frontend/.env.example and ADR-002.
     */
    proxy: {
      "/api": {
        target: "http://localhost:8000",
        changeOrigin: false,
        secure: false,
      },
    },
  },

  preview: {
    host: "0.0.0.0",
    port: 4173,
  },

  build: {
    outDir: "dist",
    sourcemap: false, /* No source maps in production builds (security) */
    target: "es2022",
  },
});
