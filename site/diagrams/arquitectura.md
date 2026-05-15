<div align="center">

# 🛠 Arquitectura — AnyStack

### Cinco documentos source-of-truth, hooks, locks, memoria runtime y trailers tipados — agnóstico de stack.

</div>

---

## 1. Vista de alto nivel

A diferencia del orquestador histórico de tres documentos, **AnyStack añade `STACK_PROFILE.yaml` y `UX_CONTRACT.md`** para desacoplar el motor del stack concreto y de la experiencia de usuario.

```mermaid
flowchart TB
    subgraph SOT[📚 Source of truth · 5 documentos canónicos]
        I[📝 instrucciones.md<br><sub>scope · journeys</sub>]
        TG[📐 *_TECHNICAL_GUIDE.md<br><sub>arquitectura · contratos · ADR</sub>]
        CL[📋 *_IMPLEMENTATION_CHECKLIST.md<br><sub>phases · Coverage Registry · DAG</sub>]
        SP[🧩 STACK_PROFILE.yaml<br><sub>frameworks · paths · enforcer</sub>]
        UX[🎨 UX_CONTRACT.md<br><sub>personas · pantallas · estados</sub>]
    end

    subgraph DERIVED[🗂 Estado derivado · solo bootstrap/hooks bajo lock]
        REG[registry.json<br><b>canónico runtime</b>]
        DAG[task-dag.json/.md<br><sub>vista derivada</sub>]
        EG[execution-graph.json<br><sub>vista derivada</sub>]
        WI[work-items/*.yaml<br><sub>per-task</sub>]
    end

    subgraph RUNTIME[⚙️ Runtime · escritura por hooks bajo lock]
        RS[runtime-state.json<br><sub>last worker · pending journeys</sub>]
        LED[ledger.jsonl<br><sub>append-only por TASK_ID</sub>]
        TP[task-packs/*.md<br><sub>contexto por TASK_ID</sub>]
    end

    subgraph AGENTS[🤖 12 agentes · escritura limitada por contrato]
        DEV[developer]
        VAL[validator]
        TST[tester]
        DBG[debugger]
        CLO[closer]
    end

    subgraph WRITES[📤 Escrituras de agentes]
        HO[handoffs/*.md<br><sub>append-only</sub>]
        EV[evidence/*]
        REP[reports/*.md]
    end

    SOT == bootstrap_source_of_truth.py ==> REG
    REG --> DAG
    REG --> EG
    REG --> WI
    REG -.escritura por hooks.-> RS
    REG -.escritura por hooks.-> LED
    REG -.proyecta a.-> TP

    DEV --> HO
    VAL --> HO
    TST --> HO
    DBG --> HO
    CLO --> REP
    DEV --> EV
    TST --> EV

    style SOT fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
    style DERIVED fill:#161c2e,stroke:#06b6d4,color:#e8ecf5
    style RUNTIME fill:#161c2e,stroke:#10b981,color:#e8ecf5
    style AGENTS fill:#161c2e,stroke:#ec4899,color:#e8ecf5
    style WRITES fill:#161c2e,stroke:#3b82f6,color:#e8ecf5
```

> [!IMPORTANT]
> **Sólo los 5 documentos en `docs/source-of-truth/` son editables a mano.** Todo lo demás se deriva o lo escriben hooks bajo lock POSIX. El hook `write_scope_guard` bloquea mecánicamente cualquier intento de editar a mano `registry.json`, `task-dag.*`, `runtime-state.json`, `ledger.jsonl` o `execution-graph.json` mientras hay un `TASK_ID` activo.

---

## 2. Hooks — el sistema nervioso

```mermaid
flowchart LR
    subgraph PRE[PreToolUse]
        SB[spawn_budget<br><sub>máx 20 spawns/slice</sub>]
        WG[write_scope_guard<br><sub>bloquea cross-task writes</sub>]
        DD[docs_discrepancy<br><sub>warn si official-doc-notes</sub>]
    end

    subgraph POST[PostToolUse]
        UL[update_ledger<br><sub>append a ledger.jsonl</sub>]
    end

    subgraph STOP[SubagentStop]
        CSS[capture_subagent_stop<br><sub>parsea trailer · valida · muta registry</sub>]
    end

    subgraph START[SessionStart]
        SC[session_context<br><sub>injecta estado al primer turn</sub>]
    end

    PRE -.bloquea o avisa.-> AGENT[🤖 Agente]
    AGENT -.consume.-> POST
    AGENT -.cierre.-> STOP
    START -.contexto inicial.-> AGENT

    style PRE fill:#1f2740,stroke:#f59e0b,color:#e8ecf5
    style POST fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
    style STOP fill:#1f2740,stroke:#10b981,color:#e8ecf5
    style START fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
```

