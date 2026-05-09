# Official-Doc Note: P00-S01-T005 — Vite publicDir files cannot be statically imported; JSON must live under src/

**Severity**: medium (architectural — affects where 24 JSON files must live)
**Status**: RESOLVED 2026-05-09 — Option A chosen (see RESOLVED block at end)
**Date**: 2026-05-09
**Task**: P00-S01-T005

## Finding

The task pack §D3 and the registry `write_set` declare that bundles live in `frontend/public/locales/**`, yet the planner's chosen strategy is **eager loading** (static `import` statements at module load). These two facts are in direct conflict.

### Official Vite 8 docs quote (vite.dev/guide/assets)

> "The public directory is intended for assets that are **not referenced in source code**, require a specific filename without hashing, or should be served at the root path. Assets placed here are **copied as-is** to the distribution directory and should be referenced using **root absolute paths** in the source code."

Also confirmed: the `publicDir` option doc says files are "copied as-is … not transformed." The Rollup bundler does not parse or process `public/` files.

### What this means for eager loading

Static `import esCommon from '../../public/locales/es/common.json'` resolves at **compile-time** via Rollup/Vite's module graph. However, the `../../public/` path fragment from `src/i18n/index.ts` does not cross into Vite's `publicDir` at compile time; Vite's module resolution for `import` statements does NOT traverse into `publicDir` — it is a copy-only directory.

**Tested understanding**: `import` from a relative path that physically resolves inside `frontend/public/` DOES work in Vite because Vite's dev server serves all files, and in build mode Rollup follows the filesystem path. The path `frontend/public/locales/…` is reachable from `frontend/src/i18n/index.ts` via `../../public/locales/…`. Rollup will resolve the JSON file from the filesystem, NOT from the public-dir serving mechanism.

### The real conflict

There are two competing behaviors:

1. **Static `import` from `src/` into `public/locales/`** — Rollup resolves the file by filesystem path, bundles it into the JS output. Result: the file is included BOTH in the built JS bundle AND copied verbatim into `dist/public/locales/`. **Double-ship**: the JSON data appears in the bundle AND as a separate served file. For tiny locale files (~few KB total) this is harmless but architecturally inconsistent.

2. **Canonical eager pattern** — move JSON files under `frontend/src/i18n/locales/{lng}/{ns}.json`. Rollup bundles them cleanly; no duplication; no public-served copy. Downside: a future switch to lazy-loading (http-backend) would require moving files back to `public/`. The planner note in D3 says "keeping JSON canonically in `public/locales/` so future lazy migration is trivial" — this is the design intent.

3. **Lazy (http-backend)** — files stay in `public/locales/`; no static import; `i18next-http-backend` fetches at runtime. Cons: dep not installed, Suspense/ready guard needed, complicates Vitest.

## Internal doc quote (task pack §D3)

> "Keeping the JSON canonically in `public/locales/` (so future lazy migration is trivial) while importing them via `import` (Vite handles JSON imports natively)."

The planner's claim "Vite handles JSON imports natively" is **correct** — Vite does support `import foo from './foo.json'` when the file is reachable via the module-resolver path. The critical nuance is: importing a file from inside `frontend/public/` via a relative path from `frontend/src/` DOES work (Rollup resolves it by filesystem), but it causes the JSON to be **bundled** (not just copied from publicDir). This means the `public/locales/` path choice has the side-effect of double-shipping those files — once bundled, once served statically.

## Recommended reconciliation options (developer chooses)

**Option A (align with planner D3 — minimal change)**: Keep JSON under `frontend/public/locales/**`. Use relative static imports from `frontend/src/i18n/index.ts` (`../../public/locales/…`). Accept the double-ship (bundle + static) for the ~few KB of locale data. The `write_set` already declares `frontend/public/locales/**` so no registry change is needed. Document the double-ship as intentional in the `index.ts` docstring.

**Option B (cleanest architecture)**: Move JSON files to `frontend/src/i18n/locales/{lng}/{ns}.json`. Update `write_set_extension` in task pack (already allowed per the planner note that `frontend/src/i18n/**` is in write_set). No double-ship. Future lazy migration: copy files to `public/` when adding http-backend. Registry `write_set` already covers `frontend/src/i18n/**`.

**Option C (pure http-backend)**: Keep `public/locales/`, add `i18next-http-backend` dep, use lazy loading. Requires changing `react.useSuspense` to true OR `{ useSuspense: false }` on hooks + `ready` guard in tests. Contradicts D3 and expands scope (new dep, test changes). NOT recommended for this slice.

## Impact on tests

Both Option A and B support `import esCommon from '…/common.json'` in Vitest — Vitest uses Vite's module resolver, so JSON imports work in both cases. No test changes needed between A and B — only the import path strings differ.

## Action required

Developer must pick Option A or B, document the choice in `frontend/src/i18n/index.ts` docstring, and add `RESOLVED: <option chosen + reason>` to this note before committing.

## Official sources

- https://vite.dev/guide/assets (The public Directory section)
- https://vite.dev/config/shared-options (publicDir option)
- https://vite.dev/guide/features (JSON import and import.meta.glob)
- Context7 `/websites/vite_dev` — confirmed 2026-05-09

RESOLVED: 2026-05-09 — Option A adopted by implementation. Bundles live at `frontend/public/locales/{es,en,fr}/{8 namespaces}.json` (matches registry `write_set: frontend/public/locales/**`). `frontend/src/i18n/index.ts` uses static `import` from `../../public/locales/...` paths; Vite/Rollup resolve them by filesystem, bundling JSON into the JS output. The double-ship (bundled in JS + copied to dist/locales/) is accepted as intentional: total locale payload ≤6 KB, the simplification (no http-backend dep, no Suspense plumbing, no test network races, synchronous i18n on first render) outweighs the duplication. The double-ship is explicitly documented in the i18n module docstring (§D3 in `frontend/src/i18n/index.ts`). Future migration to lazy http-backend (P03+ if needed) is trivial because files already live in `public/locales/`. No registry/write_set change required. Reconciled by main-orchestrator before validator/tester gate (developer completed implementation aligned with this option).
