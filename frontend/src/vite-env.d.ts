/**
 * Vite environment type declarations.
 *
 * What: Extends TypeScript with Vite-specific types so:
 *   - `import.meta.env` is typed correctly.
 *   - Side-effect CSS imports (`import './styles.css'`) are allowed without
 *     TypeScript errors (TS2882 "Cannot find module for side-effect import").
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: Vite 8 official template pattern.
 */

/// <reference types="vite/client" />
