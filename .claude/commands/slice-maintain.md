---
description: Mantenimiento entre slices. Subcomandos — `clean` (limpieza conservadora), `compact` (PROGRESS.md/memory global) y `compact-agent-memory` (memorias vivas de agentes con snapshot íntegro). Dry-run manual por defecto; next-wave auto-compacta memorias >250 líneas.
argument-hint: "clean [--apply]  |  compact [--apply] [--keep N] [--threshold-days D]  |  compact-agent-memory [--apply] [--agent NAME|--all] [--threshold-lines N]"
---

# /slice-maintain
## Rule loading

Antes de ejecutar este comando, considera cargadas las reglas no-scoped de `.claude/rules/`. Si no ves esas reglas en contexto tras `/clear`, léelas explícitamente en este orden: `00-source-of-truth.md`, `01-non-negotiables.md`, `02-phase-execution.md`, `03-dev-loop.md`, `04-traceability.md`, `05-runtime-write-contract.md`.

Comando de mantenimiento unificado. Reemplaza los antiguos `/cleanup-slice` y `/compact-progress`. Sub-uso:

- **`/slice-maintain clean [--apply]`** — limpieza conservadora de artefactos regenerables. No toca `PROGRESS.md` ni sus compañeros estructurales.
- **`/slice-maintain compact [--apply] [--keep N] [--threshold-days D]`** — compactación de ficheros vivos de `orchestrator-state/memory/` (sobre todo `PROGRESS.md`). Snapshot previo obligatorio, compacta en vez de borrar, promociona decisiones + open items a sus ficheros canónicos.
- **`/slice-maintain compact-agent-memory [--apply] [--agent NAME|--all] [--threshold-lines N]`** — compactación sin pérdida de `orchestrator-state/agent-memory/*/MEMORY.md`. Siempre archiva el original completo antes de reescribir. No toca `.claude/agents/*.md`.

**Modo por defecto: DRY-RUN.** NUNCA borres, muevas ni reescribas hasta que el usuario escriba `sí` / `confirmo` / `apply`, o hayas recibido `--apply`.

Si el usuario ejecuta sin subcomando → muestra este resumen y pregunta cuál quiere.

---

# Subcomando: `clean`

## Paso 1 — Inspección

En paralelo:

1. `orchestrator-state/memory/PROGRESS.md` (cabecera + últimas 2 fases) → fase activa, slice activa (ID en registry), últimas 2 slices cerradas (se PRESERVAN intactas).
2. `orchestrator-state/tasks/registry.json` (solo `task_dag.mode`, últimas 5 `done`, primeras `ready`, y `runtime-state.active_*` como sugerencia).
3. `du -sh` de: `orchestrator-state/memory/`, `orchestrator-state/memory/archive/`, `orchestrator-state/tasks/handoffs/`, `orchestrator-state/tasks/evidence/`, `orchestrator-state/tasks/reports/`, `orchestrator-state/tasks/context-packs/`, `orchestrator-state/tasks/contexts/`, `orchestrator-state/tasks/context/`.
   Además: `du -sh orchestrator-state/tasks/ledger.jsonl orchestrator-state/tasks/bash-ledger.jsonl` + `wc -l orchestrator-state/tasks/ledger.jsonl orchestrator-state/tasks/bash-ledger.jsonl`; cuenta cuántos ficheros `ledger-*.jsonl.gz` y `bash-ledger-*.jsonl.gz` existen en `orchestrator-state/tasks/` y su tamaño total acumulado.
4. Cuenta ficheros en esas carpetas.
5. Artefactos regenerables en TODO el proyecto (no solo `.claude/`):
   - Logs: `*.log` en roots front y back (según TECHNICAL_GUIDE) y raíz (excluyendo carpetas ignoradas por `.gitignore`).
   - Basura SO: `.DS_Store`, `Thumbs.db`.
   - Temporales: `*.tmp`, `*.bak`, `*.swp`, `*.draft.md`, `*.wip.md`.
   - Caches regenerables: `__pycache__/`, `.pytest_cache/`, `htmlcov/`, `*.egg-info/`, `coverage/`, `.nyc_output/`, etc. — fuera de carpetas de herramientas/build del stack.
   - Test outputs sueltos: `test-output*`, `test_output*`, `*-test-results.*`, `*-results.txt`.
