# Fix validation report — AnyStack DAG orchestrator

Date: 2026-05-07

## Scope reviewed

- `README.md`
- `.claude/` agents, commands, hooks/bin scripts, enforcers, rules and contract files
- `orchestrator-state/` runtime layout and regenerated BaseApp state
- `scripts/` wrappers, checkers and smoke tooling
- `docs/` source-of-truth, templates, guides and reports
- `site/diagrams/` and `site/html-site/` documentation surfaces

The uploaded request mentioned `dos/`; this repository does not contain that folder. The real documentation folder is `docs/`.

## Main fixes

1. Template layout normalized to exactly three profiles, each with five files:
   - `docs/templates/minimal/`
   - `docs/templates/large-without-base/`
   - `docs/templates/large-with-base/`
2. `large-with-base` is locked to the inherited BaseApp stack: Flutter + FastAPI + Postgres/Supabase-compatible.
3. Added registry-driven API contract generation:
   - OpenAPI JSON/YAML
   - endpoint registry snapshot
   - TypeScript frontend client stub
   - Dart frontend client stub
   - source digest manifest with `--validate-only`
4. Changed journey gate default to `journey_gate_mode=frontier`; only tasks that reference pending journeys are deferred. `strict` preserves the legacy global block.
5. Replaced the design-token enforcer stub with stack dispatch and a web scanner for React/Next/Vite-style code.
6. Updated commands, agents, rules, README, docs and diagrams to match the current flow.
7. Added smoke coverage for two generated apps per profile.

## Validation performed

### BaseApp current source-of-truth

```text
python3 -B -S .claude/bin/bootstrap_three_docs.py --validate-only
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/generate-api-contracts.sh --validate-only
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
```

Result:

```text
Bootstrapped project prefix: BASEAPP
Detected phases: 13
Generated tasks: 84
Detected journeys: 8
API contracts up to date — endpoints=41
Task DAG: OK mode=explicit_dag nodes=84 edges=134 waves=8
Journey matrix coherent — 8 journeys validadas, 0 drifts
Wiring contract coherent — 13 routes, 41 endpoints, 84 registry rows, 8 journeys, data_contract=1
```

### Template smoke

Command:

```bash
python3 -B -S scripts/smoke-template-profiles.py --keep --json
```

Result summary:

```text
ok=true
minimal / PocketPantry: tasks=4 journeys=1 waves=4 explicit_dag
minimal / TrailLog: tasks=4 journeys=1 waves=4 explicit_dag
large-without-base / CivicPulse: tasks=8 journeys=2 waves=5 explicit_dag
large-without-base / ClinicFlow: tasks=8 journeys=2 waves=5 explicit_dag
large-with-base / InvoicePilot: tasks=7 journeys=2 waves=6 explicit_dag
large-with-base / EventOps: tasks=7 journeys=2 waves=6 explicit_dag
```

Full JSON report: `docs/reports/TEMPLATE_SMOKE_REPORT.json`.

### Internal test suite

Command:

```bash
python3 -m pytest -q .claude/bin/tests
```

Result:

```text
227 passed, 5 warnings in 43.45s
```

Warnings are the existing multiprocessing/fork deprecation warnings in lock serialization tests.
