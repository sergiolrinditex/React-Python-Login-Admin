# Official Doc Note: Zod v4 is the Latest Stable + @hookform/resolvers import path

**Date**: 2026-05-08
**Task**: P00-S01-T002
**Packages**: `zod`, `@hookform/resolvers`
**Sources**:
- npm registry (`npm view zod --json`)
- Context7 `/websites/zod_dev_v4` (Source Reputation: High)
- Context7 `/react-hook-form/resolvers` (Source Reputation: High)

---

## Zod: v4 is the current latest stable

`zod@latest` = **4.4.3** (confirmed via npm dist-tags: `latest: 4.4.3`).

Zod v4 is a **major rewrite** from v3. Key breaking changes relevant to this stack:

| Change | v3 behavior | v4 behavior |
|---|---|---|
| `z.coerce.*` input type | Typed (e.g., `string`) | `unknown` |
| `z.object` defaults in optional fields | Key absent | Key present with default |
| `.merge()` | Supported | Deprecated → use `.extend()` |
| `z.string().min()` message param | `.min(n, 'msg')` | `.min(n, { message: 'msg' })` — old form deprecated |
| TypeScript peerDeps | Required TS 4+ | No declared peerDeps (works with TS 5 and TS 6) |

Note: npm dist-tags also show `next: 3.25.0-beta` — zod v3 is paradoxically continuing as `next` tag (v3 LTS). Do NOT install `zod@next`; pin to `zod@4.4.3` (the `latest`).

## @hookform/resolvers v5.2.2 — Zod v4 import path

`@hookform/resolvers@5.2.2` (latest) **supports both zod v3 and zod v4** via the same `zodResolver`.

**Critical import difference**:
- For **zod v3**: `import { z } from 'zod'`
- For **zod v4**: `import { z } from 'zod/v4'`  ← new sub-path export in zod v4 package

The `zodResolver` import itself is unchanged: `import { zodResolver } from '@hookform/resolvers/zod'`

The resolver auto-detects the schema version. Both paths use the same resolver function.

**For this project (pinning zod@4.4.3)**: developers in future slices (P01-S02, P03-S01, etc.) must import from `'zod/v4'` to get the v4 types and behavior. Importing from plain `'zod'` still works (it re-exports v4 from the top-level), but `'zod/v4'` is the canonical v4 path per official docs.

**Recommendation**: Use `import { z } from 'zod'` for simplicity (works in v4 — top-level re-exports v4). Only use `'zod/v4'` sub-path if mixing v3 and v4 in the same project. Since this project starts fresh with v4, plain `'zod'` import is fine.

---

## Expected version (from task pack)

`zod` — version `pendiente — official-docs-researcher confirmará al implementar`
`@hookform/resolvers` — version `pendiente — official-docs-researcher confirmará al implementar`

## Actual versions (from registry)

- `zod@4.4.3` — no peerDeps (TS 6 compatible)
- `@hookform/resolvers@5.2.2` — peerDeps: `react-hook-form ^7.55.0` (react-hook-form@7.75.0 satisfies this)

## Risk

**MEDIUM** — zod v4 has breaking changes from v3. Any form code written for v3 would need migration. Since this project starts fresh, there is no migration debt. Risk is future-slice developers accidentally copy-pasting v3 patterns.

## Mitigation

1. Pin `zod@4.4.3` exactly in `package.json`.
2. Pin `@hookform/resolvers@5.2.2` exactly.
3. Record in T002 handoff "Important decisions": "Zod v4 (not v3) is pinned. Use `import { z } from 'zod'`. Do NOT use deprecated `.merge()`, old `.min(n, 'msg')` positional string form, or rely on `z.coerce.*` returning typed input."
4. Future slice planners (P03-S01 sign-in form, etc.) should read this note before implementing form schemas.

---

RESOLVED: Pinned zod@4.4.3 (exact, no peerDeps, TS 6 compatible) and @hookform/resolvers@5.2.2 (exact, peerDep react-hook-form ^7.55.0 satisfied by 7.75.0). Zod v4 patterns recorded in T002 handoff: use `import { z } from 'zod'` (top-level re-exports v4); avoid deprecated `.merge()`, old positional `.min(n, 'msg')` form. Future form-schema slices (P03-S01 sign-in, etc.) must read this note.