6. Artefactos con sufijo de fecha antigua (`-YYYY-MM-DD.md`, `*-audit-*.md`, `*-validation-*.md`, `*-analysis-*.md`, `reviewer-*.md`, `tester-*.md`, `qa-*.md`, `validator-*.md`, `closer-*.md`, `security-*.md`) en `orchestrator-state/memory/` con fecha anterior a la penúltima slice cerrada.
7. Carpetas vacías en `orchestrator-state/tasks/**`.
8. Duplicados sospechosos (mismo nombre en ubicaciones distintas) — típicos: `PROGRESS.md` fuera de `orchestrator-state/memory/`, ficheros de scratch en raíz.

## Paso 2 — Clasificar y presentar el plan

### 🔒 INTOCABLES (jamás borrar/archivar)

- `docs/source-of-truth/**` (los source-of-truth docs).
- `.claude/CLAUDE.md`, `.claude/settings.json`, `.claude/settings.local.json`, `.claude/settings.local.example.json`.
- `.claude/rules/**`, `.claude/agents/**`, `.claude/skills/**`, `.claude/bin/**` (incluye `hook_*.py`), `.claude/commands/**`, `.claude/scripts/**` — `.claude/` es configuración estática; no la limpies desde runtime.
- `orchestrator-state/tasks/registry.json`, `orchestrator-state/tasks/runtime-state.json`, `orchestrator-state/tasks/ledger.jsonl` y `orchestrator-state/tasks/bash-ledger.jsonl` (se rota, no se borra).
- `orchestrator-state/memory/PROGRESS.md` (se PRESERVA — `clean` nunca lo toca; usa `compact` para eso).
- `orchestrator-state/memory/execution-graph.json`, `source-manifest.json`, `architecture-contract.md`, `project-brief.md`, `decisions.md`, `risk-register.md`, `official-doc-sources.md`, `active-*.{json,md}`, `active-context-pack.md`.
- `orchestrator-state/agent-memory/**`, `orchestrator-state/memory/official-doc-notes/**`.
- Cualquier handoff/evidence/report/context-pack cuyo `task_id` coincida con la slice activa o las 2 anteriores.
- Ficheros fuente de la app (front + back): todo dentro de roots declarados en TECHNICAL_GUIDE, manifests/lockfiles, `Dockerfile*`, `docker-compose*.yml`, migraciones, seeds, `.env*`.
- `.git/**`, `.github/**`, `.vscode/**`.
- Cualquier fichero modificado en las últimas 24h.

### Categorías

| Categoría | Acción | Ejemplos |
|---|---|---|
| **SAFE_DELETE** | Borrar directo | `*.log`, `.DS_Store`, caches regenerables, carpetas vacías |
| **ARCHIVE+SUMMARIZE** | Mover a `orchestrator-state/memory/archive/YYYY-MM-DD/` + resumir en `archive/SUMMARY-YYYY-MM-DD.md` | handoffs/evidence/reports/context-packs de slices cerradas >2 atrás, `orchestrator-state/memory/*-YYYY-MM-DD.md` anteriores |
| **ROTATE** | Rename + comprimir + crear nuevo vacío; mantener máx. 5 ficheros `ledger-*.jsonl.gz` y `bash-ledger-*.jsonl.gz` (borrar el más antiguo si se supera) | `orchestrator-state/tasks/ledger.jsonl` o `orchestrator-state/tasks/bash-ledger.jsonl` si >200 KB → `ledger-YYYY-MM-DD.jsonl.gz` / `bash-ledger-YYYY-MM-DD.jsonl.gz` |
| **CONSOLIDATE** | Unir carpetas duplicadas en la canónica | `orchestrator-state/tasks/context/` + `contexts/` → `context-packs/` |
| **INVESTIGATE** | ⚠️ Detectado, NO tocar — requiere decisión humana | Duplicados de PROGRESS.md fuera de `orchestrator-state/memory/`, ficheros de scratch en raíz |
| **KEEP** | No tocar | Todo lo demás + intocables + últimas 2 slices |

### Presentación al usuario

Muestra una tabla en este formato:

