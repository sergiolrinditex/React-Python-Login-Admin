/**
 * Vitest global test setup.
 *
 * What: Registers @testing-library/jest-dom custom matchers with Vitest so
 * assertions like `toBeInTheDocument()`, `toHaveStyle()`, etc. are available
 * in every test file without individual imports. Also registers afterEach
 * cleanup so the DOM is reset between tests (required when globals: false).
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Dependencies:
 *   - @testing-library/jest-dom 6.9.1
 *   - @testing-library/react 16.3.2 (cleanup)
 *
 * Official doc note (resolved):
 *   Must use `@testing-library/jest-dom/vitest` (NOT the legacy v5 form
 *   `@testing-library/jest-dom/extend-expect`). Verified in:
 *   orchestrator-state/memory/official-doc-notes/P00-S01-T004-testing-library-vitest-setup.md
 */

import '@testing-library/jest-dom/vitest';
import { afterEach } from 'vitest';
import { cleanup } from '@testing-library/react';

// Ensure DOM is cleaned up after each test so tests don't interfere.
// @testing-library/react auto-cleans only when globals: true; since this
// project uses globals: false, we register cleanup explicitly.
afterEach(() => {
  cleanup();
});
