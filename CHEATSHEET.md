# Orquestador DAG AnyStack — Cheat Sheet

### PR-flow invariant: next slice must start from integrated main

For `git_workflow: pr-flow`, a closed slice is not `done` just because a PR exists. The closer must run `./scripts/git-workflow.sh`, `pr-flow.sh` must wait until GitHub reports the PR as `MERGED`, and the canonical main checkout must fast-forward to `origin/main`. New task worktrees are cut from the freshly fetched default branch; if local main cannot sync safely, `/next-wave` or `/next-slice` blocks instead of starting work on stale code.


## 0. Modelo mental

```text
5 source-of-truth docs
  -> bootstrap_source_of_truth.py
  -> registry.json + task-packs + DAG derivado
  -> next-wave / claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice <TASK_ID>"
  -> verify-slice
  -> closer: report + product-baseline sync + lifecycle-event + git workflow + cleanup
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
python3 -B -S .claude/bin/bootstrap_source_of_truth.py --validate-only
python3 -B -S .claude/bin/bootstrap_source_of_truth.py --refresh
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
./scripts/generate-api-contracts.sh --validate-only
```

`reset-for-new-project.sh` limpia estado derivado, locks, runtime y memoria archivada, pero conserva los source-of-truth docs.

`bootstrap_source_of_truth.py --refresh` preserva runtime por defecto: estados de tasks existentes, `runtime-state.json`, blockers y follow-ups abiertos. Para un reset destructivo explícito usa `--reset-runtime-state`; no lo uses a mitad de una app/slice.

Production DAG-only: `./scripts/check-task-dag.sh --strict` debe reportar `mode=explicit_dag`. Si sale `missing dependency column`, corrige `Depends on` en el Coverage Registry antes de abrir workers.

Nota PR/worktree: no persigas ni commitees `registry.json`/`runtime-state.json` como "sync post-close state". El closer stagea `orchestrator-state/tasks/lifecycle-events/<TASK_ID>.json`; tras merge/reset se repara con `bash scripts/sync-lifecycle-events.sh --apply` o automáticamente en SessionStart/`next-wave`.

Main thread obligatorio: el proyecto debe arrancar con `main-orchestrator` como agente principal. `.claude/settings.json` declara `agent: main-orchestrator`, y el arranque explícito es:

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions
```

No añadas `tools:` a `.claude/agents/main-orchestrator.md`. La ausencia de `tools` es intencional: hereda todas las herramientas disponibles, incluidos MCPs y `Agent`. Una lista `tools:` sería un allowlist y podría limitar el DAG controller.

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
BOOTSTRAP_ROOT="${CLAUDE_ORCHESTRATOR_ROOT:-$(git rev-parse --show-toplevel 2>/dev/null || pwd -P)}" && ROOT="$(bash "$BOOTSTRAP_ROOT/scripts/ensure-task-worktree.sh" --print-root)" && WT="$(bash "$ROOT/scripts/ensure-task-worktree.sh" P02-S03-T001)" && cd "$WT" && PACK="$WT/orchestrator-state/tasks/task-packs/P02-S03-T001.md" && if [ ! -f "$PACK" ]; then PACK="$ROOT/orchestrator-state/tasks/task-packs/P02-S03-T001.md"; fi && export CLAUDE_ORCHESTRATOR_ROOT="$ROOT" CLAUDE_WORKTREE_ROOT="$WT" CLAUDE_ACTIVE_TASK_ID=P02-S03-T001 CLAUDE_TASK_PACK="$PACK" && echo 'Ahora ejecuta en Claude Code: claude --agent main-orchestrator --permission-mode bypassPermissions "/next-slice P02-S03-T001"'
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
unset CLAUDE_ACTIVE_TASK_ID
unset CLAUDE_TASK_PACK
unset CLAUDE_WORKTREE_ROOT
unset CLAUDE_ORCHESTRATOR_ROOT
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
  developer (+ official-docs-researcher si aplica)
  validator ‖ tester
  debugger si tester/validator fallan
  pausa en tester pass

/clear
/verify-slice <TASK_ID>
  hard reset + datos reales/proporcionados + FRONT -> BACK -> DB
  closer si verified
```

Antes de `closer`, valida el handoff:

```bash
./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice
```

Para tasks de pantalla/UX/journey/gate visual o con `VISUAL_CONTRACT_CHECK`, `/verify-slice` invoca `screen-journey-reviewer` antes del closer y valida también:

```bash
./scripts/check-handoff-contract.sh <TASK_ID> --require-ready-for-close --require-verify-slice --require-screen-journey-review
```

El reviewer es info-only: bugs reparables dentro de la slice van a debugger/retest; solo trabajo nuevo fuera de scope genera FU triageada. El handoff debe contener `OUTCOME` de validator/tester, `VERIFY_OUTCOME` de verify-slice y, cuando aplique, `Screen/Journey review`; el trailer de chat no basta tras `/clear`.

Después del closer:

```bash
./scripts/phase-gate.sh <PHASE_ID>
./scripts/next-wave.sh --limit 4
```

## 4. Scope real de ficheros compartidos

Si una slice dice que hay que tocar `docker-compose.yml`, `.env.example`, `Dockerfile*`, workflows o lockfiles, esos paths deben estar en `Write set`/`allowed_paths` del task-pack. El bootstrap infiere compose/env/docker/CI cuando aparecen literalmente en aceptación, pero lo correcto es declararlo en el Coverage Registry con un `Conflict group` compartido (`infra:compose`, `infra:env`, `infra:docker`, `ci:workflows`).

## 5. Checks rápidos de salud del orquestador

```bash
python3 -B -S -m py_compile .claude/bin/*.py scripts/*.py .claude/bin/tests/*.py
bash -n scripts/*.sh .claude/bin/*.sh .claude/enforcers/*.sh .claude/git-workflows/*.sh
python3 -B -S -m unittest discover -s .claude/bin/tests
python3 -B -S scripts/audit-agent-trailer-vocabulary.py
python3 -B -S scripts/audit-agent-reality.py
python3 -m pytest -q .claude/bin/tests
```

## 6. Smoke de templates

```bash
python3 -B -S scripts/smoke-template-profiles.py --only minimal --json
python3 -B -S scripts/smoke-template-profiles.py --only large-without-base --json
python3 -B -S scripts/smoke-template-profiles.py --only large-with-base --json
```

Para conservar los repos temporales:

```bash
python3 -B -S scripts/smoke-template-profiles.py --keep --json
```

## 7. Production DAG trailer vocabulary

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
| `slice-verifier` | `verified`, `issues_found`, `blocked` | `verified_pending_close`, `needs_debug`, `blocked` |
| `screen-journey-reviewer` | `approved`, `changes_requested`, `blocked` | ninguno *(info-only; no muta `task.status`)* |
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

Ejemplo slice-verifier correcto:

```text
CLAUDE_TRAILER:
AGENT: slice-verifier
TASK_ID: P00-S01-T001
OUTCOME: verified
NEXT_STATUS: verified_pending_close
MODE: pre-closer
MCP_BROWSER: chrome-devtools
EVIDENCE: orchestrator-state/tasks/evidence/P00-S01-T001/verify-*
HANDOFF: orchestrator-state/tasks/handoffs/P00-S01-T001.md
```

Nota validator: `NEXT_STATUS` se emite sin comentarios inline, pero el hook lo guarda como `validator_next_status`; no sobrescribe `task.status`. `tester` decide el lifecycle real (`ready_for_close`/`needs_debug`).

Nota verify: `slice-verifier` es lifecycle. `verified` mueve a `verified_pending_close`, no a `done`; el `closer` es el único que puede cerrar. Para que un verify humano sea válido, el handoff debe incluir `MCP_BROWSER: chrome-devtools|claude-in-chrome|agent360-browser-mcp|browser-mcp`, datos/evidencia (`DATA_CONTRACT_ROWS`, `DATA_SETUP`, `PERSISTED_DATA_OBSERVED`, `FLOWS_TESTED`, `EVIDENCE`) y `VERIFY_OUTCOME: verified`. El MCP debe estar usable, no sólo listado; la prioridad es Chrome DevTools primero, claude-in-chrome segundo fallback y Agent360/browser-mcp tercer fallback. Si Chrome DevTools MCP falla por lock de profile, diagnostica con `bash scripts/chrome-mcp-doctor.sh || true` y muestra `scripts/chrome-devtools-isolated-session.sh --task <TASK_ID>` antes de probar fallbacks. La única excepción sin MCP es `VERIFY_MODE: auto` + `RISK_LEVEL: low` con evidencia determinista. Campos de handoff: usa `- AGENT: ...`, no `### AGENT: ...`; el checker tolera H3 sólo para recovery.

