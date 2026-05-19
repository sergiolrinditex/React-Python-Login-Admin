/**
 * Hilo People — i18n language constants.
 *
 * Slice/Phase: P00-S01-T005 — i18n resources ES/EN/FR / Phase 0 Scaffold.
 *
 * Responsibility: single source of truth for supported language codes and default
 *   language. All i18n modules, selectors, and tests import from here.
 *
 * Source ref: instrucciones.md §3.3 (es/en/fr, fallback es), §6 (idiomas soportados),
 *   §11.1 env DEFAULT_LANGUAGE=es.
 *
 * Key deps: none (pure constants — no framework imports).
 */

// ---------------------------------------------------------------------------
// Supported languages
// ---------------------------------------------------------------------------

/**
 * Ordered list of supported locale codes.
 * Source: instrucciones.md §6 "Idiomas soportados: es, en, fr."
 *
 * @remarks
 *   - `es` is first because it is the default and fallback.
 *   - Adding a new language here requires adding bundles in public/locales/{lng}/ too.
 */
export const SUPPORTED_LANGUAGES = ["es", "en", "fr"] as const;

/**
 * Union type derived from SUPPORTED_LANGUAGES.
 * Use this for any prop, store field, or function parameter that represents a locale.
 */
export type Language = (typeof SUPPORTED_LANGUAGES)[number];

/**
 * Default language for the application.
 * Matches DEFAULT_LANGUAGE env var used by the backend (instrucciones.md §11.1).
 * Detecor is DISABLED in P0; T005 keeps `lng` static. AccountPage (P03-S02-T004)
 * persists the user preference via PATCH /api/v1/users/me/language.
 */
export const DEFAULT_LANGUAGE: Language = "es";

/**
 * Declared i18n namespaces, in order of declaration in index.ts.
 * Source: instrucciones.md §6 "Namespaces: common, auth, chat, account,
 *   admin-ai, rag, mcp, errors."
 *   Updated P04-S03-T002: added "usage" namespace (§D-T002-I18N-NSLIST).
 *
 * Used in tests to assert that all 9 namespaces are registered.
 */
export const I18N_NAMESPACES = [
  "common",
  "auth",
  "chat",
  "account",
  "admin-ai",
  "rag",
  "mcp",
  "agents",
  "errors",
  "usage",
] as const;

/**
 * Default namespace. Used as `defaultNS` in i18next init and as the fallback
 * when a namespace is not specified in t().
 */
export const DEFAULT_NAMESPACE = "common" as const;