| Hook | Cuándo dispara | Qué hace |
|---|---|---|
| `spawn_budget` | Antes de cualquier `Agent` | Bloquea si la slice ya consumió **20 spawns** (`permissionDecision: deny`). |
| `write_scope_guard` | Antes de `Write/Edit/MultiEdit/NotebookEdit` | Bloquea cross-`TASK_ID`, mutaciones a derivado y edición de source-of-truth con TASK_ID activo. |
| `docs_discrepancy` | Antes de `Write/Edit` | Warn si hay `orchestrator-state/memory/official-doc-notes/*.md` sin `RESOLVED:`. **Nunca bloquea.** |
| `update_ledger` | Después de `Bash/Write/Edit/MultiEdit/NotebookEdit` | Append append-only a `ledger.jsonl` con scope `CLAUDE_ACTIVE_TASK_ID`. |
| `capture_subagent_stop` | Al cerrar un subagente | Parsea trailer, valida `OUTCOME/NEXT_STATUS`, muta `registry.json` + `runtime-state.json` bajo lock POSIX. |
| `session_context` | Al arrancar sesión Claude Code | Inyecta el estado canónico (DAG task, phase, pending journeys, hook errors) al primer turn. |

---

## 3. Memoria runtime — qué vive dónde

```mermaid
flowchart TD
    subgraph PERSISTENT[🗃 Persistente · sobrevive a /clear]
        SOT[docs/source-of-truth/<br><sub>5 documentos editables</sub>]
        REG[orchestrator-state/tasks/registry.json<br><sub>canónico runtime</sub>]
        AM[orchestrator-state/agent-memory/<br><sub>memoria por agente</sub>]
        BL[docs/product-baseline/<br><sub>baseline acumulativo</sub>]
    end

    subgraph SESSION[🔄 Sesión · puede repoblar]
        TP[task-packs/*.md<br><sub>contexto por TASK_ID</sub>]
        TP[task-packs/&lt;TASK_ID&gt;.md<br><sub>per-task DAG pack</sub>]
    end

    subgraph EPHEMERAL[💨 Efímero · regenerable]
        DAG[task-dag.json/.md]
        EG[execution-graph.json]
        WI[work-items/*.yaml]
        RS[runtime-state.json]
        LED[ledger.jsonl]
    end

    SOT == bootstrap ==> REG
    REG --> DAG
    REG --> EG
    REG --> WI
    REG --> TP

    style PERSISTENT fill:#1f2740,stroke:#10b981,color:#e8ecf5
    style SESSION fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style EPHEMERAL fill:#1f2740,stroke:#6b7591,color:#e8ecf5
```

> [!TIP]
> En modo DAG explícito, `CLAUDE_ACTIVE_TASK_ID` + `CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/<TASK_ID>.md` son la fuente autoritativa. cada terminal usa su task pack por `TASK_ID`.

---

## 4. STACK_PROFILE → enforcer plugin pattern

AnyStack desacopla el motor del stack vía un patrón de plugin: `STACK_PROFILE.yaml` declara qué enforcer de design tokens aplicar y dónde están los paths del proyecto.

```mermaid
flowchart LR
    SP[🧩 STACK_PROFILE.yaml<br><sub>frontend · backend · db · git_workflow</sub>]
    DTE[design_tokens_enforcer<br><sub>plugin name</sub>]
    TR[frontend.theme_root<br><sub>módulo de tokens</sub>]
    PLUG[.claude/enforcers/&lt;plugin&gt;.sh<br><sub>script ejecutable</sub>]
    RULES[.claude/enforcers/&lt;plugin&gt;/RULES.md<br><sub>política de violaciones</sub>]
    SCAN[scanner stack-aware<br><sub>framework específico · react · vue · ...</sub>]

    SP --> DTE
    SP --> TR
    DTE --> PLUG
    PLUG --> RULES
    PLUG --> SCAN
    TR --> SCAN

    style SP fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
    style DTE fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style PLUG fill:#1f2740,stroke:#10b981,color:#e8ecf5
    style RULES fill:#1f2740,stroke:#f59e0b,color:#fcd34d
    style SCAN fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
```

> [!NOTE]
> El plugin recomendado por defecto es `design_tokens_v1`, que lee `frontend.framework` y aplica el escaneo específico (framework declarado). `design_tokens_enforcer: none` es válido solo cuando el proyecto deshabilita la enforcement de visual tokens **explícitamente** y deja el trade-off documentado en source-of-truth.

---

## 5. Trailer schema — fuente única de outcomes

```mermaid
flowchart LR
    AGENT[🤖 Agente emite trailer]
    HOOK[🪝 capture_subagent_stop]
    SCHEMA[📜 trailer_schema.roles<br><sub>orchestrator-contract.json</sub>]
    SCHEMA_ERR[⚠️ schema missing<br><sub>log visible + no lifecycle mutation</sub>]
    REG[🗂 registry.json]

    AGENT --> HOOK
    HOOK --> SCHEMA
    SCHEMA -.no responde.-> SCHEMA_ERR
    HOOK -- valida y muta --> REG

    style AGENT fill:#1f2740,stroke:#ec4899,color:#e8ecf5
    style HOOK fill:#1f2740,stroke:#10b981,color:#e8ecf5
    style SCHEMA fill:#1f2740,stroke:#8b5cf6,color:#c4b5fd
    style SCHEMA_ERR fill:#1f2740,stroke:#6b7591,color:#6b7591
    style REG fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
```

