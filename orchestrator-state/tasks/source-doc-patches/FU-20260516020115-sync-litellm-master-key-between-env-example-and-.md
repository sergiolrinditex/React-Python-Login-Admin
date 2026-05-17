# Source-of-truth amendment — FU-20260516020115-sync-litellm-master-key-between-env-example-and-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S01-T006 | wiring | Sync LITELLM_MASTER_KEY between .env.example and verification fixture | Runtime follow-up P00-S01-T001 | current | planned | medium | human | P00-S01-T001 | config:env-template | .env.example, docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md | — | — | — | — | runtime-followup#FU-20260516020115-sync-litellm-master-key-between-env-example-and- | runtime-followup#FU-20260516020115-sync-litellm-master-key-between-env-example-and- | After cp .env.example .env (sin editar manualmente), docker compose up litellm + backend smoke chat works without 401 from proxy. .env.example value matches credential_plain in active fixture. TECHNICAL_GUIDE §11.1 row LITELLM_MASTER_KEY notes the matching requirement explicitly. | Reset .env from .env.example, restart litellm + backend, run smoke curl POST /chat/completions with master key. Expect HTTP 200 not 401. |
```
