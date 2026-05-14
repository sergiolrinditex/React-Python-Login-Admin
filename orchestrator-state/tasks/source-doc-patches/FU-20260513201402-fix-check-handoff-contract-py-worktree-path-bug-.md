# Source-of-truth amendment — FU-20260513201402-fix-check-handoff-contract-py-worktree-path-bug-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S03-T007 | wiring | Fix check_handoff_contract.py — worktree path bug in pr-flow | Runtime follow-up P02-S03-T004 | current | planned | medium | human | P02-S03-T004 | infra:orchestrator-scripts | .claude/bin/check_handoff_contract.py, .claude/bin/tests/test_handoff_contract.py | J100 | — | — | — | runtime-followup#FU-20260513201402-fix-check-handoff-contract-py-worktree-path-bug- | runtime-followup#FU-20260513201402-fix-check-handoff-contract-py-worktree-path-bug- | (1) check_handoff_contract.py works correctly when invoked from a pr-flow worktree (CLAUDE_WORKTREE_ROOT or cwd != main repo root), (2) new test asserts the worktree path case (mock workspace_root or use tmp_path) | From a worktree: ./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice exits 0 when handoff is valid, the details.handoff string is a relative path under the worktree, not absolute |
```
