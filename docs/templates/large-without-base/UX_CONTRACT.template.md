# UX_CONTRACT — {{APP_NAME}}

## Screen/Journey Lane Redactor Contract

- No modeles la app como `backend/API primero`, luego `frontend`, y `UX polish` al final. Esa separación rompe la pantalla aunque los tests pasen.
- Cada pantalla importante debe nacer de una **screen/journey lane**: contrato de pantalla + contrato API/datos + implementación conectada + estados UX obligatorios + verificación del journey.
- Las slices de API/backend pueden existir separadas sólo si son foundation real o contrato técnico que alimenta una pantalla/journey nombrado en `Journey refs`.
- Criterio de cierre de pantalla: datos reales/proporcionados conectados front -> back -> DB, estados `loading`, `empty`, `error_network`, `error_validation`, `permission_denied` cuando aplique, `success`, navegación/next action, responsive básico y accesibilidad básica.
- Tamaño recomendado: pantalla crítica 3-6 slices; módulo/journey lane 8-15 slices. No hagas una slice por botón/componente pequeño; tampoco cierres una pantalla sólo porque compila.
- Defectos dentro de la pantalla actual van por `validator/tester -> debugger -> retest`. Sólo crea FU si falta trabajo nuevo fuera de scope: pantalla, endpoint, tabla, journey, contrato de datos reales o decisión humana no declarada.

## 1. UX purpose

Describe the product experience in business/user language. This is the UX source-of-truth; implementation details live in the technical guide.

## 2. Personas

| Persona | Goal | Critical journeys | Data required |
|---|---|---|---|
| {{persona}} | {{goal}} | {{Jx refs}} | {{real/provided data}} |

## 3. Screen inventory

| Route | Screen/Page | Primary journey refs | Required UI states | Real data contract |
|---|---|---|---|---|
| {{/route}} | {{PageName}} | {{J1}} | loading,error,success,empty/streaming if applicable | {{persisted rows / external accounts / files}} |

## 4. Interaction model

For each route, specify primary actions, next action, empty/error copy and what the user sees after success.

## 5. Verification rules

State which flows require real/provided persisted data. If data is missing, record that the user/team must provide it before verification; do not invent unprovided data loads.

## 6. Accessibility and responsive minimum

Keyboard/focus, labels, error visibility, responsive breakpoints and visual-token expectations.