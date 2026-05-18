# Source-of-truth amendment — FU-20260518081321-re-launch-p04-s03-t002-usagepage-from-rescue-bra

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S03-T004 | followup | Re-launch P04-S03-T002 UsagePage from rescue branch (ready_for_close → closer) | Runtime follow-up P04-S03-T002 | current | planned | high | human | P04-S03-T002 | front:usage | frontend/src/features/admin/**, frontend/src/pages/admin/usage/**, frontend/src/app/router.tsx, frontend/src/i18n/**, frontend/package.json, frontend/package-lock.json | J103 | /admin/usage | — | — | runtime-followup#FU-20260518081321-re-launch-p04-s03-t002-usagepage-from-rescue-bra | runtime-followup#FU-20260518081321-re-launch-p04-s03-t002-usagepage-from-rescue-bra | UsagePage /admin/usage accesible en main, ruta funcional con cards de uso real desde GET /api/v1/admin/usage, handoff con ## verify-slice VERIFY_OUTCOME=verified, branch dev/P04-S03-T002 mergeada a main vía pr-flow, status=done en registry. | Tras retoma: /verify-slice P04-S03-T002 con MCP browser, login auditor → /admin/usage muestra tabla con datos reales, smoke GET /api/v1/admin/usage?from=2026-05-01&to=2026-05-31 → 200, vitest frontend verde. |
```
