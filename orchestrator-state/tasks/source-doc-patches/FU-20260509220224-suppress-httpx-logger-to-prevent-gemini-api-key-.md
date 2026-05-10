# Source-of-truth amendment — FU-20260509220224-suppress-httpx-logger-to-prevent-gemini-api-key-

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S02-T009 | security | Suppress httpx logger to prevent Gemini API key leak in verbose logs | Runtime follow-up P00-S02-T006 | current | planned | medium | human | P00-S02-T006 | logging_config | backend/app/core/logging.py | J103 | — | — | — | runtime-followup#FU-20260509220224-suppress-httpx-logger-to-prevent-gemini-api-key- | runtime-followup#FU-20260509220224-suppress-httpx-logger-to-prevent-gemini-api-key- | grep -E 'AIza\|sk-[A-Za-z0-9]{20}' verbose_logs.txt returns 0 matches when ENABLE_VERBOSE_LOGGING=true and endpoint makes a real Gemini API call | ENABLE_VERBOSE_LOGGING=true pytest test_admin_ai_discover_models.py::test_discover_models_gemini_real -v && grep -E 'AIza' logs.txt \| wc -l (expect 0) |
```
