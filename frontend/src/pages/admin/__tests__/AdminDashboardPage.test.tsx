/**
 * Hilo People — AdminDashboardPage component tests.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-TESTS
 *
 * Responsibility: Component tests covering all 5 required UX states + nav + i18n.
 *   useDashboardUsage hook is mocked (hook boundary).
 *   useAuth is mocked to provide authenticated admin session.
 *   react-router useNavigate is mocked.
 *   i18n is real (inline resources from i18n/index.ts).
 *
 * Cases (as per task pack §9.2 §D-T001-TESTS):
 *   P01 — loading state: aria-busy skeleton visible.
 *   P02 — empty state: Wordmark + empty title/body + manageModels CTA.
 *   P03 — success with KPIs + table: 4 KPI tiles + table rows.
 *   P04 — error_network + retry CTA: error view + retry triggers refetch.
 *   P05 — permission_denied: ForbiddenView with title + body.
 *   P06 — manageModels CTA navigation in success state: navigates to /admin/ai/models.
 *   P07 — i18n EN: dashboard title renders in English.
 *   P08 — all 10 nav items rendered in AdminShell.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import AdminDashboardPage from "../AdminDashboardPage";
import {
  AdminAiNetworkError,
  AdminAiForbiddenError,
} from "../../../features/admin-ai/data/errors";
import type { UseDashboardUsageResult } from "../../../features/admin-ai/presentation/useDashboardUsage";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../features/admin-ai/presentation/useDashboardUsage", () => ({
  useDashboardUsage: vi.fn(),
}));

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

import { useDashboardUsage } from "../../../features/admin-ai/presentation/useDashboardUsage";
import { useAuth } from "../../../features/auth/presentation/AuthProvider";

const mockUseDashboardUsage = vi.mocked(useDashboardUsage);
const mockUseAuth = vi.mocked(useAuth);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_ADMIN_USER = {
  id: "aaaa-bbbb-cccc-dddd",
  email: "admin@test.com",
  full_name: "Admin User",
  status: "active" as const,
  preferred_language: "es" as const,
  roles: ["people_admin"],
  employee_profile: null,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const MOCK_ROWS = [
  {
    tokens_in: 1234,
    tokens_out: 567,
    estimated_cost: 0.0123,
    latency_ms_avg: 842,
    invocations: 12,
    model_name: "gpt-4o-mini",
  },
];

const MOCK_TOTALS = {
  tokens_in: 1234,
  tokens_out: 567,
  estimated_cost: 0.0123,
  invocations: 12,
  latency_ms_avg: 842,
};

const MOCK_USAGE_SUMMARY = {
  from: "2026-04-16T00:00:00Z",
  to: "2026-05-16T00:00:00Z",
  group_by: "model" as const,
  rows: MOCK_ROWS,
  totals: MOCK_TOTALS,
};

const FROM_ISO = "2026-04-16T00:00:00.000Z";
const TO_ISO = "2026-05-16T00:00:00.000Z";

const DEFAULT_HOOK_STATE: UseDashboardUsageResult = {
  isLoading: false,
  isSuccess: true,
  isError: false,
  error: null,
  data: MOCK_USAGE_SUMMARY,
  refetch: vi.fn(),
  from: FROM_ISO,
  to: TO_ISO,
};

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={["/admin"]}>
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          <AdminDashboardPage />
        </I18nextProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Setup helpers
// ---------------------------------------------------------------------------

function setupMocks(hookOverrides: Partial<UseDashboardUsageResult> = {}): void {
  mockUseAuth.mockReturnValue({
    status: "authenticated",
    user: MOCK_ADMIN_USER,
    signInAccepted: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  });
  const mockRefetch = vi.fn();
  mockUseDashboardUsage.mockReturnValue({
    ...DEFAULT_HOOK_STATE,
    refetch: mockRefetch,
    ...hookOverrides,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdminDashboardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockNavigate.mockReset();
  });

  afterEach(async () => {
    await i18n.changeLanguage("es");
  });

  it("P01 — loading state: aria-busy skeleton visible", () => {
    setupMocks({ isLoading: true, isSuccess: false, data: undefined });
    renderPage();

    const loadingEl = screen.getByTestId("admin-dashboard-loading");
    expect(loadingEl).toBeInTheDocument();
    expect(loadingEl).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByTestId("admin-dashboard-empty")).not.toBeInTheDocument();
    expect(screen.queryByTestId("kpi-grid")).not.toBeInTheDocument();
  });

  it("P02 — empty state: Wordmark + empty title/body + manageModels CTA", () => {
    setupMocks({
      isLoading: false,
      isSuccess: true,
      data: {
        from: FROM_ISO,
        to: TO_ISO,
        group_by: "model",
        rows: [],
        totals: { tokens_in: 0, tokens_out: 0, estimated_cost: 0, invocations: 0, latency_ms_avg: 0 },
      },
    });
    renderPage();

    expect(screen.getByTestId("admin-dashboard-empty")).toBeInTheDocument();
    // Wordmark (multiple "Hilo" exist: nav + empty state — assert by testid area)
    const emptyEl = screen.getByTestId("admin-dashboard-empty");
    expect(emptyEl.textContent).toContain("Hilo");
    // Empty title from ES i18n
    expect(screen.getByTestId("empty-title")).toHaveTextContent("Sin uso registrado");
    // Empty body
    expect(screen.getByTestId("empty-body")).toBeInTheDocument();
    // CTA
    expect(screen.getByTestId("empty-manage-models-cta")).toBeInTheDocument();
  });

  it("P03 — success: 4 KPI tiles + table row rendered", () => {
    setupMocks();
    renderPage();

    expect(screen.getByTestId("kpi-grid")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-invocations")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-tokens")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-cost")).toBeInTheDocument();
    expect(screen.getByTestId("kpi-latency")).toBeInTheDocument();
    // KPI value for invocations = 12
    expect(screen.getByTestId("kpi-invocations")).toHaveTextContent("12");
    // Table section present
    expect(screen.getByTestId("usage-table-section")).toBeInTheDocument();
    // Model name in table
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
  });

  it("P04 — error_network: error view visible + retry CTA triggers refetch", async () => {
    const mockRefetch = vi.fn();
    setupMocks({
      isLoading: false,
      isSuccess: false,
      isError: true,
      error: new AdminAiNetworkError("Network failed"),
      data: undefined,
      refetch: mockRefetch,
    });
    renderPage();

    const errorEl = screen.getByTestId("admin-dashboard-error-network");
    expect(errorEl).toBeInTheDocument();
    expect(screen.getByTestId("error-network-title")).toHaveTextContent(
      "No se pudo cargar el resumen",
    );
    expect(screen.getByTestId("error-network-retry-cta")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("error-network-retry-cta"));
    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it("P05 — permission_denied: ForbiddenView with title and body", () => {
    setupMocks({
      isLoading: false,
      isSuccess: false,
      isError: true,
      error: new AdminAiForbiddenError(),
      data: undefined,
    });
    renderPage();

    expect(screen.getByTestId("admin-dashboard-forbidden")).toBeInTheDocument();
    expect(screen.getByTestId("forbidden-title")).toHaveTextContent("Acceso restringido");
    expect(screen.getByTestId("forbidden-body")).toBeInTheDocument();
    // No error_network view
    expect(screen.queryByTestId("admin-dashboard-error-network")).not.toBeInTheDocument();
  });

  it("P06 — success: manageModels CTA navigates to /admin/ai/models", () => {
    setupMocks();
    renderPage();

    const cta = screen.getByTestId("manage-models-cta");
    expect(cta).toBeInTheDocument();
    fireEvent.click(cta);
    expect(mockNavigate).toHaveBeenCalledWith("/admin/ai/models");
  });

  it("P07 — i18n EN: dashboard title renders in English", async () => {
    await i18n.changeLanguage("en");
    setupMocks();
    renderPage();

    expect(screen.getByTestId("dashboard-title")).toHaveTextContent("Admin AI overview");
    expect(screen.getByText("Manage models")).toBeInTheDocument();
  });

  it("P08 — all 10 nav items rendered in AdminShell", () => {
    setupMocks();
    renderPage();

    // All 10 nav items from D-T001-NAV-LINKS
    expect(screen.getByText("Resumen")).toBeInTheDocument(); // dashboard (active)
    expect(screen.getByText("Modelos")).toBeInTheDocument();
    expect(screen.getByText("Nuevo modelo")).toBeInTheDocument();
    expect(screen.getByText("Documentos RAG")).toBeInTheDocument();
    expect(screen.getByText("Colecciones")).toBeInTheDocument();
    expect(screen.getByText("Servidores MCP")).toBeInTheDocument();
    expect(screen.getByText("Nuevo MCP")).toBeInTheDocument();
    expect(screen.getByText("Agentes")).toBeInTheDocument();
    expect(screen.getByText("Auditoría")).toBeInTheDocument();
    expect(screen.getByText("Coste y latencias")).toBeInTheDocument();
  });
});
