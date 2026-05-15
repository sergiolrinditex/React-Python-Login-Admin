<div align="center">

# 🎯 Outcomes — `trailer_schema.roles`

### Vocabulario único por agente. Fuente: `.claude/orchestrator-contract.json`.

</div>

---

> [!IMPORTANT]
> Esta tabla refleja `orchestrator-contract.json → trailer_schema.roles`. El hook `capture_subagent_stop` carga el schema y no muta lifecycle si el contrato falta o el rol no existe. El test `test_contract_invariants.py` verifica que los enums no diverjan.

---

## Tabla maestra

| Agente | OUTCOME | NEXT_STATUS | Lifecycle | Info-only | Cierre task |
|---|---|---|:---:|:---:|:---:|
| 🔒 **closer** | `committed` ✅ · `blocked` 🚫 | `done` ✅ · `blocked` 🚫 | ✅ muta | — | ✅ |
| 🐛 **debugger** | `fixed` ✅ · `blocked` 🚫 · `failed` ❌ | `validator_tester_pending` 🔄 · `blocked` 🚫 | ✅ muta | — | — |
| 🚀 **deployer** | `deployed` ✅ · `planned` 📋 · `blocked` 🚫 · `failed` ❌ | `done` ✅ · `blocked` 🚫 | ✅ muta | — | — |
| 🔧 **developer** | `success` ✅ · `blocked` 🚫 · `failed` ❌ | `validator_tester_pending` 🔄 · `blocked` 🚫 | ✅ muta | — | — |
| 📄 **document-analyzer** | `valid` ✅ · `invalid` 🚫 | — | — | — | — |
| 🎼 **main-orchestrator** | `ready` ✅ · `blocked` 🚫 | — | — | ℹ️ | — |
| 📚 **official-docs-researcher** | `verified` ✅ · `discrepancy` ⚠️ · `insufficient` ➖ | — | — | ℹ️ | — |
| 🗂 **planner** | `ready` ✅ · `blocked` 🚫 | — | — | ℹ️ | — |
| 🏛 **project-architect** | `ready` ✅ · `blocked` 🚫 | — | — | — | — |
| 📋 **task-planner** | `ready` ✅ · `blocked` 🚫 | — | — | — | — |
| 🧪 **tester** | `pass` ✅ · `fail` ❌ · `blocked` 🚫 | `ready_for_close` 🟢 · `needs_debug` ⚠️ · `blocked` 🚫 | ✅ muta | — | — |
| 🧭 **slice-verifier** | `verified` ✅ · `issues_found` ⚠️ · `blocked` 🚫 | `verified_pending_close` 🟢 · `needs_debug` ⚠️ · `blocked` 🚫 | ✅ muta | — | — |
| 👁️ **screen-journey-reviewer** | `approved` ✅ · `changes_requested` ⚠️ · `blocked` 🚫 | — | — | ℹ️ | — |
| ✅ **validator** | `approved` ✅ · `changes_requested` ⚠️ · `blocked` 🚫 | `ready_for_close` 🟢 · `needs_debug` ⚠️ · `blocked` 🚫 | — | ℹ️ | — |

---

## Por categoría

### 🟢 Lifecycle owners — pueden mutar `task.status`

```mermaid
flowchart LR
    DEV[🔧 developer<br>success → validator_tester_pending]
    TST[🧪 tester<br>pass → ready_for_close<br>fail → needs_debug]
    SV[🧭 slice-verifier<br>verified → verified_pending_close<br>issues_found → needs_debug]
    DBG[🐛 debugger<br>fixed → validator_tester_pending]
    CLO[🔒 closer<br>committed → done]
    DEP[🚀 deployer<br>deployed → done]

    DEV --> TST
    DEV --> DBG
    DBG --> TST
    TST --> SV
    SV --> CLO
    SV --> DBG
    CLO --> DEP

    style DEV fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style TST fill:#1f2740,stroke:#10b981,color:#e8ecf5
    style DBG fill:#1f2740,stroke:#ef4444,color:#e8ecf5
    style CLO fill:#10b98122,stroke:#10b981,color:#10b981
    style DEP fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
```

### ℹ️ Info-only — NO mutan `task.status`

