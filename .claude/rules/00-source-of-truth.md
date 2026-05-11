# Source-of-truth rule

The project is governed by the canonical source-of-truth set in `docs/source-of-truth/`:

- `instrucciones.md` — goals, scope, business rules, Journey Coverage Matrix and authority order.
- `*_IMPLEMENTATION_CHECKLIST.md` — phases, steps, Coverage Registry, DAG fields, risk and verify mode.
- `*_TECHNICAL_GUIDE.md` — architecture, contracts, endpoints, DB, ADRs and verification data contract.
- `STACK_PROFILE.yaml` — framework/language, module roots, commands, design-token enforcer and Git workflow.
- `UX_CONTRACT.md` — personas, screen inventory, required UI states and UX verification rules.

If any source-of-truth file is missing, duplicated, stale or contradictory, stop and repair the contract first.

Rules:

- These source files are the only authority. Everything under `orchestrator-state/memory/` and `orchestrator-state/tasks/` is a derived execution artifact.
- If official docs and these docs disagree: stop coding, write the discrepancy to `orchestrator-state/memory/official-doc-notes/`, reconcile, and only then continue.
- Full-read of source-of-truth is done on bootstrap and on explicit `planner` extraction. Daily work reads PROGRESS.md + task-pack instead.

## Secciones obligatorias

Dos secciones tienen home semántico fijo dentro de los documentos source-of-truth y no pueden vivir en otro sitio (ni en `orchestrator-state/memory/`, que es derivado/efímero):

### User journeys → `instrucciones.md`

- Sección dedicada dentro de `instrucciones.md` (sugerencia: subsección bajo Alcance / Scope, p. ej. `### 3.4 Recorridos del usuario`).
- Feature-app inicial: 2–6 recorridos reales en lenguaje plano que cruzan varias pantallas; después pueden crecer hasta 10 si el producto lo requiere. Un journey de un solo paso es una feature, no un journey.
- Cada journey usa **identificadores compartidos con el resto de docs**: nombres de ruta del router declarado del `TECHNICAL_GUIDE` y nombres de pantalla del `CHECKLIST`. Ejemplo: `user → /login → tap "Continue with Google" → callback OAuth → /home`.
- Owner: producto. Cambia cuando cambia el alcance, no cuando cambia la implementación.

### Architectural Decision Records (ADR) → `*_TECHNICAL_GUIDE.md`

- Sección al final del doc (sugerencia: `## Architectural Decision Records (ADR)`), append-only.
- Umbral para crear un ADR: elección **no obvia** donde alternativas se consideraron de verdad. Convenciones de estilo, defaults triviales o reglas ya cubiertas en `01-non-negotiables.md` no necesitan ADR.
- Formato canónico de cada entrada (8–15 líneas):
  - **Fecha** — `YYYY-MM-DD`.
  - **Contexto** — 1 frase: el problema o la fuerza que dispara la decisión.
  - **Decisión** — 1–2 frases: qué se elige.
  - **Alternativas descartadas** — 1 línea por alternativa con el motivo del rechazo. Sin esto el ADR no aporta valor.
  - **Consecuencias** — los tradeoffs que se aceptan.
- Cuando un ADR queda obsoleto **no se borra**: se marca `SUPERSEDED por ADR-N (YYYY-MM-DD)` y se añade el nuevo bloque al final. El log es lineal y append-only para preservar el porqué histórico.
