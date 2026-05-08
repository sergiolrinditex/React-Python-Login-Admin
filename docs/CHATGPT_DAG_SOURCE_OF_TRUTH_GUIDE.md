# ChatGPT DAG Source-of-Truth Guide

La guía operativa canónica vive en `docs/guides/CHATGPT_DAG_SOURCE_OF_TRUTH_GUIDE.md`. Este fichero de compatibilidad conserva la ruta histórica que usan tests y enlaces antiguos.

Contrato actual:

- Genera 5 source-of-truth docs: `instrucciones.md`, `<APP>_TECHNICAL_GUIDE.md`, `<APP>_IMPLEMENTATION_CHECKLIST.md`, `STACK_PROFILE.yaml`, `UX_CONTRACT.md`.
- Usa uno de tres perfiles: `minimal`, `large-without-base`, `large-with-base`.
- `large-with-base` hereda `docs/base-app/` y conserva Flutter + FastAPI + Postgres/Supabase-compatible.
- `minimal` y `large-without-base` son AnyStack y deben declarar su stack en `STACK_PROFILE.yaml`.
- El `Canonical Coverage Registry` debe incluir `Depends on`, `Conflict group`, `Write set`, `Journey refs`, `Product increment` y `Build state` para producir `mode=explicit_dag`.
- Antes de ejecutar slices, valida con `./scripts/check-wiring-contract.sh --strict --require-new-template-columns`.
- Cada terminal debe exportar `CLAUDE_ACTIVE_TASK_ID` y `CLAUDE_TASK_PACK` antes de llamar `/next-slice <TASK_ID>`.

Lee la guía completa en `docs/guides/CHATGPT_DAG_SOURCE_OF_TRUTH_GUIDE.md` antes de generar documentos.
