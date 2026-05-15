# Non-negotiables (single source)

This file is the ONLY place where project-wide non-negotiables live. Agents, skills, commands and CLAUDE.md reference it instead of repeating it. If a rule below is missing in an agent prompt, the agent still applies it — they are implicit.

## Production quality

- Real production product, not a prototype or demo.
- Real validations, real error handling, real security from day 1.
- No fake data, no hardcoded responses, no "TODO: implement later", no shortcuts.

## Code architecture

- Clean Architecture on both sides: `presentation → domain ← data`. Domain imports nothing external.
- Feature-based modules: `src/features/{feature}/` on the frontend, `api/features/{feature}/` (or equivalent) on the backend.
- Shared code under `src/shared/` or `api/shared/` ONLY when used by 2+ features.
- DRY / KISS / YAGNI. Zero speculative features.

## Design system & tokens (stack-agnostic)

Visual branding tokens must live in one declared module. Hardcoded visual literals outside that module are forbidden. The concrete module path and scanner are not hardcoded in this rule; they are declared by:

- `docs/source-of-truth/STACK_PROFILE.yaml -> frontend.theme_root`
- `docs/source-of-truth/STACK_PROFILE.yaml -> design_tokens_enforcer`
- `.claude/enforcers/<design_tokens_enforcer>.sh`
- `.claude/enforcers/<design_tokens_enforcer>/RULES.md`

The default recommended plugin is `design_tokens_v1`, which reads `frontend.framework` and applies stack-specific scanning internally. Use `design_tokens_enforcer: none` only when the project intentionally disables visual-token enforcement, and make that trade-off explicit in source-of-truth.

## File size

- **One responsibility per file** — this is the rule; the line count is the signal.
  - Target **~200 lines**; hard cap **~300 lines**. Approaching 300 lines almost always means hidden sub-responsibilities: split by concern, not by line count.
  - Self-contained UI components (widget, screen, page, view) may reach ~300 lines when they contain only layout, local state, and lifecycle — no business logic leaking in.
  - Entities, use cases, and repositories follow the stricter ~200-line target: a use case approaching 200 lines likely has hidden sub-steps that deserve their own class.
- Max **~50 lines** per function/method.
- 1 component per file. 1 use case per file. 1 entity per file.

## Tests are REAL

- No mocking business logic. No stubbing of services you control.
- Backend tests hit real service → real repository → real DB.
- Frontend integration tests hit real use cases → real repositories → real backend.
- E2E tests simulate a real user with real backend + real DB running.
- Only acceptable mocks: external third-party APIs you do not control (Stripe, FCM, gateways).
- If a test passes with the backend or DB down, it is NOT a valid integration/E2E test — rewrite it.
- Unit tests for pure logic (entities, validators, formatters) CAN be isolated.

## Logging

- Every function, use case, repository, endpoint and component action logs BEFORE the operation (what will be done, with what input) and AFTER (result or error).
- Errors log with full context (input, state, stack trace). Never log tokens, passwords, or PII.
- Flag `ENABLE_VERBOSE_LOGGING` controls visibility: `true` shows the full flow, `false` shows only warning+error.
- Code is never modified to remove logs — only the flag changes.

## PROGRESS.md

- `orchestrator-state/memory/PROGRESS.md` is the live project snapshot.
- The `developer` updates it after EVERY slice with: current phase, last slice, next slice, backend endpoints, frontend routes, DB tables/migrations, test counts by level, milestones, recent decisions, known issues.
- After `/clear` or session restart, agents read PROGRESS.md FIRST.
- PROGRESS.md is a DERIVED artifact — the five source-of-truth docs remain the authority when present; the five source-of-truth docs are mandatory for production.

## Documentation

- Every file starts with a docstring explaining what it does, the slice/phase, and key dependencies beyond imports.
- Every public class/method/function/endpoint has a doc comment with purpose, parameters, return, possible errors.
- Every use case documents its business rule and side effects.
- Non-obvious decisions have an inline comment pointing to the source doc.

## Error handling

