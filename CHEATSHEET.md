# Orquestador DAG AnyStack — Cheat Sheet

## 0. Modelo mental

```text
5 source-of-truth docs
  -> bootstrap_three_docs.py
  -> registry.json + task-packs + DAG derivado
  -> next-wave / claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>"
  -> verify-slice
  -> closer: report + baseline + git workflow + cleanup
```

Los cinco documentos vivos son:

```text
docs/source-of-truth/instrucciones.md
docs/source-of-truth/*_TECHNICAL_GUIDE.md
docs/source-of-truth/*_IMPLEMENTATION_CHECKLIST.md
docs/source-of-truth/UX_CONTRACT.md
docs/source-of-truth/STACK_PROFILE.yaml
```

## 1. Crear o cambiar de app

```bash
./scripts/reset-for-new-project.sh
# pegar los 5 source-of-truth docs en docs/source-of-truth/
python3 -B -S .claude/bin/bootstrap_three_docs.py --validate-only
python3 -B -S .claude/bin/bootstrap_three_docs.py --refresh
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
./scripts/generate-api-contracts.sh --validate-only
```

`reset-for-new-project.sh` limpia estado derivado, locks, runtime y memoria archivada, pero conserva los source-of-truth docs.

## 2. Ver siguiente wave segura

```bash
./scripts/next-wave.sh --limit 4
```

Copia el `export CLAUDE_ACTIVE_TASK_ID=... CLAUDE_TASK_PACK=...` que imprime el script en cada terminal worker. El bloque imprimirá también el comando completo para lanzar Claude Code:

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>"
```

Ejemplo de salida/copy-paste esperado:

```bash
export CLAUDE_ACTIVE_TASK_ID=P02-S03-T001 CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P02-S03-T001.md && echo 'Ahora ejecuta: claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P02-S03-T001"'
```

### Uso correcto del terminal worker

El `export` es **por terminal**. Solo afecta a la shell donde lo pegas y se queda activo hasta que cierres ese terminal o ejecutes `unset`.

Regla práctica:

```text
1 terminal worker = 1 TASK_ID activo
```

Flujo recomendado en cada terminal worker:

```bash
# 1) Pega el export que te dio next-wave en ESTE terminal.
export CLAUDE_ACTIVE_TASK_ID=P02-S03-T001 CLAUDE_TASK_PACK=orchestrator-state/tasks/task-packs/P02-S03-T001.md

# 2) Lanza la slice en ese mismo terminal.
claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P02-S03-T001"

# 3) Cuando /next-slice termine en tester pass, NO limpies aun el entorno si vas a verificar esa misma task.
#    Haz /clear dentro de Claude Code si lo necesitas y verifica la misma task con el mismo TASK_ID.
claude --agent main-orchestrator --permission-mode bypassPermissions "/verify-slice P02-S03-T001"

# 4) Tras /verify-slice + closer/commit, ya puedes reutilizar el terminal.
unset CLAUDE_ACTIVE_TASK_ID CLAUDE_TASK_PACK
```

Cerrar el terminal equivale a limpiar esos exports. Si reutilizas la misma terminal para otra task, haz siempre el `unset` antes de pegar el nuevo `export`, para no ejecutar una slice con un `TASK_ID` viejo.

Para comprobar qué task tiene activa un terminal:

```bash
printf 'CLAUDE_ACTIVE_TASK_ID=%s\nCLAUDE_TASK_PACK=%s\n' "$CLAUDE_ACTIVE_TASK_ID" "$CLAUDE_TASK_PACK"
```

## 3. Ciclo de una slice

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>"
  planner
  developer ‖ official-docs-researcher
  validator ‖ tester
  debugger si tester/validator fallan
  pausa en tester pass

/clear
/verify-slice <TASK_ID>
  hard reset + datos reales/prod-like + FRONT -> BACK -> DB
  closer si verified
```

Después del closer:

```bash
./scripts/phase-gate.sh <PHASE_ID>
./scripts/next-wave.sh --limit 4
```

## 4. Checks rápidos de salud del orquestador

```bash
python3 -B -S -m py_compile .claude/bin/*.py scripts/*.py .claude/bin/tests/*.py
bash -n scripts/*.sh .claude/bin/*.sh .claude/enforcers/*.sh .claude/git-workflows/*.sh
python3 -B -S -m unittest discover -s .claude/bin/tests
python3 -B -S scripts/audit-agent-trailer-vocabulary.py
python3 -B -S scripts/audit-agent-reality.py
python3 -m pytest -q .claude/bin/tests
```

## 5. Smoke de templates

