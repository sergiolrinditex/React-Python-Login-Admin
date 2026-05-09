# Official Doc Note: @testing-library/jest-dom v6 — Vitest setup import path

**Task**: P00-S01-T004
**Date**: 2026-05-09
**Severity**: warn-only (developer-actionable, not blocking)

## What internal docs say

The task pack (§9 Test plan) references `@testing-library/jest-dom` for setup files but does not specify the exact import path. PROGRESS.md and T002 handoff verified the package version (6.9.1) but did not record the Vitest-specific import path.

## What official docs say today

Source: https://github.com/testing-library/jest-dom/blob/main/README.md (Context7, 2026-05-09)

For **Vitest** the setup file must use:
```typescript
// vitest-setup.ts (or any name in setupFiles)
import '@testing-library/jest-dom/vitest'
```

NOT the legacy Jest form `import '@testing-library/jest-dom/extend-expect'` (v5 pattern, deprecated in v6).

Official quote: "If you are using vitest, this module will work as-is, but you will need to use a different import in your tests setup file."

For tsconfig.json, add:
```json
{
  "compilerOptions": {
    "types": ["vitest/globals", "@testing-library/jest-dom"]
  },
  "include": ["./vitest-setup.ts"]
}
```

## Suggested resolution for developer

In `frontend/vitest-setup.ts` (or equivalent setupFile):
```typescript
import '@testing-library/jest-dom/vitest'
```

In `vitest.config.ts` (or the test block in `vite.config.ts`):
```typescript
test: {
  environment: 'jsdom',
  setupFiles: ['./vitest-setup.ts'],
  globals: true,
}
```

In `tsconfig.json`:
```json
"types": ["vitest/globals", "@testing-library/jest-dom"]
```

## Additional confirmed patterns (all verified 2026-05-09)

- **Vite 8 entry**: `index.html` at project root with `<script type="module" src="/src/main.tsx">` — canonical, unchanged.
- **vite.config.ts**: `import { defineConfig } from 'vite'` — unchanged in Vite 8.
- **Vitest config**: `import { defineConfig } from 'vitest/config'` — still the canonical import for test-only config. Co-location in `vite.config.ts` via `test:` block also valid; separate `vitest.config.ts` NOT mandatory.
- **React 19 createRoot**: `import { createRoot } from 'react-dom/client'` — canonical, unchanged. React 19.2.0 confirmed.
- **react-router v7 minimal**: `import { createBrowserRouter } from 'react-router'` + `import { RouterProvider } from 'react-router/dom'`. `createBrowserRouter([{ path: '/showcase', element: <ShowcasePage /> }])` is the minimal one-route pattern. `<BrowserRouter>` not deprecated but `createBrowserRouter` is recommended for new code.
- **TS 6 tsconfig fields**: `"moduleResolution": "bundler"`, `"verbatimModuleSyntax": true`, `"jsx": "react-jsx"`, `"isolatedModules": true` — all confirmed. Task pack R6 already lists the correct set.

## Resolution

RESOLVED: Developer must use `import '@testing-library/jest-dom/vitest'` in the Vitest setup file. All other patterns match internal docs exactly. No blocking discrepancy.