- Never `catch` generic Exception/Error. Catch typed domain errors.
- Frontend repositories return Result/Either; never throw upward.
- Backend endpoints return `{ error, code, details }` via centralized error middleware.
- Form validation returns ALL errors at once, validated on both client and server.
- UI shows user-facing messages from a centralized mapper; never raw stack traces.
- Global error boundary/handler on both sides.

## Security

### General
- Secrets only in env vars or secret manager. Never in source or frontend bundles.
- All traffic HTTPS only.
- Parametrized queries ALWAYS. Sanitize all inputs on both sides.
- CORS whitelist specific origins. Rate-limit public endpoints, especially auth.
- Passwords hashed with bcrypt/argon2 (o delegado al proveedor gestionado declarado).
- OWASP top 10 compliance (XSS, CSRF, SQL injection, broken auth, misconfig).
- Security headers: HSTS, X-Content-Type-Options, X-Frame-Options, CSP.
- Production builds minified; source maps not exposed.

### Token storage — platform-aware (NUNCA negociable)
- **Mobile (iOS/Android)**: access y refresh tokens SIEMPRE en secure storage del OS (Keychain en iOS, EncryptedSharedPreferences en Android) vía `flutter_secure_storage` o equivalente. NUNCA en `SharedPreferences`, `NSUserDefaults` ni `localStorage`. NUNCA en claro en disco.
- **Web**: refresh token SIEMPRE en cookie `HttpOnly; Secure; SameSite=Lax; Path=/auth`. El access token vive solo en memoria del cliente (variable de runtime del cliente, nunca persistido). NUNCA access ni refresh en `localStorage` ni `sessionStorage`.
- Cuando se usa un SDK gestionado que persiste tokens en `localStorage` por defecto (SDK gestionado declarado, etc.), se implementa patrón **BFF (Backend-For-Frontend)**: el navegador no habla directamente con el proveedor de auth — habla con endpoints propios del backend (`/auth/login`, `/auth/refresh`, `/auth/logout`, `/auth/session`) que manejan la sesión server-side y devuelven cookies httpOnly al navegador.
- Access token con TTL corto (900-1800s). Refresh rotativo en cada uso.

### Claves de proveedores externos (LLM, embeddings, payments, etc.)
- NUNCA en texto plano en base de datos ni logs.
- Cifrado en reposo con `cryptography.Fernet` (o equivalente AEAD) y master key en variable de entorno rotable (`PROVIDER_ENCRYPTION_KEY`).
- Cuando hay múltiples proveedores intercambiables para la misma categoría, se aplica invariante "como máximo un proveedor activo a la vez por categoría" a nivel DB (partial unique index `WHERE is_active = true`). No se confía en la lógica de aplicación para este invariante.
- El cliente frontend NUNCA recibe la clave — el admin panel muestra key enmascarada (`sk-****1234`). Toda interacción con el proveedor pasa por el backend.

### Audit log (obligatorio para GDPR / compliance)
- Acciones sensibles se registran en `audit_log(id, user_id, action, resource, timestamp, ip, user_agent, metadata_jsonb, request_id)`.
- Acciones sensibles mínimas: cambio de email, cambio de password, borrado de cuenta solicitado/confirmado, activación/rotación de proveedor AI, creación/eliminación de admin, export de datos GDPR, logout global.
- Los logs de auditoría se retienen indefinidamente (GDPR Art. 30 "records of processing").
- Al borrar una cuenta (derecho al olvido, GDPR Art. 17), el `user_id` en audit log se pseudonimiza (hash SHA-256 del UUID con salt global), pero la entrada no se borra — la linkabilidad al sujeto queda rota, la traza operativa persiste.

### Request correlation
- Cada request HTTP lleva un header `X-Request-ID` (UUID v4). Si el cliente no lo provee, un middleware lo genera.
- El request ID viaja en TODOS los logs relacionados (backend, repositorios, AI pipelines, tool calls) como campo `request_id` del log estructurado.
- El backend devuelve el `X-Request-ID` en la response header. Permite trazabilidad end-to-end en producción (logs + soporte al usuario).

