/**
 * Hilo People — Vitest configuration.
 *
 * Slice: P00-S01-T002 (WRITE_SET_DRIFT accepted: without this file, `vitest --run`
 * cannot resolve the React JSX transform, the jsdom environment, or TSX source files.)
 * Updated in P00-S01-T004: import from vitest/config (not vite) to avoid Plugin<any>
 * type incompatibility between Vite 8 (rolldown) and Vitest 3 (rollup) internals.
 *
 * Responsibilities:
 *   - Configure jsdom as the test environment (browser-like APIs for React rendering).
 *   - Register @vitejs/plugin-react so Vitest can compile TSX via Babel/SWC.
 *   - Set up @testing-library/jest-dom matchers globally via setupFiles.
 *   - Enable globals (describe/it/expect without imports) for cleaner test files.
 *
 * Key deps: vitest ^3.0.0, @vitejs/plugin-react ^6.0.1, jsdom ^25.0.0.
 */

import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./vitest.setup.ts"],
  },
});