```
📋 PLAN DE LIMPIEZA (dry-run)
=============================
Slice activa: <ID>
Slices preservadas: <ID_N>, <ID_N-1>
Espacio total identificado: <MB>

SAFE_DELETE (<N> ítems, <MB>):
  - <path> (<tamaño>, <razón corta>)
  ...

ARCHIVE+SUMMARIZE (<N> ítems, <MB>):
  - <path> → archive/YYYY-MM-DD/<path>
  ...

ROTATE:
  - ledger.jsonl o bash-ledger.jsonl (<MB>) → ledger-YYYY-MM-DD.jsonl.gz / bash-ledger-YYYY-MM-DD.jsonl.gz

CONSOLIDATE:
  - <path origen> → <path canónico>

INVESTIGATE (requieren decisión):
  - <path> (<razón>)

KEEP: <N> ítems preservados

Para ejecutar, responde "sí" / "confirmo" / "apply" o relanza con --apply.
```

## Paso 3 — Ejecución (solo con --apply)

- Borra SAFE_DELETE uno a uno. Si alguno da error → log pero no pares.
- Para ARCHIVE+SUMMARIZE: crea `archive/YYYY-MM-DD/`, mueve, luego genera `SUMMARY-YYYY-MM-DD.md` con 1 línea por fichero movido.
- Para ROTATE: comprime (`gzip`), renombra a `ledger-YYYY-MM-DD.jsonl.gz`, crea nuevo `ledger.jsonl` o `bash-ledger.jsonl` vacío (el hook escribe en el nuevo). Si tras la rotación existen >5 ficheros `ledger-*.jsonl.gz` y `bash-ledger-*.jsonl.gz`, borra el más antiguo. El ledger siempre debe mantenerse escribible para el hook.
- Para CONSOLIDATE: muévelos a la canónica, verifica que los agentes siguen referenciándola.
- Reporta al usuario: ítems borrados/archivados/rotados, espacio recuperado, INVESTIGATEs pendientes.

---

# Subcomando: `compact`

Este subcomando SÍ toca `PROGRESS.md` (que `clean` declara intocable), pero bajo contrato estricto: snapshot previo obligatorio, compacta en vez de borrar, promueve decisiones vivas + open items a sus ficheros canónicos.

## Paso 1 — Inspección

En paralelo:

1. Mide `PROGRESS.md`: `wc -l`, `wc -c`, nº secciones `## `, índice con `grep -n '^## '`.
2. Lee cabecera (primeras ~50 líneas):
   - Bloque `# Project Progress — Live Snapshot`.
   - Avisos `> 🚩 ... BINDING` / `> ✅ ...` / `> 🔧 ...` / `> 🧪 ...` (blockquotes `>` consecutivos).
   - Inicio de `## Current State`.
3. `orchestrator-state/tasks/registry.json` → `task_dag.mode`, últimos 5 `done`, primeras `ready`.
4. `orchestrator-state/tasks/runtime-state.json` → eventos, follow-ups y contadores; no contiene identidad de worker.
5. Compañeros de `PROGRESS.md` en `orchestrator-state/memory/`:
   - `ls -la orchestrator-state/memory/*.md`, `du -sh`.
   - Orphans con fecha pegada: `*-stage-*-YYYY-MM-DD.md`, `chrome-smoke-*.md`, `*-BRIEF.md`, `reviewer-*.md`, `validator-*.md`, `tester-*.md`, `qa-*.md`, `security-*.md`, `closer-*.md`.
   - Cuáles están referenciados desde PROGRESS.md (grep) vs cuáles no.
6. `orchestrator-state/memory/official-doc-notes/` — fecha de cada nota + citada en últimas 3 slices o no.
7. `orchestrator-state/memory/decisions.md` + `risk-register.md` — qué ya está promovido para no duplicar.

## Paso 2 — Clasificar

### 🔒 INTOCABLES (jamás compactar ni mover)

