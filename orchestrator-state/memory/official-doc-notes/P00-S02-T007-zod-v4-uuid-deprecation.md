# Official Doc Note: Zod v4 — z.string().uuid() is deprecated

**Date**: 2026-05-10
**Task**: P00-S02-T007
**Package**: `zod@4.4.3`
**Sources**:
- Context7 `/colinhacks/zod/v4.0.1` — changelog: "String format methods moved to top-level functions"
- Source: https://github.com/colinhacks/zod/blob/main/packages/docs/content/v4/changelog.mdx

---

## SUMMARY

The task pack §12.4 instructs the developer to validate the provider UUID input with `z.string().uuid()`. In Zod v4, `z.string().uuid()` is **deprecated** — the canonical pattern is the top-level `z.uuid()`.

The chained `.uuid()` on `z.string()` still works at runtime in Zod 4.4.3 (backward compat shim), but the official v4 docs explicitly mark it as deprecated with `// ❌ deprecated`.

## EVIDENCE

From the Zod v4.0.1 changelog (canonical):

```typescript
// Deprecated method forms
z.string().uuid(); // ❌ deprecated
z.uuid();          // ✅ canonical v4 form
```

From the Zod v4 API docs (string formats):
> `z.uuid()` — Validates a UUID (Universally Unique Identifier).
> Also available: `z.uuidv4()`, `z.uuidv6()`, `z.uuidv7()` for version-specific validation.

## AFFECTED FILES

- `frontend/src/features/admin_ai/data/discoverModels.ts` (or wherever the input UUID is validated before calling the API)
- Any schema file in `frontend/src/features/admin_ai/` that validates the provider_id UUID input

## RECOMMENDATION

Developer must use:

```typescript
import { z } from 'zod';

// Schema for provider UUID input — step 1 of the wizard
const providerIdSchema = z.uuid(); // ✅ Zod v4 canonical

// For inline field-level use (e.g., within a z.object):
const wizardStep1Schema = z.object({
  providerId: z.uuid({ error: 'Invalid UUID format' }),
});
```

Do NOT use:
```typescript
z.string().uuid(); // ❌ deprecated in v4 (still works but will be removed in a future minor)
```

Note: `z.uuid()` is standalone — it is NOT `z.string().uuid()`. The type inferred is still `string`.

## SEVERITY

Low — runtime behavior is identical in 4.4.3 (the deprecated form still works). However, using deprecated API in new code contradicts the project's production-quality rule ("no shortcuts"). The developer should use `z.uuid()` from the start.

---

RESOLVED: Used z.uuid() (top-level, Zod v4 canonical) in ModelWizardPage.tsx for the providerIdSchema. z.string().uuid() is not used anywhere in admin_ai/. The providerIdSchema const is declared as `const providerIdSchema = z.uuid()` at module level in ModelWizardPage.tsx.
