# Validator memory — Hilo People

Patterns and conventions discovered while reviewing slices. Append-only.

## Conventions established (verified live)

- **`.gitkeep` placeholders** are valid in scaffold slices when the task pack §Impact analysis explicitly enumerates them as required layout pins. They are NOT silent write-set widening if listed in the pack. Verify the task pack itemizes them before deciding scope.
- **Module/file docstring contract** (per `01-non-negotiables.md#documentation`) requires: what it does, slice/phase, dependencies. The project follows this with a top comment block including `Slice:` and `Phase:` lines. Apply this check to every new Python and shell file.
- **Logging stub for early scaffold slices**: developer uses stdlib `logging.basicConfig` gated by `ENABLE_VERBOSE_LOGGING`. structlog lands later (T003). This is the canonical bootstrap pattern; do not flag `basicConfig` as wrong in scaffold slices, but DO flag if it persists past T003.
- **`noqa: E402` after `logging.basicConfig`** is acceptable if the import order is intentional (gate the log level before any framework imports its own logger). Look for an inline comment justifying it.

## Bootstrap-generated files vs developer edits

When `git status` shows `??` for paths under `orchestrator-state/memory/*.json`, `task-dag.*`, `active-task.*`, `active-phase.*`, `registry.json`, `runtime-state.json`, these are bootstrap artifacts, NOT developer edits in the current slice. Distinguish via:

```bash
git status --porcelain | grep -E "^( M|MM)" | grep -E "(\.claude/|docs/source-of-truth/|...)"
```

`?? ` (untracked) on those paths during the first slice after bootstrap is normal. Only `M` (modified) on protected paths signals a violation.

`ledger.jsonl` is hook-managed (PostToolUse). Modified state on it is expected and not a developer write.

## Scaffold slice acceptance baseline

For the very first slice (P00-S01-T001 type), tests are intentionally absent. Task pack states T003 introduces dependency_smoke. Do NOT block on missing tests if:

1. Task pack §Verification plan says `verify_mode=auto` and lists only structural commands.
2. Task pack §Out-of-scope explicitly defers tests to a later slice.

Block ONLY if the slice ships product code that should be testable but has zero tests.

## Security checklist baselines

- `.env.example` audit: every secret-bearing var must be `<change-me>` or non-sensitive default. Flag any real-looking value (sk-..., real domains, real ports outside dev range, etc.).
- Health endpoints: no PII, no tokens, no DB connection strings in response or logs. Only status/version/uptime.
- Always check for `noqa`/`type: ignore`/`@ts-ignore` and require an inline justification.

## Useful gates / scripts

- `bash scripts/check-progress-updated.sh --auto` — exit 0 pass / 1 missing / 2 docs-only / 3 inconclusive / 4 error. Must run on every review.
- `bash scripts/check-journey-matrix.sh` — exit 0 if matrix coherent. Run when the diff touches any pantalla/endpoint/tabla declared in TECHNICAL_GUIDE §6 or instrucciones.md §3.5/§3.7.

## Red flags learned

(none yet — first slice)
