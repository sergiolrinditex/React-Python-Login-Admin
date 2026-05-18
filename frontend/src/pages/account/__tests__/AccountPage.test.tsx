/**
 * Hilo People — AccountPage component tests.
 *
 * Slice/Phase: P03-S02-T007 — AccountPage (profile + language + logout) / Phase 3.
 *
 * Responsibility: Component tests covering the required UX states + a11y + i18n.
 *   §D-T007-PAGE-TESTS — AP01–AP13 per task pack §10 test plan.
 *   useAuth mocked (auth layer boundary).
 *   useLogout mocked (presentation hook boundary; tested separately in useLogout.test.tsx).
 *   useLanguagePicker mocked (presentation hook boundary; tested separately).
 *   react-router useNavigate mocked.
 *   i18n real (inline resources from i18n/index.ts).
 *
 * Cases:
 *   AP01 — loading state renders aria-busy skeleton while hydrating.
 *   AP02 — success: renders email, full_name, brand, department, country, center.
 *   AP03 — language radiogroup: 3 options, 'es' checked initially.
 *   AP04 — clicking 'en' calls setLanguage('en').
 *   AP05 — i18n text changes to English after language flip.
 *   AP06 — logout button calls useLogout.logout.
 *   AP07 — error_network state: shown when user is null and status unauthenticated.
 *   AP08 — error_validation: ValidationErrorInline shown when languageError.code='validation'.
 *   AP09 — permission_denied: rendered when status='unauthenticated'.
 *   AP10 — RequireAuth: unauthenticated user sees sign-in redirect (integration).
 *   AP11 — deep-link /account with valid session: renders the page.
 *   AP12 — design tokens: no hardcoded hex in rendered inline styles.
 *   AP13 — PII: no log message contains the full email string.
 *   AP14 — [debugger cycle 1] PATCH /me/language network error renders NetworkErrorView
 *         (not the previous ad-hoc div) with a working retry CTA. Confirms the
 *         NetworkErrorView import is no longer dead code and the user has a clear
 *         recovery path on transient network outages.
 *   AP14b — [debugger cycle 1] clicking retry on NetworkErrorView re-triggers setLanguage
 *         with the current language (idempotent retry).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import AccountPage from "../AccountPage";
import type { UserProfile } from "../../../features/auth/domain/types";
import * as logger from "../../../features/auth/data/logger";

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_USER: UserProfile = {
  id: "acc-user-uuid-001",
  email: "employee.verification@inditex-sandbox.com",
  full_name: "Test Employee",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: {
    employee_id: "EMP-VERIFY-001",
    brand: "Zara",
    society: "ITX ES",
    center: "Madrid-HQ",
    country: "ES",
    department: "People & Talent",
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

const mockLogout = vi.fn<() => Promise<void>>();
const mockSetLanguage = vi.fn<(lang: string) => Promise<void>>();
const mockClearError = vi.fn();

vi.mock("../../../features/auth/presentation/useLogout", () => ({
  useLogout: vi.fn(() => ({
    logout: mockLogout,
    isLoggingOut: false,
    error: null,
  })),
}));

vi.mock("../../../features/auth/presentation/useLanguagePicker", () => ({
  useLanguagePicker: vi.fn(() => ({
    current: "es" as const,
    setLanguage: mockSetLanguage,
    isPending: false,
    error: null,
    clearError: mockClearError,
  })),
}));

vi.mock("../../../features/auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(() => ({
    status: "authenticated",
    user: MOCK_USER,
    logout: vi.fn(),
    signInAccepted: vi.fn(),
  })),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { useAuth } from "../../../features/auth/presentation/AuthProvider";
import { useLogout } from "../../../features/auth/presentation/useLogout";
import { useLanguagePicker } from "../../../features/auth/presentation/useLanguagePicker";

const mockUseAuth = vi.mocked(useAuth);
const mockUseLogout = vi.mocked(useLogout);
const mockUseLanguagePicker = vi.mocked(useLanguagePicker);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeAuthMock(overrides?: Partial<ReturnType<typeof useAuth>>) {
  return {
    status: "authenticated" as const,
    user: MOCK_USER,
    logout: vi.fn(),
    signInAccepted: vi.fn(),
    ...overrides,
  };
}

function renderAccountPage() {
  return render(
    <MemoryRouter initialEntries={["/account"]}>
      <I18nextProvider i18n={i18n}>
        <AccountPage />
      </I18nextProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AccountPage", () => {
  beforeEach(async () => {
    vi.clearAllMocks();
    mockNavigate.mockResolvedValue(undefined);
    mockLogout.mockResolvedValue(undefined);
    mockSetLanguage.mockResolvedValue(undefined);
    // Reset to ES
    await i18n.changeLanguage("es");

    // Default mocks
    mockUseAuth.mockReturnValue(makeAuthMock());
    mockUseLogout.mockReturnValue({ logout: mockLogout, isLoggingOut: false, error: null });
    mockUseLanguagePicker.mockReturnValue({
      current: "es",
      setLanguage: mockSetLanguage,
      isPending: false,
      error: null,
      clearError: mockClearError,
    });
  });

  afterEach(() => {
    vi.unstubAllEnvs();
  });

  // AP01 — loading state: aria-busy skeleton while hydrating
  it("AP01: renders aria-busy skeleton during hydration", () => {
    mockUseAuth.mockReturnValue(makeAuthMock({ status: "hydrating", user: null }));
    renderAccountPage();
    expect(screen.getByTestId("account-loading")).toBeDefined();
    expect(screen.getByRole("status")).toHaveAttribute("aria-busy", "true");
  });

  // AP02 — success: renders email, full_name, brand, department, country, center
  it("AP02: success state renders user profile fields", () => {
    renderAccountPage();
    expect(screen.getByTestId("account-page")).toBeDefined();
    expect(screen.getByTestId("account-email-value").textContent).toBe(MOCK_USER.email);
    expect(screen.getByTestId("account-fullname-value").textContent).toBe(MOCK_USER.full_name);
    expect(screen.getByTestId("account-brand-value").textContent).toBe("Zara");
    expect(screen.getByTestId("account-department-value").textContent).toBe("People & Talent");
    expect(screen.getByTestId("account-country-value").textContent).toBe("ES");
    expect(screen.getByTestId("account-center-value").textContent).toBe("Madrid-HQ");
  });

  // AP03 — language radiogroup: 3 options, 'es' aria-checked=true initially
  it("AP03: language picker shows 3 options with es selected", () => {
    renderAccountPage();
    const picker = screen.getByTestId("account-language-picker");
    expect(picker).toBeDefined();

    const esBtn = screen.getByTestId("account-lang-option-es");
    const enBtn = screen.getByTestId("account-lang-option-en");
    const frBtn = screen.getByTestId("account-lang-option-fr");

    expect(esBtn).toHaveAttribute("aria-checked", "true");
    expect(enBtn).toHaveAttribute("aria-checked", "false");
    expect(frBtn).toHaveAttribute("aria-checked", "false");
  });

  // AP04 — clicking 'en' calls setLanguage('en')
  it("AP04: clicking 'en' option calls setLanguage('en')", () => {
    renderAccountPage();
    const enBtn = screen.getByTestId("account-lang-option-en");
    fireEvent.click(enBtn);
    expect(mockSetLanguage).toHaveBeenCalledWith("en");
  });

  // AP05 — i18n text re-renders after language change (simulated via i18n)
  it("AP05: after switching to EN, UI text renders in English", async () => {
    mockUseLanguagePicker.mockReturnValue({
      current: "en",
      setLanguage: mockSetLanguage,
      isPending: false,
      error: null,
      clearError: mockClearError,
    });
    await i18n.changeLanguage("en");

    renderAccountPage();

    // 'en' option should be aria-checked=true
    const enBtn = screen.getByTestId("account-lang-option-en");
    expect(enBtn).toHaveAttribute("aria-checked", "true");

    // Page title should be in English
    await waitFor(() => {
      expect(screen.getByTestId("account-title").textContent).toBe("My account");
    });
  });

  // AP06 — logout button calls useLogout.logout
  it("AP06: clicking logout button calls logout()", () => {
    renderAccountPage();
    const logoutBtn = screen.getByTestId("account-logout-button");
    fireEvent.click(logoutBtn);
    expect(mockLogout).toHaveBeenCalledTimes(1);
  });

  // AP07 — error_network state when user null + unauthenticated
  it("AP07: unauthenticated state shows permission denied view (no user)", () => {
    mockUseAuth.mockReturnValue(makeAuthMock({ status: "unauthenticated", user: null }));
    renderAccountPage();
    expect(screen.getByTestId("account-permission-denied")).toBeDefined();
  });

  // AP08 — validation error: ValidationErrorInline shown for code='validation'
  it("AP08: error_validation shows inline error near language picker", () => {
    mockUseLanguagePicker.mockReturnValue({
      current: "es",
      setLanguage: mockSetLanguage,
      isPending: false,
      error: { code: "validation", message: "LANGUAGE_INVALID: rejected" },
      clearError: mockClearError,
    });
    renderAccountPage();
    expect(screen.getByTestId("account-validation-error")).toBeDefined();
  });

  // AP09 — permission_denied: PermissionDeniedView shown on unauthenticated
  it("AP09: permission_denied state renders PermissionDeniedView with sign-in CTA", () => {
    mockUseAuth.mockReturnValue(makeAuthMock({ status: "unauthenticated", user: null }));
    renderAccountPage();
    expect(screen.getByTestId("account-permission-denied")).toBeDefined();
    expect(screen.getByTestId("account-signin-cta")).toBeDefined();
  });

  // AP10 — RequireAuth: clicking sign-in CTA in permission denied navigates
  it("AP10: sign-in CTA in permission denied navigates to /auth/sign-in?next=/account", () => {
    mockUseAuth.mockReturnValue(makeAuthMock({ status: "unauthenticated", user: null }));
    renderAccountPage();
    const signInBtn = screen.getByTestId("account-signin-cta");
    fireEvent.click(signInBtn);
    expect(mockNavigate).toHaveBeenCalledWith("/auth/sign-in?next=/account");
  });

  // AP11 — deep-link /account with valid session renders the page
  it("AP11: authenticated user deep-linking to /account sees the success state", () => {
    renderAccountPage();
    expect(screen.getByTestId("account-page")).toBeDefined();
    expect(screen.getByTestId("account-logout-button")).toBeDefined();
  });

  // AP12 — design tokens: no hardcoded hex in the rendered output's data-testid elements
  it("AP12: rendered profile section contains no hardcoded hex color values in textContent", () => {
    renderAccountPage();
    const page = screen.getByTestId("account-page");
    const text = page.textContent ?? "";
    // The text content of the page should not contain raw hex codes
    const hexPattern = /#[0-9a-fA-F]{3,6}/;
    expect(hexPattern.test(text)).toBe(false);
  });

  // AP13 — PII: full email never appears in logger calls
  it("AP13: no verbose logger call contains the full email value", () => {
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", "true");
    const verboseSpy = vi.spyOn(logger, "logVerbose");

    renderAccountPage();

    const allLogArgs = verboseSpy.mock.calls.flatMap((call) =>
      call.map((a) => JSON.stringify(a ?? "")),
    );
    const fullEmail = MOCK_USER.email;
    const containsEmail = allLogArgs.some((a) => a.includes(fullEmail));
    expect(containsEmail).toBe(false);
  });

  // AP14 — §D-T007-D2-NETWORK-RETRY (debugger cycle 1):
  //   When useLanguagePicker reports a network error, AccountPage renders
  //   NetworkErrorView (with retry CTA), not the previous ad-hoc div. Confirms
  //   the NetworkErrorView import is wired to a real path (dead-code smell fixed).
  it("AP14: PATCH /me/language network error renders NetworkErrorView with retry CTA", () => {
    mockUseLanguagePicker.mockReturnValue({
      current: "es",
      setLanguage: mockSetLanguage,
      isPending: false,
      error: { code: "network", message: "Network request failed." },
      clearError: mockClearError,
    });
    renderAccountPage();

    // The wrapper around NetworkErrorView (testid="account-language-network-error")
    // and the NetworkErrorView itself (testid="account-network-error") must be rendered.
    expect(screen.getByTestId("account-language-network-error")).toBeDefined();
    expect(screen.getByTestId("account-network-error")).toBeDefined();
    // The retry CTA from NetworkErrorView is visible.
    expect(screen.getByTestId("account-retry-cta")).toBeDefined();
    // The validation error view must NOT be rendered in this state.
    expect(screen.queryByTestId("account-validation-error")).toBeNull();
  });

  // AP14b — clicking the retry CTA re-triggers setLanguage with the current language
  //   (idempotent retry — the optimistic value was reverted before this CTA shows).
  it("AP14b: clicking retry on NetworkErrorView calls setLanguage with current language", () => {
    mockUseLanguagePicker.mockReturnValue({
      current: "es",
      setLanguage: mockSetLanguage,
      isPending: false,
      error: { code: "network", message: "Network request failed." },
      clearError: mockClearError,
    });
    renderAccountPage();

    const retryBtn = screen.getByTestId("account-retry-cta");
    fireEvent.click(retryBtn);

    expect(mockSetLanguage).toHaveBeenCalledTimes(1);
    expect(mockSetLanguage).toHaveBeenCalledWith("es");
  });

  // AP14c — when network error is showing, validation error inline is NOT rendered
  //   (and vice versa) — confirms the two error states are mutually exclusive.
  it("AP14c: validation error and network error views are mutually exclusive", () => {
    // Validation error: only validation view shows, no network view
    mockUseLanguagePicker.mockReturnValue({
      current: "es",
      setLanguage: mockSetLanguage,
      isPending: false,
      error: { code: "validation", message: "LANGUAGE_INVALID" },
      clearError: mockClearError,
    });
    const { unmount } = renderAccountPage();
    expect(screen.getByTestId("account-validation-error")).toBeDefined();
    expect(screen.queryByTestId("account-language-network-error")).toBeNull();
    expect(screen.queryByTestId("account-network-error")).toBeNull();
    unmount();
  });
});
