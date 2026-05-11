# Official Doc Note: P00-S01-T004 — Frontend stack for design tokens + router scaffold

DATE: 2026-05-11
TASK_ID: P00-S01-T004
TOPIC: Vite 8 + React 19 + TypeScript 6 + React Router v7 — config patterns and discrepancies

---

## SOURCE_URL

- https://github.com/vitejs/vite/blob/v8.0.10/packages/create-vite/template-react-ts/README.md (official Vite template doc)
- https://github.com/vitejs/vite/blob/v8.0.10/docs/plugins/index.md (official plugin list)
- https://github.com/vitejs/vite/blob/v8.0.10/docs/guide/features.md (tsconfig types)
- https://github.com/vitejs/vite/blob/v8.0.10/docs/guide/migration.md (SWC migration)
- https://context7.com/vitejs/vite/llms.txt (Vite config reference)
- https://github.com/remix-run/react-router/blob/main/docs/api/data-routers/RouterProvider.md
- https://context7.com/remix-run/react-router/llms.txt
- https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties (CSS custom properties — stable)

---

## 1. @vitejs/plugin-react vs @vitejs/plugin-react-swc — DISCREPANCY

### Finding
The task pack §D states:
> `@vitejs/plugin-react-swc` — used by router.tsx [as the TypeScript toolchain plugin]

`frontend/package.json` (current, installed, human-confirmed 2026-05-11) contains:
```json
"@vitejs/plugin-react": "^6.0.1"
```
NOT `@vitejs/plugin-react-swc`.

### Official Vite 8 docs (v8.0.10 README + plugins/index.md)
Two official plugins exist:
- `@vitejs/plugin-react` — React Fast Refresh via **Oxc Transformer** (current default since Vite 6+, replaces Babel with Oxc).
- `@vitejs/plugin-react-swc` — uses SWC during development for SWC plugin usage; SWC+Oxc during production builds. Recommended for large projects needing custom SWC plugins.

Both are official and valid. For projects not requiring custom SWC plugins, `@vitejs/plugin-react` (Oxc) is the standard default template choice.

### Impact
- `frontend/package.json` uses `@vitejs/plugin-react@^6.0.1` — this is CORRECT and consistent with the Vite 8 React+TS template default.
- Task pack §D text reference to `-swc` is STALE/WRONG. The developer must use `@vitejs/plugin-react` (already in package.json), not `@vitejs/plugin-react-swc`.
- `vite.config.ts` import must be: `import react from '@vitejs/plugin-react'` — NOT `@vitejs/plugin-react-swc`.
- `@vitejs/plugin-react-swc` is NOT installed in `frontend/package.json` and must NOT be added unless there is an explicit SWC plugin requirement (none declared in source-of-truth).

### Status
DISCREPANCY — developer must use `@vitejs/plugin-react`, not `-swc`. The task pack §D text is wrong.

---

## 2. vite.config.ts canonical shape for Vite 8 + React 19

### Official pattern (Vite 8, react-ts template)
```ts
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,        // default; set explicitly for clarity
    host: '0.0.0.0',  // matches dev_cmd in STACK_PROFILE
    strictPort: false, // default; set true only if port collision must hard-fail
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
```

Key points:
- `defineConfig` is the canonical helper.
- `server.host: '0.0.0.0'` required for docker / LAN access (matches STACK_PROFILE `dev_cmd`).
- `resolve.alias` with `@` → `src/` is conventional and recommended for this project (task pack §H Q2: planner recommends YES).
- `server.port` default is 5173 for Vite 8. Making it explicit prevents confusion.
- No `strictPort` override needed for dev; default false is fine.

### Status
RESOLVED: confirmed — pattern is correct per official Vite 8 docs.

---

## 3. tsconfig.json — official Vite 8 recommended compilerOptions

### Official pattern (Vite docs, v8.0.10)
```json
{
  "compilerOptions": {
    "target": "ES2020",
    "useDefineForClassFields": true,
    "module": "ESNext",
    "lib": ["ES2020", "DOM", "DOM.Iterable"],
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowImportingTsExtensions": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "noEmit": true,
    "jsx": "react-jsx",
    "strict": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "types": ["vite/client"]
  },
  "include": ["src"]
}
```

