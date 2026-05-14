---
description: Convierte hallazgos reales de validator/tester/verify en una propuesta formal y, con aprobación humana, en una task DAG + YAML + source-of-truth amendment.
argument-hint: "propose|promote|waive|list ..."
---

# /register-followup

## Rule loading

Lee `.claude/rules/05-runtime-write-contract.md` y `.claude/orchestrator-contract.json` antes de actuar.

Este comando existe para que ningún hallazgo productivo quede en el aire. Si validator, tester, debugger, `/verify-slice` o `/verify-journey` descubren trabajo real que NO pertenece al `TASK_ID` actual, no edites `registry.json` ni inventes una nota suelta: crea una propuesta y promuévela con aprobación humana.


## Relación con /promote-followup

`/register-followup` es el comando de bajo nivel para proponer, listar y waivear. Para convertir una FU aprobada en task DAG productiva, usa preferentemente:

```bash
claude --agent main-orchestrator --permission-mode bypassPermissions "/promote-followup <FOLLOWUP_ID>"
```

Ese flujo inspecciona la FU, pide confirmación humana literal, llama al script de promoción bajo locks y revalida DAG/wiring. El closer nunca lo ejecuta automáticamente.

## Triage anti-spam

Antes de proponer una FU decide si el hallazgo es realmente fuera de scope:

- `in_scope_defect`: pertenece al TASK_ID actual y debe ir por `validator/tester -> debugger -> retest`; no crees FU.
- `out_of_scope|missing_coverage|missing_real_data|external_dependency|future_enhancement|scope_expansion|blocked_by_human_decision`: puede ser FU si explicas `--why-not-debugger`.

El script rechaza `--scope-classification in_scope_defect`. Para `high|critical|blocker`, `--why-not-debugger` es obligatorio.

## Casos

### 1. Proponer sin mutar DAG

Seguro durante una slice activa:

```bash
./scripts/register-followup-task.sh propose \
  --origin-task <TASK_ID> \
  --severity high|medium|low \
  --kind bug|ux|wiring|data|test|security|followup \
  --scope-classification out_of_scope|missing_coverage|missing_real_data|external_dependency|future_enhancement|scope_expansion|blocked_by_human_decision \
  --why-not-debugger "<por qué debugger/retest no lo puede arreglar dentro del TASK_ID>" \
  --product-increment <v0|v1|v2|current> \
  --title "<título>" \
  --description "<hallazgo real>" \
  --journey-ref <JID> \
  --conflict-group <grupo> \
  --write-set '<path-o-glob>' \
  --acceptance "<criterio de cierre>" \
  --verify "<verificación con datos reales/proporcionados>"
```

Notas de seguridad:

- Pon comillas simples en patrones glob de `--write-set`, por ejemplo `--write-set 'docs/source-of-truth/**'`, para que el shell no los expanda antes de llegar al script.
- Usa `--journey-ref` sólo con journeys que ya existen en `UX_CONTRACT.md`/journey matrix. Si el follow-up define una journey nueva, primero crea/amplía el source-of-truth de esa journey o no pases `--journey-ref` hasta que exista.

Esto escribe:

```text
orchestrator-state/tasks/follow-ups/<FOLLOWUP_ID>.yaml
orchestrator-state/tasks/runtime-state.json.open_followups[]
orchestrator-state/tasks/ledger.jsonl
```

### 2. Promover a task DAG real

Solo después de aprobación humana explícita:

```bash
./scripts/register-followup-task.sh promote <FOLLOWUP_ID>
```

Esto escribe bajo locks:

```text
docs/source-of-truth/*_IMPLEMENTATION_CHECKLIST.md  Runtime Follow-up Coverage Registry
  (incluye Product increment + Build state)
orchestrator-state/tasks/registry.json
orchestrator-state/tasks/work-items/<TASK_ID>.yaml
orchestrator-state/memory/task-dag.json
orchestrator-state/memory/task-dag.md
orchestrator-state/tasks/runtime-state.json
orchestrator-state/tasks/ledger.jsonl
```

Luego ejecuta:

```bash
./scripts/check-task-dag.sh --strict
./scripts/check-journey-matrix.sh --strict
./scripts/check-wiring-contract.sh --strict --require-new-template-columns
./scripts/next-wave.sh
```

### 3. Waive explícito

Solo si el usuario decide no convertirlo en trabajo:

```bash
./scripts/register-followup-task.sh waive <FOLLOWUP_ID> --reason "<motivo>"
```

## JSON

`--json` puede ir antes o después del subcomando, por ejemplo:

```bash
./scripts/register-followup-task.sh --json list
./scripts/register-followup-task.sh list --json
```

## Regla de bloqueo

Las propuestas `high`, `critical` o `blocker` bloquean `/next-wave` y `claim_task.py` hasta estar `promoted` o `waived`. No bloquean al `closer` del `origin_task_id` cuando ya existen como YAML `proposed`: el cierre debe meterlas en el PR automáticamente y dejar la decisión de promoción/waiver para después.
