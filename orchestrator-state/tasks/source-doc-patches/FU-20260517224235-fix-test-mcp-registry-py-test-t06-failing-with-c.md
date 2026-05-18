# Source-of-truth amendment — FU-20260517224235-fix-test-mcp-registry-py-test-t06-failing-with-c

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P04-S01-T011 | bug | Fix test_mcp_registry.py::test_T06 failing with cryptography.fernet.InvalidToken (pre-existing, out-of-scope) | Runtime follow-up P04-S01-T007 | current | planned | medium | human | P04-S01-T007 | mcp:registry-tests | backend/tests/integration/test_mcp_registry.py, backend/app/security/encryption.py | — | — | — | — | runtime-followup#FU-20260517224235-fix-test-mcp-registry-py-test-t06-failing-with-c | runtime-followup#FU-20260517224235-fix-test-mcp-registry-py-test-t06-failing-with-c | pytest backend/tests/integration/test_mcp_registry.py -k test_T06 returns PASSED with current ENCRYPTION_KEY. | pytest backend/tests/integration/test_mcp_registry.py -v -k test_T06 confirms PASSED, full-file run shows no fernet.InvalidToken. |
```