Key confirmed facts:
- `moduleResolution: "bundler"` — correct for Vite 8 + TS6 (replaces `"node16"`/`"nodenext"` for bundler-mode).
- `jsx: "react-jsx"` — correct for React 17+ automatic runtime (no `import React from 'react'` needed).
- `target: "ES2020"` — Vite 8 official template default. Task pack §B suggests ES2022; both are valid for modern browsers; ES2020 is the template default, ES2022 is acceptable (top-level await, etc.).
- `noEmit: true` — correct when Vite handles transpilation; tsc runs only for type-checking (`tsc -b` in build script).
- `allowImportingTsExtensions: true` — correct when `noEmit: true`; allows `.tsx` imports without `.js` extensions.
- `verbatimModuleSyntax` — NOT listed in the Vite 8 official template. It is a TypeScript 5.0+ option for stricter `import type` enforcement; compatible but NOT required. Developer may add it; it is NOT breaking.
- `types: ["vite/client"]` — adds `ImportMeta.env` types. Recommended.

### Status
RESOLVED: confirmed — `moduleResolution: "bundler"` + `jsx: "react-jsx"` + `strict: true` + `noEmit: true` are the canonical combination. `verbatimModuleSyntax` is optional (not in Vite template but compatible with TS6).

---

## 4. tsconfig.node.json — needed or not?

### Official pattern
Vite 8 react-ts template ships TWO tsconfig files:
- `tsconfig.json` — for app source code (`"include": ["src"]`)
- `tsconfig.node.json` — for Vite config files themselves (`"include": ["vite.config.ts"]`) with different settings (`"module": "ESNext"`, `"moduleResolution": "bundler"`, `allowSyntheticDefaultImports`, etc.)

The `tsconfig.json` references it via `"references": [{ "path": "./tsconfig.node.json" }]`.

### Status
RESOLVED: `tsconfig.node.json` IS needed in the Vite 8 react-ts template. Task pack §B marks it as "conditional: add if `vite.config.ts` imports `defineConfig` and tsc complains" — this is a safe conservative approach, but the official template always includes it. Developer should create it to match the official template exactly and avoid TS project reference errors.

Canonical `tsconfig.node.json`:
```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2023"],
    "module": "ESNext",
    "skipLibCheck": true,
    "moduleResolution": "bundler",
    "allowSyntheticDefaultImports": true,
    "strict": true
  },
  "include": ["vite.config.ts"]
}
```

And `tsconfig.json` should reference it:
```json
{
  "references": [{ "path": "./tsconfig.node.json" }],
  "compilerOptions": { ... }
}
```

---

## 5. React Router v7 — RouterProvider vs BrowserRouter + import path

### Official React Router v7 docs
Canonical setup for data router (library mode, SPA):
```tsx
import { createBrowserRouter } from "react-router";
import { RouterProvider } from "react-router/dom";
```

Key confirmed facts:
- `createBrowserRouter` exports from `"react-router"` (main package).
- `RouterProvider` for browser environments should import from `"react-router/dom"` (DOM-specific subpath) to get automatic `ReactDOM.flushSync` wiring.
- `BrowserRouter` is the legacy declarative API — still available in v7 but `createBrowserRouter` + `RouterProvider` is the **canonical data router** recommended approach.
- Lazy routes use `lazy: () => import('./module')` pattern (no `React.lazy`/`Suspense` needed at route level — React Router handles it internally).

### Task pack §A states
> Router scaffold at `frontend/src/app/router.tsx` exporting a `<AppRouter>` component that mounts at minimum the `/showcase` route under `BrowserRouter`

### Assessment
Using `BrowserRouter` for the T004 scaffold is acceptable since:
1. Only `/showcase` route is needed now (no loaders/actions/data features yet).
2. The task pack explicitly approves `BrowserRouter` for this slice.
3. Migration to `RouterProvider` + `createBrowserRouter` can happen in P03 when real routes with loaders land.

However, if the developer chooses `createBrowserRouter` + `RouterProvider` (the canonical modern approach), it is also fully valid and preferred.

