<div align="center">

# 📜 Comandos — AnyStack

### Slash commands del orquestador. Cada uno tiene su lugar en el ciclo del slice.

</div>

---

## Ciclo recomendado por slice

```mermaid
flowchart TB
    A[1️⃣ /next-wave] --> B[2️⃣ /next-slice TASK_ID]
    B --> C[3️⃣ /clear<br><sub>libera ~150k tokens</sub>]
    C --> D[4️⃣ /verify-slice TASK_ID]
    D -- ✅ verified --> E[5️⃣ closer<br><sub>commit + git workflow</sub>]
    D -- ❌ issues --> F[debugger]
    F --> B
    E --> G[6️⃣ /slice-maintain clean]
    G --> H[7️⃣ /clear]
    H --> A

    style A fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style B fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
    style C fill:#1f2740,stroke:#6b7591,color:#e8ecf5
    style D fill:#1f2740,stroke:#f59e0b,color:#e8ecf5
    style E fill:#10b98122,stroke:#10b981,color:#10b981
    style F fill:#1f2740,stroke:#ef4444,color:#e8ecf5
    style G fill:#1f2740,stroke:#6b7591,color:#e8ecf5
    style H fill:#1f2740,stroke:#6b7591,color:#e8ecf5
```

---

## 🌊 Scheduler

### `/next-wave`

