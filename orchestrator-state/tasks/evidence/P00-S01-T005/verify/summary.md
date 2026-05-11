# /verify-slice evidence — P00-S01-T005 (i18n resources ES/EN/FR)

- TASK_ID: P00-S01-T005
- Timestamp: 2026-05-11T16:00:00Z
- Mode: pre-closer
- Verifier: main-orchestrator + Chrome DevTools MCP (autonomous)
- Worktree: `.claude/worktrees/agent-aba9672c77f4f9801`
- Dev server: `VITE_ENABLE_VERBOSE_LOGGING=true npm --prefix frontend run dev -- --host 0.0.0.0 --port 5173` (PID 33485, port 5173)

## Hard reset

Frontend-only static slice. No backend, no DB. Hard reset = stop dev server (none running), start fresh from T005 worktree with verbose logging on. No data setup needed: the slice is build-time static JSON bundles.

## Reproduction (Chrome MCP, real DOM, real React)

| Step | Action | Observed | Pass |
|---|---|---|---|
| 1 | Open `http://localhost:5173/showcase` | Section 10 visible (`10 · I18N DEMO — ES / EN / FR`); default ES | ✅ |
| 2 | Read ES values | `common:productName=Hilo`, `auth:signIn.title=Entrar`, `errors:AUTH_INVALID_CREDENTIALS=Email o contraseña incorrectos`, `account:language=Idioma`, `Active locale: es`, `i18next initialized: true` | ✅ |
| 3 | Click "Switch language to en" | `auth:signIn.title=Sign in`, `errors:AUTH_INVALID_CREDENTIALS=Incorrect email or password`, `account:language=Language`, `Active locale: en` | ✅ |
| 4 | Click "Switch language to fr" | `auth:signIn.title=Connexion`, `errors:AUTH_INVALID_CREDENTIALS=Email ou mot de passe incorrect`, `account:language=Langue`, `Active locale: fr` | ✅ |
| 5 | Click "Switch language to es" (revert) | Back to ES literals | ✅ |
| 6 | `common:productName` across all 3 languages | Always `"Hilo"` (brand constant) | ✅ |

## Verbose logs (browser console, includePreservedMessages=true)

- `i18n.init.start` (msgid=3) and `i18n.init.ok` (msgid=4) — emitted at module load. **Confirms BEFORE/AFTER init gated by `VITE_ENABLE_VERBOSE_LOGGING=true`.**
- `i18n-demo.changeLanguage.start` / `i18n-demo.changeLanguage.ok` pairs (msgid=64–69) — one pair per click (EN, FR, ES). **Confirms BEFORE/AFTER consumer logs gated.**
- `providers.init.start` / `providers.init.ok` (msgid=7–10) — pre-existing T002 logs, not regressed by T005.
- Zero PII / tokens / secrets in any log payload.

## Network requests (33 total during init)

- Vite HMR client + react/react-dom/react-router/react-i18next/i18next deps + tokens.css/global.css + showcase modules + I18nDemoSection.tsx + i18n/index.ts + i18n/languages.ts.
- **Zero requests to `/locales/**/*.json`** during normal app boot or during the 3 language switches. Bundles are inline (TS literal objects in `src/i18n/index.ts`) — matches task pack §2.5 decision (no `i18next-http-backend`, no lazy load).
- `fetch('/locales/es/auth.json')` returned **200** when invoked manually — Vite serves `public/locales/` as static assets (canonical reference / future migration path), but the app does NOT consume them at runtime. Both facts coexist by design (handoff §Developer run, decision 1).

## Storage / cookies

- `localStorage`: `{}` (empty)
- `sessionStorage`: `{}` (empty)
- `i18nextLng` key: **absent** — confirms language detector OFF (heredado T002 R1).
- `document.cookie`: `csrf_token=...` (from previous backend session, not from i18n — unrelated to T005).
- `document.documentElement.lang`: `"es"` (static from `index.html`; i18next does not mutate it — by design, KISS).

## Verification Data Contract

Per task pack §2.2, T005 is a frontend-only static slice with no DB write. The §6.5 Verification Data Contract rows (J100/J101/J102) are consumed by downstream slices that materialize `users.preferred_language` (P01-S02-T007), not by T005. The "data" of T005 is the 24 JSON bundles, all validated by the tester run (`python3 JSON.load() × 24 files: PASS`).

Rows used: **n/a — slice without persistence**.

## Findings

None. All acceptance criteria from task pack §9 are visually and behaviorally confirmed in browser:

- 8 namespaces × 3 langs = 24 bundles loaded (visible via i18next `options.resources`).
- Fallback `es` (covered by tester unit test 3 in `i18n.test.ts`).
- `lng=es`, `fallbackLng=es`, `defaultNS=common` (confirmed in `Active locale: es` default + tester test 1).
- `errors:AUTH_INVALID_CREDENTIALS` resolves in all 3 langs (visible in demo).
- EN/FR not copy-paste of ES (visible distinct strings).
- `changeLanguage` updates resolution (visible after each button click).
- Missing-key handler does not throw (covered by tester test 6).
- BEFORE/AFTER logs gated by `VITE_ENABLE_VERBOSE_LOGGING` (visible in console).
- Detector OFF, no `i18nextLng` in storage (verified directly).

## Files

- 01-es-default.png — section 10 in ES
- 02-en.png — after clicking EN
- 03-fr.png — after clicking FR
- 04-es-revert.png — after clicking ES again
- console-messages.txt — full console dump
- network-requests.txt — full network dump
- storage-state.txt — storage/cookies inspection
