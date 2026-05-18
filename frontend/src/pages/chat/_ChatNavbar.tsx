/**
 * Hilo People — _ChatNavbar (private to chat pages cluster).
 *
 * Slice/Phase: P03-S02-T009 — Add /account link from chat shell (navbar entry point) / Phase 3.
 *
 * Responsibility: Renders a persistent account navigation link across all chat-area pages.
 *   A single <Link to={ROUTE_ACCOUNT}> with an inline SVG account icon and an accessible
 *   aria-label from the `account` i18n namespace. Mounted as the first child of MobileFrame
 *   inside ChatHomePage, HistoryPage, and ConversationPage (non-forbidden branches only).
 *
 * Decisions applied:
 *   §D-T009-LINK-NOT-BUTTON: uses <Link> for free role=link semantics + middle-click + keyboard.
 *   §D-T009-NAVBAR-PLACEMENT-INSIDE-PAGE: not promoted to a shared app-shell; 3 local mounts.
 *   §D-T009-NAVBAR-VISIBILITY: hidden only in ForbiddenView / permission_denied branches.
 *   §D-T009-I18N-NAMESPACE-ACCOUNT: accessible name from account:nav.openAccount key.
 *   §D-T009-I18N-KEYS: key path = account.nav.openAccount; ES/EN/FR lockstep.
 *
 * Security:
 *   - No token access. No auth state. RequireAuth already wraps the parent routes.
 *   - No PII in logs (no email, no full_name).
 *
 * Accessibility: §UX_CONTRACT §7 / rules/01 §Accessibility.
 *   - tap target ≥ 44×44px via explicit padding.
 *   - Focus ring via :focus-visible outline using var(--color-ink).
 *   - aria-label from i18n (no color-only information conveyed).
 *
 * Design tokens (§D-T009-DESIGN-TOKENS):
 *   - background: var(--color-paper) — NO hardcoded hex.
 *   - ink: var(--color-ink) — NO hardcoded hex.
 *   - hairline below: var(--hairline).
 *   - NO border-radius (--radius 0 rule).
 *   - NO box-shadow.
 *
 * Dependencies: react-router Link, react-i18next, chat feature logger.
 * Route ref: ROUTE_ACCOUNT from frontend/src/app/router.tsx.
 */

import { type CSSProperties, type ReactNode, useEffect, useCallback } from "react";
import { Link } from "react-router";
import { useTranslation } from "react-i18next";
import { ROUTE_ACCOUNT } from "../../app/router";
import { logVerbose } from "../../features/chat/data/logger";

// ---------------------------------------------------------------------------
// Styles (design tokens only — no hardcoded colors, radii, or shadows)
// ---------------------------------------------------------------------------

/**
 * Outer container: full-width row with hairline divider below.
 * background: var(--color-paper) ensures it sits on the page surface.
 * No border-radius (--radius 0 rule applies throughout).
 */
const NAVBAR_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  justifyContent: "flex-end",
  alignItems: "center",
  width: "100%",
  background: "var(--color-paper)",
  borderBottom: "var(--hairline)",
  padding: "0 0",
};

/**
 * The <Link> element doubles as the tap target (≥44×44px).
 * padding: 10px gives 24px icon + 20px padding = 44px height.
 * No border-radius (design system rule).
 * color-scheme: monochrome via var(--color-ink).
 * textDecoration: none — visual affordance is the icon itself.
 */
const ACCOUNT_LINK_STYLE: CSSProperties = {
  display: "flex",
  alignItems: "center",
  justifyContent: "center",
  minWidth: "44px",
  minHeight: "44px",
  padding: "10px",
  color: "var(--color-ink)",
  textDecoration: "none",
  // outline on :focus-visible handled via global CSS / browser default;
  // we enforce the token color inline for specificity where needed.
};

// ---------------------------------------------------------------------------
// AccountIcon — inline SVG, no external library dep (rules/01 §Dependencies)
// ---------------------------------------------------------------------------

/**
 * Minimal monochrome account/person SVG glyph, 24×24 viewBox.
 * No fill color — inherits `currentColor` from the Link's color token.
 * No rounded path that would imply border-radius.
 */
function AccountIcon(): ReactNode {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="square"
      strokeLinejoin="miter"
      aria-hidden="true"
      focusable="false"
    >
      {/* Head — rectangular outline (no border-radius, consistent with --radius 0) */}
      <rect x="8" y="3" width="8" height="8" />
      {/* Shoulders — trapezoid connecting head to frame bottom */}
      <path d="M4 21 C4 16 8 14 12 14 C16 14 20 16 20 21" />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// ChatNavbar — exported default
// ---------------------------------------------------------------------------

interface ChatNavbarProps {
  /** Optional testid override (default: "chat-navbar"). */
  "data-testid"?: string;
}

/**
 * Chat shell navbar — renders the account entry point link.
 *
 * Used as first child of MobileFrame in ChatHomePage, HistoryPage, and
 * ConversationPage (non-forbidden branches). The link navigates to ROUTE_ACCOUNT.
 *
 * @returns ChatNavbar element.
 */
export default function ChatNavbar({ "data-testid": testId = "chat-navbar" }: ChatNavbarProps): ReactNode {
  const { t } = useTranslation(["account"]);

  // BEFORE: log on mount (render start)
  useEffect(() => {
    logVerbose("chat.navbar.render.start");
  }, []);

  const handleAccountLinkClick = useCallback((): void => {
    // AFTER: log click (navigation intent, no PII)
    logVerbose("chat.navbar.account_link.click");
  }, []);

  return (
    <nav
      style={NAVBAR_CONTAINER_STYLE}
      data-testid={testId}
      aria-label={t("account:nav.openAccount")}
    >
      <Link
        to={ROUTE_ACCOUNT}
        style={ACCOUNT_LINK_STYLE}
        aria-label={t("account:nav.openAccount")}
        onClick={handleAccountLinkClick}
        data-testid="chat-navbar-account-link"
      >
        <AccountIcon />
      </Link>
    </nav>
  );
}
