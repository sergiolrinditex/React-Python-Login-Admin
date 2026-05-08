# UX_CONTRACT — {{APP_NAME}}

## 1. UX purpose

One paragraph: what the small app lets a user accomplish.

## 2. Persona

| Persona | Goal | Journey | Data required |
|---|---|---|---|
| {{persona}} | {{goal}} | J1 | {{one real persisted entity}} |

## 3. Screen inventory

| Route | Screen/Page | Primary journey refs | Required UI states | Real data contract |
|---|---|---|---|---|
| {{/route}} | {{PageName}} | J1 | loading,error,success,empty | {{real/prod-like entity rows}} |

## 4. Verification rules

For `Verify mode=human`, use real persisted data. For `Verify mode=auto`, commands must be deterministic and cannot close a journey.