## Accessibility

- Every interactive element has an accessible label.
- Every image has alt text (decorative → `alt=""`).
- Tap targets min 44x44 px. Contrast meets WCAG AA.
- Keyboard-only navigation works end-to-end.
- Dynamic content changes announced via `aria-live`.
- Never convey information with color alone.

## Dependencies

- Audit npm/PyPI score, maintenance, license before adding anything.
- Never add a package for something doable in <20 lines.
- Pin exact versions. Use lockfiles. Backend ≤25, frontend ≤30 direct deps.
- Audit (`npm audit`, `pip audit`) at each phase gate.

## Database

- Every schema change is a migration file. Never modify DB manually.
- Migrations reversible. Tested in both directions.
- Data setup scripts may load only real/provided verification data, never decorative demo data.
- Every frontend entity has a matching DB table/collection.
- Indexes on every field used in WHERE / ORDER BY / JOIN.
- Transactions for multi-step ops; rollback on failure.

## API contract

- Every endpoint documented in TECHNICAL_GUIDE: method, path, request schema, response schema, error codes, auth.
- Version routes: `/api/v1/...`.
- Consistent envelope: `{ data, meta, errors }`.
- Cursor or offset pagination on list endpoints; no unbounded lists.
- Input validation at controller level; return 400 with field-level errors.
- Auth endpoints: login, register, refresh, logout minimum.
- Health check: `GET /health` → 200 with `{ status, version, uptime }`.
- OpenAPI/Swagger spec kept in sync with implementation.

## Chain discipline (per slice)

Allowed max chain = 20 spawns, with aggressive parallelism:

1. `planner` (blocking — selects task, builds pack, impact analysis)
2. `developer` (+ `official-docs-researcher` si aplica; mismo mensaje cuando se invoque)
   - `developer` implements.
   - `official-docs-researcher` runs only when the planner marks `NEEDS_OFFICIAL_DOCS: yes` or the slice touches unconfirmed external API/library/security/AI/RAG/MCP/streaming/DB/deploy behavior. Give it 1–5 concrete questions; it uses cache/MCP/Context7 first and writes a discrepancy note only for a real official-doc mismatch with the source-of-truth.
3. `validator` ‖ `tester` (parallel — one message, two Agent calls)
4. `debugger` (if tester fails OR validator requests changes; then re-run step 3). Max 3 cycles; on the 4th failure the debugger emits `OUTCOME: blocked` with reason `max_debug_cycles_reached` and escalates to the human.
5. `closer` (evidence + atomic commit via configured Git workflow (`./scripts/git-workflow.sh`) + safe worktree cleanup)

Between steps 4 and 5 the human gate is mandatory: `/verify-slice` delegates to `slice-verifier` for hard reset + datos reales/proporcionados + human reproduction through Chrome DevTools MCP, claude-in-chrome or Agent360 Browser MCP (`browser-mcp`). `/verify-slice` is resilient to `/clear` — it rebuilds state from disk (PROGRESS.md, runtime-state, registry, handoff, TECHNICAL_GUIDE). The `closer`'s pre-check refuses to commit unless `## verify-slice` has `VERIFY_OUTCOME: verified` plus MCP/data/evidence fields (or explicit `VERIFY_WAIVED: <reason>`). The state sequence is `ready_for_close -> verified_pending_close -> done`.

Never skip mandatory steps. Parallelize where possible.

## AI/ML libraries — volatile ecosystem

LangChain, LlamaIndex, CrewAI, AutoGen, Semantic Kernel, Haystack, DSPy, Instructor, OpenAI SDK, Anthropic SDK, Google AI SDK, HuggingFace, transformers, and any dep >1.x in the AI ecosystem change fast. `official-docs-researcher` MUST verify the latest stable version, imports, and patterns before the developer touches them. Never rely on training memory for these.

## Auto-approve policy

- Agents MUST NOT ask permission before modifying project files. Permissions are pre-approved in `settings.json`.
- This includes PROGRESS.md, handoff files, ledger, registry, task-pack files, and any project code/config.

