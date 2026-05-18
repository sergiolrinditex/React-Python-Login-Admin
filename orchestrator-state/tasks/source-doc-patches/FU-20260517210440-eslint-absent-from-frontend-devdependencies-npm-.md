# Source-of-truth amendment — FU-20260517210440-eslint-absent-from-frontend-devdependencies-npm-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S01-T008 | security | eslint absent from frontend devDependencies — npm run lint always fails | Runtime follow-up P04-S01-T003 | current | planned | medium | human | P04-S01-T003 | front:tooling | frontend/package.json, frontend/package-lock.json, frontend/eslint.config.*, frontend/.eslintrc*, frontend/src/**/*.{ts, tsx} | — | — | — | — | runtime-followup#FU-20260517210440-eslint-absent-from-frontend-devdependencies-npm- | runtime-followup#FU-20260517210440-eslint-absent-from-frontend-devdependencies-npm- | eslint (or chosen linter e.g. oxlint/biome) installed in devDependencies, npm run lint exits 0 with zero warnings on the existing codebase. | npm --prefix frontend run lint exits 0 in a clean worktree, pre-commit lint hook (if any) green. |
```
