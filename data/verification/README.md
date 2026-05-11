# data/verification/ — Verification Fixture Data

## Purpose

This directory contains the canonical verification fixtures for the Hilo People
platform. These fixtures are loaded by:

```bash
python -m app.verification_data.bootstrap --source data/verification
```

They power all `/verify-slice`, `/verify-journey`, and integration test runs.

## Security Notice (R3 — TOTP secret in plain text)

**DECISION (P00-S02-T003):** The TOTP secret in `auth/mfa_primary.json` is
stored in plain text so `/verify-slice` for J100 can generate reproducible
TOTP codes without additional tooling.

**This is acceptable for a sandbox/internal development repository.** It MUST
be replaced with a secrets management solution (Vault, AWS Secrets Manager,
environment variable injection) before any deployment to a shared or production
environment.

The file `data/verification/` should be added to `.gitignore` in a production
fork of this repository. Current decision: commit it, since this is an internal
sandbox app (see §P.1 of P00-S02-T003 task pack).

**HUMAN CONFIRM REQUIRED at /verify-slice:** The operator must acknowledge this
trade-off during verification.

## Directory Structure

```
data/verification/
├── users/
│   ├── employee_primary.json    # Primary employee user (J100, J101, J102)
│   └── admin_peopletech.json   # Admin user (J103, J104, J105)
├── auth/
│   └── mfa_primary.json        # TOTP secret for employee_primary (J100)
├── rag_chat/
│   ├── collections/
│   │   └── politicas_tienda.json
│   └── documents/
│       └── politica_vacaciones_es.json
├── rag_docs/
│   └── documents/
│       └── politica_vacaciones_es.json
├── admin_ai/
│   └── providers/
│       └── litellm_verification.json
├── mcp_agents/
│   ├── servers/
│   │   └── sandbox_readonly.json
│   └── agents/
│       └── people_helper.json
└── history/
    └── conversations.json
```

## Canonical Keys (Public Contract)

These keys MUST NOT be renamed without a source-of-truth amendment:

- `users/employee_primary.json.email` → referenced by J100, P01-S02, P03-S01
- `users/admin_peopletech.json.email` → referenced by J103, P02-S05, P04-S01
- `auth/mfa_primary.json.totp_secret` → referenced by J100 MFA flow
- `rag_chat/collections/politicas_tienda.json.name` → referenced by J101, J104
- `mcp_agents/agents/people_helper.json.name` → referenced by J105

## Adding New Fixtures

1. Create a new JSON file under the appropriate group directory.
2. Ensure it validates against the Pydantic schema in
   `backend/app/verification_data/schemas.py`.
3. Run `python -m app.verification_data.bootstrap --source data/verification --dry-run`
   to confirm validation passes before loading.

## Groups

| Group | CLI flag | Tables | Journey |
|---|---|---|---|
| auth | --only auth | users, employee_profiles | J100 |
| rag_chat | --only rag_chat | rag_collections, documents | J101 |
| history | --only history | users, conversations | J102 |
| admin_ai | --only admin_ai | users, ai_providers | J103 |
| rag_docs | --only rag_docs | rag_collections, documents | J104 |
| mcp_agents | --only mcp_agents | mcp_servers, agents | J105 |
