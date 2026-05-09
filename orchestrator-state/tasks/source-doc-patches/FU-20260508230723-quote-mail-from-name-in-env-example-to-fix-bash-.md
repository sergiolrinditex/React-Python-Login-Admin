# Source-of-truth amendment — FU-20260508230723-quote-mail-from-name-in-env-example-to-fix-bash-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P01-S01-T003 | bug | Quote MAIL_FROM_NAME in .env.example to fix bash source failure | Runtime follow-up P00-S02-T001 | current | planned | low | human | P01-S01-T001 | infra:env | .env.example | — | — | — | — | runtime-followup#FU-20260508230723-quote-mail-from-name-in-env-example-to-fix-bash- | runtime-followup#FU-20260508230723-quote-mail-from-name-in-env-example-to-fix-bash- | bash scripts/dev-restart.sh --check exits with backend UP, not 'command not found' | grep 'MAIL_FROM_NAME="Hilo People"' .env.example |
```
