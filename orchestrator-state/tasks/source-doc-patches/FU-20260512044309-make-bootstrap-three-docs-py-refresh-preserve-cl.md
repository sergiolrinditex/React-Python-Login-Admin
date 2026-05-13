# Source-of-truth amendment — FU-20260512044309-make-bootstrap-three-docs-py-refresh-preserve-cl

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P01-S02-T010 | framework | make bootstrap_source_of_truth.py --refresh preserve closer-set task status | Runtime follow-up P01-S02-T002 | current | planned | medium | human | P01-S02-T002 | framework:bootstrap | .claude/bin/bootstrap_source_of_truth.py, .claude/bin/build_registry.py, .claude/bin/tests/test_bootstrap_refresh_preserves_done.py | — | — | — | — | runtime-followup#FU-20260512044309-make-bootstrap-three-docs-py-refresh-preserve-cl | runtime-followup#FU-20260512044309-make-bootstrap-three-docs-py-refresh-preserve-cl | bootstrap_source_of_truth.py --refresh on a registry where a task has status=done + last_outcome=committed leaves those two fields unchanged. A new pytest under .claude/bin/tests/ enforces this for all closer-final statuses. Manual patch of registry.json after refresh is no longer needed. | Set task P01-S02-T001.status=done in registry.json. Run python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh. Assert: (a) refresh exits 0, (b) git diff registry.json shows the task's status, last_outcome, last_updated_by, last_stop_at unchanged, (c) the new pytest test_bootstrap_refresh_preserves_done_status passes. |
```
