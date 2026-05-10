---
name: dev-loop
description: Start, restart, or check the dev servers (back + front). Use at session start or when servers need to be restarted.
disable-model-invocation: true
allowed-tools: Read Bash Glob
---

Manage the development servers for the fullstack project.

## Objective

Ensure both backend and frontend dev servers are running with hot-reload.

## Steps

1. Read `docs/source-of-truth/*_TECHNICAL_GUIDE.md` → extract backend start command + port, frontend start command + port, health endpoints.

2. Check if servers are already running:

   ```bash
   lsof -i :<BACK_PORT>  2>/dev/null || echo "Backend not running"
   lsof -i :<FRONT_PORT> 2>/dev/null || echo "Frontend not running"
   ```

3. If not running, start in background using the TECHNICAL_GUIDE commands:

   ```bash
   cd back  && <start_command> &
   cd front && <start_command> &
   ```

4. Wait and verify:

   ```bash
   sleep 3
   curl -s http://localhost:<BACK_PORT>/health
   curl -s -o /dev/null -w "%{http_code}" http://localhost:<FRONT_PORT>
   ```

5. Report status to the user with URLs to open.

## Notes

- Adapt commands from the TECHNICAL_GUIDE — never hardcode.
- If ports are occupied, report the conflict.
- If the project has an auxiliary runtime (AI worker, queue, etc.), include it.
- **Prefer `scripts/dev-restart.sh --soft`**: the framework ships a generic dispatcher (`scripts/dev-restart.sh`) plus a neutral stack profile (`scripts/dev-restart.profile.sh`). The dispatcher only orchestrates `--soft|--check|--reset`; all stack-specific commands (start backend, start frontend, reset DB, health probes) live in the profile. A generated app replaces the **profile only** — the dispatcher and the contract stay untouched. If a project deletes the profile, the dispatcher aborts with a clear error pointing to the missing file rather than guessing.