```mermaid
flowchart LR
    VAL[✅ validator<br>approved · changes_requested · blocked]
    ODR[📚 official-docs-researcher<br>verified · discrepancy · insufficient]
    PL[🗂 planner<br>ready · blocked]
    MO[🎼 main-orchestrator<br>ready · blocked]

    VAL -.opina vía OUTCOME.-> CLO[🔒 closer]
    ODR -.warning si discrepancy.-> DEV[🔧 developer]
    PL -.escribe task-pack.-> DEV
    MO -.coordina.-> ALL[todo el ciclo]

    style VAL fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
    style ODR fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
    style PL fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
    style MO fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
```

> [!NOTE]
> **Validator es info-only** intencionalmente. Su `NEXT_STATUS` se guarda como `task.validator_next_status` (metadata) pero NO sobrescribe `task.status`. Esto resuelve la race condition con `tester` cuando ambos cierran a la vez en el par paralelo. El **closer** lee el `OUTCOME` del validator desde el handoff y rechaza el commit si no es `approved`.
>
> **slice-verifier es lifecycle**: `verified` mueve a `verified_pending_close`; `closer` sigue siendo el único rol que puede marcar `done`.

### 📦 Bootstrap — solo se ejecutan al inicio del proyecto

```mermaid
flowchart LR
    DA[📄 document-analyzer<br>valida los 5 docs SOT]
    PA[🏛 project-architect<br>compila contrato técnico]
    TPL[📋 task-planner<br>genera tasks atómicas]

    DA --> PA
    PA --> TPL
    TPL -.entrega.-> RUNTIME[🚀 Runtime DAG]

    style DA fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style PA fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style TPL fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style RUNTIME fill:#10b98122,stroke:#10b981,color:#10b981
```

> [!TIP]
> En AnyStack los 5 documentos SOT son: `instrucciones.md`, `*_TECHNICAL_GUIDE.md`, `*_IMPLEMENTATION_CHECKLIST.md`, `STACK_PROFILE.yaml` y `UX_CONTRACT.md`. Los tres bootstrap agents validan, compilan y atomizan estos cinco documentos antes de que arranque el runtime DAG.

---

## Closer guardrail — el cierre tiene 5 candados

```mermaid
flowchart TD
    T[🔒 closer trailer:<br>OUTCOME: committed<br>NEXT_STATUS: done]
    C1{REPORT_READY: yes?}
    C2{BASELINE_SYNC_READY: yes?}
    C3{GIT_READY: yes?}
    C4{PUSH_READY: yes?}
    C5{WORKTREES_CLEANED: yes?}
    DONE[✅ task.status = done]
    BLOCK[🚫 Hook reescribe<br>NEXT_STATUS: blocked]

    T --> C1
    C1 -- ✅ --> C2
    C1 -- ❌ --> BLOCK
    C2 -- ✅ --> C3
    C2 -- ❌ --> BLOCK
    C3 -- ✅ --> C4
    C3 -- ❌ --> BLOCK
    C4 -- ✅ --> C5
    C4 -- ❌ --> BLOCK
    C5 -- ✅ --> DONE
    C5 -- ❌ --> BLOCK

    style T fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
    style DONE fill:#10b98122,stroke:#10b981,color:#10b981
    style BLOCK fill:#ef444422,stroke:#ef4444,color:#fca5a5
```

> [!CAUTION]
> El guardrail es **mecánico** (`enforce_closer_done_guardrail` en `hook_capture_subagent_stop.py`). No depende de la disciplina del agente. Si el closer intenta `done` sin las 5 pruebas, el hook fuerza `blocked`. Además, el closer rechaza el commit upfront si en el handoff falta `## verify-slice` completo con `VERIFY_OUTCOME: verified` + MCP/datos/evidencia (o `VERIFY_WAIVED: <motivo>`).

---

## 5 documentos SOT — quién edita cada uno

AnyStack añade dos documentos al contrato canónico (vs el contrato histórico de 3 documentos). Cada uno tiene un owner semántico claro:

```mermaid
flowchart TB
    subgraph PROD[👔 Producto]
        I[📝 instrucciones.md<br><sub>scope · journeys · business rules</sub>]
        UX[🎨 UX_CONTRACT.md<br><sub>personas · pantallas · estados UI</sub>]
    end

    subgraph TECH[🛠 Tech lead]
        TG[📐 *_TECHNICAL_GUIDE.md<br><sub>arquitectura · contratos · ADR</sub>]
        SP[🧩 STACK_PROFILE.yaml<br><sub>frameworks · paths · enforcer</sub>]
    end

    subgraph PM[📋 PM / Tech lead]
        CL[📋 *_IMPLEMENTATION_CHECKLIST.md<br><sub>phases · Coverage Registry · DAG</sub>]
    end

    PROD -.alimenta.-> CL
    TECH -.alimenta.-> CL
    CL == bootstrap ==> RUNTIME[🚀 Runtime DAG]

    style PROD fill:#1f2740,stroke:#ec4899,color:#e8ecf5
    style TECH fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style PM fill:#1f2740,stroke:#f59e0b,color:#e8ecf5
    style RUNTIME fill:#10b98122,stroke:#10b981,color:#10b981
```

> [!IMPORTANT]
> El bootstrap **falla** si falta cualquiera de los 5 documentos o si presentan contradicciones (p.ej. una pantalla declarada en UX_CONTRACT que no aparece en el Coverage Registry, o un endpoint del TECHNICAL_GUIDE no referenciado por ninguna task). `document-analyzer` verifica esta consistencia.

---

## Outcomes globales del trailer

Líneas reservadas que el hook reconoce además de `OUTCOME` / `NEXT_STATUS`:

| Línea | Quién la emite | Qué dispara |
|---|---|---|
| `JOURNEY_VERIFIED_INLINE: <JID>` | closer | Marca journey `verified` bajo lock (rama "ahora" §5.bis) |
| `JOURNEY_PENDING_VERIFY: <JID>` | closer | Añade a `pending_journey_verifications` (rama "aparte") |
| `JOURNEY_REVERIFY_RECOMMENDED: <JID>` | closer | Warning, no bloqueante |
| `JOURNEY_VERIFY_OUTCOME: verified\|issues_found` | /verify-journey | Mutar `verification_status` |
| `JOURNEY_VERIFY_WAIVED: <reason>` | /verify-journey | Marca `waived` con razón firmada |
| `REPORT_READY: yes\|no` | closer | Parte del guardrail done |
| `BASELINE_SYNC_READY: yes\|no` | closer | Parte del guardrail done |
| `GIT_READY: yes\|no` | closer | Parte del guardrail done |
| `PUSH_READY: yes\|no` | closer | Parte del guardrail done |
| `WORKTREES_CLEANED: yes\|no` | closer | Parte del guardrail done |

---

## Drift protection

```mermaid
flowchart LR
    SRC[trailer_schema.roles<br>orchestrator-contract.json]
    SCHEMA[trailer_schema.roles<br><i>única fuente</i>]
    HOOK[hook_capture_subagent_stop.py<br>schema-only validation<br><i>no lifecycle mutation if schema missing</i>]
    TEST[test_contract_invariants.py<br>verifica que no diverjan]

    SRC -.archived snapshot.-> MIRROR
    SRC == fuente real ==> HOOK
    TEST -.valida invariante.-> SRC
    TEST -.valida invariante.-> MIRROR
    TEST -.valida carga de schema.-> HOOK

    style SRC fill:#1f2740,stroke:#10b981,color:#10b981
    style MIRROR fill:#1f2740,stroke:#6b7591,color:#6b7591
    style HOOK fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style TEST fill:#1f2740,stroke:#f59e0b,color:#fcd34d
```

> [!TIP]
> Si añades un outcome a un agente, el flujo correcto es:
> 1. Editar `trailer_schema.roles.<agent>.outcome_values` en el JSON
> 2. Editar el agente `.md` para emitir el nuevo outcome
> 3. Correr `pytest .claude/bin/tests/test_contract_invariants.py`
>
> Si el test pasa, todos los espejos están sincronizados.

---

<div align="center">
<sub>
🎯 Outcomes ·
<a href="../../README.md">← README</a> ·
<a href="dag-flujo.md">DAG flujo →</a> ·
<a href="arquitectura.md">Arquitectura →</a> ·
<a href="comandos.md">Comandos →</a>
</sub>
</div>
