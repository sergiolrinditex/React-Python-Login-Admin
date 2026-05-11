---
name: dev-verify
description: Verify that the current slice works in localhost — visually and functionally. Opens browser, takes screenshots, verifies the motor works. Used by `closer` pre-check and by `/verify-slice` for deep verification.
disable-model-invocation: true
allowed-tools: Read Bash WebFetch Agent mcp__*
---

Verify the current slice in localhost — VISUALLY and FUNCTIONALLY.

## Objective

After each slice, confirm:

1. Both dev servers are running.
2. Backend endpoints respond correctly.
3. Frontend renders the expected UI and looks professional.
4. The **motor** works: data flows frontend → API → DB → frontend.
5. Tests are REAL (no mocks of business logic).
6. Logging works under both `ENABLE_VERBOSE_LOGGING` modes.
7. PROGRESS.md is updated.

## Steps

### 1. Servers alive

- Read TECHNICAL_GUIDE → dev server commands and ports.
- Health: `curl -s http://localhost:<BACK_PORT>/health` → 200.
- Front: `curl -s -o /dev/null -w "%{http_code}" http://localhost:<FRONT_PORT>` → 200/304.
- If either is down → report and suggest restart.

### 2. Backend slice

- Identify current slice's API endpoints from the checklist/task pack.
- Run `curl` against each — capture status code and response shape.
- Report any errors.

### 3. Visual verification in Chrome (CRITICAL)

Use Claude in Chrome MCP or computer-use to:

1. Open the app at the correct URL.
2. Navigate to the page/feature just built.
3. Screenshot the page.
4. Verify visually: professional design? Correct tokens? No broken elements / overflow / misalignment? Looks like production, not prototype?
5. Test the motor: click buttons, submit forms, navigate. Data flows? Loading states show? Errors show elegantly?
6. Screenshot each key state (empty, loading, data, error).
7. Document in the verify report.

If Chrome MCP is unavailable, fall back to curl + describe what the user should see.

### 4. Tests REAL

- Run test suite with backend + DB running.
- If any test passes with backend down → CRITICAL finding.

### 5. Logging

- `ENABLE_VERBOSE_LOGGING=true` shows full flow of the slice.
- `ENABLE_VERBOSE_LOGGING=false` shows only warning + error.

### 6. PROGRESS.md

- Read `orchestrator-state/memory/PROGRESS.md` → verify updated with this slice's results.

### 7. Verify report

Create/update `orchestrator-state/tasks/reports/verify-<slice-id>.md`:

```
## VERIFY: <Slice Name>

### Servers
- Backend:  localhost:BACK_PORT (200 OK)
- Frontend: localhost:FRONT_PORT (200 OK)

### Backend checks
- GET /api/xxx  → 200, returns expected schema
- POST /api/xxx → 201, creates correctly

### Visual check (Chrome)
- Page loaded: YES
- Looks professional: YES/NO — [details]
- Motor works:       YES/NO — [details]
- Screenshots: [paths]

### Tests
- Real tests (no mocks of business logic): YES/NO
- All green: YES/NO

### Logging
- Verbose on:  full flow visible: YES/NO
- Verbose off: only warn+error:   YES/NO

### PROGRESS.md updated: YES/NO

### Status: VERIFIED / ISSUES FOUND
```

This verification MUST pass before `closer` stages the commit.
