# Source-of-truth amendment — FU-20260512044309-generate-32-byte-jwt-dev-key-default-enable-verb

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P01-S02-T009 | security | generate ≥32-byte JWT dev key + default ENABLE_VERBOSE_LOGGING in dev .env | Runtime follow-up P01-S02-T002 | current | planned | low | human | P01-S02-T002 | config:env | .env.example, scripts/setup-from-scratch.sh, scripts/gen-dev-secrets.sh | — | — | — | — | runtime-followup#FU-20260512044309-generate-32-byte-jwt-dev-key-default-enable-verb | runtime-followup#FU-20260512044309-generate-32-byte-jwt-dev-key-default-enable-verb | After a fresh setup-from-scratch.sh run on a clean repo, .env contains JWT_PRIVATE_KEY with len>=32 (real random, not 'replace-with-dev-key') AND ENABLE_VERBOSE_LOGGING=true. Backend startup no longer warns about JWT key length. .env.example documents both. | Clone fresh, run setup-from-scratch.sh, then: (a) grep '^JWT_PRIVATE_KEY=' .env, assert value length >= 32 and is not 'replace-with-dev-key', (b) grep '^ENABLE_VERBOSE_LOGGING=true' .env returns a match, (c) start uvicorn, assert no 'JWT_PRIVATE_KEY too short' warning in startup logs. |
```
