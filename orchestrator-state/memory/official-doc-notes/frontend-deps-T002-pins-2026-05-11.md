# Official Doc Note: Frontend dependency pins — T002
DATE: 2026-05-11
TASK_ID: P00-S01-T002
TOPIC: Verified version pins for all 8 production deps + test deps

## SUMMARY

All 8 frontend libraries from TECHNICAL_GUIDE §2.0 verified against official npm registry and
official docs on 2026-05-11. React 19.2.6 / TypeScript 6.0.3 / Vite 8.0.12 / vitest 3.x compat
confirmed for all packages. One discrepancy (react-router-dom → react-router) filed separately.
One advisory (Zod v4 API changes) documented below. All others: ok.

## SOURCES
- https://registry.npmjs.org/react-router/latest (7.15.0)
- https://registry.npmjs.org/react-router-dom/latest (7.15.0, thin wrapper)
- https://reactrouter.com/start/library/installation
- https://registry.npmjs.org/@tanstack/react-query/latest (5.100.9)
- https://github.com/tanstack/query/blob/main/docs/eslint/stable-query-client.md
- https://registry.npmjs.org/react-hook-form/latest (7.75.0)
- https://registry.npmjs.org/@hookform/resolvers/latest (5.2.2)
- https://github.com/react-hook-form/resolvers — README (zodResolver import path)
- https://registry.npmjs.org/zod/latest (4.x current stable)
- https://zod.dev/v4 (breaking changes v3→v4)
- https://registry.npmjs.org/i18next/latest (26.1.0)
- https://registry.npmjs.org/react-i18next/latest (17.0.7)
- https://registry.npmjs.org/i18next-browser-languagedetector/latest (8.2.1)
- https://registry.npmjs.org/@testing-library/react/latest (16.3.2)
- https://github.com/testing-library/react-testing-library/releases (React 19 added in 16.1.0)
- https://vitest.dev/guide/environment.html

---

## Q1 — react-router-dom / react-router

ANSWER: Current stable is v7 (7.15.0). `react-router-dom` is a thin re-export shim in v7 — the
canonical package name to install is `react-router`. peerDeps: react >=18 (React 19 satisfies).
CITATION: https://reactrouter.com/start/library/installation
BREAKING-NOTES: In v7, `import { BrowserRouter, Outlet } from "react-router-dom"` still works
via the shim but the official package is `react-router`. All source should use `from "react-router"`.
DOM-specific: `RouterProvider` moves to `from "react-router/dom"`.
VERDICT: discrepancy — task pack says install `react-router-dom`; official docs say install `react-router`.
SEE: frontend-deps-T002-react-router-2026-05-11.md

### Recommended package.json entry
```json
"react-router": "^7.15.0"
```

---

## Q2 — @tanstack/react-query

ANSWER: v5.100.9 is current stable. peerDependencies: `"react": "^18 || ^19"` — React 19 fully supported.
CITATION: https://registry.npmjs.org/@tanstack/react-query/latest + tanstack.com/query docs
BREAKING-NOTES: none for this slice. v5 stable has been the line since 2023; v5.51+ confirmed React 19.
VERDICT: ok

### Import paths (confirmed canonical from official docs)
```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
```

### Constructor shape (confirmed from stable-query-client eslint rule doc)
```tsx
// Outside component (module-level) OR via useState lazy init — both correct:
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
    },
  },
});
// --- or inside a Providers component ---
const [queryClient] = useState(() => new QueryClient({ defaultOptions: { queries: { retry: 1 } } }));
```
`new QueryClient({ defaultOptions: { queries: { retry: 1 } } })` is the SUPPORTED constructor shape.
For `providers.tsx`, the recommended pattern for a singleton provider is module-level or `useState` lazy.

### Recommended package.json entry
```json
"@tanstack/react-query": "^5.100.9"
```

---

## Q3 — react-hook-form + @hookform/resolvers + zod

### react-hook-form
ANSWER: v7.75.0 current stable. peerDependencies: `"react": "^16.8.0 || ^17 || ^18 || ^19"` — React 19 fully supported.
CITATION: https://registry.npmjs.org/react-hook-form/latest
BREAKING-NOTES: RHF v8 beta exists (migrate-v7-to-v8.mdx seen) but v7 is current stable release.
Note: in v8 `register` ref behavior changes, but v7 is the current stable line.
VERDICT: ok

