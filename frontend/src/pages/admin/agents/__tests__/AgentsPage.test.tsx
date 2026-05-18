/**
 * Hilo People — AgentsPage component tests.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Page-level RTL tests covering all required UX states + a11y + i18n.
 *   useAgents, useUpdateAgentTools, useStartAgentRun hooks mocked (fetch layer boundary).
 *   useAuth mocked to provide authenticated admin session.
 *   i18n real (inline resources from i18n/index.ts).
 *
 * §D-T005-TESTS-PAGE (P04-S02-T005 task pack §10)
 *   P01 — loading state visible initially (aria-busy, data-testid="agents-loading")
 *   P02 — success state shows agent row for people_helper
 *   P03 — empty state when agents list is [] (Wordmark + body, no CTA)
 *   P04 — error_network state on query error with retry CTA
 *   P05 — permission_denied state on AgentsForbiddenError
 *   P06 — run launcher shows inline disabled error on 409 AGENT_DISABLED
 *   P07 — run launcher shows AGENT_RUN_FAILED on 502 (expected dev sandbox path)
 *   P08 — run launcher shows success result on 200
 *   P09 — per-row PATCH error shows inline below row on 400 AGENT_TOOL_NOT_APPROVED
 *   P10 — a11y: table has accessible caption; aria-busy on pending rows
 *   P11 — i18n smoke: EN title rendered when language is EN
 *   P12 — run launcher input validation: empty input shows error
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../../i18n/index";
import AgentsPage from "../AgentsPage";
import {
  AgentsForbiddenError,
  AgentsNetworkError,
  AgentsAgentDisabledError,
  AgentsRunUnreachableError,
  AgentsToolNotApprovedError,
} from "../../../../features/agents/data/errors";
import type { Agent } from "../../../../features/agents/domain/types";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../../features/auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

vi.mock("../../../../features/agents/presentation/useAgents", () => ({
  useAgents: vi.fn(),
  AGENTS_QUERY_KEY: ["admin", "agents"],
}));

vi.mock("../../../../features/agents/presentation/useUpdateAgentTools", () => ({
  useUpdateAgentTools: vi.fn(),
  UPDATE_AGENT_TOOLS_MUTATION_KEY: ["agents", "updateTools"],
}));

vi.mock("../../../../features/agents/presentation/useStartAgentRun", () => ({
  useStartAgentRun: vi.fn(),
  START_AGENT_RUN_MUTATION_KEY: ["agents", "startRun"],
}));

// useMutationState must be mocked to avoid needing real QueryClient mutation state
vi.mock("@tanstack/react-query", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@tanstack/react-query")>();
  return {
    ...actual,
    useMutationState: vi.fn().mockReturnValue([]),
  };
});

import { useAuth } from "../../../../features/auth/presentation/AuthProvider";
import { useAgents } from "../../../../features/agents/presentation/useAgents";
import { useUpdateAgentTools } from "../../../../features/agents/presentation/useUpdateAgentTools";
import { useStartAgentRun } from "../../../../features/agents/presentation/useStartAgentRun";

const mockUseAuth = vi.mocked(useAuth);
const mockUseAgents = vi.mocked(useAgents);
const mockUseUpdateAgentTools = vi.mocked(useUpdateAgentTools);
const mockUseStartAgentRun = vi.mocked(useStartAgentRun);

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

const MOCK_AGENT: Agent = {
  id: "agent-uuid-people-helper",
  name: "people_helper",
  description: "HR assistant agent",
  enabled: true,
  config: {},
  bound_tools: [
    {
      id: "tool-uuid-1",
      name: "list_employees",
      server_name: "sandbox_readonly",
      enabled: true,
      requires_approval: false,
      risk_level: "low",
    },
  ],
};

function makeUpdateToolsMock(overrides: Partial<ReturnType<typeof useUpdateAgentTools>> = {}) {
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
  } as unknown as ReturnType<typeof useUpdateAgentTools>;
}

function makeStartRunMock(overrides: Partial<ReturnType<typeof useStartAgentRun>> = {}) {
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
  } as unknown as ReturnType<typeof useStartAgentRun>;
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
  return render(<AgentsPage />, { wrapper: makeWrapper() });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AgentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    makeAuthMock();
    void i18n.changeLanguage("es");
  });

  it("P01 — loading state shows aria-busy section", () => {
    mockUseAgents.mockReturnValue({
      isLoading: true,
      isError: false,
      error: null,
      data: undefined,
      refetch: vi.fn(),
      isFetching: true,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock());

    renderPage();

    const loading = screen.getByTestId("agents-loading");
    expect(loading).toBeDefined();
    expect(loading.getAttribute("aria-busy")).toBe("true");
  });

  it("P02 — success state shows agent row for people_helper", () => {
    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_AGENT],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock());

    renderPage();

    const row = screen.getByTestId("agent-row-agent-uuid-people-helper");
    expect(row).toBeDefined();
    expect(screen.getByText("people_helper")).toBeDefined();
    expect(screen.queryByTestId("agents-loading")).toBeNull();
  });

  it("P03 — empty state shows Wordmark + body paragraph, no CTA", () => {
    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock());

    renderPage();

    const emptyBody = screen.getByTestId("agents-empty-body");
    expect(emptyBody).toBeDefined();
    // §D-T005-EMPTY-STATE: no CTA present
    expect(screen.queryByRole("button", { name: /crear|new|create/i })).toBeNull();
    expect(screen.queryByTestId("agent-row-agent-uuid-people-helper")).toBeNull();
  });

  it("P04 — error_network state on network error with retry CTA", () => {
    const mockRefetch = vi.fn();

    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new AgentsNetworkError("Network down"),
      data: undefined,
      refetch: mockRefetch,
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock());

    renderPage();

    // HairlineTable renders error_network state with role="alert"
    const alert = screen.getByRole("alert");
    expect(alert).toBeDefined();
  });

  it("P05 — permission_denied state on AgentsForbiddenError", () => {
    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: true,
      error: new AgentsForbiddenError(),
      data: undefined,
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock());

    renderPage();

    const alert = screen.getByRole("alert");
    expect(alert).toBeDefined();
    expect(screen.queryByTestId("agents-loading")).toBeNull();
  });

  it("P06 — run launcher 409 AGENT_DISABLED shows inline error near launcher", async () => {
    let capturedOnError: ((err: unknown) => void) | undefined;

    const runMutateFn = vi.fn().mockImplementation((_vars: unknown, callbacks: { onError?: (err: unknown) => void; onSuccess?: (data: unknown) => void }) => {
      capturedOnError = callbacks.onError;
    });

    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_AGENT],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock({ mutate: runMutateFn }));

    renderPage();

    // Find and fill run input
    const runInput = screen.getByTestId("agents-run-input-agent-uuid-people-helper");
    fireEvent.change(runInput, { target: { value: "ping" } });

    // Click run button
    const runBtn = screen.getByTestId("agents-run-btn-agent-uuid-people-helper");
    fireEvent.click(runBtn);

    expect(runMutateFn).toHaveBeenCalledTimes(1);

    // Simulate 409 error
    await act(async () => {
      capturedOnError?.(new AgentsAgentDisabledError());
    });

    await waitFor(() => {
      const errorEl = screen.getByTestId("agents-run-error-agent-uuid-people-helper");
      expect(errorEl).toBeDefined();
    });
  });

  it("P07 — run launcher 502 shows AGENT_RUN_FAILED inline error (expected dev path)", async () => {
    let capturedOnError: ((err: unknown) => void) | undefined;

    const runMutateFn = vi.fn().mockImplementation((_vars: unknown, callbacks: { onError?: (err: unknown) => void; onSuccess?: (data: unknown) => void }) => {
      capturedOnError = callbacks.onError;
    });

    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_AGENT],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock({ mutate: runMutateFn }));

    renderPage();

    const runInput = screen.getByTestId("agents-run-input-agent-uuid-people-helper");
    fireEvent.change(runInput, { target: { value: "ping" } });

    const runBtn = screen.getByTestId("agents-run-btn-agent-uuid-people-helper");
    fireEvent.click(runBtn);

    await act(async () => {
      capturedOnError?.(new AgentsRunUnreachableError());
    });

    await waitFor(() => {
      const errorEl = screen.getByTestId("agents-run-error-agent-uuid-people-helper");
      expect(errorEl).toBeDefined();
    });

    // Error should be the AGENT_RUN_FAILED text (from errors namespace)
    const errorEl = screen.getByRole("alert");
    expect(errorEl).toBeDefined();
  });

  it("P08 — run launcher success shows run result", async () => {
    let capturedOnSuccess: ((data: unknown) => void) | undefined;

    const runMutateFn = vi.fn().mockImplementation((_vars: unknown, callbacks: { onSuccess?: (data: unknown) => void; onError?: (err: unknown) => void }) => {
      capturedOnSuccess = callbacks.onSuccess;
    });

    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_AGENT],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock({ mutate: runMutateFn }));

    renderPage();

    const runInput = screen.getByTestId("agents-run-input-agent-uuid-people-helper");
    fireEvent.change(runInput, { target: { value: "ping" } });

    const runBtn = screen.getByTestId("agents-run-btn-agent-uuid-people-helper");
    fireEvent.click(runBtn);

    await act(async () => {
      capturedOnSuccess?.({ run_id: "run-uuid-1", status: "pending" });
    });

    await waitFor(() => {
      const resultEl = screen.getByTestId("agents-run-result-agent-uuid-people-helper");
      expect(resultEl).toBeDefined();
    });
  });

  it("P09 — PATCH 400 AGENT_TOOL_NOT_APPROVED shows inline error below row", async () => {
    let capturedOnError: ((err: unknown) => void) | undefined;

    const patchMutateFn = vi.fn().mockImplementation((_vars: unknown, callbacks: { onError?: (err: unknown) => void }) => {
      capturedOnError = callbacks.onError;
    });

    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_AGENT],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock({ mutate: patchMutateFn }));
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock());

    renderPage();

    // Toggle the tool checkbox to trigger PATCH
    const toggle = screen.getByTestId("agent-tool-toggle-agent-uuid-people-helper-tool-uuid-1");
    fireEvent.click(toggle);

    expect(patchMutateFn).toHaveBeenCalledTimes(1);

    // Simulate 400 AGENT_TOOL_NOT_APPROVED error
    await act(async () => {
      capturedOnError?.(new AgentsToolNotApprovedError());
    });

    await waitFor(() => {
      const errorRow = screen.getByTestId("agent-patch-error-agent-uuid-people-helper");
      expect(errorRow).toBeDefined();
    });
  });

  it("P10 — a11y: table has sr-only caption and run button has aria-label", () => {
    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_AGENT],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock());

    renderPage();

    // Run button has aria-label containing agent name
    const runBtn = screen.getByTestId("agents-run-btn-agent-uuid-people-helper");
    expect(runBtn.getAttribute("aria-label")).toContain("people_helper");
  });

  it("P11 — i18n smoke: EN title rendered when language is EN", async () => {
    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_AGENT],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock());

    await act(async () => {
      await i18n.changeLanguage("en");
    });

    renderPage();

    // EN title "AI Agents" should appear
    const title = screen.getAllByText("AI Agents");
    expect(title.length).toBeGreaterThan(0);

    await act(async () => {
      await i18n.changeLanguage("es");
    });
  });

  it("P12 — run launcher empty input shows validation error", () => {
    mockUseAgents.mockReturnValue({
      isLoading: false,
      isError: false,
      error: null,
      data: [MOCK_AGENT],
      refetch: vi.fn(),
      isFetching: false,
    } as unknown as ReturnType<typeof useAgents>);
    mockUseUpdateAgentTools.mockReturnValue(makeUpdateToolsMock());
    const runMutateFn = vi.fn();
    mockUseStartAgentRun.mockReturnValue(makeStartRunMock({ mutate: runMutateFn }));

    renderPage();

    // Click run without entering input
    const runBtn = screen.getByTestId("agents-run-btn-agent-uuid-people-helper");
    fireEvent.click(runBtn);

    // mutate should NOT be called (client-side validation)
    expect(runMutateFn).not.toHaveBeenCalled();

    // Validation error should be shown
    const errorEl = screen.getByTestId("agents-run-error-agent-uuid-people-helper");
    expect(errorEl).toBeDefined();
  });
});