### Import path for T004
- If using `BrowserRouter`: `import { BrowserRouter, Routes, Route } from 'react-router'`
- If using `RouterProvider`: `import { createBrowserRouter } from 'react-router'` + `import { RouterProvider } from 'react-router/dom'`
- `react-router-dom` package exists as a thin shim in v7 but import from `"react-router"` is canonical.

### Task pack §D discrepancy
§D states: `react-router-dom` ← used by `router.tsx`

This is stale. React Router v7 canonical import is from `"react-router"` (not `"react-router-dom"`). The T002 note in MEMORY.md confirmed this discrepancy already (note: `frontend-deps-T002-react-router-2026-05-11.md`). Confirm `package.json` has `react-router` installed (check T002 deliverables).

### Status
DISCREPANCY — task pack §D says `react-router-dom`; v7 canonical is `import from 'react-router'`. Developer must use `from 'react-router'` imports (and `from 'react-router/dom'` for `RouterProvider`). Check T002 installed `react-router` not `react-router-dom`.

---

## 6. CSS custom properties (design tokens) — W3C/MDN status in 2026

### Official source
CSS custom properties (`--token: value`) defined on `:root` and consumed via `var(--token)` remain the W3C-recommended approach. No breaking changes in 2026. CSS Custom Properties Level 1 is a full W3C Recommendation. Level 2 (typed custom properties via `@property`) is Candidate Recommendation — NOT required for T004.

The `design_tokens_v1` enforcer is an internal project tool (not a third-party package). Its rules are declared in `.claude/enforcers/design_tokens_v1/RULES.md` — developer should read it before writing `scripts/check-design-tokens.sh`.

### Status
RESOLVED: confirmed — CSS custom properties on `:root` is the correct W3C-stable approach for 2026. No changes needed.

---

## 7. Accessibility — WCAG AA / labels / contrast / keyboard nav in 2026

### Official status
WCAG 2.1 Level AA remains the active compliance baseline (WCAG 2.2 published October 2023 adds 9 new criteria — notably `Focus Not Obscured`, `Dragging Movements`, `Target Size (Minimum)` — but is backward compatible with 2.1 AA). No regression in 2026: the 44×44px tap target rule, `aria-live`, keyboard nav, and contrast 4.5:1 ratio rules are unchanged and still required.

### Status
RESOLVED: confirmed — WCAG 2.1 AA minimum (WCAG 2.2 AA preferred). Rules in `01-non-negotiables.md` are current and correct.

---

## Summary table

| Topic | Status | Action for developer |
|---|---|---|
| `@vitejs/plugin-react` (not `-swc`) | DISCREPANCY (task pack §D wrong) | Use `@vitejs/plugin-react` in vite.config.ts — it's already in package.json |
| `vite.config.ts` shape (port, host, alias) | RESOLVED: confirmed | Pattern confirmed; use `host: '0.0.0.0'`, default port 5173 |
| `tsconfig.json` (moduleResolution bundler, jsx react-jsx, strict, noEmit) | RESOLVED: confirmed | All correct per official Vite 8 docs |
| `tsconfig.node.json` needed | RESOLVED: YES, include it | Create per canonical template |
| React Router v7 import path | DISCREPANCY (task pack §D wrong) | Import from `"react-router"` not `"react-router-dom"` |
| CSS custom properties on `:root` | RESOLVED: confirmed | W3C-stable, no changes needed |
| WCAG AA accessibility rules | RESOLVED: confirmed | Rules unchanged, 2.1 AA minimum |

---

RESOLVED: 2026-05-11 main-orchestrator — Developer reconciled implicitly: code uses `@vitejs/plugin-react` (NOT -swc) in vite.config.ts:23, and `import { BrowserRouter, ... } from "react-router"` (v7 canonical, NOT react-router-dom) in src/app/router.tsx:25. Verified against frontend/package.json: react-router@^7.15.0 and @vitejs/plugin-react@^6.0.1 installed. The discrepancies were in task pack §D (planner doc reference), not in product code. Code is correct; task pack §D will be cleaned in a future planner refresh. No FU needed.
