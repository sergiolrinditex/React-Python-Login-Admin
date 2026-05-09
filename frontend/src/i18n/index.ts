/**
 * i18next singleton initialisation for Hilo People.
 *
 * What: Configures and exports the i18next instance with all 8 namespaces
 * and 3 locales (es/en/fr), using eager (static import) loading so the
 * instance is synchronously ready on first render without network races.
 *
 * Phase/Slice: P00 / P00-S01-T005 — i18n resources ES/EN/FR
 *
 * Dependencies (non-obvious):
 *   - i18next 26.0.10 — init API; `use()` chaining
 *   - react-i18next 17.0.7 — `initReactI18next` plugin
 *   - All 24 JSON bundles under frontend/public/locales/{es,en,fr}/*.json
 *     (Vite handles JSON imports natively; `resolveJsonModule: true` in tsconfig)
 *
 * Source-of-truth refs:
 *   - instrucciones.md §1.4 (line 42): locale list (es, en, fr)
 *   - instrucciones.md §6: authoritative key inventory and productive copy
 *   - TECHNICAL_GUIDE §6.5: i18n loading strategy decision
 *   - TECHNICAL_GUIDE §11.1: DEFAULT_LANGUAGE=es env var
 *
 * Design decisions (recorded here per 01-non-negotiables.md §Documentation):
 *
 * D2 — fallbackLng: 'es' (singular string, matches instrucciones §1.4 + users DEFAULT 'es')
 *
 * D3 — EAGER loading: JSON files imported at module load via Vite JSON import,
 *      bundled into the JS output (~few KB total). Avoids i18next-http-backend
 *      dependency, network races in tests, and Suspense boundaries. Future
 *      migration to lazy loading is trivial (files stay in public/locales/).
 *
 * D4 — Language detector intentionally NOT registered here. Detection belongs
 *      to the AccountPage language preference flow (P03-S02-T004) and the
 *      PATCH /users/me/language endpoint (P01-S02-T007). After login, the FE
 *      calls i18n.changeLanguage(user.preferred_language). See also D4 in task
 *      pack P00-S01-T005.md. i18next-browser-languagedetector is installed but
 *      not registered until P03-S02-T004.
 *
 * Adding keys: copy verbatim from `instrucciones.md §6` table; update all 3
 * locales in the same commit. Never add a key to one locale without the others
 * — the drift-detector test in __tests__/i18n.test.ts will fail.
 */

import i18n from 'i18next';
import { initReactI18next } from 'react-i18next';

import { SUPPORTED_LANGUAGES, NAMESPACES } from './languages';

// ── Locale bundles (eager static imports) ────────────────────────────────────
// Vite resolves JSON imports natively. tsconfig.json has resolveJsonModule: true.

import esCommon from '../../public/locales/es/common.json';
import esAuth from '../../public/locales/es/auth.json';
import esChat from '../../public/locales/es/chat.json';
import esAccount from '../../public/locales/es/account.json';
import esAdminAi from '../../public/locales/es/admin-ai.json';
import esRag from '../../public/locales/es/rag.json';
import esMcp from '../../public/locales/es/mcp.json';
import esErrors from '../../public/locales/es/errors.json';

import enCommon from '../../public/locales/en/common.json';
import enAuth from '../../public/locales/en/auth.json';
import enChat from '../../public/locales/en/chat.json';
import enAccount from '../../public/locales/en/account.json';
import enAdminAi from '../../public/locales/en/admin-ai.json';
import enRag from '../../public/locales/en/rag.json';
import enMcp from '../../public/locales/en/mcp.json';
import enErrors from '../../public/locales/en/errors.json';

import frCommon from '../../public/locales/fr/common.json';
import frAuth from '../../public/locales/fr/auth.json';
import frChat from '../../public/locales/fr/chat.json';
import frAccount from '../../public/locales/fr/account.json';
import frAdminAi from '../../public/locales/fr/admin-ai.json';
import frRag from '../../public/locales/fr/rag.json';
import frMcp from '../../public/locales/fr/mcp.json';
import frErrors from '../../public/locales/fr/errors.json';

// ── Initialise the singleton ─────────────────────────────────────────────────

if (!i18n.isInitialized) {
  i18n.use(initReactI18next).init({
    // D2: singular fallback language (instrucciones.md §1.4 + TECHNICAL_GUIDE §11.1)
    lng: 'es',
    fallbackLng: 'es',

    supportedLngs: [...SUPPORTED_LANGUAGES],

    // All 8 namespaces; defaultNS resolves bare keys like t('productName')
    ns: [...NAMESPACES],
    defaultNS: 'common',

    // D3: eager resources tree — all 24 bundles preloaded at module import time
    resources: {
      es: {
        common: esCommon,
        auth: esAuth,
        chat: esChat,
        account: esAccount,
        'admin-ai': esAdminAi,
        rag: esRag,
        mcp: esMcp,
        errors: esErrors,
      },
      en: {
        common: enCommon,
        auth: enAuth,
        chat: enChat,
        account: enAccount,
        'admin-ai': enAdminAi,
        rag: enRag,
        mcp: enMcp,
        errors: enErrors,
      },
      fr: {
        common: frCommon,
        auth: frAuth,
        chat: frChat,
        account: frAccount,
        'admin-ai': frAdminAi,
        rag: frRag,
        mcp: frMcp,
        errors: frErrors,
      },
    },

    interpolation: {
      // React already escapes output — double-escaping causes broken HTML entities
      escapeValue: false,
    },

    react: {
      // Synchronous mode: no Suspense boundary needed (matches D3 eager strategy)
      useSuspense: false,
    },
  });
}

export default i18n;
