# {{APP_NAME}} — Instrucciones minimal DAG

> Perfil: **minimal**. Usa este template para una app pequeña sin BaseApp. Debe producir una app real/MVP de producción con 2-4 phases, 3-8 tasks, 1-2 journeys reales y `mode=explicit_dag`.
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
