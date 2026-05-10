# Source-of-truth amendment — FU-20260509222920-dev-env-missing-valid-encryption-key-has-legacy-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S02-T011 | data | Dev .env missing valid ENCRYPTION_KEY (has legacy PROVIDER_ENCRYPTION_KEY=dev-encryption-key-placeholder) | Runtime follow-up P00-S02-T006 | current | planned | medium | human | P00-S02-T006 | dev_env_setup | .env, scripts/setup-from-scratch.sh, docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md | J100, J103 | — | — | — | runtime-followup#FU-20260509222920-dev-env-missing-valid-encryption-key-has-legacy- | runtime-followup#FU-20260509222920-dev-env-missing-valid-encryption-key-has-legacy- | fresh dev clone after running setup-from-scratch.sh has a valid Fernet ENCRYPTION_KEY in .env (or generated dynamically), bootstrap_verification_data succeeds without manual export, live discover-models endpoint encrypt/decrypt works first try | rm .env then bash scripts/setup-from-scratch.sh, bash scripts/dev-restart.sh --reset succeeds without ENCRYPTION_KEY warning, curl POST /api/v1/admin/ai/providers/<id>/discover-models with seeded prod-like data returns 200 (not 502 CryptoError) |
```