![Tipo](https://img.shields.io/badge/tipo-scheduler-06b6d4?style=flat-square)
![Side effects](https://img.shields.io/badge/side_effects-none-10b981?style=flat-square)

Lista nodos `ready` seguros e imprime exports copy/paste por terminal. **No hace claim, no muta estado**.

```bash
./scripts/next-wave.sh --limit 4
```

**Imprime:**
```bash
export CLAUDE_ACTIVE_TASK_ID=P02-S03-T001 \
       CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P02-S03-T001.md
```

> [!TIP]
> Excluye nodos que pisan el mismo `Conflict group` o `Write set` que otro nodo ya activo. Si quieres ver TODOS los ready (incluidos los que se serializarían), añade `--unsafe`.

---

## 🔧 Pipeline de slice

### `/next-slice TASK_ID`

![Tipo](https://img.shields.io/badge/tipo-pipeline-8b5cf6?style=flat-square)
![Spawns](https://img.shields.io/badge/max_spawns-20-f59e0b?style=flat-square)

Claim atómico + pipeline completo hasta tester pass. **No invoca closer directamente** — pausa en tester pass para que tú lances `/verify-slice`. `/verify-slice` delega la verificación humana en `slice-verifier`, que requiere Chrome DevTools MCP, claude-in-chrome o Agent360 Browser MCP (`browser-mcp`) para poder cerrar.

```mermaid
flowchart LR
    A[planner<br><sub>blocking</sub>] --> B[developer + docs-researcher opcional]
    B --> C[validator ‖ tester]
    C -- pass --> D[⏸ pause<br>→ /verify-slice]
    C -- fail --> E[debugger<br><sub>máx 3 ciclos</sub>]
    E --> C

    style A fill:#1f2740,stroke:#8b5cf6,color:#e8ecf5
    style B fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style C fill:#1f2740,stroke:#10b981,color:#e8ecf5
    style D fill:#1f2740,stroke:#f59e0b,color:#fcd34d
    style E fill:#1f2740,stroke:#ef4444,color:#e8ecf5
```

> [!NOTE]
> En DAG-only, `runtime-state.pending_journey_verifications` difiere sólo las tasks que referencian esos journeys. Las ramas independientes pueden seguir; las tasks afectadas deben resolver el journey gate inline en `/verify-slice §5.bis` o aparte con `/verify-journey`.

---

## 👤 Gates humanos

### `/verify-slice TASK_ID`

![Tipo](https://img.shields.io/badge/tipo-gate_humano-f59e0b?style=flat-square)
![Datos](https://img.shields.io/badge/datos-reales_proporcionados-ec4899?style=flat-square)

Verificación con datos reales del `Verification Data Contract` definido en el `*_TECHNICAL_GUIDE.md`. Reset controlado, carga de datos reales/proporcionados y reproducción humana usando el método declarado en `STACK_PROFILE.frontend.visual_check` (browser, emulador, simulador, device), logs vivos.

**Acciones según resultado:**

| Resultado | Acción |
|---|---|
| ✅ `verified` sin journey | Spawnea `closer` |
| ✅ `verified` cierra journey | Pregunta: verify-journey **inline** o **aparte** (§5.bis) |
| ⚠️ Hallazgos menores en scope | Llama `debugger`, repite `validator ‖ tester`, re-verifica |
| ❌ Hallazgos mayores fuera scope | Registra follow-up formal con `register-followup propose` |

> [!IMPORTANT]
> El closer **no commitea sin** `## verify-slice` completo con `VERIFY_OUTCOME: verified` + MCP/datos/evidencia en el handoff. Único waiver: `VERIFY_WAIVED: <motivo>` firmado por humano explícitamente. `/verify-slice` es resiliente al `/clear`: reconstruye el contexto desde disco (PROGRESS.md, runtime-state, registry, handoff, TECHNICAL_GUIDE).

---

### Journey verify §5.bis — inline vs aparte

Cuando una slice cierra al menos un journey de `registry.journeys[]` y `VERIFY_OUTCOME: verified`, el comando pregunta al usuario qué hacer:

```mermaid
flowchart TD
    A[/verify-slice<br>VERIFY_OUTCOME: verified/] --> B{¿Cierra journey?}
    B -- No --> Z[closer commit normal]
    B -- Sí --> C{Pregunta al usuario}
    C -- "ahora" inline --> D[Verifica journey<br>aprovechando entorno reseteado]
    D --> E["## verify-journey<br>en MISMO handoff<br>JOURNEY_VERIFY_OUTCOME: verified"]
    E --> F[closer emite<br>JOURNEY_VERIFIED_INLINE: JID]
    F --> Z
    C -- "aparte" --> G[closer emite<br>JOURNEY_PENDING_VERIFY: JID]
    G --> H[runtime-state.pending_journey_verifications<br>+= JID]
    H --> I[planner BLOQUEA<br>/next-slice hasta resolver]
    I --> J[/verify-journey JID/<br>aparte]

    style A fill:#1f2740,stroke:#f59e0b,color:#e8ecf5
    style D fill:#10b98122,stroke:#10b981,color:#10b981
    style F fill:#10b98122,stroke:#10b981,color:#10b981
    style G fill:#1f2740,stroke:#ec4899,color:#e8ecf5
    style I fill:#ef444422,stroke:#ef4444,color:#fca5a5
```

> [!TIP]
> La rama "ahora" evita el doble gate: aprovecha el entorno ya reseteado y los datos reales/proporcionados cargados, apendiza `## verify-journey` al **mismo handoff** del slice (no usa `journey-handoffs/`). El closer reconoce `JOURNEY_VERIFIED_INLINE` y el SubagentStop hook marca el journey como `verified` bajo lock, sin añadirlo a `pending_journey_verifications`.

---

### `/verify-journey JID`

![Tipo](https://img.shields.io/badge/tipo-gate_E2E-ec4899?style=flat-square)
![Manual](https://img.shields.io/badge/uso-rescate_manual-6b7591?style=flat-square)

Gate end-to-end multi-pantalla. Reproducción del journey completo + estados marginales (empty, error_network, permission_denied, deep_link, back, reload).

> [!NOTE]
> En el flujo normal, los journeys se verifican **inline** en `/verify-slice §5.bis`. Este comando queda dormido salvo para waivers, re-verificaciones aisladas o cuando el usuario eligió "aparte" en §5.bis.

---

## ⚡ Auto-verify

### `/auto-verify-slice TASK_ID`

![Tipo](https://img.shields.io/badge/tipo-auto-10b981?style=flat-square)
![Restringido](https://img.shields.io/badge/solo-low+auto-f59e0b?style=flat-square)
![Sin journey](https://img.shields.io/badge/no_cierra-journey-ef4444?style=flat-square)

Verificación automática **solo si** la slice cumple TODAS las condiciones:

- ✅ `Risk level=low` declarado en Coverage Registry
- ✅ `Verify mode=auto` declarado en Coverage Registry
- ✅ NO cierra journey
- ✅ Tiene comando determinista en `Verify mínimo`
- ✅ Produce handoff y evidence

> [!CAUTION]
> Si el agente intenta auto-verify sobre una slice que cierra journey, toca auth, pagos o PII, **rechaza** y fuerza `/verify-slice` humano. El gate es estructural, no opcional.

---

## 🛑 Phase gate

### `/phase-gate Pxx`

![Tipo](https://img.shields.io/badge/tipo-phase_gate-ef4444?style=flat-square)
![Bloqueante](https://img.shields.io/badge/bloqueante-sí-ef4444?style=flat-square)

Verifica **mecánicamente** que una phase está cerrada antes de avanzar a la siguiente.

```mermaid
flowchart TD
    P[/phase-gate Pxx/] --> C1{Tasks done?}
    C1 -- No --> X[🚫 BLOQUEA]
    C1 -- Sí --> C2{Reports + evidence + handoffs?}
    C2 -- Falta alguno --> X
    C2 -- OK --> C3{Journeys verified/waived?}
    C3 -- pending no vacío --> X
    C3 -- OK --> C4{Follow-ups high+ resueltos?}
    C4 -- No --> X
    C4 -- Sí --> C5{Git limpio?<br><sub>opcional</sub>}
    C5 -- No --> X
    C5 -- Sí --> OK[✅ Phase cerrada]

    style P fill:#1f2740,stroke:#ef4444,color:#e8ecf5
    style X fill:#ef444422,stroke:#ef4444,color:#fca5a5
    style OK fill:#10b98122,stroke:#10b981,color:#10b981
```

```bash
./scripts/phase-gate.sh P03
./scripts/phase-gate.sh P03 --require-git-clean
```

---

## 📋 Backlog dinámico

### `/register-followup`

![Tipo](https://img.shields.io/badge/tipo-backlog-3b82f6?style=flat-square)

Convierte hallazgos de QA en task DAG real persistida en source-of-truth.

```mermaid
flowchart LR
    A[Validator/tester/verify<br>encuentra trabajo nuevo] --> B[propose<br>YAML proposal]
    B --> C{Severidad}
    C -- high/critical/blocker --> D[🚫 Bloquea<br>nuevas waves]
    C -- medium/low --> E[Backlog visible]
    D --> F[Decisión humana]
    E --> F
    F -- promote --> G[Task DAG real<br>+ source-of-truth amendment]
    F -- waive --> H[Documentado<br>+ razón]

    style A fill:#1f2740,stroke:#3b82f6,color:#e8ecf5
    style B fill:#1f2740,stroke:#06b6d4,color:#e8ecf5
    style D fill:#ef444422,stroke:#ef4444,color:#fca5a5
    style G fill:#10b98122,stroke:#10b981,color:#10b981
    style H fill:#1f2740,stroke:#6b7591,color:#e8ecf5
```

**Subcomandos:**

| Subcomando | Qué hace |
|---|---|
| `propose` | Crea YAML en `orchestrator-state/tasks/follow-ups/` |
| `promote` | Promociona a task DAG real, actualiza source-of-truth + registry + DAG |
| `waive` | Documenta decisión de no implementar con razón firmada |
| `list` | Lista propuestas abiertas (con `--json` para machine-readable) |

```bash
./scripts/register-followup-task.sh propose \
  --origin-task P02-S03-T001 \
  --severity high \
  --kind ux \
  --title "Estado empty real en ResultsPage" \
  --acceptance "Empty state con datos sandbox persistidos" \
  --verify "/verify-slice observa estado empty con cuenta sandbox"
```

---

## 🔄 Corrección

### `/revise-slice TASK_ID "motivo"`

![Tipo](https://img.shields.io/badge/tipo-correctivo-6b7591?style=flat-square)

Reabre slice canónica sin cambiar el DAG ni crear IDs temporales. Útil cuando aparece un bug menor tras el cierre. Mantiene `TASK_ID`, memoria, DAG, journeys y cableado; corrige, revalida, re-verify y closer correctivo con commit + push.

---

## 🧹 Mantenimiento

### `/slice-maintain clean | compact`

![Tipo](https://img.shields.io/badge/tipo-housekeeping-6b7591?style=flat-square)

Housekeeping entre slices. Dry-run obligatorio por defecto.

```mermaid
flowchart LR
    SM[/slice-maintain/] --> A{subcomando}
    A -- clean --> CL[Limpieza conservadora<br>de artefactos regenerables<br><sub>preserva 2-3 últimas slices</sub>]
    A -- compact --> CP[Compactación PROGRESS.md]
    CP --> S1[Snapshot previo]
    S1 --> S2[Promueve decisions+risks<br>a ficheros canónicos]
    S2 --> S3[Verifica post-compact]
    S3 -- OK --> DONE[✅ Compactado]
    S3 -- falta info crítica --> ROLL[🔄 Restore desde snapshot<br>+ aborta]

    style SM fill:#1f2740,stroke:#6b7591,color:#e8ecf5
    style CP fill:#1f2740,stroke:#f59e0b,color:#e8ecf5
    style DONE fill:#10b98122,stroke:#10b981,color:#10b981
    style ROLL fill:#ef444422,stroke:#ef4444,color:#fca5a5
```

| Subcomando | Qué hace |
|---|---|
| `clean` | Limpia worktrees `done`, ledger entries antiguas, orphan task-packs |
| `compact` | Compacta `PROGRESS.md` preservando últimas N slices, decisions, risks, commit SHAs y must-carry bullets |

> [!TIP]
> `compact` se ejecuta solo bajo gate humano y con verificación post-compact obligatoria. Si detecta que algún elemento crítico falta tras compactar, restaura desde snapshot y aborta. **Nunca pierde información crítica.**

---

## Resumen visual

| Comando | Cuándo | Bloquea | Muta estado |
|---|---|---|---|
| `/next-wave` | Antes de empezar slice | — | — |
| `/next-slice` | Empezar pipeline | Si quedan pending journeys o blocking follow-ups | ✅ claim |
| `/verify-slice` | Tras tester pass | Si falta MCP browser / datos / evidencia | ✅ via `slice-verifier` + closer |
| `/auto-verify-slice` | Solo low+auto | Si cierra journey o riesgo > low | ✅ via closer |
| `/verify-journey` | Manual / waiver | — | ✅ status journey |
| `/phase-gate` | Cierre de phase | Si faltan tasks/journeys/evidence | — |
| `/register-followup` | QA descubre trabajo nuevo | Severidad high+ bloquea waves | ✅ source-of-truth |
| `/revise-slice` | Bug post-cierre | — | ✅ revisión |
| `/slice-maintain` | Entre slices | — | Limpieza |

---

<div align="center">
<sub>
📜 Comandos ·
<a href="../../README.md">← README</a> ·
<a href="dag-flujo.md">DAG flujo →</a> ·
<a href="arquitectura.md">Arquitectura →</a> ·
<a href="outcomes.md">Outcomes →</a>
</sub>
</div>
