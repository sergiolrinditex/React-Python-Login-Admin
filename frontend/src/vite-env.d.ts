/**
 * Hilo People — Vite environment type declarations.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Provides:
 *   - import.meta.env types (via vite/client triple-slash reference)
 *   - CSS module side-effect import declarations
 *
 * Key deps: vite ^8.0.12.
 */

/// <reference types="vite/client" />

/** Allow side-effect imports of CSS files (e.g., import './styles/tokens.css') */
declare module "*.css" {
  const content: Record<string, string>;
  export default content;
}
