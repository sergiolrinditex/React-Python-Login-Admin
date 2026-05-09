# Planner — manual memory

## Patterns learned

### Scaffold slices (P00-S01-T001 family)

- For "Repo scaffold + scripts + env" tasks, the Write set declares categories ("package manifests"), not paths. Translate each category into a concrete Allowed Paths list in the task pack so developer cannot drift.
- `backend/app/main.py` "compiles" acceptance is best read as: valid Python syntax + matches the API contract Health spec. Imports may not resolve until the deps slice (T003) lands. Document this explicitly to prevent developer from preinstalling deps.
- Always include an "Out-of-scope" table mapping each adjacent concern to its owner slice. The Coverage Registry is right there in the same Step, so reviewers infer scope greedily — fight that with an explicit table.
- `verify_mode=auto` + low risk + non-journey ⇒ pack must mark `Verification data contract: n/a` to prevent tester/verify from chasing fixtures that don't exist yet.

### Task-packing

- Cite §s of source-of-truth, never copy-paste large blocks. Keep the pack scannable; the developer reads PROGRESS.md + this pack only on a daily basis.
- The five source-of-truth files are present: `instrucciones.md`, `*_IMPLEMENTATION_CHECKLIST.md`, `*_TECHNICAL_GUIDE.md`, `STACK_PROFILE.yaml`, `UX_CONTRACT.md`. Confirm all five exist before writing the extract; missing one ⇒ `CONTEXT_READY: no`.

## Modules that tend to break together

- `backend/app/main.py` ↔ `backend/app/api/router.py` ↔ `backend/app/core/config.py` — split across T001 (stub), T003 (config), P00-S02-T002 (router). Keep each refactor strictly inside its slice's Write set.
- `frontend/package.json` ↔ `frontend/src/app/providers.tsx` ↔ `frontend/src/i18n/index.ts` — three different slices (T001 manifest stub, T002 deps + provider, T005 i18n).

### Dependency-pack slices (P00-S01-T002 family)

- When the registry write set lists **only** the manifest + lockfile + one source file, but Acceptance + Verify command imply tests, the planner MUST amend the write set explicitly in the pack (NEW: `*.test.tsx`, `vitest.config.ts`). Validator gets the heads-up upfront; otherwise it flags drift.
- Frontend test environment: Vitest 4 default env is `node`. Any React DOM mount needs `vitest.config.ts` with `test.environment = 'jsdom'` AND `jsdom` in devDependencies. Without this, smoke tests fail with `document is not defined`.
- `@testing-library/react` is implied by `instrucciones.md §11.0` + `TECHNICAL_GUIDE §2.1` for "tests de componentes" — declare its addition explicitly in the dependency-pack pack so it's not "silent expansion".
- For provider wiring slices, ALWAYS specify the exact export name + signature in the pack. Downstream slices import it; lock it now.
- For library installs against pinned framework majors (React 19, Vite 8, TS 6), the `npm install` step itself is the fail gate. Researcher must report peerDeps live; `--legacy-peer-deps` is forbidden.
- "First provider wired" intentionally excludes Router. Router lands with auth (P01-S03-T001) because `BrowserRouter` is coupled to redirect-after-login behavior. The pack must explicitly say "do NOT add BrowserRouter" or developer will pre-empt P01-S03.
- T001 closer left frontend stack pinned to React 19 / TS 6 / Vite 8 / Vitest 4. T002 inherits these — pack must call them out as "do not regress" so dependency conflict resolution doesn't downgrade them.

### Design-token slices (P00-S01-T004 family)

- The CHECKLIST registry write_set may be intentionally narrow (theme-only). When the verify command requires a build, the pack MUST record a `write_set_extension` block listing the bootstrap-completion paths (tsconfig, tsconfig.node, vite.config, index.html, main.tsx, the showcase route page itself). Justify with PROGRESS.md "Known Issues" + previous-handoff explicit deferrals. This is "Path A" in the planner pack template.
- "Path B" (split into a follow-up to amend source-of-truth) is the wrong call when (a) the verify command can't pass without those files and (b) the previous handoff already pre-declared the deferral. Path B remains valid post-close as a `/register-followup` to update the registry write_set for reproducibility.
- The `/showcase` route is NOT in UX_CONTRACT screen inventory by design — it is a dev-only design-system surface, not a productive screen. Document `Required UI states: n/a` per state with reasons; otherwise validator/tester chase missing loading/empty/error/permission/success states that don't apply.
- For pure presentational components (Wordmark, TrackedLabel, StatusDot, HairlineTable, MobileFrame, AdminShell), `BEFORE/AFTER` logging applies once they gain a real action handler in a downstream slice — same precedent as T002 `providers.tsx`. Document in the component docstring + handoff "Logging exemption".
- Component naming drift between `instrucciones.md §7` (descriptive) and `*_TECHNICAL_GUIDE §7` (architectural) — TECHNICAL_GUIDE wins for component identifiers (`MobileFrame`, not `MobileShell`). instrucciones is descriptive marketing copy; do not let a developer "harmonize" it back. Record in the pack `## Discrepancies` table.
- `design_tokens_v1` excludes `tokens|theme|themes|design-system` directory names by default; `frontend.theme_root=frontend/src/shared/styles` is auto-excluded. Sanity-run before adding hex literals so the developer doesn't waste time chasing false negatives.

## Recurring unknowns / blockers

- React Router v7 vs v6 published-stability on a given date — researcher decides per slice. Pack must capture the decision so downstream auth slice isn't surprised.
- TanStack Query v5 minor that supports React 19 — researcher confirms; pack must note "respect peerDeps".
- Frontend `tsconfig.json` is missing from T001's bootstrap. Bootstrap drift candidate; do NOT fix unilaterally in T002. Likely belongs to T004 design tokens. **Confirmed in T004**: lands here under Path A `write_set_extension`.
- Frontend dev port: vite default 5173 may collide with a sibling project; project pinned `FRONT_PORT=5174` in `.env`. The vite.config must read it from env (not hardcode 5173).
- STACK_PROFILE `git_workflow=push-to-main` overrides instrucciones §9 `pr-flow` (resolved 9b2a9f4). When the two source-of-truth docs disagree on a structural value, the YAML profile wins because it is the machine-readable contract; instrucciones can lag.
