/**
 * Hilo People — ChatHomePage co-located smoke tests (P03-S02-T009).
 *
 * Slice/Phase: P03-S02-T009 — Add /account link from chat shell (navbar entry point) / Phase 3.
 *
 * Responsibility: Co-located smoke tests for the ChatNavbar integration in ChatHomePage.
 *   Verifies that the navbar account link is present in the page tree and absent in the
 *   forbidden (permission_denied) state.
 *
 *   Note: ChatHomePage deep integration coverage (10 tests) lives in
 *   features/chat/.../ChatHomePage.test.tsx (P03-S02-T001). This file only asserts the
 *   T009 acceptance criteria: navbar presence/absence per §D-T009-NAVBAR-VISIBILITY.
 *
 * Cases:
 *   N01 — success state: navbar account link visible.
 *   N02 — error_network state: navbar account link visible.
 *   N03 — permission_denied state: navbar account link HIDDEN.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import ChatHomePage from "../ChatHomePage";
import { ChatNetworkError, ChatForbiddenError } from "../../../features/chat/data/errors";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../features/auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => vi.fn(),
  };
});

vi.mock("../../../features/chat/presentation/useCreateConversation", () => ({
  useCreateConversation: vi.fn(),
}));

vi.mock("../../../features/chat/data/logger", () => ({
  logVerbose: vi.fn(),
  logWarn: vi.fn(),
  logError: vi.fn(),
}));

import { useAuth } from "../../../features/auth/presentation/AuthProvider";
import { useCreateConversation } from "../../../features/chat/presentation/useCreateConversation";

const mockUseAuth = vi.mocked(useAuth);
const mockUseCreateConversation = vi.mocked(useCreateConversation);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

function makeAuthMock() {
  mockUseAuth.mockReturnValue({
    user: {
      id: "user-uuid",
      email: "emp@test.com",
      full_name: "Test Emp",
      status: "active",
      preferred_language: "es",
      roles: ["employee"],
      employee_profile: null,
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    },
    status: "authenticated",
    accessToken: null,
    login: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  } as unknown as ReturnType<typeof useAuth>);
}

function makeMutation(overrides: Record<string, unknown> = {}) {
  mockUseCreateConversation.mockReturnValue({
    mutate: vi.fn(),
    isPending: false,
    error: null,
    reset: vi.fn(),
    ...overrides,
  } as unknown as ReturnType<typeof useCreateConversation>);
}

// ---------------------------------------------------------------------------
// Test harness
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return React.createElement(
      QueryClientProvider,
      { client: queryClient },
      React.createElement(
        I18nextProvider,
        { i18n },
        React.createElement(MemoryRouter, {}, children),
      ),
    );
  };
}

function renderPage() {
  return render(<ChatHomePage />, { wrapper: makeWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ChatHomePage — navbar (P03-S02-T009)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    makeAuthMock();
  });

  it("N01 — success state: navbar account link is present", () => {
    makeMutation({ error: null });
    renderPage();

    const navbar = screen.getByTestId("chat-navbar");
    expect(navbar).toBeDefined();

    const link = screen.getByTestId("chat-navbar-account-link");
    expect(link).toBeDefined();
    expect(link.getAttribute("href")).toBe("/account");
  });

  it("N02 — error_network state: navbar account link still present", () => {
    makeMutation({ error: new ChatNetworkError("Network down") });
    renderPage();

    const navbar = screen.getByTestId("chat-navbar");
    expect(navbar).toBeDefined();
  });

  it("N03 — permission_denied (forbidden) state: navbar account link HIDDEN", () => {
    makeMutation({ error: new ChatForbiddenError() });
    renderPage();

    expect(screen.queryByTestId("chat-navbar")).toBeNull();
    expect(screen.queryByTestId("chat-navbar-account-link")).toBeNull();
  });
});