### @hookform/resolvers
ANSWER: v5.2.2 current stable. peerDependencies: `"react-hook-form": "^7.55.0"`.
Zod is NOT a peer dependency — it is an optional dependency per resolver type. The package
exports a `./zod` subpath for Zod resolver. README example shows `import { z } from 'zod' // or 'zod/v4'`
confirming v5.2.2 supports BOTH Zod v3 and Zod v4.
CITATION: https://registry.npmjs.org/@hookform/resolvers/latest + GitHub README
VERDICT: ok

### zod
ANSWER: v4 is current stable. Latest point release: ~4.4.3. v3 is NOT the current stable line.
CITATION: https://zod.dev/v4 + https://github.com/colinhacks/zod/releases

BREAKING-NOTES (Zod v3 → v4 — items relevant to this project):
1. `z.string().email()` and similar string format validators are DEPRECATED in v4. They still work
   but will be removed in v5. Preferred v4 form: `z.email()` (top-level function).
2. Error customization: `message`, `invalid_type_error`, `required_error` replaced by unified `error`.
3. Refinements now stored inside schemas (no longer wrapped in ZodEffects), enabling chaining.
4. `import { z } from "zod"` unchanged. `import { z } from "zod/mini"` available for tree-shaking.
5. `@hookform/resolvers` v5.2.2 README shows `from 'zod/v4'` as an alternate import confirming compat.

VERDICT for this slice: ok — install zod v4. Downstream slices (T005, P03-S01-T001+) that write
Zod schemas must use v4 API style (prefer top-level `z.email()` over chained `.email()` deprecated form).

### Recommended package.json entries
```json
"react-hook-form": "^7.75.0",
"@hookform/resolvers": "^5.2.2",
"zod": "^4.4.3"
```

### Import paths (canonical)
```tsx
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
// For T002 providers.tsx: none of these are needed; these are for downstream form slices.
```

---

## Q4 — i18next + react-i18next + i18next-browser-languagedetector

### i18next
ANSWER: v26.1.0 current stable. peerDependencies: `typescript: ^5 || ^6` (optional). No React peer dep.
CITATION: https://registry.npmjs.org/i18next/latest

### react-i18next
ANSWER: v17.0.7 current stable. peerDependencies: `i18next >= 26.0.10`, `react >= 16.8.0`.
React 19.2.6 fully satisfies `>= 16.8.0`.
CITATION: https://registry.npmjs.org/react-i18next/latest

### i18next-browser-languagedetector
ANSWER: v8.2.1 current stable. No peerDependencies.
Package name is CONFIRMED: `i18next-browser-languagedetector` (no extra 's', no typo).
CITATION: https://registry.npmjs.org/i18next-browser-languagedetector/latest
VERDICT: ok — package name matches task pack exactly.

### I18nextProvider import path (confirmed)
```tsx
import { I18nextProvider } from "react-i18next";
// Usage:
<I18nextProvider i18n={i18n}>...</I18nextProvider>
```

### Minimal i18n instance without resources (T002 requirement)
i18next CAN be initialized without resources — simply omit the `resources` key and the `backend` plugin.
T002 only needs a minimal init so providers.tsx can mount `I18nextProvider`. T005 will supply resources.
```ts
import i18n from "i18next";
import { initReactI18next } from "react-i18next";

i18n
  .use(initReactI18next)
  .init({
    lng: "es",           // T002 default; T005 wires full detection
    fallbackLng: "es",
    resources: {},       // empty — T005 fills these
    interpolation: { escapeValue: false },
  });

export default i18n;
```
This is valid. i18next supports empty resources; `t("key")` returns the key string (correct behavior for T002).
Do NOT `.use(LanguageDetector)` in providers.tsx for T002 — the browser language detector reads `window.navigator`
which does NOT crash in jsdom (jsdom provides `window.navigator.language`), BUT the detector is browser-only and
the task pack decision is to wire it in T005. Safe to omit from providers.tsx.

### vitest / Node jsdom safety for i18next-browser-languagedetector
- The browser language detector reads `window.navigator.language`, `localStorage`, cookies, etc.
- Under `jsdom` environment these are all available (jsdom provides a mock `window`).
- Under `node` environment (no jsdom), accessing `window` would throw. If providers.tsx is tested
  with the detector enabled and `environment: "node"`, it will crash.
- SAFE PATTERN for T002: do NOT register `i18next-browser-languagedetector` in `providers.tsx`.
  Register it only in the i18n singleton init file (T005). For T002 the minimal init above is sufficient.
VERDICT: ok

### Recommended package.json entries
```json
"i18next": "^26.1.0",
"react-i18next": "^17.0.7",
"i18next-browser-languagedetector": "^8.2.1"
```

---

