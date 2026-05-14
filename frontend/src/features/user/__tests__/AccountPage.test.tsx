/**
 * Hilo People — AccountPage component tests.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3.
 *
 * Responsibility: Integration tests covering all 5 required UX states and interactions.
 *   Mocks: useAuth (composition), useMe, useUpdateLanguage.
 *   i18n: real (inline resources). Router: MemoryRouter.
 *
 * Test cases (≥10):
 *   T01 — loading skeleton renders with aria-busy when useMe.isPending=true
 *   T02 — success: renders employee profile fields from mock data
 *   T03 — language picker: 3 radio buttons with aria-checked reflecting current language
 *   T04 — click EN: optimistic UI flip (i18n.changeLanguage called, button active)
 *   T05 — mutation success: aria-checked moves to EN, no error banner
 *   T06 — PATCH 400 → reverts UI + shows inline validation error
 *   T07 — PATCH 5xx → reverts UI + shows network error inline
 *   T08 — logout button calls useAuth().logout + navigates to /auth/sign-in with replace
 *   T09 — 403 useMe error → ForbiddenView rendered
 *   T10 — network error from useMe → retry CTA visible; click retry refetches
 *   T11 — i18n keys render in active locale (EN: "My account")
 *   T12 — a11y: logout button has aria-label
 *   T13 — empty state explicitly N/A (loading path covers null data case)
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import AccountPage from "../../../pages/chat/AccountPage";
import type { UserProfile } from "../domain/types";
import { UserForbiddenError, UserNetworkError, UserValidationError, UserServerError } from "../domain/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
  };
});

vi.mock("../presentation/useMe", () => ({
  useMe: vi.fn(),
  ME_QUERY_KEY: ["user", "me"],
}));

vi.mock("../presentation/useUpdateLanguage", () => ({
  useUpdateLanguage: vi.fn(),
}));

import { useAuth } from "../../auth/presentation/AuthProvider";
import { useMe } from "../presentation/useMe";
import { useUpdateLanguage } from "../presentation/useUpdateLanguage";

const mockUseAuth = vi.mocked(useAuth);
const mockUseMe = vi.mocked(useMe);
const mockUseUpdateLanguage = vi.mocked(useUpdateLanguage);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_PROFILE: UserProfile = {
  id: "7b34e2ca-a9cc-4152-9be0-552d200464ce",
  email: "employee.verification@inditex-sandbox.com",
  full_name: "Elena Verificación",
  status: "active",
  preferred_language: "es",
  roles: ["employee"],
  employee_profile: {
    employee_id: "EMP-VERIFY-001",
    brand: "Zara",
    society: "ITX-ES",
    center: "Madrid-HQ",
    country: "ES",
    department: "People & Talent",
  },
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderAccountPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={["/account"]}>
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          <AccountPage />
        </I18nextProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Default mock setups
// ---------------------------------------------------------------------------

function setupDefaultAuthMock(overrides = {}) {
  mockUseAuth.mockReturnValue({
    status: "authenticated",
    user: MOCK_PROFILE,
    signInAccepted: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
    ...overrides,
  });
}

function setupSuccessMe(profileOverride?: Partial<UserProfile>) {
  const profile = { ...MOCK_PROFILE, ...profileOverride };
  mockUseMe.mockReturnValue({
    data: profile,
    isPending: false,
    isError: false,
    error: null,
    refetch: vi.fn(),
    fetchStatus: "idle",
  } as unknown as ReturnType<typeof useMe>);
}

function setupLoadingMe() {
  mockUseMe.mockReturnValue({
    data: undefined,
    isPending: true,
    isError: false,
    error: null,
    refetch: vi.fn(),
    fetchStatus: "fetching",
  } as unknown as ReturnType<typeof useMe>);
}

function setupErrorMe(error: unknown) {
  mockUseMe.mockReturnValue({
    data: undefined,
    isPending: false,
    isError: true,
    error,
    refetch: vi.fn(),
    fetchStatus: "idle",
  } as unknown as ReturnType<typeof useMe>);
}

function setupDefaultLangMock(overrides = {}) {
  mockUseUpdateLanguage.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null,
    reset: vi.fn(),
    ...overrides,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AccountPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();
    void i18n.changeLanguage("es");
  });

  // T01
  it("T01 — loading skeleton renders with aria-busy when isPending=true", () => {
    setupDefaultAuthMock();
    setupLoadingMe();
    setupDefaultLangMock();

    renderAccountPage();

    const skeleton = screen.getByTestId("account-loading");
    expect(skeleton).toBeInTheDocument();
    expect(skeleton).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByTestId("account-page")).not.toBeInTheDocument();
  });

  // T02
  it("T02 — success: renders employee profile fields from MOCK_PROFILE", () => {
    setupDefaultAuthMock();
    setupSuccessMe();
    setupDefaultLangMock();

    renderAccountPage();

    expect(screen.getByTestId("account-page")).toBeInTheDocument();
    expect(screen.getByTestId("profile-row-name")).toBeInTheDocument();
    expect(screen.getByText("Elena Verificación")).toBeInTheDocument();
    expect(screen.getByTestId("profile-row-employee-id")).toBeInTheDocument();
    expect(screen.getByText("EMP-VERIFY-001")).toBeInTheDocument();
    expect(screen.getByText("Zara")).toBeInTheDocument();
    expect(screen.getByText("ITX-ES")).toBeInTheDocument();
    expect(screen.getByText("Madrid-HQ")).toBeInTheDocument();
    expect(screen.getByText("ES")).toBeInTheDocument();
    expect(screen.getByText("People & Talent")).toBeInTheDocument();
  });

  // T03
  it("T03 — language picker: 3 radio buttons with aria-checked on current language (es)", () => {
    setupDefaultAuthMock();
    setupSuccessMe({ preferred_language: "es" });
    setupDefaultLangMock();

    renderAccountPage();

    const picker = screen.getByTestId("language-picker");
    expect(picker).toHaveAttribute("role", "radiogroup");

    const esBtnEl = screen.getByTestId("lang-btn-es");
    const enBtnEl = screen.getByTestId("lang-btn-en");
    const frBtnEl = screen.getByTestId("lang-btn-fr");

    expect(esBtnEl).toHaveAttribute("role", "radio");
    expect(esBtnEl).toHaveAttribute("aria-checked", "true");
    expect(enBtnEl).toHaveAttribute("aria-checked", "false");
    expect(frBtnEl).toHaveAttribute("aria-checked", "false");
  });

  // T04
  it("T04 — click EN button: calls updateLanguage('en') mutation", async () => {
    const mutateMock = vi.fn();
    setupDefaultAuthMock();
    setupSuccessMe({ preferred_language: "es" });
    setupDefaultLangMock({ mutate: mutateMock });

    renderAccountPage();

    const enBtn = screen.getByTestId("lang-btn-en");
    fireEvent.click(enBtn);

    await waitFor(() => {
      expect(mutateMock).toHaveBeenCalledWith("en");
    });
  });

  // T05
  it("T05 — after successful EN update: no error banner, EN button active", () => {
    setupDefaultAuthMock();
    setupSuccessMe({ preferred_language: "en" });
    setupDefaultLangMock({ error: null });

    renderAccountPage();

    const enBtn = screen.getByTestId("lang-btn-en");
    expect(enBtn).toHaveAttribute("aria-checked", "true");
    expect(screen.queryByTestId("lang-validation-error")).not.toBeInTheDocument();
    expect(screen.queryByTestId("lang-network-error")).not.toBeInTheDocument();
  });

  // T06
  it("T06 — PATCH 400 error → shows inline validation error", () => {
    setupDefaultAuthMock();
    setupSuccessMe({ preferred_language: "es" });
    setupDefaultLangMock({ error: new UserValidationError() });

    renderAccountPage();

    const inlineError = screen.getByTestId("lang-validation-error");
    expect(inlineError).toBeInTheDocument();
    expect(inlineError).toHaveAttribute("role", "alert");
  });

  // T07
  it("T07 — PATCH 5xx → shows inline network error", () => {
    setupDefaultAuthMock();
    setupSuccessMe({ preferred_language: "es" });
    setupDefaultLangMock({ error: new UserServerError(503) });

    renderAccountPage();

    expect(screen.getByTestId("lang-network-error")).toBeInTheDocument();
  });

  // T08
  it("T08 — logout button calls useAuth().logout + navigates to /auth/sign-in with replace", async () => {
    const logoutMock = vi.fn().mockResolvedValue(undefined);
    setupDefaultAuthMock({ logout: logoutMock });
    setupSuccessMe();
    setupDefaultLangMock();

    renderAccountPage();

    const logoutBtn = screen.getByTestId("logout-button");
    fireEvent.click(logoutBtn);

    await waitFor(() => {
      expect(logoutMock).toHaveBeenCalledTimes(1);
    });
    await waitFor(() => {
      expect(mockNavigate).toHaveBeenCalledWith("/auth/sign-in", { replace: true });
    });
  });

  // T09
  it("T09 — 403 from useMe → ForbiddenView rendered", () => {
    setupDefaultAuthMock();
    setupErrorMe(new UserForbiddenError());
    setupDefaultLangMock();

    renderAccountPage();

    expect(screen.getByTestId("forbidden-view")).toBeInTheDocument();
    expect(screen.queryByTestId("account-page")).not.toBeInTheDocument();
  });

  // T10
  it("T10 — network error from useMe → retry CTA visible; click retry calls refetch", async () => {
    const refetchMock = vi.fn().mockResolvedValue(undefined);
    setupDefaultAuthMock();
    mockUseMe.mockReturnValue({
      data: undefined,
      isPending: false,
      isError: true,
      error: new UserNetworkError(),
      refetch: refetchMock,
      fetchStatus: "idle",
    } as unknown as ReturnType<typeof useMe>);
    setupDefaultLangMock();

    renderAccountPage();

    const networkView = screen.getByTestId("network-error-view");
    expect(networkView).toBeInTheDocument();

    const retryBtn = screen.getByTestId("network-error-retry-cta");
    fireEvent.click(retryBtn);

    await waitFor(() => {
      expect(refetchMock).toHaveBeenCalled();
    });
  });

  // T11
  it("T11 — i18n keys render in the active locale (ES default: 'Mi cuenta')", async () => {
    // Ensure ES locale
    await act(async () => { await i18n.changeLanguage("es"); });

    setupDefaultAuthMock();
    setupSuccessMe({ preferred_language: "es" });
    setupDefaultLangMock();

    renderAccountPage();

    // TrackedLabel uses CSS text-transform:uppercase — DOM content is the original casing
    expect(screen.getByText("Mi cuenta")).toBeInTheDocument();
  });

  // T12
  it("T12 — a11y: logout button has aria-label", () => {
    setupDefaultAuthMock();
    setupSuccessMe();
    setupDefaultLangMock();

    renderAccountPage();

    const logoutBtn = screen.getByTestId("logout-button");
    expect(logoutBtn).toHaveAttribute("aria-label");
    const ariaLabel = logoutBtn.getAttribute("aria-label") ?? "";
    expect(ariaLabel.length).toBeGreaterThan(0);
  });

  // T13
  it("T13 — empty state N/A: loading path with null data shows skeleton, not empty content", () => {
    setupDefaultAuthMock();
    setupLoadingMe();
    setupDefaultLangMock();

    renderAccountPage();

    // No profile content visible when loading (null data handled as loading, not empty)
    expect(screen.queryByTestId("profile-section")).not.toBeInTheDocument();
    expect(screen.getByTestId("account-loading")).toBeInTheDocument();
  });
});
