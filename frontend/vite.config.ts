/**
 * Hilo People — Vite configuration.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *   Write set extension §B (human-approved in planner pack): Vite runtime config
 *   required for `npm run build` and `npm run dev` to succeed.
 *
 * Responsibility:
 *   - Register @vitejs/plugin-react (SWC-based JSX transform for React 19).
 *   - Declare path alias @/ → frontend/src/ (consumed by all downstream tasks).
 *   - Set dev server to port 5173 / host 0.0.0.0 (Docker-safe; STACK_PROFILE §frontend.dev_cmd).
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