El JSON declara para cada agente:

```json
{
  "trailer_schema": {
    "roles": {
      "tester": {
        "outcome_values": ["pass", "fail", "blocked"],
        "next_status_values": ["ready_for_close", "needs_debug", "blocked"],
        "info_only": false,
        "mutates_registry_lifecycle": true,
        "allowed_to_close_task": false,
        "required_keys": ["TASK_ID", "OUTCOME", "NEXT_STATUS"]
      },
      "validator": {
        "outcome_values": ["approved", "changes_requested", "blocked"],
        "info_only": true,
        "mutates_registry_lifecycle": false
      }
    }
  }
}
```

---

## 6. Closer guardrail — por qué no se puede mentir

```mermaid
flowchart TD
    CLO[🔒 closer]
    T[Trailer:<br>OUTCOME: committed<br>NEXT_STATUS: done]
    GR{¿Todos en yes?<br>REPORT_READY<br>BASELINE_SYNC_READY<br>GIT_READY<br>PUSH_READY<br>WORKTREES_CLEANED}
    DONE[✅ task.status = done]
    BLOCKED[🚫 Hook fuerza<br>NEXT_STATUS: blocked]

    CLO --> T
    T --> GR
    GR -- ✅ todos yes --> DONE
    GR -- ❌ alguno no --> BLOCKED

    style CLO fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
    style T fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style GR fill:#161c2e,stroke:#f59e0b,color:#fcd34d
    style DONE fill:#10b98122,stroke:#10b981,color:#10b981
    style BLOCKED fill:#ef444422,stroke:#ef4444,color:#fca5a5
```

> [!CAUTION]
> El guardrail está en `enforce_closer_done_guardrail()` en `hook_capture_subagent_stop.py`. Si el closer intenta marcar `done` sin las pruebas, el hook reescribe el trailer a `blocked`. Es **mecánico**, no basado en el prompt del agente. Además, el closer rechaza el commit si en el handoff falta `## verify-slice` completo con `VERIFY_OUTCOME: verified` + MCP/datos/evidencia (o `VERIFY_WAIVED: <motivo>`).

---

## 7. 12 agentes especializados

```mermaid
flowchart LR
    subgraph BOOTSTRAP[Bootstrap · una vez por proyecto]
        DA[document-analyzer]
        PA[project-architect]
        TPL[task-planner]
    end

    subgraph LIFECYCLE[Lifecycle · ciclo del slice]
        PL[planner]
        DEV[developer]
        ODR[official-docs-researcher]
        VAL[validator]
        TST[tester]
        DBG[debugger]
        CLO[closer]
    end

    subgraph SPECIAL[Especializado]
        DEP[deployer]
        MO[main-orchestrator]
    end

    BOOTSTRAP -.una vez.-> LIFECYCLE
    LIFECYCLE -.cuando aplique.-> SPECIAL

    style BOOTSTRAP fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style LIFECYCLE fill:#1f2740,stroke:#10b981,color:#e8ecf5
    style SPECIAL fill:#1f2740,stroke:#f59e0b,color:#e8ecf5
```

[**→ Ver outcomes y vocabulario por agente**](outcomes.md)

---

## 8. Concurrencia real, no decorativa

Cuando `validator` y `tester` cierran a la vez, hay race condition por defecto. AnyStack la resuelve por contrato: solo uno es lifecycle owner, el otro queda como info-only.

```mermaid
sequenceDiagram
    participant V as ✅ validator
    participant T as 🧪 tester
    participant H1 as 🪝 hook (validator)
    participant H2 as 🪝 hook (tester)
    participant L as 🔒 fcntl.flock
    participant R as 🗂 registry.json

    par validator y tester en paralelo
        V->>H1: SubagentStop<br>OUTCOME: approved
        T->>H2: SubagentStop<br>OUTCOME: pass
    end

    H1->>L: file_lock(registry)
    L-->>H1: 🔓 acquired
    Note over H1,R: validator es info-only<br>solo escribe metadata
    H1->>R: task.validator_outcome = approved
    H1->>L: 🔒 release

    H2->>L: file_lock(registry)
    L-->>H2: 🔓 acquired
    Note over H2,R: tester decide lifecycle
    H2->>R: task.status = ready_for_close
    H2->>L: 🔒 release
```

> [!NOTE]
> **El validator no toca `task.status`**. Su `NEXT_STATUS` se guarda como `validator_next_status` (metadata informativa). Esto elimina la race condition cuando ambos cierran a la vez en el par paralelo. El **closer** lee el `OUTCOME` del validator desde el handoff antes de cerrar y rechaza el commit si no es `approved`. La clasificación info-only/lifecycle vive sólo en `.claude/orchestrator-contract.json -> trailer_schema.roles` y el hook la deriva de ese schema; no hay whitelist hardcodeada.

---

<div align="center">
<sub>
🛠 Arquitectura ·
<a href="../../README.md">← README</a> ·
<a href="dag-flujo.md">DAG flujo →</a> ·
<a href="comandos.md">Comandos →</a> ·
<a href="outcomes.md">Outcomes →</a>
</sub>
</div>
