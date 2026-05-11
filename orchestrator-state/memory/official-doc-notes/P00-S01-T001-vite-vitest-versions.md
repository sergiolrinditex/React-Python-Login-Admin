# Official Doc Note — Vite + Vitest + @vitejs/plugin-react Version Discrepancy

**Date**: 2026-05-11
**Task**: P00-S01-T001
**Sources**:
- https://registry.npmjs.org/vite/latest
- https://registry.npmjs.org/vitest/latest
- https://registry.npmjs.org/@vitejs/plugin-react/latest
- https://github.com/vitest-dev/vitest/blob/main/docs/guide/migration.md (Context7)
- https://github.com/vitejs/vite/blob/main/docs/blog/announcing-vite8.md (Context7)

## What the task pack / internal docs say

- `STACK_PROFILE.yaml` and the task pack reference "Vite 5.x" as the frontend build tool.
- The task pack says "Vitest — última stable (¿2.x?)".
- No explicit @vitejs/plugin-react version is pinned.

## What official docs say

| Package | Internal assumption | npm latest stable (2026-05-11) |
|---|---|---|
| `vite` | 5.x | **8.0.11** |
| `vitest` | ~2.x | **4.1.5** |
| `@vitejs/plugin-react` | (unspecified, assumed v4/v5 for Vite 5) | **6.0.1** |

### Critical compatibility chain (official)

- **Vitest 4.0** requires `vite >= 6.0.0` (migration guide: "Prerequisites: Vite version 6.0.0 or higher").
- **Vitest 4.1** adds Vite 8 support explicitly.
- **@vitejs/plugin-react 6.0.1** declares `peerDependencies: { "vite": "^8.0.0" }`. It uses Oxc (not Babel) for React Refresh transforms. v5 remains compatible with Vite 8 for staged upgrades.
- **Vite 5 is no longer the latest stable** — it is two major versions behind. Vite 7 and 8 are released and stable.

### Why this matters

Pinning `vite@5` while using `vitest@4` is a **hard compatibility break** — Vitest 4 will refuse to run on Vite 5. If the developer pins Vite 5 and Vitest 2, that stack works, but both are significantly outdated compared to the current ecosystem and Vitest 2 is EOL-adjacent.

## RECOMMENDED FIX for developer

**Option A (recommended — current ecosystem)**: Pin `vite@^8.0.0`, `vitest@^4.1.5`, `@vitejs/plugin-react@^6.0.1`. This is the fully compatible, current-ecosystem choice as of 2026-05.

**Option B (conservative)**: Pin `vite@^6.x` (stable LTS-equivalent), `vitest@^3.x` or `@^4.x` (both require Vite 6+), `@vitejs/plugin-react@^5.x` (compatible with Vite 6-8). Still requires dropping Vite 5.

**In no case should Vite 5 be used** — it is incompatible with the current Vitest stable series (4.x) and @vitejs/plugin-react 6.x.

The developer should update `STACK_PROFILE.yaml` frontend dependency references from "Vite 5.x" to "Vite 8.x" (or ≥6.x minimum) and align Vitest accordingly.

<!-- RESOLVED: 2026-05-11 — frontend/package.json updated to vite ^8.0.0, vitest ^4.1.0, @vitejs/plugin-react ^6.0.1 per official npm registry; declaration only, install happens in T002. -->
