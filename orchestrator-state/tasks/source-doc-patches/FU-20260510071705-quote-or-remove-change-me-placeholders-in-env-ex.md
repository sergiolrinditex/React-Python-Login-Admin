# Source-of-truth amendment — FU-20260510071705-quote-or-remove-change-me-placeholders-in-env-ex

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S02-T013 | bug | Quote or remove <change-me> placeholders in .env.example to fix bash source on fresh clones | Runtime follow-up P00-S02-T011 | current | planned | medium | human | P00-S02-T011 | dev_env_setup | .env.example | J100 | — | — | — | runtime-followup#FU-20260510071705-quote-or-remove-change-me-placeholders-in-env-ex | runtime-followup#FU-20260510071705-quote-or-remove-change-me-placeholders-in-env-ex | After fresh git clone + bash scripts/setup-from-scratch.sh, 'set -a, source .env, set +a' succeeds with exit 0, bash scripts/dev-restart.sh --reset succeeds end-to-end (back+front+seed) without manual .env edits | rm .env then bash scripts/setup-from-scratch.sh, ( set -a, source .env, set +a, echo ok ) returns exit 0, bash scripts/dev-restart.sh --reset starts back :8000 healthy and front :5173 reachable |
```
