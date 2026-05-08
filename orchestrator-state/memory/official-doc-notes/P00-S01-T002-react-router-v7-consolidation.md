# Official Doc Note: react-router-dom v7 Package Consolidation

**Date**: 2026-05-08
**Task**: P00-S01-T002
**Package**: `react-router-dom`
**Source**: npm registry + Context7 `/remix-run/react-router` (Source Reputation: High)

---

## Summary

`react-router-dom@latest` is **7.15.0**. This is fully compatible with React 19 (peerDeps: `react >= 18`).

**Key architectural fact the developer must record in the T002 handoff:**

In React Router v7, the package `react-router-dom` is a **thin re-export wrapper** over `react-router`. Installing `react-router-dom@7.15.0` automatically installs `react-router@7.15.0` as a direct dependency.

- `BrowserRouter` still exists and is exported from `react-router-dom` (for library/"declarative" mode).
- `createBrowserRouter` is the recommended API for "data" mode (loaders, actions, fetchers).
- Official upgrade docs recommend: "npm uninstall react-router-dom && npm install react-router" for a clean v7 migration, but using `react-router-dom` as the install target is also valid — it re-exports everything from `react-router`.

**Impact on this slice (P00-S01-T002)**: Install `react-router-dom@7.15.0` as planned — the package still exists and is the standard install name. No blocker.

**Impact on P01-S03-T001** (router wiring slice): The developer of that slice should use either:
- `import { BrowserRouter } from 'react-router-dom'` (library mode — works fine), OR
- `import { createBrowserRouter, RouterProvider } from 'react-router-dom'` (data mode — recommended for production apps with loaders/actions).

Decision authority: P01-S03-T001 developer + planner. This note surfaces the choice so it is made intentionally, not by accident.

---

## Expected version (from task pack)

`react-router-dom` — version `pendiente — official-docs-researcher confirmará al implementar`

## Actual version (from registry)

`7.15.0` — peerDeps: `react >= 18, react-dom >= 18`. React 19.2.6 satisfies `>= 18`.

## Risk

**LOW** for this slice. The install proceeds normally. The risk is architectural for P01-S03-T001: the v7 API surface (especially data router) differs substantially from v6. Not a blocker here.

## Mitigation

Developer installs `react-router-dom@7.15.0` (exact pin). No `BrowserRouter` is wired in this slice — that is P01-S03-T001's scope. Record this note in the T002 handoff "Important decisions" section so P01-S03-T001 planner sees it.

---

RESOLVED: Pinned react-router-dom@7.15.0 (exact, confirmed npm registry 2026-05-08). React 19.2.6 satisfies peerDep `>= 18`. No BrowserRouter wired in this slice — that is P01-S03-T001 scope. Architectural note recorded in T002 handoff "Important decisions": v7 consolidates react-router-dom as thin wrapper over react-router; P01-S03-T001 planner must choose between library mode (BrowserRouter) and data mode (createBrowserRouter) intentionally.