- **Cabecera de PROGRESS.md**: desde línea 1 hasta el final del último blockquote `>` que precede a `## Current State`.
- **Sección `## Current State` entera**.
- **Las N últimas slices verbatim** (default 3, configurable con `--keep N`, mínimo 2).
- **Ventana 24h**: cualquier fichero (incluido PROGRESS si fue editado <24h) solo se opera sobre secciones antiguas, no sobre el fichero completo.
- **Secciones de referencia permanente** dentro de PROGRESS.md: `## V1 Baseline`, `## V2 Upgrade Scope`, `## Decision log — *` con "binding"/"must-carry", `## Known Issues / Risks`, `## DB Migrations`, `## Routes`, `## USER VALIDATION CHECKLIST` vigente.
- **Bullets must-carry** (`L-1`, `L-2`, etc.) y **UUIDs seed hardcodeados** (cualquier UUID citado por `/verify-slice` o tests seed).
- **Todo SHA de commit** referenciado (7+ chars hex). Deben persistir o migrar al snapshot archivado.
- **Ficheros fuera de `orchestrator-state/memory/`**: este subcomando NO toca `orchestrator-state/tasks/`, `docs/`, código de app, configs, source-of-truth, registry, ledger, runtime-state, execution-graph.
- **Ficheros estructurales en `orchestrator-state/memory/`**: `execution-graph.json`, `active-*.{json,md}`, `architecture-contract.md`, `project-brief.md`, `source-manifest.json`, `official-doc-sources.md`, cualquier `*_ROLE_*.md` o similar estructural.

### Categorías

| Categoría | Acción | Ejemplos |
|---|---|---|
| **COMPACT_INLINE** | Reemplazar entrada larga por resumen 3-6 líneas EN EL MISMO PROGRESS.md, bajo sección nueva `## Archived entries (compacted YYYY-MM-DD)` colocada ANTES de las secciones permanentes | Entradas `## {SLICE_ID} — ...` y bullets `> ✅/🔧/🧪` con fecha < `threshold-days` y NO dentro de `--keep N` ni intocables |
| **PROMOTE_TO_DECISIONS** | Extraer bloques "Decision log", líneas `Decision:` / `D1/D2/D3:` vigentes → append a `orchestrator-state/memory/decisions.md` con ref a slice origen | Must-carry invariants activos, decisiones arquitectónicas vivas |
| **PROMOTE_TO_ISSUES** | Extraer open items / follow-ups / deferred / known-issues vivos → append a `orchestrator-state/memory/risk-register.md` con slice origen + severidad | Follow-ups pendientes, latent traps, "deferred to Phase N" |
| **ARCHIVE_ORPHAN** | Mover a `orchestrator-state/memory/archive/{fecha_hoy}/stage-reports/` | `reviewer-stage-*-YYYY-MM-DD.md`, `tester-stage-*.md`, `validator-stage-*.md`, `qa-stage-*.md`, `chrome-smoke-*.md`, `STAGE-*-BRIEF.md` (si la stage ya cerró) |
| **INVESTIGATE** | ⚠️ NO tocar, requiere decisión | `active-context-pack.md` >48h sin tocar y sin ref, notas en `official-doc-notes/` >2 semanas sin cita, secciones de PROGRESS con formato inusual |
| **KEEP** | No tocar | INTOCABLES + slices dentro de `--keep N` + Current State + referencias permanentes |

### Reglas de buena compactación

Para cada entrada COMPACT_INLINE el resumen debe capturar en **≤6 líneas** con datos concretos:

1. Cabecera (1 línea): `- **{fecha}** · **{ID}** · {título} · {status: committed {sha}/reverted/superseded by {ID}}`.
2. Qué se entregó (1 línea): endpoints back (`POST /api/v1/X`), pantallas front (`XPage`), tablas/migraciones. Sin LOC, sin rutas de fichero.
3. Decisiones que aún aplican (1 línea, si las hay): `Dec: {resumen ≤15 palabras} → promoted to decisions.md`.
4. Open items pendientes (1 línea): `Pending: {resumen} → promoted to risk-register.md` o `-`.
5. Tests (1 línea): `Tests: N/N green` o `N passing + M pre-existing failures (unrelated, see {ref})`.
6. (Opcional) Commit SHA: `Commit: {sha7}`.

## Paso 3 — Snapshot previo (OBLIGATORIO antes de apply)

Antes de tocar PROGRESS.md:

- Copia el fichero completo a `orchestrator-state/memory/archive/{fecha_hoy}/PROGRESS-pre-compact-{hora}.md`.
- Registra en el plan: path del snapshot.

Si el snapshot falla → **cancela `--apply`**.

## Paso 4 — Presentar plan al usuario

