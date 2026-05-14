<div align="center">

# 🔀 Flujo DAG — AnyStack

### Cómo se desbloquean nodos, qué serializa el scheduler, cómo cooperan terminales paralelos.

</div>

---

## 1. El DAG se deriva, no se escribe a mano

```mermaid
flowchart LR
    A[📋 Coverage Registry<br><sub>Depends on · Conflict group · Write set</sub>]
    B[⚙️ bootstrap_source_of_truth.py]
    C["🗂 registry.json<br>tasks[] + task_dag"]
    D[task-dag.json]
    E[task-dag.md]
    F[execution-graph.json]

    A --> B
    B --> C
    C --> D
    C --> E
    C --> F

    style A fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
    style B fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style C fill:#1f2740,stroke:#10b981,color:#e8ecf5
    style D fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
    style E fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
    style F fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
```

> [!IMPORTANT]
> La **única fuente editable** es la columna `Depends on` del Coverage Registry en `*_IMPLEMENTATION_CHECKLIST.md`. Editar a mano `task-dag.json` o `registry.json` está bloqueado por el hook `write_scope_guard`. Para cambiar ordenación o paralelismo: edita `Depends on` / `Conflict group` / `Write set` y rerun `bootstrap_source_of_truth.py --refresh` + `scripts/check-task-dag.sh --strict`.

---

## 2. Join real con dos roots independientes

Un join solo se desbloquea cuando **todos** sus predecessors están `done`.

```mermaid
flowchart LR
    A[Terminal A<br>P00-S01-T001<br>✅ done]
    B[Terminal B<br>P00-S01-T003<br>⏳ in_progress]
    J[JOIN<br>P00-S02-T001<br>🚫 blocked]
    N[successor<br>...<br>—]

    A --> J
    B --> J
    J --> N

    style A fill:#10b98122,stroke:#10b981,color:#10b981
    style B fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style J fill:#f59e0b22,stroke:#f59e0b,color:#fcd34d
    style N fill:#1f2740,stroke:#6b7591,color:#6b7591
```

> [!WARNING]
> Mientras `Terminal B` no cierre `P00-S01-T003`, **`/next-wave` no puede proponer `P00-S02-T001` aunque `Terminal A` ya esté libre**. `claim_task.py` deniega el claim si las deps no están `done` o si hay conflicto activo por `Conflict group` / `Write set`.

Cuando `Terminal B` cierra:

```mermaid
flowchart LR
    A[Terminal A<br>P00-S01-T001<br>✅ done]
    B[Terminal B<br>P00-S01-T003<br>✅ done]
    J[JOIN<br>P00-S02-T001<br>🟢 ready]
    N[successor<br>...<br>—]

    A --> J
    B --> J
    J --> N

    style A fill:#10b98122,stroke:#10b981,color:#10b981
    style B fill:#10b98122,stroke:#10b981,color:#10b981
    style J fill:#06b6d422,stroke:#06b6d4,color:#67e8f9
    style N fill:#1f2740,stroke:#6b7591,color:#6b7591
```

---

## 3. Conflict groups y Write sets — serialización segura

Dos slices **independientes en el grafo** (no comparten `depends_on`) pueden serializarse igualmente si pisan el mismo recurso.

```mermaid
flowchart LR
    M1[P03-S01-T001<br>migration auth<br>db:migrations]
    M2[P03-S02-T001<br>migration profile<br>db:migrations]
    A[P03-S01-T002<br>endpoint /auth<br>api:auth]
    P[P03-S02-T002<br>endpoint /profile<br>api:profile]

    M1 -.serializa.- M2
    M1 --> A
    M2 --> P

    style M1 fill:#1f2740,stroke:#f59e0b,color:#e8ecf5
    style M2 fill:#1f2740,stroke:#f59e0b,color:#e8ecf5
    style A fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style P fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
```

> [!TIP]
> M1 y M2 no dependen una de otra, pero ambas declaran `Conflict group: db:migrations`. `/next-wave` propondrá una sola en cada wave para evitar conflictos en `alembic/versions/` (o el equivalente del stack declarado en `STACK_PROFILE.yaml`).

### Recursos típicos serializados (varían por stack)

| Recurso | Conflict group | Write set típico |
|---|---|---|
| Migraciones DB | `db:migrations` | `api/alembic/versions/**` (o equivalente del stack) |
| Router frontend | `front:router` | `<frontend_router_path>`, `src/router/**` |
| API client global | `front:api-client` | `<frontend_api_client_glob>`, `src/api/**` |
| Theme / design tokens | `front:theme` | rutas declaradas en `STACK_PROFILE.frontend.theme_root` |
| Auth backend | `api:auth` | `<backend_auth_glob>` |
| Workflow CI | `ci` | `.github/workflows/**` |
| Dependencias | `deps` | `<dependency_manifest>`, `<lockfile>` |

---

## 4. Coordinación entre terminales — sin push notifications

