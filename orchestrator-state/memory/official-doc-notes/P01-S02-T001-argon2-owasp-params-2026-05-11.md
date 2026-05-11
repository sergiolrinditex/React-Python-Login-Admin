# Official Doc Note: Argon2id OWASP 2026 Parameters vs argon2-cffi 25.1.0 Defaults

TOPIC: Argon2id OWASP 2026 recommended parameters vs argon2-cffi 25.1.0 PasswordHasher defaults
SOURCE: https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html
RETRIEVED: 2026-05-11
INTERNAL: Task pack §F.3 states "Use `argon2.PasswordHasher()` with library defaults: time_cost=3, memory_cost=64*1024 KiB = 64 MiB, parallelism=4, hash_len=32, salt_len=16. These are the OWASP 2024 minimums for Argon2id."
OFFICIAL: OWASP Password Storage Cheat Sheet (latest, retrieved 2026-05-11) specifies FIVE equivalent minimum configurations for Argon2id:

  1. m=47104 KiB (46 MiB), t=1, p=1
  2. m=19456 KiB (19 MiB), t=2, p=1
  3. m=12288 KiB (12 MiB), t=3, p=1
  4. m=9216  KiB (9 MiB),  t=4, p=1
  5. m=7168  KiB (7 MiB),  t=5, p=1

  Notable points:
  - Argon2id is explicitly recommended over Argon2i and Argon2d.
  - All five configs use parallelism=1 (p=1), not p=4.
  - The OWASP document does NOT specify recommended salt_len or hash_len — these are left to library defaults (typically 16 bytes salt, 32 bytes hash).
  - These are MINIMUM thresholds, not optimal targets.

  argon2-cffi 25.1.0 PasswordHasher defaults (confirmed from ReadTheDocs 25.1.0):
  - time_cost=3, memory_cost=65536 KiB (64 MiB), parallelism=4, hash_len=32, salt_len=16
  - type=Type.ID (Argon2id — correct variant)
  - Source: RFC_9106_LOW_MEMORY profile (changed in v21.2.0)

RECOMMENDATION: The task pack's characterization is factually inaccurate but the RECOMMENDATION to use defaults is CORRECT and safe. Specifically:
  - The argon2-cffi defaults (64 MiB / t=3 / p=4) EXCEED all five OWASP minimum configurations.
  - The closest OWASP config to the defaults is config 3 (m=12288, t=3, p=1) — the defaults use 5x more memory (64 MiB vs 12 MiB) and 4x the parallelism.
  - Using `PasswordHasher()` with no arguments is production-grade and ABOVE OWASP minimums.
  - Do NOT lower params to match OWASP minimums — use the library defaults as-is.
  - Do NOT explicitly pass `type=Type.ID`; the default is already Argon2id (Type.ID).
  - If the server is memory-constrained (< 64 MiB free per request), tune `memory_cost` down to OWASP config 1 (46 MiB minimum), but document the trade-off.
  - Developer should note in `password.py` docstring: "Parameters exceed OWASP 2026 Argon2id minimums; see OWASP Password Storage Cheat Sheet §Argon2id."

ACTION REQUIRED BY DEVELOPER:
  - Implementation: use `PasswordHasher()` defaults as the task pack says — no code change needed.
  - Docstring in `password.py`: correct the comment to say "defaults EXCEED OWASP 2026 minimums" (not "are the OWASP minimums").
  - This note should be marked RESOLVED once the docstring is correct.

RESOLVED: Developer corrected password.py docstring to state params EXCEED OWASP 2026 minimums (not ARE the minimums). No code change needed — PasswordHasher() defaults are production-grade and above OWASP thresholds. Updated 2026-05-11.