Budget: `slice-verifier` tiene `maxTurns: 130` para Chrome DevTools MCP; no cambia el límite global de 20 spawns. Si se acerca al límite, debe cerrar con handoff `blocked` + `BLOCKER_REASON: mcp_budget_exhausted_or_scope_too_large`, no partial.

No uses sinónimos naturales como estados del trailer. El hook los rechazará y los registrará en `orchestrator-state/hook-errors.log`.

## 8. Git workflow

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

Nota DAG importante: no uses `git stash` / `git stash pop` durante el cierre. El flujo correcto es que el closer cree el commit atómico antes de ejecutar `git-workflow.sh`. Los eventos Bash se registran en `orchestrator-state/tasks/bash-ledger.jsonl`, runtime-only e ignorado por Git, para no dirty-ear el working tree después del commit/push.

## 9. Follow-ups formales

Regla anti-spam:

```text
Defecto dentro del TASK_ID -> debugger/retest, NO FU.
Trabajo nuevo fuera de scope -> FU triageada.
```

Crear propuesta:

```bash
./scripts/register-followup-task.sh propose \
  --origin-task P00-S01-T001 \
  --severity medium \
  --kind bug \
  --scope-classification out_of_scope|missing_coverage|missing_real_data|external_dependency|future_enhancement|scope_expansion|blocked_by_human_decision \
  --why-not-debugger "por qué debugger/retest no lo puede arreglar dentro del TASK_ID" \
  --title "Titulo corto" \
  --description "Descripcion" \
  --product-increment v1 \
  --acceptance "Criterio" \
  --verify "Comando o verify esperado"
```

El script rechaza `--scope-classification in_scope_defect`. Para `high|critical|blocker`, `--why-not-debugger` es obligatorio. Cita siempre los globs de `--write-set` con comillas simples, por ejemplo `--write-set '<frontend_module_root>/features/<feature>/**'`. Usa `--journey-ref` sólo si el journey ya existe en `UX_CONTRACT.md`/journey matrix; si la FU define una journey nueva, primero materializa esa journey en source-of-truth o no pases `--journey-ref`.

Listar/promover/waivear:

```bash
./scripts/register-followup-task.sh list
claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup FU-YYYYMMDDHHMMSS"
./scripts/register-followup-task.sh waive FU-YYYYMMDDHHMMSS --reason "decision humana"
```

`high`, `critical` y `blocker` bloquean nuevas waves/claims hasta promover o waivear, pero no bloquean el PR de la slice origen cuando ya son FU YAML `proposed` e incluidas en el commit. El closer nunca promueve automáticamente: registra/incluye y sigue el cierre. `/promote-followup` actualiza source-of-truth, registry, DAG, work-item YAML, runtime y ledger; Bash PostToolUse se registra en `bash-ledger.jsonl` runtime-only para no ensuciar Git; si la nueva task conflictúa con una task activa/claimed/in_progress por `conflict_group` o `write_set`, queda `blocked` con `blocked_reason: conflict_with_worker_task` hasta que `promote_ready_tasks` pueda desbloquearla.

No promuevas FU desde un terminal worker que está ejecutando otra slice si puede tocar los mismos ficheros. Primero mira `./scripts/next-wave.sh`; el promote respeta locks y conflictos, pero la decisión de convertir deuda en task DAG debe ser explícita.

### Promoción segura de FU

```bash
unset CLAUDE_ACTIVE_TASK_ID
unset CLAUDE_TASK_PACK
unset CLAUDE_WORKTREE_ROOT
unset CLAUDE_ORCHESTRATOR_ROOT
claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"
```

