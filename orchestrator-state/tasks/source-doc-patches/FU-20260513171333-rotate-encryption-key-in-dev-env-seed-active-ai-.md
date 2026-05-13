# Source-of-truth amendment — FU-20260513171333-rotate-encryption-key-in-dev-env-seed-active-ai-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P02-S03-T004 | data | Rotate ENCRYPTION_KEY in dev .env + seed active AI provider with encrypted credentials | Runtime follow-up P02-S03-T002 | current | planned | medium | human | P02-S03-T002 | infra:dev-secrets | scripts/gen-dev-secrets.sh, .env.example, data/verification/admin_ai/** | J101, J103 | — | — | ai_providers, ai_provider_credentials, ai_models | runtime-followup#FU-20260513171333-rotate-encryption-key-in-dev-env-seed-active-ai- | runtime-followup#FU-20260513171333-rotate-encryption-key-in-dev-env-seed-active-ai- | scripts/gen-dev-secrets.sh rotates ENCRYPTION_KEY if placeholder (Fernet.generate_key() pattern), data/verification loads at least one ai_providers row with encrypted credential for an active chat model, ENCRYPTION_KEY is valid Fernet key (44 base64-url chars + =) | After rotation: curl POST /api/v1/chat/conversations creates a conv (201), curl POST /api/v1/chat/conversations/{id}/stream returns text/event-stream with meta->chunk->usage->done SSE events |
```
