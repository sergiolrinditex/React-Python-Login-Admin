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

## Recurring unknowns / blockers

- (none yet — first slice)
