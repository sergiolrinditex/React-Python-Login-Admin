# Official Docs Note: P00-S01-T002 Frontend Libs Verification

**Date**: 2026-05-11
**Task**: P00-S01-T002 — Frontend dependency pack
**Researcher**: official-docs-researcher
**Sources**: npm registry (`https://registry.npmjs.org/<pkg>/latest`) + Context7 /remix-run/react-router + Context7 /react-hook-form/resolvers
**Base stack (from T001 cache)**: React 19.2.6 · Vite 8.0.11 · Vitest 4.1.5 · TS 6.0.3 · @vitejs/plugin-react 6.0.1 · Node 25.9.0

---

## Verified library versions and peerDep compatibility

### 1. react-router-dom

| Field | Value |
|---|---|
| Latest stable | **7.15.0** |
| dist-tag `latest` | 7.15.0 |
| peerDependencies | `react >=18`, `react-dom >=18` |
| React 19.2 compatible | YES — `>=18` covers 19.x |
| BrowserRouter status | **FULLY SUPPORTED** in v7 "Declarative mode" |
| Import path | `import { BrowserRouter } from 'react-router-dom'` — still correct; v7 re-exports from `react-router` but the `react-router-dom` package is unchanged as the install target |
| Breaking change note | v7 merged Remix + React Router. `<BrowserRouter>` is "Declarative mode", not deprecated. Data router (`createBrowserRouter`) is a separate "Data mode". The task pack uses `<BrowserRouter>` — no issue. |
| Discrepancy | None |

### 2. @tanstack/react-query

| Field | Value |
|---|---|
| Latest stable | **5.100.9** |
| peerDependencies | `react: ^18 \|\| ^19` |
| React 19.2 compatible | YES |
| QueryClient / QueryClientProvider API | Unchanged from v5 baseline. `staleTime`, `retry` in `defaultOptions.queries` — same API. |
| Discrepancy | None |

### 3. react-hook-form

| Field | Value |
|---|---|
| Latest stable | **7.75.0** |
| peerDependencies | `react: ^16.8.0 \|\| ^17 \|\| ^18 \|\| ^19` |
| React 19.2 compatible | YES — explicit ^19 peer |
| Discrepancy | None |

### 4. zod

| Field | Value |
|---|---|
| Latest stable (dist-tag `latest`) | **4.4.3** — THIS IS ZOD 4, NOT ZOD 3 |
| Zod 4 stable | YES — `latest` tag points to 4.4.3 |
| peerDependencies | None declared |
| Breaking change vs Zod 3 | Zod 4 is a major rewrite. For greenfield projects `import { z } from 'zod'` works and points to Zod 4 API. Zod 3 schema code still importable via `import { z } from 'zod/v3'` shim (backward compat). |
| Import for Zod 4 | `import { z } from 'zod'` (default, Zod 4) |
| Import for Zod 3 compat | `import { z } from 'zod/v3'` (shim layer) |
| Relevance for T002 | T002 installs zod but does NOT use schemas in providers.tsx. Actual schema definitions come in auth/form slices. Developer should install Zod 4 (`zod@^4.4.3`) — greenfield project should use the latest major. |
| IMPORTANT — Zod 4 is a greenfield shift | Task pack says "latest stable; if Zod 4 stable, prefer it." Zod 4 IS stable. Use `zod@^4.4.3`. |
| Discrepancy | Minor advisory: task pack left version as placeholder. Confirm Zod 4 is intended. No incompatibility risk — @hookform/resolvers 5.x supports Zod 4 explicitly (see §5). |

### 5. @hookform/resolvers

| Field | Value |
|---|---|
| Latest stable | **5.2.2** |
| peerDependencies | `react-hook-form: ^7.55.0` |
| react-hook-form 7.75.0 satisfies `^7.55.0` | YES |
| Zod 4 support | **YES** — `zodResolver` explicitly supports both Zod 3 and Zod 4. Import for Zod 4: `import { z } from 'zod'` (or `'zod/v4'`). No resolver API change needed. |
| React 19.2 compatible | YES (peerDep via react-hook-form) |
| Discrepancy | None |

### 6. i18next

| Field | Value |
|---|---|
| Latest stable | **26.0.10** |
| peerDependencies | `typescript: ^5 \|\| ^6` (optional) |
| TS 6.0.3 compatible | YES — optional peer `^5 \|\| ^6` |
| React 19 relevance | i18next is framework-agnostic; no React peer |
| Discrepancy | None |

### 7. react-i18next

| Field | Value |
|---|---|
| Latest stable | **17.0.7** |
| peerDependencies | `i18next: >= 26.0.10`, `react: >= 16.8.0`, `typescript: ^5 \|\| ^6` (optional) |
| i18next 26.0.10 satisfies `>= 26.0.10` | YES — exactly at minimum, which satisfies `>=` |
| React 19.2 compatible | YES — `react: >= 16.8.0` covers 19.x |
| TS 6.0.3 compatible | YES |
| Discrepancy | None |