El comando `/promote-followup` es el flujo recomendado para convertir FU en task DAG: lista/inspecciona la propuesta, pide confirmación literal `PROMOTE <FOLLOWUP_ID>`, ejecuta el script bajo locks y revalida DAG/wiring. El comando bajo nivel `./scripts/register-followup-task.sh promote <FOLLOWUP_ID>` existe, pero úsalo solo dentro de ese flujo o para mantenimiento manual consciente.


## 10. Limpieza segura entre slices

```bash
./scripts/slice-clean.sh          # dry-run
./scripts/slice-clean.sh --apply  # aplica limpieza segura
./scripts/cleanup-worktrees.sh --verbose
```

No borres `orchestrator-state/` entre slices de la misma app. Ahí vive el runtime que permite continuar tras `/clear`.

## 11. Compactar memorias de agentes

`/slice-maintain compact` es para `PROGRESS.md` y memoria global. Las memorias vivas de agentes se auto-compactan al inicio de `./scripts/next-wave.sh` si superan 250 líneas. Dry-run manual:

```bash
python3 -B -S scripts/compact-agent-memory.py --all
python3 -B -S scripts/compact-agent-memory.py --agent developer
```

Aplicar manualmente si quieres adelantarte al `next-wave`:

```bash
python3 -B -S scripts/compact-agent-memory.py --all --apply
```

Para desactivar la auto-compactación en una sesión:

```bash
CLAUDE_AUTO_COMPACT_AGENT_MEMORY=0 ./scripts/next-wave.sh
```

Garantías:

```text
- No toca .claude/agents/*.md.
- No toca docs/source-of-truth, registry, runtime, task-dag ni execution-graph.
- Antes de compactar, archiva el MEMORY.md íntegro en:
  orchestrator-state/agent-memory/<agent>/archive/MEMORY.full.<timestamp>.md
- El MEMORY.md compacto referencia el archive full y su SHA-256.
```

Después de aplicar:

```bash
find orchestrator-state/agent-memory -path '*/archive/MEMORY.full.*.md' -type f -print
wc -l orchestrator-state/agent-memory/*/MEMORY.md
python3 -B -S scripts/audit-agent-reality.py
python3 -B -S scripts/audit-agent-trailer-vocabulary.py
```


## Phase / Step / Slice sizing para templates

- **Phase** = milestone o módulo de producto con visión completa; máximo operativo recomendado: `<=20` slices.
- **Step** = lane coherente dentro de la phase: pantalla/journey lane, módulo de dominio, foundation lane o contrato API que alimenta una pantalla nombrada. Objetivo sano: `6-12` slices; máximo: `<=15`.
- **Slice/Task** = unidad ejecutable/verificable por worker, con `Depends on`, `Write set`, `Conflict group`, `Journey refs` y `Verify mínimo` claros.
- No dividas un step coherente sólo por tener 11-12 slices. Divide cuando mezcle lanes no relacionadas, toque write sets incompatibles o pierda trazabilidad de producto.
- La pantalla no se cierra por capas aisladas: cada pantalla importante debe cubrir contrato de pantalla, API/datos, UI conectada, estados UX obligatorios y verificación del journey.
- API/backend slices pueden existir separadas sólo como foundation real o como contrato que alimenta una pantalla/journey nombrado; no hagas `backend completo -> frontend completo -> UX polish`.
- Los templates deben sustituir todos los ejemplos por el dominio real de la app y usar datos reales/proporcionados; si faltan datos, bloquea o registra follow-up.

### Git workflow y ledger local

- `./scripts/git-workflow.sh` es transporte Git: no usa `git stash`; sólo puede hacer `commit --amend --no-edit` para trazas tardías permitidas (`ledger.jsonl`, `bash-ledger.jsonl`, `runtime-state.json`) y bloquea cualquier otro path dirty.
- El closer debe crear el commit atómico antes de ejecutarlo.
- `hook_update_ledger.py` escribe eventos Bash en `orchestrator-state/tasks/bash-ledger.jsonl`, runtime-only e ignorado por Git, para que los Bash PostToolUse no re-ensucien el repo después del commit/push.
- `orchestrator-state/tasks/ledger.jsonl` queda como ledger canónico para eventos lifecycle no-Bash.

## Stack Docker compartido entre worktrees paralelos