## Q5 — @testing-library/react + vitest 3.x + jsdom vs happy-dom

### @testing-library/react
ANSWER: v16.3.2 current stable. peerDependencies: `"react": "^18.0.0 || ^19.0.0"` — React 19 fully supported.
Minimum version supporting React 19: **v16.1.0** (React 19 support added in 16.1.0, released 2024-12-05).
CITATION: https://registry.npmjs.org/@testing-library/react/latest + GitHub releases page

### jsdom vs happy-dom for vitest + react-i18next
Both are valid. Key difference:
- `jsdom` is heavier, more complete spec coverage, very mature.
- `happy-dom` is lighter, faster, generally sufficient for React component tests.
For the `providers.tsx` smoke test (render `<Providers><div /></Providers>`), either works.
RECOMMENDATION for T002: use `jsdom` — it is the most common choice in React + i18next projects
and has the most complete `window.navigator` mock, which matters if the browser language detector
is ever accidentally imported. `happy-dom` is fine too; either can be pinned.

### Vitest config file requirement
Vitest 3.x defaults to `node` environment when no config is provided.
To use `jsdom` environment, either:
(a) A `vitest.config.ts` (or `vite.config.ts`) must set `test.environment: "jsdom"`, OR
(b) Each test file uses `@vitest-environment jsdom` docblock comment (per-file override, no global config needed).
The planner's CANDIDATE EXTENSION recommendation is to add `frontend/vitest.config.ts` (minimal, ~10 LOC).
Without a config file at all, vitest runs in node env and `window` is undefined — `providers.tsx` using
`import.meta.env` may or may not fail depending on Vite plugin injection. A minimal config is SAFER.
VERDICT: ok — `jsdom` + minimal `vitest.config.ts` is the recommended pattern.

### react-i18next polyfill requirement in jsdom
No special polyfill needed for jsdom. `react-i18next` uses only `React.createContext` and the i18next
instance API. No `TextEncoder` or `URLPattern` polyfill needed for the providers smoke test.

### Recommended devDependencies entries
```json
"@testing-library/react": "^16.3.2",
"jsdom": "^26.0.0"
```
(jsdom latest stable is 26.x as of 2026-05-11 — developer should confirm with npm registry)

---

## Summary pin table (all 8 production deps + test deps)

| Package | Recommended pin | React 19 compat | Notes |
|---|---|---|---|
| `react-router` | `^7.15.0` | YES (>=18) | DISCREPANCY: install `react-router`, not `react-router-dom` |
| `@tanstack/react-query` | `^5.100.9` | YES (^18\|\|^19) | ok |
| `react-hook-form` | `^7.75.0` | YES (^16.8\|\|…\|\|^19) | ok |
| `@hookform/resolvers` | `^5.2.2` | — (via RHF) | supports zod v3 AND v4 |
| `zod` | `^4.4.3` | — | v4 current stable; v3 method style deprecated |
| `i18next` | `^26.1.0` | — | ok |
| `react-i18next` | `^17.0.7` | YES (>=16.8) | requires i18next >=26.0.10 |
| `i18next-browser-languagedetector` | `^8.2.1` | — | package name confirmed exact |
| `@testing-library/react` | `^16.3.2` (devDep) | YES (^18\|\|^19) | React 19 since 16.1.0 |
| `jsdom` | `^26.0.0` (devDep) | — | recommended env for vitest |

RESOLVED: 2026-05-11T11:50:00+00:00 — All pins in `frontend/package.json` confirmed to match the researcher's recommended table verbatim. After the react-router-dom → react-router reconciliation (see sister note `frontend-deps-T002-react-router-2026-05-11.md`), the live deps are: `react@^19.2.6`, `react-dom@^19.2.6`, `react-router@^7.15.0`, `@tanstack/react-query@^5.100.9`, `react-hook-form@^7.75.0`, `zod@^4.4.3`, `@hookform/resolvers@^5.2.2`, `i18next@^26.1.0`, `react-i18next@^17.0.7`, `i18next-browser-languagedetector@^8.2.1`; devDeps include `@testing-library/react@^16.3.2`, `@testing-library/jest-dom@^6.9.1`, `jsdom@^25.0.0`, `vitest@^3.0.0`, `@vitejs/plugin-react@^6.0.1`. Minor drift: developer pinned `jsdom@^25` not `^26` as recommended — vitest 3.x is compatible with both; tests pass green (4/4) in jsdom 25. If a strict jsdom upgrade is desired, raise as an FU; not a discrepancy for T002. Lock regenerated and verified by reconciliation pass.
