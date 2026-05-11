# Dev loop and verification

Project: backend server, client runtime (dev server, emulator, simulator, or equivalent per TECHNICAL_GUIDE), and database MUST be up before any implementation work.

## Pre-conditions

- Backend server running; `curl localhost:{port}/health` → 200.
- Client runtime running (dev server, emulator, simulator, or equivalent per TECHNICAL_GUIDE); verify availability using the method defined in TECHNICAL_GUIDE.
- Database: migrations applied, seed loaded.
- Ports, commands and health endpoints come from the TECHNICAL_GUIDE — never hardcoded.

If any server is down, restart before continuing work.

## Per-slice verification

After completing a slice the developer runs:

- Backend lint → zero issues.
- Backend tests → all green.
- Client/frontend lint → zero issues.
- Client/frontend tests → all green.
- Visual check using the method defined in TECHNICAL_GUIDE (browser, emulator, simulator, device, etc.).

A slice is not ✅ until:

- Backend endpoint verified (curl or API test).
- Client UI verified visually using the method defined in TECHNICAL_GUIDE (browser, emulator, device, etc.).
- All tests green on both sides.
- Logs correct under both `ENABLE_VERBOSE_LOGGING` values.
- PROGRESS.md updated.
- Handoff written.

If a slice cannot be verified in localhost, split it.

## Visual check (mandatory)

1. Launch the app using the method defined in TECHNICAL_GUIDE (browser URL, emulator, simulator, physical device, etc.).
2. Navigate to the new page/feature.
3. Verify professional design: design tokens, spacing, typography, alignment.
4. Verify the motor: click → data flows → backend responds → UI updates.
5. Document what you saw in PROGRESS.md.

If design is off → fix before moving on. If the motor is off → fix before moving on.

The full human visual verification is performed by `/verify-slice` after tester pass: hard reset, real/provided data, reproduction in browser, live watch of 3 logs, validation table. `/verify-slice` is resilient to `/clear` — it rebuilds context from disk (PROGRESS.md, runtime-state.json, registry.json, handoff, TECHNICAL_GUIDE) so you can (and should) `/clear` between tester pass and verify to free the ~100-200k tokens consumed by the pipeline.
