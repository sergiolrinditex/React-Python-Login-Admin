# Source-of-truth amendment — FU-20260513210148-fix-orchestrator-ci-journey-state-stack-profile-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S05-T004 | test | Fix orchestrator CI: journey_state + stack_profile contract regressions | Runtime follow-up P02-S05-T002 | current | planned | high | human | P02-S05-T002 | orchestrator:tests | .claude/bin/**, .claude/hooks/**, scripts/git-workflow.sh | — | — | — | — | runtime-followup#FU-20260513210148-fix-orchestrator-ci-journey-state-stack-profile- | runtime-followup#FU-20260513210148-fix-orchestrator-ci-journey-state-stack-profile- | All 3 jobs of Orchestrator tests workflow turn green on a PR against main: Lint (python + json + bash + shellcheck), Unit tests (python 3.11), Unit tests (python 3.12). PR #15 and any subsequent slice PRs do not regress this state. | CI on GitHub Actions Orchestrator tests workflow green, gh pr view <new-PR> --json statusCheckRollup shows all SUCCESS. |
```
