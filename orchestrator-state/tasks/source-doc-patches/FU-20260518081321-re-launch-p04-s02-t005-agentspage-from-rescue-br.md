# Source-of-truth amendment — FU-20260518081321-re-launch-p04-s02-t005-agentspage-from-rescue-br

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S02-T007 | followup | Re-launch P04-S02-T005 AgentsPage from rescue branch (needs_debug → closer) | Runtime follow-up P04-S02-T005 | current | planned | high | human | P04-S02-T005 | front:agents | frontend/src/features/agents/**, frontend/src/pages/admin/agents/**, frontend/src/app/router.tsx, frontend/src/i18n/index.ts, frontend/src/i18n/languages.ts | J105 | /admin/ai/agents | — | — | runtime-followup#FU-20260518081321-re-launch-p04-s02-t005-agentspage-from-rescue-br | runtime-followup#FU-20260518081321-re-launch-p04-s02-t005-agentspage-from-rescue-br | AgentsPage /admin/ai/agents accesible en main, ruta funcional, 40 tests verdes en frontend, handoff con ## verify-slice VERIFY_OUTCOME=verified, branch dev/P04-S02-T005 mergeada a main vía pr-flow, status=done en registry. | Tras retoma: pytest backend/tests verde, vitest frontend/src verde, navegación browser a /admin/ai/agents como people_admin renderiza la página, smoke API GET /api/v1/admin/ai/agents → 200. |
```