```bash
python3 -B -S scripts/smoke-template-profiles.py --only minimal --json
python3 -B -S scripts/smoke-template-profiles.py --only large-without-base --json
python3 -B -S scripts/smoke-template-profiles.py --only large-with-base --json
```

Para conservar los repos temporales:

```bash
python3 -B -S scripts/smoke-template-profiles.py --keep --json
```

## 6. Production DAG trailer vocabulary

Closed trailer enums live in `.claude/orchestrator-contract.json` → `trailer_schema.roles.<agent>.outcome_values` and `trailer_schema.roles.<agent>.next_status_values`. Read that path before emitting the trailer. Scope writes by `CLAUDE_ACTIVE_TASK_ID`/`CLAUDE_TASK_PACK`; never edit generated registry/runtime/task-dag directly. Use `/register-followup` for discovered work outside current slice.

La fuente normativa es:

```text
.claude/orchestrator-contract.json -> trailer_schema.roles.<agent>
```

| Agente | OUTCOME válido | NEXT_STATUS válido |
|---|---|---|
| `planner` | `ready`, `blocked` | ninguno |
| `main-orchestrator` | `ready`, `blocked` | ninguno |
| `official-docs-researcher` | `verified`, `discrepancy`, `insufficient` | ninguno |
| `developer` | `success`, `blocked`, `failed` | `validator_tester_pending`, `blocked` |
| `validator` | `approved`, `changes_requested`, `blocked` | `ready_for_close`, `needs_debug`, `blocked` *(info-only; no muta `task.status`)* |
| `tester` | `pass`, `fail`, `blocked` | `ready_for_close`, `needs_debug`, `blocked` |
| `debugger` | `fixed`, `blocked`, `failed` | `validator_tester_pending`, `blocked` |
| `closer` | `committed`, `blocked` | `done`, `blocked` |
| `deployer` | `deployed`, `planned`, `blocked`, `failed` | `done`, `blocked` |
| `document-analyzer` | `valid`, `invalid` | ninguno |
| `project-architect` | `ready`, `blocked` | ninguno |
| `task-planner` | `ready`, `blocked` | ninguno |

Ejemplo developer correcto:

```text
CLAUDE_TRAILER:
TASK_ID: P00-S01-T001
OUTCOME: success
NEXT_STATUS: validator_tester_pending
HANDOFF: orchestrator-state/tasks/handoffs/P00-S01-T001.md
```

Ejemplo validator correcto:

```text
CLAUDE_TRAILER:
TASK_ID: P00-S01-T001
OUTCOME: approved
NEXT_STATUS: ready_for_close
HANDOFF: orchestrator-state/tasks/handoffs/P00-S01-T001.md
```

Nota validator: `NEXT_STATUS` se emite sin comentarios inline, pero el hook lo guarda como `validator_next_status`; no sobrescribe `task.status`. `tester` decide el lifecycle real (`ready_for_close`/`needs_debug`).

No uses sinónimos naturales como estados del trailer. El hook los rechazará y los registrará en `orchestrator-state/hook-errors.log`.

## 7. Git workflow

El modo está en `docs/source-of-truth/STACK_PROFILE.yaml`:

```yaml
git_workflow: push-to-main   # push directo a main; alias: direct-main
git_workflow: pr-flow        # requiere feature branch y PR
```

El closer debe ejecutar siempre:

```bash
./scripts/git-workflow.sh
```

Si `pr-flow` se ejecuta desde `main`, fallará correctamente. Para push directo a main usa `push-to-main` o `direct-main`; no hagas fallback manual fuera del script.

## 8. Follow-ups formales

Crear propuesta:

```bash
./scripts/register-followup-task.sh propose \
  --origin-task P00-S01-T001 \
  --severity medium \
  --kind bug \
  --title "Titulo corto" \
  --description "Descripcion" \
  --product-increment v1 \
  --acceptance "Criterio" \
  --verify "Comando o verify esperado"
```

Listar/promover/waivear:

```bash
./scripts/register-followup-task.sh list
./scripts/register-followup-task.sh promote FU-YYYYMMDDHHMMSS
./scripts/register-followup-task.sh waive FU-YYYYMMDDHHMMSS --reason "decision humana"
```

`high`, `critical` y `blocker` bloquean waves/closer hasta promover o waivear.

## 9. Limpieza segura entre slices

```bash
./scripts/slice-clean.sh          # dry-run
./scripts/slice-clean.sh --apply  # aplica limpieza segura
./scripts/cleanup-worktrees.sh --verbose
```

No borres `orchestrator-state/` entre slices de la misma app. Ahí vive el runtime que permite continuar tras `/clear`.