```
📦 PLAN DE COMPACTACIÓN (dry-run)
==================================
PROGRESS.md: <N_lineas> líneas, <N_bytes> bytes, <N_secciones> secciones
--keep: <N> slices verbatim
--threshold-days: <D>
Snapshot planeado: orchestrator-state/memory/archive/<fecha>/PROGRESS-pre-compact-<hora>.md

COMPACT_INLINE (<N> entradas, estimado <N_lineas> líneas ahorradas):
  - <ID> (<fecha>) → resumen 6 líneas
  ...

PROMOTE_TO_DECISIONS (<N>):
  - <item> → decisions.md
  ...

PROMOTE_TO_ISSUES (<N>):
  - <item> → risk-register.md (severidad: <low|med|high>)
  ...

ARCHIVE_ORPHAN (<N>):
  - <path> → archive/<fecha>/stage-reports/<path>
  ...

INVESTIGATE (<N>):
  - <path> (<razón>)

KEEP:
  - Cabecera + blockquotes
  - Current State
  - Últimas <N> slices
  - Secciones permanentes: <lista>
  - must-carry bullets: <lista>
  - UUIDs seed: <lista>
  - Commit SHAs: <lista>

Para ejecutar, responde "sí" / "confirmo" / "apply" o relanza con --apply.
```

## Paso 5 — Ejecución (solo con --apply)

Orden estricto:

1. Crear snapshot previo. Verificar que existe y tiene el tamaño correcto.
2. PROMOTE_TO_DECISIONS → append en `decisions.md` con encabezado `## From PROGRESS.md compact YYYY-MM-DD` + items.
3. PROMOTE_TO_ISSUES → append en `risk-register.md` con el mismo patrón.
4. ARCHIVE_ORPHAN → mover ficheros a `archive/YYYY-MM-DD/stage-reports/`.
5. COMPACT_INLINE → reescribir PROGRESS.md:
   - Crear/actualizar sección `## Archived entries (compacted YYYY-MM-DD)` ANTES de las secciones permanentes.
   - Reemplazar cada entrada antigua por su resumen de ≤6 líneas.
   - Preservar intactos: cabecera, Current State, últimas `N` slices, secciones permanentes, must-carry bullets, UUIDs seed, commit SHAs.
6. Verificar sintaxis del PROGRESS.md resultante (markdown parseable, sin secciones rotas).
7. **Verificación de información crítica preservada (gate fuerte)**. Compara el original (snapshot previo) contra el PROGRESS.md compactado:
   - **Commit SHAs**: extrae todos los SHAs de 7+ chars hex del original. CADA UNO debe seguir presente en el compactado (en `## Archived entries (compacted)` o en las últimas N slices verbatim). Si falta UN solo SHA → restaurar desde snapshot, abortar, reportar `SHA_MISSING: <sha>`.
   - **UUIDs seed hardcodeados**: extrae UUIDs (regex `[0-9a-f]{8}-[0-9a-f]{4}-...`). Cada uno debe seguir presente. Si falta → restaurar y abortar.
   - **must-carry bullets**: extrae líneas con prefijos `L-1`, `L-2`, etc., o blockquotes `> 🚩 ... BINDING`. Cada uno debe seguir presente. Si falta → restaurar y abortar.
   - **Decisions activas en `decisions.md`**: si una entrada tenía `Dec:` y se compactó, debe estar en `decisions.md` con ref a la slice origen. Comprueba que cada decision promovida quedó append-only en decisions.md. Si falta → restaurar y abortar.
   - **Open items en `risk-register.md`**: igual que decisions, cada open item promovido debe estar en risk-register.md con severidad. Si falta → restaurar y abortar.
8. Reportar al usuario:

```
✅ Compact aplicado
   - PROGRESS.md: <N_lineas_orig> → <N_lineas_comp> líneas (-<%>)
                  <N_bytes_orig> → <N_bytes_comp> bytes (-<%>)
   - Snapshot: <path>
   - Promoted to decisions.md: <N>
   - Promoted to risk-register.md: <N>
   - Archived stage reports: <N>
   - Compacted entries: <N>
   - Critical info preserved: ✅ <count_shas> commit SHAs · ✅ <count_uuids> UUIDs · ✅ <count_binding> must-carry
```

Si algo falla en cualquier paso → restaurar desde snapshot y reportar el motivo exacto. **Nunca dejes el PROGRESS.md a medio compactar.**

---

# Subcomando: `compact-agent-memory`

Este subcomando es distinto de `compact`:

