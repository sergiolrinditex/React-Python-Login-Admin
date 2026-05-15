/**
 * Hilo People — ResetSentPage component.
 *
 * Slice/Phase: P03-S01-T004 — ResetSentPage / Phase 3 Complete Features.
 *
 * Responsibility: Static confirmation page shown after the forgot-password form
 *   (T003 ForgotPasswordPage) navigates to /auth/reset-sent with router state
 *   containing the submitted email. Renders masked email or a generic fallback.
 *
 * Route: /auth/reset-sent (public — §D-T004-PUBLIC-ROUTE).
 *   TECHNICAL_GUIDE §6.4 Navigation Contract explicitly lists /auth/reset-sent
 *   as a public route. Authenticated users may land here while testing the
 *   recovery flow — we do NOT redirect them to /chat, because that would create
 *   a confusing loop. This is a deliberate deviation from the "redirect authed
 *   users away from /auth/*" pattern; it is documented here and in the handoff.
 *
 * Anti-enumeration alignment — §D-T004-ANTI-ENUM-UI:
 *   This page is intentionally oblivious to whether the email was found in DB.
 *   T003 (ForgotPasswordPage) always navigates here with the same state shape
 *   regardless of the backend's "user not found" or "user found" response
 *   (§D-T003-ANTI-ENUM-UI). This page simply renders what state it receives.
 *   Both the with_email and fallback variants use "if registered" phrasing per
 *   TECHNICAL_GUIDE §6.2 anti-enumeration contract.
 *
 * State contract (§D-T003-SUCCESS-REDIRECT):
 *   T003 calls navigate("/auth/reset-sent", { state: { email } }) on success.
 *   This page reads location.state?.email (§D-T004-NO-STATE-FALLBACK).
 *
 * UI states (§5 task pack):
 *   success          — state.email present: masked email shown (default variant).
 *   success_fallback — state.email absent/invalid: generic copy (fallback variant).
 *   loading          — N/A: no async work, renders synchronously.
 *   empty            — N/A: no collection; fallback covers "no email" case.
 *   error_network    — N/A: no network call on this page.
 *   error_validation — N/A: no form, no user input.
 *   permission_denied — N/A: public route, anti-enum policy.
 *
 * Design: MobileFrame + Wordmark + TrackedLabel + SolidCTA (as Link).
 *   All tokens from tokens.css. NO hardcoded colors/fonts/radii.
 *
 * Non-negotiables: §logging (§D-T004-NO-PII-LOG), §a11y (§D-T004-A11Y),
 *   §security, §i18n (§D-T004-I18N-LOCKSTEP).
 */

import { useLocation, Link } from "react-router";
import { useTranslation } from "react-i18next";

import MobileFrame from "@/shared/design-system/MobileFrame";
import Wordmark from "@/shared/design-system/Wordmark";

// ---------------------------------------------------------------------------
// Route constants
// ---------------------------------------------------------------------------

/** §D-T004-ROUTER: destination for the back-to-sign-in CTA. */
const ROUTE_AUTH_SIGN_IN = "/auth/sign-in";

// ---------------------------------------------------------------------------
// maskEmail helper — §D-T004-EMAIL-MASK
// ---------------------------------------------------------------------------

/**
 * Deterministically masks an email address for display.
 *
 * §D-T004-EMAIL-MASK — pure function, no side effects, no console output.
 * Algorithm: keep first character of local part + "***" + "@" + domain.
 *
 * Edge cases:
 *   - Empty local part (@example.com) → "***@example.com"
 *   - Missing "@" (malformed)          → "***"
 *   - Empty string ""                  → "***"
 *
 * @param email - Raw email string to mask.
 * @returns The masked representation, or "***" for malformed/empty input.
 */