`./scripts/next-wave.sh` exporta `COMPOSE_PROJECT_NAME` derivado del basename del root canónico. Todos los worktrees paralelos comparten el mismo stack Docker. Si quieres uno aislado, exporta `COMPOSE_PROJECT_NAME=otro` ANTES de pegar el bloque.
### Limpieza automática de worktrees e identidad Git

En `pr-flow`, el closer no borra la worktree activa antes de que Claude ejecute `SubagentStop`; si lo hiciera, se puede perder el trailer del closer. `cleanup-worktrees.sh` la marca como `active_deferred=1`, registra la limpieza en `orchestrator-state/tasks/cleanup-requests/<TASK_ID>.json` y `scripts/cleanup-deferred-worktrees.sh` la elimina automáticamente desde el Stop hook, y también se reintenta en `scripts/next-wave.sh`/`scripts/ensure-task-worktree.sh` si ya no es la worktree activa. El `DEFERRED_CLEANUP_COMMAND` es sólo fallback; el Stop hook lanza un janitor diferido con reintentos y `next-wave`/`next-slice` reintentan sin intervención manual.

La identidad de commits no está hardcodeada. `scripts/check-git-identity.sh` usa `git config user.name` y `git config user.email`; si quieres exigir una identidad, configura `claude.expectedUserName`/`claude.expectedUserEmail` en Git o exporta `CLAUDE_GIT_EXPECTED_NAME`/`CLAUDE_GIT_EXPECTED_EMAIL`.



### Limpieza diferida de worktrees

Si el closer reporta `active_deferred=1`, no es fallo: protegió los hooks de Claude. La limpieza se reintenta automáticamente al ejecutar `/next-wave` o crear otra worktree, pero sólo borra cuando la task ya está cerrada (`registry.status=done` o lifecycle-event `next_status=done`). Si la PR sigue abierta, la request queda pendiente y no debe ensuciar la wave. Si ya está cerrada pero la worktree sigue dirty, el cleanup no descarta cambios: imprime `DIRTY_STATUS_*` y debes revisar `git -C <worktree> status --short && git -C <worktree> diff --stat` antes de borrar. Fallback manual seguro desde el root canónico, sólo si el janitor no pudo porque la worktree seguía viva/dirty: `bash scripts/cleanup-deferred-worktrees.sh --apply --task <TASK_ID>`.

Además, `/next-wave` ejecuta `scripts/cleanup-closed-task-worktrees.sh --apply --quiet`: borra worktrees limpios y ramas locales `dev/<TASK_ID>`/`feature/<TASK_ID>` de tasks ya cerradas aunque no exista cleanup request. Es el equivalente seguro de `git worktree remove <path>` + `git branch -D dev/<TASK_ID>`, pero sólo si el TASK_ID está `done` por registry/lifecycle-event y la worktree no está activa ni dirty. Manual: `bash scripts/cleanup-closed-task-worktrees.sh --apply --task <TASK_ID> --verbose`.


`/next-wave` también ejecuta `scripts/sync-main-before-wave.sh --apply --quiet` antes de calcular el frontier. Eso hace `git fetch --prune` y fast-forward de `main` a `origin/main` cuando es seguro; si hay cambios dirty no-runtime (por ejemplo `docs/source-of-truth/*`), local-main ahead o divergencia, bloquea la wave en vez de calcular sobre una base vieja. Desactívalo sólo para inspección con `CLAUDE_SKIP_MAIN_SYNC_BEFORE_WAVE=1`.

Además ejecuta `scripts/cleanup-zombie-task-worktrees.sh --apply --quiet`: borra worktrees/ramas locales task-scoped que no tienen patches únicos frente a `origin/main` y no son live según registry. Sirve para cáscaras vacías tras squash merge u old branches equivalentes a main. No borra worktrees dirty, activas, live (`claimed`/`in_progress`/`ready_for_close`/etc.) ni branches con patches únicos. Manual/auditable: `bash scripts/cleanup-zombie-task-worktrees.sh --dry-run --verbose` y luego `--apply`.

