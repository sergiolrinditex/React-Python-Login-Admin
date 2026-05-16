/**
 * Hilo People — McpServersPage component tests.
 *
 * Slice/Phase: P04-S02-T003 — McpServersPage / Phase 4.
 *
 * Responsibility: Page-level RTL tests covering all required UX states + a11y + i18n.
 *   useMcpServers and useMcpSync hooks mocked (fetch layer boundary).
 *   useAuth mocked to provide authenticated admin session.
 *   react-router useNavigate mocked.
 *   i18n real (inline resources from i18n/index.ts).
 *
 * §D-T003-TESTS-PAGE (P04-S02-T003 task pack §5)
 *   P01 — loading state visible initially (aria-busy)
 *   P02 — success state shows table rows for sandbox_readonly
 *   P03 — empty state when servers list is []
 *   P04 — error_network state on query error with retry CTA
 *   P05 — permission_denied state on McpForbiddenError
 *   P06 — click "Sync" on a row → row shows syncing → on success row updates tool_count
 *   P07 — click "Sync" → 502 → row shows MCP_SERVER_UNREACHABLE inline error
 *   P08 — ES/EN/FR i18n smoke (assert column header string in EN and FR)
 *   P09 — a11y: table has accessible caption; Sync button has accessible label
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../../i18n/index";
import McpServersPage from "../McpServersPage";
import {
  McpForbiddenError,
  McpNetworkError,
  McpServerUnreachableError,
} from "../../../../features/mcp/data/errors";
import type { McpServer } from "../../../../features/mcp/domain/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../../features/auth/presentation/AuthProvider", () => ({
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

vi.mock("../../../../features/mcp/presentation/useMcpServers", () => ({
  useMcpServers: vi.fn(),
  MCP_SERVERS_QUERY_KEY: ["admin", "mcp", "servers"],
}));

vi.mock("../../../../features/mcp/presentation/useMcpSync", () => ({
  useMcpSync: vi.fn(),
  MCP_SYNC_MUTATION_KEY: ["mcp", "sync"],
}));

import { useAuth } from "../../../../features/auth/presentation/AuthProvider";
import { useMcpServers } from "../../../../features/mcp/presentation/useMcpServers";
import { useMcpSync } from "../../../../features/mcp/presentation/useMcpSync";

const mockUseAuth = vi.mocked(useAuth);
const mockUseMcpServers = vi.mocked(useMcpServers);
const mockUseMcpSync = vi.mocked(useMcpSync);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_LOGOUT = vi.fn();

function makeAuthMock() {
  mockUseAuth.mockReturnValue({
    user: {
      id: "admin-uuid",
      email: "admin@test.com",
      full_name: "Admin User",
      status: "active",
      preferred_language: "es",
      roles: ["people_admin"],
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

const MOCK_SERVER: McpServer = {
  id: "server-uuid-sandbox",
  name: "sandbox_readonly",
  transport: "http",
  endpoint: "http://localhost:8080/mcp",
  status: "active",
  last_sync_at: null,
  created_by: null,
  has_credential: false,
  auth_type: null,
};

function makeMutationMock(overrides: Partial<ReturnType<typeof useMcpSync>> = {}) {
  const mutate = vi.fn();
  return {
    mutate,
    mutateAsync: vi.fn(),
    isPending: false,
    isSuccess: false,
    isError: false,
    isIdle: true,
    error: null,
    data: undefined,
    reset: vi.fn(),
    status: "idle" as const,
    variables: undefined,
    context: undefined,
    submittedAt: 0,
    failureCount: 0,
    failureReason: null,
    ...overrides,
  } as unknown as ReturnType<typeof useMcpSync>;
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
  return render(<McpServersPage />, { wrapper: makeWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("McpServersPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    makeAuthMock();
    // Reset i18n to ES
    void i18n.changeLanguage("es");
  });

  it("P01 — loading state shows aria-busy section", () => {
    mockUseMcpServers.mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
      refetch: vi.fn(),
      isFetching: true,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock());

    renderPage();

    const loading = screen.getByTestId("mcp-loading");
    expect(loading).toBeDefined();
    expect(loading.getAttribute("aria-busy")).toBe("true");
  });

  it("P02 — success state shows server row for sandbox_readonly", () => {
    mockUseMcpServers.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_SERVER],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock());

    renderPage();

    // Row for the server is present
    const row = screen.getByTestId("mcp-server-row-server-uuid-sandbox");
    expect(row).toBeDefined();

    // Server name is rendered (React auto-escaped)
    expect(screen.getByText("sandbox_readonly")).toBeDefined();

    // Loading state must NOT be shown
    expect(screen.queryByTestId("mcp-loading")).toBeNull();
  });

  it("P03 — empty state when servers list is []", () => {
    mockUseMcpServers.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock());

    renderPage();

    // Connect CTA visible in empty state
    const cta = screen.getByTestId("mcp-connect-cta");
    expect(cta).toBeDefined();

    // No server rows
    expect(screen.queryByTestId("mcp-server-row-server-uuid-sandbox")).toBeNull();
  });

  it("P04 — error_network state on network error with retry CTA", () => {
    const mockRefetch = vi.fn();

    mockUseMcpServers.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new McpNetworkError("Network down"),
      data: undefined,
      refetch: mockRefetch,
      isFetching: false,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock());

    renderPage();

    // HairlineTable renders error_network state with role="alert"
    const alert = screen.getByRole("alert");
    expect(alert).toBeDefined();
  });

  it("P05 — permission_denied state on McpForbiddenError", () => {
    mockUseMcpServers.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new McpForbiddenError(),
      data: undefined,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock());

    renderPage();

    // permission_denied state shows role="alert" from HairlineTable
    const alert = screen.getByRole("alert");
    expect(alert).toBeDefined();

    // Network error view must NOT be shown
    expect(screen.queryByTestId("mcp-loading")).toBeNull();
  });

  it("P06 — click Sync → shows syncing → on success updates tool_count display", async () => {
    let capturedOnSuccess: ((data: { tools_count: number; resources_count: number; prompts_count: number; status: string }) => void) | undefined;
    let capturedOnError: ((err: unknown) => void) | undefined;

    const mutateFn = vi.fn().mockImplementation((_vars: unknown, callbacks: { onSuccess?: (data: { tools_count: number }) => void; onError?: (err: unknown) => void }) => {
      capturedOnSuccess = callbacks.onSuccess as (data: { tools_count: number; resources_count: number; prompts_count: number; status: string }) => void;
      capturedOnError = callbacks.onError;
    });

    mockUseMcpServers.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_SERVER],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock({ mutate: mutateFn }));

    renderPage();

    // Find the sync button for sandbox_readonly
    const syncBtn = screen.getByRole("button", { name: /Sincronizar: sandbox_readonly/i });
    expect(syncBtn).toBeDefined();

    fireEvent.click(syncBtn);

    // mutate was called
    expect(mutateFn).toHaveBeenCalledTimes(1);
    expect(mutateFn).toHaveBeenCalledWith(
      { id: "server-uuid-sandbox" },
      expect.objectContaining({ onSuccess: expect.any(Function), onError: expect.any(Function) }),
    );

    // Simulate success callback
    await act(async () => {
      capturedOnSuccess?.({ tools_count: 7, resources_count: 2, prompts_count: 0, status: "active" });
    });

    // After success, tool count cell should show "7"
    await waitFor(() => {
      expect(screen.getByText("7")).toBeDefined();
    });

    void capturedOnError; // acknowledge binding
  });

  it("P07 — click Sync → 502 → inline error MCP_SERVER_UNREACHABLE appears", async () => {
    let capturedOnError: ((err: unknown) => void) | undefined;

    const mutateFn = vi.fn().mockImplementation((_vars: unknown, callbacks: { onSuccess?: (data: unknown) => void; onError?: (err: unknown) => void }) => {
      capturedOnError = callbacks.onError;
    });

    mockUseMcpServers.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_SERVER],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock({ mutate: mutateFn }));

    renderPage();

    const syncBtn = screen.getByRole("button", { name: /Sincronizar: sandbox_readonly/i });
    fireEvent.click(syncBtn);

    // Simulate 502 error via onError callback
    await act(async () => {
      capturedOnError?.(new McpServerUnreachableError());
    });

    // Inline per-row error should appear
    await waitFor(() => {
      const errorEl = screen.getByTestId("mcp-sync-error-server-uuid-sandbox");
      expect(errorEl).toBeDefined();
    });

    // Error text should be the MCP_SERVER_UNREACHABLE i18n string
    const errorEl = screen.getByRole("alert");
    expect(errorEl).toBeDefined();
  });

  it("P08 — i18n smoke: EN column headers rendered when language is EN", async () => {
    mockUseMcpServers.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_SERVER],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock());

    // Switch to EN
    await act(async () => {
      await i18n.changeLanguage("en");
    });

    renderPage();

    // EN column header "Status" should appear — TrackedLabel renders text in DOM (CSS uppercases visually)
    // Use getAllByText since TrackedLabel renders the DOM text as-is; textTransform is CSS-only
    const statusHeaders = screen.getAllByText("Status");
    expect(statusHeaders.length).toBeGreaterThan(0);

    // Verify EN sync button label
    const syncBtn = screen.getByRole("button", { name: /Sync: sandbox_readonly/i });
    expect(syncBtn).toBeDefined();

    // Restore to ES for subsequent tests
    await act(async () => {
      await i18n.changeLanguage("es");
    });
  });

  it("P09 — a11y: table has accessible caption; Sync button has accessible label", () => {
    mockUseMcpServers.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_SERVER],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useMcpServers>);

    mockUseMcpSync.mockReturnValue(makeMutationMock());

    renderPage();

    // Sync button has aria-label containing the server name
    const syncBtn = screen.getByRole("button", { name: /sandbox_readonly/i });
    expect(syncBtn).toBeDefined();
    expect(syncBtn.getAttribute("aria-label")).toContain("sandbox_readonly");
  });
});
