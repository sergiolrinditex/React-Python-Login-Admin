# Architecture contract

- Generated at: 2026-05-17T17:23:59+00:00
- Source: `docs/source-of-truth/HILO_PEOPLE_TECHNICAL_GUIDE.md`

## Structural headings
- H1: Hilo People — Technical Guide (large app sin baseline)
- H2: 1. Overview específico
- H2: 2. Stack — contrato completo
- H3: 2.0 Library Discovery Pass
- H3: 2.1 Stack — paquetes auxiliares
- H2: 3. Comandos — adiciones
- H2: 4. Estructura del proyecto — adiciones
- H2: 5. Arquitectura
- H3: 5.1 Componentes nuevos
- H3: 5.2 Flujo de datos específico
- H3: 5.3 Decisiones de diseño
- H2: 6. Interfaces — adiciones
- H3: 6.1 Rutas/pantallas frontend
- H3: 6.2 Endpoints API nuevos
- H3: 6.3 Modelos de datos nuevos
- H3: 6.4 Formato de errores específico
- H3: 6.4 Navigation Contract
- H3: 6.5 Verification Data Contract
- H2: 7. Theme & Design System
- H3: 7.1 Visual Implementation Contract
- H2: 8. Logging y Observabilidad
- H2: 9. Testing
- H3: 9.1 Convenciones específicas
- H2: 10. Backend / API — adiciones
- H3: 10.1 Módulos del backend
- H3: 10.2 Auth strategy
- H3: 10.3 DB Schema — tablas nuevas
- H3: 10.4 AI stack — motor específico
- H4: LLM Gateway
- H4: RAG
- H4: Deep Agents
- H4: LangGraph
- H4: MCP
- H3: 10.5 Backend logging
- H2: 11. Deploy
- H3: 11.1 Variables de entorno adicionales
- H3: 11.2 Build targets
- H3: 11.3 Rollback strategy
- H3: 11.4 Cross-origin / reverse-proxy topology
- H2: 12. Constraints & Invariants

## Constraint and invariant signals
- | LangGraph | obligatorio en chat | disponible para workflows/approvals | chat simple no necesita complejidad de graph en V1 |
- Toda pantalla frontend debe:
- El handoff de cada slice frontend debe incluir:
- CONSTRAINT users_language_chk CHECK (preferred_language IN ('es','en','fr'))
- | `LITELLM_MASTER_KEY` | dev key | secret | secret | bearer que el backend envía al proxy LiteLLM; debe coincidir con `credential_plain` del fixture activo en `data/verification/admin_ai/credentials/*.json` |
- - SSE / streaming (P02-S04 `POST /api/v1/chat/conversations/{id}/stream`) debe verificarse explícitamente a través del proxy cuando aterrice; vite preserva chunked transfer por defecto.

## Operating note
This file is derived. Use it as an execution contract, but reconcile against the raw guide when ambiguity matters.
