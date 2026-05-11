/**
 * Hilo People — Vitest global setup file.
 *
 * Slice: P00-S01-T002 (WRITE_SET_DRIFT: companion to vitest.config.ts extension).
 * Imports @testing-library/jest-dom to extend Vitest's `expect` with DOM matchers
 * (e.g., toBeInTheDocument, toHaveTextContent) used in smoke/component tests.
 *
 * Key deps: @testing-library/jest-dom ^6.9.1.
 */

import "@testing-library/jest-dom";
