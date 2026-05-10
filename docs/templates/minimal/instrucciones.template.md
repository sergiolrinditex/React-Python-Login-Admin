# {{APP_NAME}} — Instrucciones minimal DAG

## Screen/Journey Lane Redactor Contract

- No modeles la app como `backend/API primero`, luego `frontend`, y `UX polish` al final. Esa separación rompe la pantalla aunque los tests pasen.
- Cada pantalla importante debe nacer de una **screen/journey lane**: contrato de pantalla + contrato API/datos + implementación conectada + estados UX obligatorios + verificación del journey.
- Las slices de API/backend pueden existir separadas sólo si son foundation real o contrato técnico que alimenta una pantalla/journey nombrado en `Journey refs`.
- Criterio de cierre de pantalla: datos reales/proporcionados conectados front -> back -> DB, estados `loading`, `empty`, `error_network`, `error_validation`, `permission_denied` cuando aplique, `success`, navegación/next action, responsive básico y accesibilidad básica.
- Tamaño recomendado: pantalla crítica 3-6 slices; módulo/journey lane 8-15 slices. No hagas una slice por botón/componente pequeño; tampoco cierres una pantalla sólo porque compila.
- Defectos dentro de la pantalla actual van por `validator/tester -> debugger -> retest`. Sólo crea FU si falta trabajo nuevo fuera de scope: pantalla, endpoint, tabla, journey, contrato de datos reales o decisión humana no declarada.

> Perfil: **minimal**. Usa este template para una app pequeña sin existing baseline. Debe producir una app real/MVP de producción con 2-4 phases, 3-8 tasks, 1-2 journeys reales y `mode=explicit_dag`.
>
> Este documento define negocio, UX y journeys. Debe cablearse con `<APP>_TECHNICAL_GUIDE.md` y `<APP>_IMPLEMENTATION_CHECKLIST.md`.

## 1. Identidad

- **Nombre**: {{APP_NAME}}
- **Problema de negocio**: {{PROBLEMA_CONCRETO}}
- **Usuario objetivo**: {{USUARIO_OBJETIVO}}
- **Resultado visible del MVP**: {{RESULTADO_VISIBLE}}
- **Métrica de éxito**: {{METRICA}}

## 2. Alcance minimal

### 2.1 Features

Declara solo features reales del MVP. Para cada feature, define pantalla, acción principal y dato persistido.

| Feature ID | Feature | Pantalla/Ruta | Endpoint principal | Tabla/side effect | Valor para usuario |
|---|---|---|---|---|---|
| F1 | {{FEATURE_1}} | {{PAGE_1}} {{ROUTE_1}} | {{ENDPOINT_1}} | {{TABLE_1}} | {{VALOR_1}} |
| F2 | {{FEATURE_2_OPCIONAL}} | {{PAGE_2}} {{ROUTE_2}} | {{ENDPOINT_2}} | {{TABLE_2}} | {{VALOR_2}} |

### 2.2 Fuera de alcance

- {{FUERA_1}}
- {{FUERA_2}}

## 3. Journey Coverage Matrix

> La matriz es canónica. No inventes journeys de una sola pantalla salvo que sean realmente end-to-end. Para apps pequeñas normalmente hay 1 journey real.

| ID | Milestone | Pantallas/Screens | Acciones/Actions | Endpoints | Tablas/Tables | Estado cliente/Client state | Slices | Verificación/Verification |
|---|---|---|---|---|---|---|---|---|
| J1 | M1 | {{PAGE_SEQUENCE}} | {{USER_ACTIONS}} | `{{ENDPOINT_SEQUENCE}}` | `{{TABLES}}` | `{{CLIENT_STATE}}` | `{{SLICE_IDS}}` | `/verify-journey J1` |

## 4. Milestones

| Milestone | Objetivo | Criterio visible | Journeys |
|---|---|---|---|
| M1 | MVP usable | usuario completa J1 con datos reales/proporcionados | J1 |

## 5. Reglas de verificación real

- El verify debe usar datos reales/proporcionados persistidos.
- No cierres con mocks decorativos, datos inventados o datos no persistidos.
- Si faltan datos para edge cases, el usuario/equipo debe proporcionarlos o la verificación queda bloqueada/follow-up.