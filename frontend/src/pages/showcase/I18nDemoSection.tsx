/**
 * Hilo People — i18n Demo Section for /showcase.
 *
 * Slice/Phase: P00-S01-T005 — i18n resources ES/EN/FR / Phase 0 Scaffold.
 *
 * WRITE_SET_DRIFT (controlled): this file lives in frontend/src/pages/showcase/,
 *   outside the declared write_set (frontend/src/i18n/**, frontend/public/locales/**).
 *   Justified by: verify_mode=human requires a visible i18n consumer in the browser.
 *   Precedent: T001/T002 extensions. Flagged in handoff. Validator approval expected.
 *
 * Responsibility: minimal i18n demo embedded in the /showcase page.
 *   Demonstrates:
 *   1. Language switching (ES / EN / FR buttons calling i18n.changeLanguage).
 *   2. Key resolution in common, auth, errors, and account namespaces.
 *   3. Fallback to es for account:language key present in all langs (resolves per lang).
 *
 * Business rule: NO new routes, NO new state beyond local useState. Single-responsibility.
 * a11y: buttons have aria-label. Language selector group has aria-label.
 *
 * Key deps: react-i18next ^17.0.7, i18next singleton from src/i18n/index.ts.
 */

import { useState, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import i18n from "../../i18n/index";
import { SUPPORTED_LANGUAGES, type Language } from "../../i18n/languages";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Language button labels (abbreviated locale → display label). */
const LANG_LABELS: Record<Language, string> = {
  es: "ES",
  en: "EN",
  fr: "FR",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Minimal i18n verification demo for /showcase.
 *
 * Shows language-switcher buttons + live translation output in two namespaces.
 * Used exclusively during /verify-slice human gate (P00-S01-T005).
 *
 * @returns Demo section node.
 */
export function I18nDemoSection(): ReactNode {
  const { t } = useTranslation(["common", "errors", "auth", "account"]);
  const [activeLang, setActiveLang] = useState<Language>(
    (i18n.language as Language) ?? "es",
  );

  /**
   * Switch the global i18n language and update local state.
   * @param lng - Target language code.
   */
  async function handleLangChange(lng: Language): Promise<void> {
    if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
      console.info("i18n-demo.changeLanguage.start", { lng, slice: "P00-S01-T005" });
    }
    await i18n.changeLanguage(lng);
    setActiveLang(lng);
    if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
      console.info("i18n-demo.changeLanguage.ok", { lng, language: i18n.language });
    }
  }

  return (
    <section
      aria-labelledby="i18n-demo-heading"
      style={{ marginBottom: "3rem" }}
    >
      {/* Section heading */}
      <h2
        id="i18n-demo-heading"
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.6875rem",
          letterSpacing: "var(--tracking-label)",
          textTransform: "uppercase",
          color: "var(--color-ink)",
          opacity: 0.45,
          marginBottom: "1.5rem",
          borderBottom: "var(--hairline)",
          paddingBottom: "0.5rem",
        }}
      >
        10 · i18n Demo — ES / EN / FR
      </h2>

      {/* Language selector */}
      <div
        role="group"
        aria-label="Language selector"
        style={{ display: "flex", gap: "0.5rem", marginBottom: "1.5rem" }}
      >
        {SUPPORTED_LANGUAGES.map((lng) => (
          <button
            key={lng}
            aria-label={`Switch language to ${lng}`}
            aria-pressed={activeLang === lng}
            onClick={() => void handleLangChange(lng)}
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.75rem",
              letterSpacing: "0.06em",
              padding: "0.375rem 0.875rem",
              border: "var(--hairline)",
              borderRadius: 0,
              cursor: "pointer",
              backgroundColor:
                activeLang === lng ? "var(--color-ink)" : "var(--color-paper)",
              color:
                activeLang === lng ? "var(--color-paper)" : "var(--color-ink)",
              minWidth: "44px",
              minHeight: "44px",
              transition: "background-color 0.15s, color 0.15s",
            }}
          >
            {LANG_LABELS[lng]}
          </button>
        ))}
      </div>

      {/* Translation output rows */}
      <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
        {/* common:productName — always "Hilo" */}
        <DemoRow label="common:productName" value={t("common:productName")} />

        {/* auth:signIn.title — changes per language */}
        <DemoRow label="auth:signIn.title" value={t("auth:signIn.title")} />

        {/* errors:AUTH_INVALID_CREDENTIALS — changes per language */}
        <DemoRow
          label="errors:AUTH_INVALID_CREDENTIALS"
          value={t("errors:AUTH_INVALID_CREDENTIALS")}
        />

        {/* account:language — changes per language */}
        <DemoRow label="account:language" value={t("account:language")} />
      </div>

      {/* Current language indicator */}
      <p
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.6875rem",
          color: "var(--color-ink)",
          opacity: 0.3,
          marginTop: "1rem",
          letterSpacing: "0.04em",
        }}
      >
        Active locale: {activeLang} · i18next initialized: {String(i18n.isInitialized)}
      </p>
    </section>
  );
}

// ---------------------------------------------------------------------------
// Local helper (private)
// ---------------------------------------------------------------------------

/**
 * Single translation demo row.
 * @param label - The i18n key identifier shown in the label column.
 * @param value - The resolved translation string.
 * @returns Row node.
 */
function DemoRow({ label, value }: { label: string; value: string }): ReactNode {
  return (
    <div style={{ display: "flex", gap: "1rem", alignItems: "baseline" }}>
      <span
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.6875rem",
          color: "var(--color-ink)",
          opacity: 0.4,
          minWidth: "220px",
        }}
      >
        {label}
      </span>
      <span
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.875rem",
          color: "var(--color-ink)",
        }}
      >
        {value}
      </span>
    </div>
  );
}