```mermaid
sequenceDiagram
    participant TA as 💻 Terminal A
    participant TB as 💻 Terminal B
    participant H as 🪝 capture_subagent_stop
    participant R as 🗂 registry.json
    participant RS as 🗂 runtime-state.json

    TA->>TA: closer emite trailer<br>OUTCOME: committed
    TA->>H: SubagentStop event
    H->>R: lock + set status=done
    H->>RS: lock + last_worker=closer
    Note over R,RS: orden registry → runtime-state
    H->>R: promote_ready_tasks<br>(successors → ready)
    TB->>TB: termina su slice actual
    TB->>R: ./scripts/next-wave.sh
    R-->>TB: lista nueva frontera<br>(incluye ex-successor)
    TB->>TB: export CLAUDE_ACTIVE_TASK_ID=...<br>/next-slice ...
```

> [!NOTE]
> **No hay notificación viva entre terminales.** `Terminal B` no se interrumpe cuando `Terminal A` cierra; debe **volver a invocar `/next-wave`** para ver la nueva frontera del DAG. Cada terminal lleva su propio `CLAUDE_ACTIVE_TASK_ID` en el entorno y los hooks scopean automáticamente ledger / spawn budget / handoffs a ese ID.

---

## 5. Lock order — siempre registry primero

```mermaid
flowchart TD
    L1[1️⃣ Adquirir lock registry.json]
    L2[2️⃣ Modificar registry]
    L3[3️⃣ Adquirir lock runtime-state.json]
    L4[4️⃣ Modificar runtime-state]
    L5[5️⃣ Liberar runtime-state]
    L6[6️⃣ Liberar registry]

    L1 --> L2 --> L3 --> L4 --> L5 --> L6

    style L1 fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
    style L3 fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style L5 fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style L6 fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
```

> [!CAUTION]
> El orden global del proyecto es **registry → runtime-state**. Invertirlo abre una ventana de deadlock cuando dos hooks cierran en paralelo (validator + tester finalizando a la vez). `claim_task.py` y `hook_capture_subagent_stop.py` mantienen el mismo orden de adquisición. En Windows, `fcntl.flock` se convierte en no-op — el framework está diseñado para POSIX.

---

## 6. Reglas duras del scheduler

| Regla | Garantizada por |
|---|---|
| Un nodo solo pasa a `ready` si **todas** sus deps están `done` | `promote_ready_tasks` en `common.py` |
| `claim_task.py` deniega claim si hay conflicto activo | Lock POSIX + chequeo de `Conflict group` / `Write set` |
| Joins esperan a **todos** sus predecessors, no a uno solo | Algoritmo de promoción topológica |
| Follow-ups bloqueantes (`high\|critical\|blocker`) bloquean nuevas waves | `register_followup_task.py` + hook |
| `phase-gate` bloquea si quedan tasks sin `done`, journeys sin verificar o evidence ausente | `phase-gate.sh` + `check_phase_gate.py` |
| El closer no puede marcar `done` sin commit + push + cleanup | `enforce_closer_done_guardrail` en hook |
| `pending_journey_verifications` se evalúa por frontera | DAG-only difiere solo tasks con `Journey refs` pendientes |

---

## 7. Follow-ups formales — no hay notas sueltas

Cuando validator/tester/verify descubren trabajo fuera del scope del `TASK_ID` actual, no se queda en el handoff como prosa: se convierte en propuesta YAML que regenera el DAG.

```mermaid
flowchart LR
    A[Validator/tester/verify<br>encuentra trabajo nuevo] --> B[register-followup propose<br>YAML proposal]
    B --> C{Severidad}
    C -- high/critical/blocker --> D[🚫 Bloquea<br>nuevas waves · claim · closer]
    C -- medium/low --> E[Backlog visible]
    D --> F[Decisión humana]
    E --> F
    F -- promote --> G[bootstrap-refresh<br>+ DAG rebuild<br>+ work-items YAML]
    F -- waive --> H[Documentado<br>+ razón firmada]

    style A fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
    style B fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style D fill:#ef444422,stroke:#ef4444,color:#fca5a5
    style G fill:#10b98122,stroke:#10b981,color:#10b981
    style H fill:#1f2740,stroke:#6b7591,color:#e8ecf5
```

> [!NOTE]
> `promote` apendiza una fila al `Runtime Follow-up Coverage Registry` del checklist, actualiza `registry.json`, regenera la adyacencia DAG, escribe `work-items/<TASK_ID>.yaml`, y actualiza `runtime-state` + `ledger` bajo locks. Las propuestas `high|critical|blocker` bloquean `/next-wave`, `claim_task.py` y closer `done` hasta que estén promotadas o waiveadas con firma humana explícita.

---

<div align="center">
<sub>
🔀 DAG · 🪝 Hooks · 🔒 Locks POSIX ·
<a href="../../README.md">← README</a> ·
<a href="arquitectura.md">Arquitectura →</a> ·
<a href="comandos.md">Comandos →</a> ·
<a href="outcomes.md">Outcomes →</a>
</sub>
</div>
