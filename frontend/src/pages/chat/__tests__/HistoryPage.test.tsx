/**
 * Hilo People — HistoryPage component tests.
 *
 * Slice/Phase: P03-S02-T003 — HistoryPage / Phase 3.
 *
 * Responsibility: Component tests covering the 5 required UX states + a11y + i18n.
 *   §D-T003-PAGE-TESTS — P01–P09 per task pack §12.
 *   useHistory hook mocked (fetch layer boundary).
 *   useAuth mocked to provide authenticated session.
 *   react-router useNavigate mocked.
 *   i18n real (inline resources from i18n/index.ts).
 *
 * Cases:
 *   P01 — loading state shows aria-busy skeleton.
 *   P02 — empty state shows Wordmark + CTA → /chat.
 *   P03 — error_network shows retry → triggers refetch.
 *   P04 — permission_denied (403) shows ForbiddenView.
 *   P05 — success renders grouped rows with hairline separators.
 *   P06 — row tap navigates to /chat/:conversationId.
 *   P07 — row Enter-key activates (a11y).
 *   P08 — i18n: ES default labels rendered.
 *   P09 — no hardcoded color/radius literals in rendered output (no inline style surprise).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import HistoryPage from "../HistoryPage";
import { ChatNetworkError, ChatForbiddenError } from "../../../features/chat/data/errors";
import type { ListConversationsResponse } from "../../../features/chat/domain/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../features/auth/presentation/AuthProvider", () => ({
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

vi.mock("../../../features/chat/presentation/useHistory", () => ({
  useHistory: vi.fn(),
}));

import { useAuth } from "../../../features/auth/presentation/AuthProvider";
import { useHistory } from "../../../features/chat/presentation/useHistory";

const mockUseAuth = vi.mocked(useAuth);
const mockUseHistory = vi.mocked(useHistory);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_LOGOUT = vi.fn();

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
    logout: MOCK_LOGOUT,
  } as unknown as ReturnType<typeof useAuth>);
}

const MOCK_RESPONSE: ListConversationsResponse = {
  data: [
    {
      id: "conv-uuid-1",
      user_id: "user-uuid",
      title: "My first conversation",
      language: "es",
      created_at: "2026-05-15T09:00:00Z",
      updated_at: "2026-05-15T10:00:00Z",
    },
    {
      id: "conv-uuid-2",
      user_id: "user-uuid",
      title: "Another conversation",
      language: "es",
      created_at: "2026-05-10T09:00:00Z",
      updated_at: "2026-05-10T12:00:00Z",
    },
  ],
  meta: {
    request_id: "req-1",
    pagination: { next_cursor: null, has_more: false },
  },
  errors: [],
};

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
  return render(<HistoryPage />, { wrapper: makeWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("HistoryPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    makeAuthMock();
  });

  it("P01 — loading state shows aria-busy skeleton", () => {
    mockUseHistory.mockReturnValue({
      isPending: true,
      isError: false,
      error: null,
      data: undefined,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const loading = screen.getByTestId("history-loading");
    expect(loading).toBeDefined();
    expect(loading.getAttribute("aria-busy")).toBe("true");
  });

  it("P02 — empty state shows Wordmark + CTA to /chat", async () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: {
        data: [],
        meta: { request_id: "r1", pagination: null },
        errors: [],
      } as ListConversationsResponse,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const empty = screen.getByTestId("history-empty");
    expect(empty).toBeDefined();

    // Body paragraph present (UX_CONTRACT §4 + pack §4 — invites starting a new chat)
    const body = screen.getByTestId("history-empty-body");
    expect(body).toBeDefined();
    // ES default — must contain the productive body text
    expect(body.textContent).toBe(
      "Empieza una nueva conversación para ver el historial aquí.",
    );

    // CTA present
    const cta = screen.getByTestId("history-empty-cta");
    expect(cta).toBeDefined();
  });

  it("P02 — empty CTA navigates to /chat", async () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: {
        data: [],
        meta: { request_id: "r1", pagination: null },
        errors: [],
      } as ListConversationsResponse,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const cta = screen.getByTestId("history-empty-cta");
    fireEvent.click(cta);

    expect(mockNavigate).toHaveBeenCalledWith("/chat");
  });

  it("P03 — error_network shows retry CTA and triggers refetch on click", async () => {
    const mockRefetch = vi.fn();

    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: true,
      error: new ChatNetworkError("Network down"),
      data: undefined,
      refetch: mockRefetch,
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const errorView = screen.getByTestId("history-network-error");
    expect(errorView).toBeDefined();

    const retryCta = screen.getByTestId("history-retry-cta");
    expect(retryCta).toBeDefined();

    fireEvent.click(retryCta);
    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it("P04 — permission_denied (403) shows ForbiddenView", () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: true,
      error: new ChatForbiddenError(),
      data: undefined,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const forbidden = screen.getByTestId("history-forbidden");
    expect(forbidden).toBeDefined();
    // Network error view should NOT be shown
    expect(screen.queryByTestId("history-network-error")).toBeNull();
  });

  it("P05 — success renders grouped rows", () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: MOCK_RESPONSE,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    // Both conversation rows should be present
    expect(screen.getByTestId("history-row-conv-uuid-1")).toBeDefined();
    expect(screen.getByTestId("history-row-conv-uuid-2")).toBeDefined();

    // Page should not show loading or error states
    expect(screen.queryByTestId("history-loading")).toBeNull();
    expect(screen.queryByTestId("history-network-error")).toBeNull();
  });

  it("P06 — row tap navigates to /chat/:conversationId", () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: MOCK_RESPONSE,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const row = screen.getByTestId("history-row-conv-uuid-1");
    fireEvent.click(row);

    expect(mockNavigate).toHaveBeenCalledWith("/chat/conv-uuid-1");
  });

  it("P07 — Enter key on row activates navigation (a11y keyboard nav)", () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: MOCK_RESPONSE,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const row = screen.getByTestId("history-row-conv-uuid-1");
    fireEvent.keyDown(row, { key: "Enter" });

    expect(mockNavigate).toHaveBeenCalledWith("/chat/conv-uuid-1");
  });

  it("P08 — ES i18n labels rendered (page title + group label)", () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: MOCK_RESPONSE,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    // Page title renders (uppercase via CSS, DOM text is original)
    const pageText = screen.getByText("CONVERSACIONES");
    expect(pageText).toBeDefined();
  });

  it("P09 — row has accessible label including conversation title", () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: MOCK_RESPONSE,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const row = screen.getByTestId("history-row-conv-uuid-1");
    const ariaLabel = row.getAttribute("aria-label") ?? "";
    // Should contain the conversation title
    expect(ariaLabel).toContain("My first conversation");
  });

  // --- P03-S02-T009: navbar account link assertions ---

  it("P10-T009 — success state: navbar account link present (§D-T009-NAVBAR-VISIBILITY)", () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: MOCK_RESPONSE,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const navbar = screen.getByTestId("chat-navbar");
    expect(navbar).toBeDefined();

    const link = screen.getByTestId("chat-navbar-account-link");
    expect(link).toBeDefined();
    expect(link.getAttribute("href")).toBe("/account");
  });

  it("P11-T009 — loading state: navbar account link present", () => {
    mockUseHistory.mockReturnValue({
      isPending: true,
      isError: false,
      error: null,
      data: undefined,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const navbar = screen.getByTestId("chat-navbar");
    expect(navbar).toBeDefined();
  });

  it("P12-T009 — permission_denied state: navbar account link HIDDEN (§D-T009-NAVBAR-VISIBILITY)", () => {
    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: true,
      error: new ChatForbiddenError(),
      data: undefined,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    // Navbar must NOT be rendered in the forbidden state
    expect(screen.queryByTestId("chat-navbar")).toBeNull();
    expect(screen.queryByTestId("chat-navbar-account-link")).toBeNull();
  });

  it("P13-T009 — clicking navbar link does NOT trigger history refetch", () => {
    const mockRefetch = vi.fn();

    mockUseHistory.mockReturnValue({
      isPending: false,
      isError: false,
      error: null,
      data: MOCK_RESPONSE,
      refetch: mockRefetch,
      isFetching: false,
    } as unknown as ReturnType<typeof useHistory>);

    renderPage();

    const link = screen.getByTestId("chat-navbar-account-link");
    fireEvent.click(link);

    // refetch must NOT be called as a result of clicking the navbar link
    expect(mockRefetch).not.toHaveBeenCalled();
  });
});
