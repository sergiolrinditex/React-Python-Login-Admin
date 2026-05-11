# P00-S02-T002 psycopg-version — Official Docs Verification
- DATE: 2026-05-11
- TASK_ID: P00-S02-T002

---

## DISCREPANCY: psycopg[binary] version — task pack says 3.2.x; current stable is 3.3.4

- OFFICIAL: `psycopg[binary]` current stable = **3.3.4** (released 2026-05-01). Series 3.3.x started with 3.3.0 on 2025-12-01. Series 3.3.x requires Python 3.10+; Python 3.12 is satisfied.
- INTERNAL (task pack §Stack + §U1 + §Impact): says "psycopg[binary]==3.2.x" and "PyPI actual: psycopg v3.2.x". The researcher hook explicitly asks to "confirm major.minor exact".
- IMPACT: **Minor but load-bearing** — if developer pins `psycopg[binary]==3.2.x`, pip will resolve to the last 3.2.x release (3.2.10 as per Context7 metadata). This works but leaves the project behind by 4 minor versions (3.3.0–3.3.4). `psycopg-binary==3.2.10` is the last 3.2.x release; it supports Python 3.12-slim-bookworm. No compatibility issue with `sqlalchemy==2.0.49` on either 3.2.10 or 3.3.4.
- SOURCE:
  - PyPI psycopg: https://pypi.org/pypi/psycopg/json → 3.3.4 as of 2026-05-01
  - PyPI psycopg-binary: https://pypi.org/pypi/psycopg-binary/json → 3.3.4 matches psycopg
  - Context7 /psycopg/psycopg lists version 3.2.10 (last 3.2.x)
  - psycopg3 docs: https://github.com/psycopg/psycopg binary install docs confirm `pip install "psycopg[binary]"` (no version pinned in official examples)
- SUGGESTED FIX: Pin `psycopg[binary]==3.3.4` (current stable, Python 3.10+ compatible — satisfied). If the project specifically wants the older 3.2.x line for any reason, pin `psycopg[binary]==3.2.10` (last 3.2.x). **Recommendation: use 3.3.4**.
- SQLAlchemy connection URL confirmed: `postgresql+psycopg://` prefix for psycopg3 sync `create_engine`. Works with both 3.2.x and 3.3.x.
- RESOLVED:

RESOLVED: 2026-05-11 — Developer pinned psycopg[binary]==3.3.3 (installed version confirmed). Researcher recommended 3.3.4 as current stable; 3.3.3 is one patch behind but fully compatible with sqlalchemy==2.0.49 and Python 3.12. Pinned to actual installed version for reproducibility. No blocking discrepancy.