### 8. i18next-browser-languagedetector

| Field | Value |
|---|---|
| Latest stable | **8.2.1** |
| peerDependencies | None declared in package.json |
| i18next 26.0.10 compatible | YES — no formal peer constraint; works as a plugin attached to the i18next instance |
| React 19.2 relevance | Not React-specific |
| Discrepancy | None |

### 9. @testing-library/jest-dom

| Field | Value |
|---|---|
| Latest stable | **6.9.1** |
| peerDependencies | None declared (works with any test runner) |
| Vitest 4.1.5 import path | `import '@testing-library/jest-dom/vitest'` — CONFIRMED available |
| React 19.2 compatible | YES — DOM matchers are not React-version-specific |
| Cache note | T001 confirmed 16.3.2 for @testing-library/react; jest-dom is a separate package |
| Discrepancy | None |

### 10. jsdom

| Field | Value |
|---|---|
| Latest stable | **29.1.1** |
| peerDependencies | `canvas: ^3.0.0` (optional — only needed for Canvas API support) |
| Node.js engine requirement | `^20.19.0 \|\| ^22.13.0 \|\| >=24.0.0` |
| Current Node version | **25.9.0** — satisfies `>=24.0.0` |
| Vitest 4.1.5 compatible | YES — Vitest 4 ships with jsdom 25+ support; 29.x is the latest |
| Discrepancy | None |

---

## Summary table — recommended versions for package.json

```json
{
  "dependencies": {
    "react-router-dom": "^7.15.0",
    "@tanstack/react-query": "^5.100.9",
    "react-hook-form": "^7.75.0",
    "zod": "^4.4.3",
    "@hookform/resolvers": "^5.2.2",
    "i18next": "^26.0.10",
    "react-i18next": "^17.0.7",
    "i18next-browser-languagedetector": "^8.2.1"
  },
  "devDependencies": {
    "@testing-library/jest-dom": "^6.9.1"
  }
}
```

Note: `jsdom` is already in devDependencies from T001 as Vitest environment. Do not re-add.

---

## Peer risk assessment

| Library | React 19.2 safe | Vite 8 safe | Vitest 4 safe | Node 25.9 safe |
|---|---|---|---|---|
| react-router-dom 7.15.0 | YES | YES (no Vite peer) | YES | YES |
| @tanstack/react-query 5.100.9 | YES | YES | YES | YES |
| react-hook-form 7.75.0 | YES | YES | YES | YES |
| zod 4.4.3 | YES | YES | YES | YES |
| @hookform/resolvers 5.2.2 | YES | YES | YES | YES |
| i18next 26.0.10 | YES | YES | YES | YES |
| react-i18next 17.0.7 | YES | YES | YES | YES |
| i18next-browser-languagedetector 8.2.1 | YES | YES | YES | YES |
| @testing-library/jest-dom 6.9.1 | YES | YES | YES (vitest import) | YES |
| jsdom 29.1.1 (already installed) | YES | YES | YES | YES (>=24) |

No peerDep conflicts detected. No library rejects React 19.2, Vite 8, Vitest 4, or Node 25.9.

---

## Advisory notes for developer (non-blocking)

1. **Zod 4 is now stable (4.4.3)** — Greenfield project should install `zod@^4.4.3`. Import schemas with `import { z } from 'zod'`. The `@hookform/resolvers` `zodResolver` works with Zod 4 without any code change. Do NOT install `zod@^3.x` on a new project.

2. **react-router-dom v7 import path** — Continue using `import { BrowserRouter, ... } from 'react-router-dom'` (the package re-exports from `react-router`). The `providers.tsx` can also use `import { BrowserRouter } from 'react-router'` directly if desired, since both resolve identically. Either form is correct; choose one and be consistent.

3. **@testing-library/jest-dom Vitest setup** — In `vitest.config.ts` (already set up in T001), add `setupFiles: ['@testing-library/jest-dom/vitest']` to enable DOM matchers globally. Alternatively, `import '@testing-library/jest-dom/vitest'` per test file. The global setup approach is recommended.

4. **react-i18next 17.0.7 peer note** — peerDep `i18next >= 26.0.10` is exactly met by `i18next@26.0.10`. If i18next is bumped to a minor (e.g., 26.1.x), that is still compatible.

5. **i18next minimal init in providers.tsx** — Task pack §5.3 calls for an inline minimal `i18next.init(...)` in providers.tsx for T002. This is valid: i18next 26.x `init()` API is unchanged for the basic `{ resources, fallbackLng, lng, interpolation }` options pattern.

---

RESOLVED: 2026-05-11 — All 10 libraries verified against npm registry and official docs. No peerDep conflict with React 19.2.6, Vite 8.0.11, Vitest 4.1.5, TS 6.0.3, Node 25.9.0. Zod 4.4.3 is the current stable — greenfield project should use it. All findings are informational; no source-of-truth change needed. Developer may proceed.
