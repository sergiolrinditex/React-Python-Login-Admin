---
description: Auto-verifies a low-risk DAG slice with deterministic commands, then offers closer.
argument-hint: "<TASK_ID>"
---

# /auto-verify-slice

Uso exclusivo para slices con `Risk level=low` y `Verify mode=auto`. No reemplaza `/verify-slice` para UI, journeys, auth, endpoints mutantes, datos personales, pagos ni cualquier slice `medium|high|critical`.

1. Ejecuta `./scripts/auto-verify-slice.sh <TASK_ID>`.
2. Si `VERIFY_OUTCOME=verified`, lee el handoff y ofrece spawnear `closer` con el mismo `TASK_ID`/`TASK_PACK`.
3. Si falla, spawnea `debugger`, vuelve a `validator ‖ tester` y repite el verify que corresponda.

El helper solo escribe en `orchestrator-state/tasks/handoffs/<TASK_ID>.md` y `orchestrator-state/tasks/evidence/<TASK_ID>/`.
