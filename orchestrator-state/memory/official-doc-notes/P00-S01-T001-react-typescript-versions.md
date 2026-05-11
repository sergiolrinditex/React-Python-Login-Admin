# Official Doc Note — React + TypeScript Version Discrepancy

**Date**: 2026-05-11
**Task**: P00-S01-T001
**Sources**:
- https://registry.npmjs.org/react/latest
- https://registry.npmjs.org/typescript/latest
- https://registry.npmjs.org/@testing-library/react/latest
- https://github.com/facebook/react/blob/main/packages/react/src/ReactHooks.js (Context7)

## What the task pack / internal docs say

- Task pack says "React 18.x — última (¿18.3.x?)" and explicitly asks to confirm React 19 is NOT the recommended pin.
- Task pack says "TypeScript 5.x — última stable".

## What official docs say

| Package | Internal assumption | npm latest stable (2026-05-11) |
|---|---|---|
| `react` | 18.x (explicitly warned against 19) | **19.2.6** |
| `react-dom` | 18.x | **19.2.6** |
| `typescript` | 5.x | **6.0.3** |
| `@testing-library/react` | (latest compat with React 18) | **16.3.2** (peerDeps: `^18.0.0 \|\| ^19.0.0`) |

### React 19 status (2026-05-11)

React 19 is **now the stable npm latest**. The `latest` tag on npm resolves to `19.2.6`. React 19 has been stable since late 2024 and is in the 19.2.x patch series as of 2026-05. It is no longer a migration risk for new projects — it is the current stable release.

Key React 19 changes relevant to a new project:
- `ref` is now a regular prop (no `forwardRef` needed).
- New hooks: `useActionState`, `useOptimistic`, `use()`.
- `element.ref` access is deprecated (warning in dev).
- The ecosystem (react-router, tanstack-query, etc.) has broadly adopted React 19.

The internal docs rationale ("riesgo de breakage en ecosystem") was valid in 2024 when React 19 was RC, but is no longer valid in 2026 — the ecosystem has fully caught up.

### TypeScript 6.0 status (2026-05-11)

TypeScript 6.0.3 is the npm latest stable. TypeScript 5.x is NOT the latest anymore. TS 6 ships with `--erasableSyntaxOnly` replacing `--verbatimModuleSyntax` and other changes, but is backward-compatible for most modern codebases. For a greenfield project, TS 6 is the correct current choice.

Context7 Vite repo shows templates using `"typescript": "~6.0.2"` as of the latest Vite 8 release.

### @testing-library/react 16.3.2

Supports both React 18 and React 19 via `peerDependencies: "^18.0.0 || ^19.0.0"`. No discrepancy if either React version is chosen.

## RECOMMENDED FIX for developer

1. **React**: Use `react@^19.2.0` and `react-dom@^19.2.0`. React 19 is the current stable for new projects in 2026. The ecosystem concern cited in internal docs was valid in early 2024 and is now resolved.

2. **TypeScript**: Use `typescript@^6.0.3`. TS 5 is still maintained but 6.x is current stable and greenfield projects should use it.

3. **@testing-library/react**: Use `@testing-library/react@^16.3.2` — compatible with both React 18 and 19.

4. Update `STACK_PROFILE.yaml` and any source-of-truth references from "React 18.x" to "React 19.x" and from "TypeScript 5.x" to "TypeScript 6.x".

RESOLVED: 2026-05-11 — frontend/package.json (T001 commit 09154e5) pins react/react-dom ^19.2.0 and typescript ^6.0.0 per official npm registry; greenfield 2026-05 pin, declaration only. T002 will run the actual `npm install`.

<!-- RESOLVED: 2026-05-11 — frontend/package.json updated to react/react-dom ^19.2.0 and typescript ^6.0.0 per official npm registry; greenfield 2026-05 pin, declaration only. -->
