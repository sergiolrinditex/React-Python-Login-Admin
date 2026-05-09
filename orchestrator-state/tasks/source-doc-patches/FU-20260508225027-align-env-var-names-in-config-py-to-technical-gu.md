# Source-of-truth amendment — FU-20260508225027-align-env-var-names-in-config-py-to-technical-gu

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P01-S01-T002 | wiring | Align env var names in config.py to TECHNICAL_GUIDE §11.1 | Runtime follow-up P00-S02-T001 | current | planned | medium | human | P01-S01-T001 | backend:config | backend/app/core/config.py, .env.example | — | — | — | — | runtime-followup#FU-20260508225027-align-env-var-names-in-config-py-to-technical-gu | runtime-followup#FU-20260508225027-align-env-var-names-in-config-py-to-technical-gu | config.py field names match TECHNICAL_GUIDE §11.1 exactly, all existing smoke tests still pass, docker-compose.yml env overrides updated to match | grep JWT_PRIVATE_KEY backend/app/core/config.py && grep ENCRYPTION_KEY backend/app/core/config.py |
```
