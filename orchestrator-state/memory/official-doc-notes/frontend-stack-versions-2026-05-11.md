# Official Doc Note: Frontend Stack Versions — React / Vite / TypeScript

DATE: 2026-05-11
TASK_ID: P00-S01-T001
TOPIC: Frontend package.json version pins for React + Vite + TypeScript

---

## SOURCE_URL

- https://registry.npmjs.org/react/latest (npm registry, live)
- https://registry.npmjs.org/vite/latest (npm registry, live)
- https://registry.npmjs.org/typescript/latest (npm registry, live)
- https://registry.npmjs.org/@vitejs/plugin-react/latest (npm registry, live)
- https://github.com/vitejs/vite (Context7 /vitejs/vite — Vite create-vite template-vue-ts as proxy for current tool versions)
- https://github.com/facebook/react (Context7 /facebook/react — React 19.2.0 confirmed)

## SOURCE_VERSION (verified live on 2026-05-11)

| Package | Latest stable | Context7 version list |
|---|---|---|
| react | **19.2.6** | v18_3_1, v19_1_1, v19_2_0 |
| react-dom | **19.2.6** | (same as react) |
| vite | **8.0.12** | v7.0.0, v5.4.21, v8.0.0, v7.3.1, v8.0.7, v8.0.10 |
| @vitejs/plugin-react | **6.0.1** | — |
| typescript | **6.0.3** | v5.9.2, v5.8.3, v5.9.3, v6.0.2, v4.7.4 |
| @types/react | (tracks react) | — |
| @types/react-dom | (tracks react) | — |

## INTERNAL_CLAIM

The task pack §4.1 refers to "React 18 + Vite + TypeScript" from `instrucciones.md §1.3` which states "Frontend React + Vite + TypeScript". The planner pack §10.4 (Unknowns) explicitly acknowledges: "Exact Vite/React/TS versions to declare in `frontend/package.json`. The planner does not pin them — `official-docs-researcher` runs in parallel with the developer and will verify." No explicit version pins are set by the source-of-truth docs.

## DISCREPANCY

The phrase "React 18" in the user-facing task description and the naming convention in CLAUDE.md ("React 18 + Vite 5 + TypeScript 5") is OUTDATED as of May 2026:

- React **19** (19.2.6) is the current stable, not React 18.x.
- Vite **8** (8.0.12) is the current stable, not Vite 5.
- TypeScript **6** (6.0.3) is the current stable, not TypeScript 5.
- `@vitejs/plugin-react` **6.0.1** corresponds to Vite 8 (not plugin-react 4.x that shipped with Vite 5).

React 18.x (18.3.1) is still available and in security support, but React 19 is the current stable default from the npm `latest` tag.

The create-vite scaffold (Vue+TS template confirmed) now ships `typescript: ~6.0.2` and `vite: ^8.0.8`.

## IMPACT_ON_TASK

- `frontend/package.json` will be wrong if it pins `react@^18`, `vite@^5`, `typescript@^5` — it will install outdated versions.
- Downstream slices T002 (frontend deps) and T004 (design tokens) depend on the correct React version because:
  - React Router v7 requires React 19 for its new APIs.
  - TanStack Query v5+ officially supports and recommends React 19.
  - `@vitejs/plugin-react` 6.x targets Vite 8 and React 19's new JSX transform.
- TypeScript 6 introduces breaking changes vs 5.x (strictness improvements). Pinning wrong version will cause type-check failures in T003+ when strict mode is enforced.

## RECOMMENDATION

Developer should use the following version pins in `frontend/package.json`:

```json
{
  "dependencies": {
    "react": "^19.2.6",
    "react-dom": "^19.2.6"
  },
  "devDependencies": {
    "@vitejs/plugin-react": "^6.0.1",
    "@types/react": "^19.1.2",
    "@types/react-dom": "^19.1.2",
    "typescript": "~6.0.3",
    "vite": "^8.0.12"
  }
}
```

If the human/product owner prefers to stay on React 18 LTS for stability, `react@^18.3.1` + `vite@^7.3.1` + `typescript@~5.9.3` + `@vitejs/plugin-react@^4.3.4` is a valid conservative path, but it is NOT the current stable default. This decision requires explicit human sign-off in the source-of-truth docs — the developer should NOT silently use 18 without escalating.

RESOLVED: Human signed off 2026-05-11 on "Current stable (R19/V8/TS6)" via /next-slice prompt. frontend/package.json rewritten to react@^19.2.6, react-dom@^19.2.6, @vitejs/plugin-react@^6.0.1, @types/react@^19.1.2, @types/react-dom@^19.1.2, typescript@~6.0.3, vite@^8.0.12, vitest@^3.x. Source-of-truth docs (instrucciones.md, TECHNICAL_GUIDE) carry no version pins, so this is recorded here as the authoritative project default for the React/Vite/TS stack going forward; downstream slices T002/T004 will follow.