function maskEmail(email: string): string {
  const atIndex = email.indexOf("@");
  if (atIndex === -1) {
    // Missing "@" — return safe sentinel
    return "***";
  }
  const local = email.slice(0, atIndex);
  const domain = email.slice(atIndex); // includes "@"
  if (local.length === 0) {
    // Empty local part e.g. "@example.com"
    return `***${domain}`;
  }
  return `${local[0]}***${domain}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Password-reset confirmation page.
 *
 * Renders the anti-enumeration success confirmation after ForgotPasswordPage
 * posts the reset request. Shows a masked email when router state carries one;
 * falls back to generic copy otherwise (§D-T004-NO-STATE-FALLBACK).
 *
 * No fetch, no auth read, no side effects. Pure presentation.
 *
 * @returns ReactElement
 */
export default function ResetSentPage(): React.ReactElement {
  const { t } = useTranslation("auth");
  const location = useLocation();

  // §D-T004-NO-STATE-FALLBACK: derive masked email; fall back to null if absent/invalid.
  const stateEmail = (location.state as { email?: unknown } | null)?.email;
  const masked: string | null =
    typeof stateEmail === "string" && stateEmail.length > 0
      ? maskEmail(stateEmail)
      : null;

  // §D-T004-NO-PII-LOG: verbose logging emits only non-PII metadata.
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    const emailPresent = masked !== null;
    const emailDomain =
      typeof stateEmail === "string" && stateEmail.includes("@")
        ? stateEmail.split("@")[1]
        : "<none>";
    const emailLocalLen =
      typeof stateEmail === "string" && stateEmail.includes("@")
        ? stateEmail.split("@")[0].length
        : 0;
    console.info("auth.reset_sent.page.render.start", {
      slice: "P03-S01-T004",
      email_present: emailPresent,
      email_domain: emailDomain,
      email_local_len: emailLocalLen,
    });
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <MobileFrame asMain>
      {/* Brand header — div wrapper so Wordmark is not in h1 (avoids dual h1 with page title) */}
      <div style={{ marginBottom: "2rem" }}>
        <div
          style={{
            fontFamily: "var(--font-display)",
            fontSize: "2rem",
            color: "var(--color-ink)",
            margin: 0,
            lineHeight: 1.1,
          }}
        >
          <Wordmark size="2rem" aria-label="Hilo" />
        </div>
      </div>

      {/*
       * §D-T004-A11Y: single <h1> with page title text — the only h1 on the page.
       * First meaningful heading for screen readers after the Hilo brand div.
       * No separate TrackedLabel hint: the 4 i18n keys defined for this page
       * (title, body.with_email, body.fallback, actions.back_to_sign_in) do not
       * include a "titleHint" (YAGNI — not declared in §D-T004-I18N-LOCKSTEP).
       */}
      <h1
        data-testid="reset-sent-title"
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "1.375rem",
          color: "var(--color-ink)",
          margin: "0 0 1.5rem 0",
          lineHeight: 1.25,
        }}
      >
        {t("reset_sent.title")}
      </h1>

      {/*
       * §D-T004-A11Y: role="status" + aria-live="polite" announce confirmation to screen readers.
       * §D-T004-ANTI-ENUM-UI: both variants use anti-enumeration "if registered" phrasing.
       * §D-T004-NO-STATE-FALLBACK: masked !== null → with_email variant; otherwise → fallback.
       */}
      <div
        role="status"
        aria-live="polite"
        data-testid="reset-sent-status-region"
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "1rem",
          color: "var(--color-ink)",
          lineHeight: 1.55,
          marginBottom: "2rem",
        }}
      >
        {masked !== null ? (
          // State-present variant: show masked email
          <p data-testid="reset-sent-body-with-email" style={{ margin: 0 }}>
            {t("reset_sent.body.with_email", { maskedEmail: masked })}
          </p>
        ) : (
          // Fallback variant: generic anti-enumeration copy
          <p data-testid="reset-sent-body-fallback" style={{ margin: 0 }}>
            {t("reset_sent.body.fallback")}
          </p>
        )}
      </div>

      {/*
       * §D-T004-A11Y: real <Link> from react-router renders as <a href>,
       * keyboard-navigable, focus ring intact, accessible name from text content.
       * Styled to match SolidCTA visual contract: ink bg, paper fg, tracking-label,
       * min-height 44px (tap target ≥44×44 px), no border-radius, uppercase.
       */}
      <Link
        to={ROUTE_AUTH_SIGN_IN}
        data-testid="reset-sent-cta"
        style={{
          display: "inline-flex",
          alignItems: "center",
          justifyContent: "center",
          width: "100%",
          minHeight: "44px",
          padding: "0.75rem 1.5rem",
          backgroundColor: "var(--color-ink)",
          color: "var(--color-paper)",
          fontFamily: "var(--font-sans)",
          fontSize: "0.6875rem",
          fontWeight: 500,
          letterSpacing: "var(--tracking-label)",
          textTransform: "uppercase",
          textDecoration: "none",
          borderRadius: 0,
          boxSizing: "border-box",
        }}
      >
        {t("reset_sent.actions.back_to_sign_in")}
      </Link>
    </MobileFrame>
  );
}
