/**
 * i18n language and namespace constants for Hilo People.
 *
 * What: Exports the canonical list of supported languages, namespace names
 * and a type-guard helper for downstream use. These constants are consumed by:
 *   - `frontend/src/i18n/index.ts` (i18next init)
 *   - `P01-S02-T007` (PATCH /users/me/language backend call)
 *   - `P03-S02-T002..T004` (AccountPage language switcher)
 *
 * Phase/Slice: P00 / P00-S01-T005 — i18n resources ES/EN/FR
 *
 * Source-of-truth refs:
 *   - instrucciones.md §1.4 (line 42): "español, inglés y francés; fallback español"
 *   - instrucciones.md §3.1 (line 58): `el idioma solo puede ser 'es', 'en' o 'fr'`
 *   - TECHNICAL_GUIDE §10.3 (line 398): `users.preferred_language CHECK IN ('es','en','fr')`
 *   - TECHNICAL_GUIDE §4: namespace list
 */

/** The three supported locales, ordered by priority (fallback first). */
export const SUPPORTED_LANGUAGES = ['es', 'en', 'fr'] as const;

/** Union type derived from the supported language tuple. */
export type SupportedLanguage = (typeof SUPPORTED_LANGUAGES)[number];

/**
 * All eight i18n namespaces for Hilo People.
 *
 * Namespace → instrucciones.md §6 canonical key prefix mapping:
 *   common    → common.*  (e.g. productName)
 *   auth      → auth.*    (signIn, forgot, twoFactor)
 *   chat      → chat.*    (empty, citation)
 *   account   → account.* (language)
 *   admin-ai  → adminAi.* (models, mcp)
 *   rag       → rag.*     (documents)
 *   mcp       → mcp.*     (servers — minimal seed; productive keys land in P02-S07/S08)
 *   errors    → errors.*  (AUTH_INVALID_CREDENTIALS)
 */
export const NAMESPACES = [
  'common',
  'auth',
  'chat',
  'account',
  'admin-ai',
  'rag',
  'mcp',
  'errors',
] as const;

/** Union type derived from the namespace tuple. */
export type Namespace = (typeof NAMESPACES)[number];

/**
 * Type-guard: returns true if `x` is a supported language code.
 *
 * Used downstream by:
 *   - P01-S02-T007 (validate `preferred_language` before PATCH call)
 *   - P03-S02-T004 (AccountPage language switcher selection handler)
 *
 * @param x - Any string value to check.
 * @returns `true` if `x` is 'es', 'en' or 'fr'; `false` otherwise.
 */
export function isSupportedLanguage(x: string): x is SupportedLanguage {
  return (SUPPORTED_LANGUAGES as readonly string[]).includes(x);
}
