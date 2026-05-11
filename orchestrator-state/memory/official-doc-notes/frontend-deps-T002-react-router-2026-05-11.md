# Official Doc Note: react-router — T002 Frontend dependency pack
DATE: 2026-05-11
TASK_ID: P00-S01-T002
TOPIC: react-router package name, version, import paths

## SUMMARY

The task pack and TECHNICAL_GUIDE §2.0 list `react-router-dom` as the package to install.
In React Router v7 (current stable: 7.15.0), the canonical package is `react-router`, NOT `react-router-dom`.
`react-router-dom` v7.15.0 still EXISTS on npm as a thin wrapper that re-exports from `react-router`,
but the official v7 migration guide explicitly instructs: `npm uninstall react-router-dom && npm install react-router@latest`.
All imports move from `"react-router-dom"` to `"react-router"` (or `"react-router/dom"` for DOM-specific APIs).

## SOURCES
- https://reactrouter.com/start/library/installation (official v7 docs, 2026-05-11)
- https://github.com/remix-run/react-router/blob/main/docs/upgrading/v6.md (v6→v7 migration guide)
- https://registry.npmjs.org/react-router-dom/latest (npm registry, version 7.15.0)
- https://registry.npmjs.org/react-router/latest (npm registry, version 7.15.0)

## DETAIL

### Current stable
- react-router: **7.15.0** (current stable as of 2026-05-11)
- react-router-dom: **7.15.0** (re-exports from react-router; deprecated as the primary install name)
- peerDependencies for both: react >=18, react-dom >=18 (React 19 satisfies this)

### Import path changes (v6 → v7)
```diff
# INSTALL
- npm install react-router-dom
+ npm install react-router

# IMPORTS — general (BrowserRouter, Outlet, etc.)
- import { BrowserRouter, Outlet, useNavigate } from "react-router-dom";
+ import { BrowserRouter, Outlet, useNavigate } from "react-router";

# IMPORTS — DOM-specific (RouterProvider when used with createBrowserRouter)
- import { RouterProvider } from "react-router-dom";
+ import { RouterProvider } from "react-router/dom";
```

### Minimal provider wrapper impact
For `providers.tsx` this slice does NOT mount BrowserRouter (T004 does that).
The task pack explicitly says: `<BrowserRouter> is NOT mounted here`.
Therefore the import path discrepancy affects T004, not directly T002.
However, installing `react-router-dom` and importing from it will still work in v7 because
`react-router-dom` v7 re-exports from `react-router`. The risk is:
1. The project has the WRONG package name in its dependency list long-term.
2. Future `npm ls` and lock files will show `react-router-dom` when the ecosystem has moved on.

### v6 vs v7 choice
The task pack §Risks says "R5: react-router-dom v7 (current) ships ESM-only and tightens React 19 peer deps."
Both v6 and v7 satisfy React 19 peerDependencies (v7: `>=18`; v6.x last was 6.30.3 also `>=18`).
v7 is current stable. v6.30.3 is the last v6 release (LTS-style, no new features).
Recommendation: use `react-router@^7.15.0` (the canonical package name).

## IMPACT_ON_TASK

- `frontend/package.json` dependency key MUST be `react-router`, not `react-router-dom`.
- Install command: `npm install react-router`
- Import in downstream files (T004+): `from "react-router"` not `from "react-router-dom"`.
- For THIS slice (T002 providers.tsx): no BrowserRouter import needed; only the package install matters.
- The TECHNICAL_GUIDE §2.0 table lists `react-router-dom` as the library name — this is the legacy v6 name. Developer must update package.json to use `react-router`.

## RECOMMENDATION

Install `react-router@^7.15.0` (NOT `react-router-dom`) in `frontend/package.json`.
Add to `dependencies` (not devDependencies):
```json
"react-router": "^7.15.0"
```
Importing `react-router-dom` still works via the re-export shim but is the deprecated form.
The planner pack consistently says "react-router-dom" in the table — developer must reconcile this
discrepancy by using `react-router` in package.json and all future imports.

RESOLVED: 2026-05-11T11:50:00+00:00 — Reconciled by developer reconciliation pass (orchestrated from main-orchestrator after the parallel researcher reported the discrepancy late in the developer's first pass). Action: renamed `frontend/package.json` dependency `react-router-dom` → `react-router` at version `^7.15.0`; regenerated `frontend/package-lock.json` via `npm install` (164 packages, no shim refs left — grep -c "react-router-dom" frontend/package-lock.json → 0). No src/**.tsx changes were needed because providers.tsx for T002 does not mount `<BrowserRouter>` (per planner shape contract; router mount is deferred to T004). Vitest re-ran green: 4/4 in 1.11s (evidence: orchestrator-state/tasks/evidence/P00-S01-T002/test-output-reconciliation.txt). Source-of-truth amendment of TECHNICAL_GUIDE §2.0 row text ("react-router-dom" → "react-router") is recorded as informational drift in the handoff's "Developer reconciliation pass > Source-of-truth amendment note" section; closer/maintenance owns the amendment, not this slice.
