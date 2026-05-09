# Source-of-truth amendment — FU-20260509073000-replace-synthetic-verification-bundle-with-peopl

Appended to `docs/source-of-truth/HILO_PEOPLE_IMPLEMENTATION_CHECKLIST.md`:

```md
| P00-S02-T005 | data | Replace synthetic verification bundle with People Tech delivery | Runtime follow-up P00-S02-T003 | current | planned | medium | human | P00-S02-T003 | seed:data | data/verification/** | J100, J101, J102, J103, J104, J105 | — | — | — | runtime-followup#FU-20260509073000-replace-synthetic-verification-bundle-with-peopl | runtime-followup#FU-20260509073000-replace-synthetic-verification-bundle-with-peopl | data/verification/ contains files exactly matching People Tech delivery (signed manifest), loader's synthetic- guard relaxed or moved to env-flag, J100..J105 verified end-to-end with the real bundle. | Journey verifications J100..J105 reproduced against the People Tech bundle, pytest backend/tests/integration -k seed green, no synthetic- placeholders remaining in data/verification/. |
```
