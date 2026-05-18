/**
 * Hilo People — _ChatNavbar unit tests.
 *
 * Slice/Phase: P03-S02-T009 — Add /account link from chat shell (navbar entry point) / Phase 3.
 *
 * Responsibility: Unit tests for the ChatNavbar component.
 *   §D-T009-NAVBAR-PLACEMENT-INSIDE-PAGE — renders a single accessible link to /account.
 *   §D-T009-LINK-NOT-BUTTON — role="link", not role="button".
 *   §D-T009-NAVBAR-VISIBILITY — component is mountable standalone.
 *   §D-T009-I18N-KEYS — aria-label from account:nav.openAccount.
 *
 * Cases:
 *   T01 — renders a single accessible link to /account with aria-label from i18n.
 *   T02 — clicking the link calls logVerbose (mock of chat/data/logger).
 *   T03 — tap target has minHeight >= 44px via inline style.
 *   T04 — link element renders with to="/account" href.
 *   T05 — data-testid attribute present (default "chat-navbar").
 *   T06 — no element has borderRadius or boxShadow inline style.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { I18nextProvider } from "react-i18next";
import React from "react";
import i18n from "../../../i18n/index";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../features/chat/data/logger", () => ({
  logVerbose: vi.fn(),
  logWarn: vi.fn(),
  logError: vi.fn(),
}));

import ChatNavbar from "../_ChatNavbar";
import { logVerbose } from "../../../features/chat/data/logger";

const mockLogVerbose = vi.mocked(logVerbose);

// ---------------------------------------------------------------------------
// Harness
// ---------------------------------------------------------------------------

function makeWrapper() {
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      I18nextProvider,
      { i18n },
      React.createElement(MemoryRouter, {}, children),
    );
  };
}

function renderNavbar(props?: { "data-testid"?: string }) {
  return render(<ChatNavbar {...props} />, { wrapper: makeWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatNavbar", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T01 — renders a single accessible link to /account with aria-label from i18n", () => {
    renderNavbar();

    // The link must be found by role
    const link = screen.getByRole("link");
    expect(link).toBeDefined();

    // aria-label must match the i18n key in the default (ES) language
    const ariaLabel = link.getAttribute("aria-label") ?? "";
    expect(ariaLabel).toBeTruthy();
    // ES value: "Abrir cuenta"
    expect(ariaLabel).toBe("Abrir cuenta");
  });

  it("T02 — clicking the link calls logVerbose once with account_link.click event", () => {
    renderNavbar();

    const link = screen.getByRole("link");
    fireEvent.click(link);

    // logVerbose must have been called with the click event
    expect(mockLogVerbose).toHaveBeenCalledWith("chat.navbar.account_link.click");
  });

  it("T03 — tap target has minHeight >= 44px via inline style", () => {
    renderNavbar();

    const link = screen.getByTestId("chat-navbar-account-link");
    expect(link).toBeDefined();

    // minHeight must be set to "44px" (from ACCOUNT_LINK_STYLE)
    const style = link.getAttribute("style") ?? "";
    // Inline style includes min-height: 44px
    expect(style).toContain("44px");
  });

  it("T04 — link element has href pointing to /account", () => {
    renderNavbar();

    const link = screen.getByRole("link");
    const href = link.getAttribute("href") ?? "";
    expect(href).toBe("/account");
  });

  it("T05 — default data-testid is 'chat-navbar'", () => {
    renderNavbar();

    const navbar = screen.getByTestId("chat-navbar");
    expect(navbar).toBeDefined();
  });

  it("T05b — custom data-testid override works", () => {
    renderNavbar({ "data-testid": "my-custom-navbar" });

    const navbar = screen.getByTestId("my-custom-navbar");
    expect(navbar).toBeDefined();
  });

  it("T06 — no element has inline style with borderRadius or boxShadow", () => {
    const { container } = renderNavbar();

    // All elements in the rendered tree
    const allElements = container.querySelectorAll("*");
    allElements.forEach((el) => {
      const style = el.getAttribute("style") ?? "";
      // Design system rule: --radius 0, no box-shadow
      expect(style).not.toContain("border-radius");
      expect(style).not.toContain("borderRadius");
      expect(style).not.toContain("box-shadow");
      expect(style).not.toContain("boxShadow");
    });
  });
});
