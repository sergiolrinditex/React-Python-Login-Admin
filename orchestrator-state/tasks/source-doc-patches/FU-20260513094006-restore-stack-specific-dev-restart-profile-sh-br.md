# Source-of-truth amendment — FU-20260513094006-restore-stack-specific-dev-restart-profile-sh-br

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S03-T003 | wiring | restore stack-specific dev-restart.profile.sh broken by framework refactor c4c91ae | Runtime follow-up P02-S03-T001 | current | planned | high | human | P02-S03-T001 | api:chat | scripts/dev-restart.profile.sh | — | — | — | — | runtime-followup#FU-20260513094006-restore-stack-specific-dev-restart-profile-sh-br | runtime-followup#FU-20260513094006-restore-stack-specific-dev-restart-profile-sh-br | ./scripts/dev-restart.sh --reset arranca backend en :8000, frontend en :5173, /health=200, /ready db=ok, datos reales/proporcionados base cargados sin error. ./scripts/dev-restart.sh --soft también funciona. | Ejecutar ./scripts/dev-restart.sh --reset desde checkout limpio + comprobar /health, /ready, conteo de filas en users/conversations/messages tras bootstrap, y dispatch correcto de --soft. |
```
