# Debugger cycle 1 — P04-S03-T002

## Hypothesis
Validator F-1 + Tester F-1 (consensus): `eslint: ^10.4.0` was placed in `frontend/package.json -> dependencies` (production tree) instead of `devDependencies`. The edits to `frontend/package.json` and `frontend/package-lock.json` were not declared in §10 WRITE_SET_DRIFT of the task pack or in the `## Developer run` handoff section.

## Root cause
The developer ran (presumably) `npm install eslint` without `--save-dev`, so npm placed it under `"dependencies"`. The edit was a silent (undeclared) drift of write_set.

## Fix anchor — §D-T002-FIX-ESLINT-DEVDEP (post-developer, in_scope, no source-of-truth amendment)

1. Edited `frontend/package.json`: moved `"eslint": "^10.4.0"` from `"dependencies"` to `"devDependencies"`. Version range kept exactly the same.
2. Regenerated `frontend/package-lock.json` via `npm --prefix frontend install` (full fresh install). The frontend lockfile now reports `eslint.dev: true`, name `hilo-people-frontend`, 310 total package entries.
3. Restored the canonical workspace-root `package-lock.json` from `HEAD` (it had been transiently disturbed by a `npm install` run from `frontend/` before I realised the project uses the per-frontend lockfile convention used by sibling worktrees, not the workspace-root one). The canonical root lockfile is untouched relative to `main`.

## Files changed by this debugger cycle
- `frontend/package.json` — eslint moved deps → devDeps (1 line move; field-stable).
- `frontend/package-lock.json` — regenerated.
- No source files, no tests, no router, no i18n, no docs.

## Verifications re-run (final, after restored canonical root lockfile)
- `./node_modules/.bin/tsc --noEmit` → exit 0 (tsc.log)
- `npm run build` → 222 modules transformed, exit 0 (build.log)
- `ENABLE_VERBOSE_LOGGING=true ./node_modules/.bin/vitest run` → 16 files, 190/190 PASS (vitest-verbose-true.log)
- `ENABLE_VERBOSE_LOGGING=false ./node_modules/.bin/vitest run` → 16 files, 190/190 PASS (vitest-verbose-false.log)
- `bash scripts/check-design-tokens.sh` → exit 0 (design-tokens.log)
- `npm run lint` → exit 2 (lint.log). **PRE-EXISTING, NOT caused by this slice.** Reason: ESLint 10 requires `eslint.config.js` (flat config) and the project does not provide one. The lint script `"lint": "eslint src"` predates this slice (commit `af03140` P00-S01-T002) and would fail identically on `main`. Fixing it requires adopting a flat config and an ADR — out of scope for P04-S03-T002 (UsagePage). Lint was not part of tester's verification command set either. The eslint binary itself is correctly invocable from devDependencies.

## Test count
- Before debugger: 190/190 PASS (per tester report).
- After debugger: 190/190 PASS unchanged — the bug was a packaging classification, not a runtime defect.

## Evidence files
- `package-json-before.txt` / `package-json-after.txt` / `package-json.diff` — proves the move.
- `lockfile-verify.txt` — JSON snapshot proving eslint is now `dev: true` in `frontend/package-lock.json`.
- `tsc.log`, `build.log`, `vitest-verbose-true.log`, `vitest-verbose-false.log`, `design-tokens.log`, `lint.log`.

## Production tree impact
Before fix: `npm install --omit=dev` would have pulled eslint + ~48 transitives into the production tree (acorn-jsx, ajv, eslint-scope, eslint-visitor-keys, espree, esquery, esrecurse, file-entry-cache, flat-cache, levn, optionator, prelude-ls, type-check, etc.).
After fix: production tree is clean of eslint and its transitives; eslint and its transitives are confirmed `dev: true` in `frontend/package-lock.json`.