- `compact` toca `orchestrator-state/memory/PROGRESS.md` y compañeros de memoria global.
- `compact-agent-memory` toca sólo `orchestrator-state/agent-memory/<agent>/MEMORY.md` y crea snapshots íntegros bajo `orchestrator-state/agent-memory/<agent>/archive/`.
- Los snapshots y locks de compactación son runtime local gitignored; no deben entrar en PRs de producto.

**Dry-run por defecto cuando lo invoca un humano.** `./scripts/next-wave.sh` ejecuta una compactación automática conservadora al inicio con umbral 250 líneas. Esa ruta archiva el original completo y no toca `.claude/agents/*.md`.

## Comando mecánico recomendado

Dry-run de todos los agentes:

```bash
python3 -B -S scripts/compact-agent-memory.py --all
```

Dry-run de un agente:

```bash
python3 -B -S scripts/compact-agent-memory.py --agent developer
```

Aplicar sólo tras revisar el plan:

```bash
python3 -B -S scripts/compact-agent-memory.py --all --apply
```

Umbral por defecto: 250 líneas. Override:

```bash
python3 -B -S scripts/compact-agent-memory.py --all --threshold-lines 150
```

## Contrato de seguridad

1. No toca `.claude/agents/*.md`; esos son prompts estáticos, no memoria viva.
2. No toca `docs/source-of-truth/**`, `docs/product-baseline/**`, `registry.json`, `runtime-state.json`, `task-dag.json`, `execution-graph.json`, handoffs ni evidence.
3. Antes de reescribir un `MEMORY.md`, copia el original completo byte-for-byte a:

```text
orchestrator-state/agent-memory/<agent>/archive/MEMORY.full.<YYYY-MM-DD-HHMMSS>.md
```

4. El nuevo `MEMORY.md` debe incluir:
   - ruta del archive full;
   - SHA-256 del original archivado;
   - invariantes vigentes;
   - decisiones/gotchas de alta señal;
   - índice de headings del original;
   - referencias a `.claude/orchestrator-contract.json`, `.claude/rules/` y `CHEATSHEET.md`.
5. Si hace falta un detalle que no está en el compacto, lee el archive full antes de asumir.

## Qué preservar explícitamente

Para `developer`:

- production DAG-only / `explicit_dag`;
- `bootstrap_source_of_truth.py --refresh` preserva runtime por defecto;
- no editar `registry.json`, `runtime-state.json`, `task-dag.json` o `execution-graph.json` directamente;
- scope por `CLAUDE_ACTIVE_TASK_ID` / `CLAUDE_TASK_PACK`;
- `allowed_paths` / `Write set`;
- `docker-compose.yml`, `Dockerfile*`, `.env.example`, `.github/workflows/**` requieren scope explícito;
- follow-ups: developer propone, no promueve automáticamente;
- trailer válido: `OUTCOME: success|blocked|failed`, `NEXT_STATUS: validator_tester_pending|blocked`.

Para `official-docs-researcher`:

- documentación oficial y versionada;
- orden rápido: local/cache, ToolSearch/MCP, Context7, MCP vendor, WebFetch/WebSearch oficial;
- fan-out paralelo para consultas independientes;
- evidencia con fuente/versiones;
- trailer válido: `OUTCOME: verified|discrepancy|insufficient`;
- nunca emitir `OUTCOME: researched`.

## Plan esperado en dry-run

```text
AGENT MEMORY COMPACTION
=======================
mode: dry-run
threshold_lines: 250
COMPACT developer: 433 lines -> snapshot orchestrator-state/agent-memory/developer/archive/MEMORY.full.<ts>.md
COMPACT official-docs-researcher: 510 lines -> snapshot orchestrator-state/agent-memory/official-docs-researcher/archive/MEMORY.full.<ts>.md
Dry-run only. Re-run with --apply to archive originals and compact MEMORY.md.
```

## Verificación después de `--apply`

```bash
python3 -B -S scripts/audit-agent-reality.py
python3 -B -S scripts/audit-agent-trailer-vocabulary.py
./scripts/run-all-tests.sh lint
```

Confirma también:

```bash
find orchestrator-state/agent-memory -path '*/archive/MEMORY.full.*.md' -type f -print
wc -l orchestrator-state/agent-memory/*/MEMORY.md
```

Si un archive full no existe o tiene tamaño cero, restaura desde Git y no continúes.