También ejecuta `scripts/cleanup-merged-pr-branches.sh --apply --quiet`: borra ramas remotas `origin/dev/<TASK_ID>`/`origin/feature/<TASK_ID>` sólo cuando GitHub confirma que la PR está `MERGED` y el SHA de la rama remota coincide con `headRefOid` de esa PR. PRs abiertas, cerradas sin merge, forks, ramas movidas o ambiguas quedan intactas. Manual/auditable: `bash scripts/cleanup-merged-pr-branches.sh --dry-run --verbose` y, si el plan es correcto, `bash scripts/cleanup-merged-pr-branches.sh --apply --verbose`. Desactívalo en una sesión con `CLAUDE_DISABLE_REMOTE_BRANCH_CLEANUP=1 ./scripts/next-wave.sh` o `CLAUDE_CLEAN_MERGED_PR_BRANCHES=0 ./scripts/next-wave.sh`.

Para limpiar también ramas remotas de PR tras squash-merge en el cierre de la propia slice, `pr-flow.sh` usa `gh pr merge --delete-branch` y, después de confirmar `MERGED`, intenta `git push <remote> --delete <branch>` como fallback idempotente y hace `git fetch --prune`. Recomendado una vez por repo si tienes permisos admin: `bash scripts/configure-github-pr-cleanup.sh` para activar delete-branch-on-merge en GitHub; si reglas/protecciones lo impiden, el cleanup remoto de `/next-wave` hace de janitor conservador.

### `/next-slice` context inspector

When `/next-slice <TASK_ID>` starts inside a task worktree it may show that the local task pack/handoff is missing. That is normal before planner materializes the per-slice files; the canonical root may already contain the pack. Use the read-only inspector instead of ad-hoc JSON snippets:

```bash
ROOT="$(bash scripts/ensure-task-worktree.sh --print-root 2>/dev/null || pwd -P)"
bash "$ROOT/scripts/inspect-task-state.sh" --task <TASK_ID>
```

Do not assume `registry.json.tasks` is a dictionary. The canonical schema is `tasks[]`.


Nota DAG: los avisos de tamaño de phase/step (`phase >20`, `step >15`) son hygiene/advisory por defecto; `--strict` sigue fallando por errores estructurales del DAG, drift de vistas o dependencias inválidas. Para convertir esos avisos de tamaño en fallo CI, usa `CLAUDE_DAG_ENFORCE_SIZE_BUDGETS=1 ./scripts/check-task-dag.sh --strict` o `--enforce-size-budgets`.


### Learned guardrails

- FU path drift: resolve real files with `find`/`grep`; do not open a second FU just to fix a `write_set` string.
- Duplicate FU: recommend waiver `duplicate_of_done:<id>`; only main-orchestrator/user decides.
- Shared frontend/auth/chat/router/error files require real browser `/verify-slice` evidence before closer; auto verify is for low-risk non-UI/non-shared tasks only.
- Planner must block stale task worktrees as `stale_worktree_dep_missing`; it must not auto-rebase/merge/reset.

## Guardrails añadidos por lecciones lifecycle/FU

- `scripts/check-worktree-deps-visible.sh <TASK_ID>` bloquea planning si la worktree no ve deps ya cerradas en `origin/main`/root canónico.
- FU duplicadas: validator/tester sólo escriben `FU_PROPOSAL`; main-orchestrator registra/promueve y el script avisa/bloquea duplicados probables.
- `write_set` de FU promovida puede estar desviado: hacer `find`/`grep`, documentar path real en el pack; no abrir otra FU para corregir el string.
- Shared files (`errors.ts`, auth/chat/routing/providers/context/store) no aceptan auto-verify y las bajas grandes/estructurales requieren `destructive_edit_set`.

### PR-flow invariant

Run `./scripts/next-wave.sh` from anywhere in the repo/worktree: it resolves the canonical root, syncs `main` from `origin/main` when safe, and only then prints ready tasks. New PR-flow worktrees are created from `origin/main`; in-flight worktrees are not rebased by planner. If sync blocks, resolve dirty source-of-truth/product files before starting another slice.

### Follow-up promotion and bootstrap refresh safety

`register-followup-task.sh promote` appends a runtime follow-up as new DAG work; it must not reopen already-closed slices. Bootstrap refresh preserves closer-final tasks as `done` even if their source fingerprint later drifts, records `source_fingerprint_changed_after_done`, and keeps all-done phases as `complete`. If the changed source represents new product work, create/promote a new follow-up instead of mutating the closed slice.

