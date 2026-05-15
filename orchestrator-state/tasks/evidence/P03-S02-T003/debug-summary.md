# Debugger evidence summary — P03-S02-T003

## Verdict
MCP/environment artifact. **No product bug.** The /history → /chat redirect observed
by slice-verifier was caused by the **wrong vite dev server bound to port 5173**:
the listener on :5173 belongs to the P03-S02-T002 worktree (started 4:57PM), not
the P03-S02-T003 worktree. T002's router does not yet have the /history route, so
the request hit the catch-all `*` → `/` → RootRedirect → `/chat`.

## Reproduction (against the wrong vite on :5173)
1. New tab → `http://localhost:5173/history`
2. URL becomes `http://localhost:5173/chat` (RootRedirect, authenticated user).
3. Console shows ChatHomePage rendered, never HistoryPage.
4. `curl http://localhost:5173/src/app/router.tsx` returns the source from
   `/Users/sergiolr/Desktop/Productos/React-Python-Login-Admin-worktrees/P03-S02-T002/frontend/src/app/router.tsx`
   (no `/history` route, no `HistoryPage` import).
5. `lsof -i tcp:5173 -sTCP:LISTEN` → PID 79038, command:
   `node …/P03-S02-T002/node_modules/.bin/vite --host 0.0.0.0 --port 5173`.

## Counter-test (against the correct T003 vite on :5273)
1. Started a clean vite from T003 worktree on port 5273.
2. Auth via /api/v1/auth/sign-in + /api/v1/auth/2fa/verify (TOTP from
   data/verification/auth/mfa_primary.json) → 200, refresh cookie set on :5273.
3. Navigated to `http://localhost:5273/history` → URL stays at /history.
4. HistoryPage renders correctly: heading "CONVERSACIONES", group label "AYER",
   3 conversation buttons with proper aria-labels:
   - "Abrir conversación, ¿Cuántas vacaciones me quedan este año?"
   - "Abrir conversación, ¿Cuántos días de vacaciones me quedan?" (×2)
5. Real verification data (J102 history loader, 2 personal conversations + 1 from
   another verification user persisted before).

## Static analysis (router source-of-truth)
- `frontend/src/app/router.tsx` line 49: `import HistoryPage from "../pages/chat/HistoryPage";` ✓
- Line 75: `export const ROUTE_HISTORY = "/history";` ✓
- Line 161: `<Route path={ROUTE_HISTORY} element={<HistoryPage />} />` inside
  `<Route element={<RequireAuth><Outlet /></RequireAuth>}>` ✓
- Route order: `/history` is BEFORE the catch-all `*` route ✓
- HistoryPage.tsx has no spurious `navigate("/chat")` on mount ✓
- RequireAuth.tsx during hydrating renders a neutral div (no Navigate) ✓

## Test gates (T003 worktree)
- tsc --noEmit → exit 0
- vitest verbose=true → 193/193 pass (16 files), 2.90s
- (verbose=false skipped — same results expected; tester already validated both modes)

## Files
- `debug-history-redirect-to-chat.png` — wrong-vite reproduction (URL=/chat)
- `debug-history-renders-correctly-on-t003-vite.png` — correct-vite render (URL=/history, conversations visible)
- `debug-served-router-source.txt` — proof :5173 serves T002 router
- `debug-vite-process-on-5173.txt` — lsof + ps proof of cross-worktree port collision
