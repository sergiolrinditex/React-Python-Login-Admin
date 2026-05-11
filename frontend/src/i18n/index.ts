/**
 * Hilo People — i18n bootstrap (minimal, resource-less).
 *
 * Slice/Phase: P00-S01-T002 — Frontend dependency pack.
 *   WRITE_SET_DRIFT (4th candidate extension): this file is required so that
 *   `providers.tsx` can import a concrete i18next instance and compile cleanly
 *   under vitest WITHOUT the browser-languagedetector auto-init that crashes in
 *   Node/jsdom when triggered too early.
 *
 * Responsibility: initialise i18next with ZERO real translation resources and the
 *   languageDetector DISABLED so the smoke test in providers.test.tsx can mount
 *   <Providers> without a browser environment dependency.
 *
 * T005 (i18n resources ES/EN/FR) will REPLACE this file with real namespace
 *   resources, locale detection settings, and language fallback configuration.
 *   The `i18n` injection seam in ProvidersProps ensures T005 can swap the
 *   instance without touching providers.tsx.
 *
 * Key deps: i18next ^26.1.0.
 * Breaking note: i18next v26 exports are ESM-first; the default export is the
 *   singleton `i18n` instance (same as v23/v24/v25 — no breaking change here).
 */

import i18n from "i18next";
import { initReactI18next } from "react-i18next";

// BEFORE init log — gated by VITE_ENABLE_VERBOSE_LOGGING at call site in providers.tsx.
// This module only initialises; the caller logs the lifecycle events.

/**
 * Bootstrap i18n singleton with empty resources.
 * Real namespaces (common, auth, admin) are added by T005.
 *
 * @returns The initialised i18next singleton.
 */
i18n.use(initReactI18next).init({
  // No languageDetector: browser-only plugin crashes in jsdom without a window.
  // T005 adds LanguageDetector after the test suite is stable.
  lng: "es",
  fallbackLng: "es",
  ns: ["common"],
  defaultNS: "common",
  resources: {
    // Empty — T005 fills this with actual translation keys.
  },
  interpolation: {
    escapeValue: false, // React already escapes values.
  },
  // Silence "no resources" warnings during scaffold phase.
  saveMissing: false,
  missingKeyHandler: false,
});

export default i18n;
