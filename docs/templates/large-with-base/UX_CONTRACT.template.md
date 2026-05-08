# UX_CONTRACT — {{APP_NAME}}

## 1. UX purpose

Describe the product experience in business/user language. This is the UX source-of-truth; implementation details live in the technical guide.

## 2. Personas

| Persona | Goal | Critical journeys | Data required |
|---|---|---|---|
| {{persona}} | {{goal}} | {{Jx refs}} | {{real/prod-like data}} |

## 3. Screen inventory

| Route | Screen/Page | Primary journey refs | Required UI states | Real data contract |
|---|---|---|---|---|
| {{/route}} | {{PageName}} | {{J1}} | loading,error,success,empty/streaming if applicable | {{persisted rows / external accounts / files}} |

## 4. Interaction model

For each route, specify primary actions, next action, empty/error copy and what the user sees after success.

## 5. Verification rules

State which flows must use real/prod-like persisted data and which edge cases may use synthetic fixtures.

## 6. Accessibility and responsive minimum

Keyboard/focus, labels, error visibility, responsive breakpoints and visual-token expectations.
