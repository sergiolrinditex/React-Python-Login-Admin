/**
 * Hilo People — AdminAiModelsPage component tests.
 *
 * Slice/Phase: P04-S01-T002 — AdminAiModelsPage / Phase 4.
 * Write-set anchor: §D-T002-TESTS
 *
 * Responsibility: Component tests covering all 5 required UX states + table + i18n.
 *   useAdminAiModels hook is mocked (hook boundary).
 *   useAuth is mocked to provide authenticated admin session.
 *   react-router useNavigate is mocked.
 *   i18n is real (inline resources from i18n/index.ts).
 *
 * Cases (P01..P08 per task pack §10.3):
 *   P01 — loading state: aria-busy skeleton visible.
 *   P02 — success: hairline table with joined rows + tracked-label headers.
 *   P03 — StatusDot active state: provider.status=active AND model.enabled=true.
 *   P04 — StatusDot inactive state: model.enabled=false (modelDisabled label).
 *   P05 — empty state: Wordmark + body + Create-model CTA when providers=[] OR models=[].
 *   P06 — error_network: NetworkErrorView visible + retry CTA calls refetch.
 *   P07 — permission_denied: ForbiddenView renders when error instanceof AdminAiForbiddenError.
 *   P08 — cost cell: em-dash when pricing={}, formatted currency when pricing.input_per_1k_tokens set.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import AdminAiModelsPage, { formatCost, formatLatency, deriveStatusDotState, deriveStatusLabelKey } from "../ai/AdminAiModelsPage";
import {
  AdminAiNetworkError,
  AdminAiForbiddenError,
  AdminAiInternalError,
} from "../../../features/admin-ai/data/errors";
import type { UseAdminAiModelsResult, AdminAiModelRow } from "../../../features/admin-ai/presentation/useAdminAiModels";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../features/admin-ai/presentation/useAdminAiModels", () => ({
  useAdminAiModels: vi.fn(),
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

import { useAdminAiModels } from "../../../features/admin-ai/presentation/useAdminAiModels";
import { useAuth } from "../../../features/auth/presentation/AuthProvider";

const mockUseAdminAiModels = vi.mocked(useAdminAiModels);
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

const MOCK_PROVIDER = {
  id: "prov-uuid-1",
  name: "litellm_verification_sandbox",
  provider_type: "litellm" as const,
  base_url: "http://localhost:4000",
  status: "active" as const,
  created_by: null,
  has_credentials: false,
  credential_auth_type: null,
  expires_at: null,
};

const MOCK_MODEL_ROW: AdminAiModelRow = {
  id: "model-uuid-1",
  model_id: "gpt-4o-mini",
  model_type: "chat",
  enabled: true,
  is_default: true,
  pricing: {},
  latency_ms_avg: null,
  provider_id: "prov-uuid-1",
  providerName: "litellm_verification_sandbox",
  providerStatus: "active",
};

const DEFAULT_HOOK_STATE: UseAdminAiModelsResult = {
  isLoading: false,
  isSuccess: true,
  isError: false,
  error: null,
  data: {
    providers: [MOCK_PROVIDER],
    models: [{
      id: MOCK_MODEL_ROW.id,
      provider_id: MOCK_MODEL_ROW.provider_id,
      model_id: MOCK_MODEL_ROW.model_id,
      model_type: MOCK_MODEL_ROW.model_type,
      capabilities: [],
      enabled: MOCK_MODEL_ROW.enabled,
      is_default: MOCK_MODEL_ROW.is_default,
      pricing: MOCK_MODEL_ROW.pricing,
      latency_ms_avg: MOCK_MODEL_ROW.latency_ms_avg,
    }],
    rows: [MOCK_MODEL_ROW],
  },
  refetch: vi.fn(),
};

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <MemoryRouter initialEntries={["/admin/ai/models"]}>
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          <AdminAiModelsPage />
        </I18nextProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

function setupMocks(hookOverrides: Partial<UseAdminAiModelsResult> = {}): void {
  mockUseAuth.mockReturnValue({
    status: "authenticated",
    user: MOCK_ADMIN_USER,
    signInAccepted: vi.fn(),
    logout: vi.fn().mockResolvedValue(undefined),
  });
  const mockRefetch = vi.fn();
  mockUseAdminAiModels.mockReturnValue({
    ...DEFAULT_HOOK_STATE,
    refetch: mockRefetch,
    ...hookOverrides,
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AdminAiModelsPage", () => {
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

    const loadingEl = screen.getByTestId("admin-ai-models-loading");
    expect(loadingEl).toBeInTheDocument();
    expect(loadingEl).toHaveAttribute("aria-busy", "true");
    expect(screen.queryByTestId("models-table-section")).not.toBeInTheDocument();
    expect(screen.queryByTestId("admin-ai-models-empty")).not.toBeInTheDocument();
  });

  it("P02 — success: hairline table with joined rows and tracked-label headers", () => {
    setupMocks();
    renderPage();

    expect(screen.getByTestId("models-table-section")).toBeInTheDocument();
    // Table should have column headers
    expect(screen.getByText("Modelo")).toBeInTheDocument();
    expect(screen.getByText("Tipo")).toBeInTheDocument();
    expect(screen.getByText("Proveedor")).toBeInTheDocument();
    expect(screen.getByText("Estado")).toBeInTheDocument();
    // Model row data (model_id from mock)
    expect(screen.getByText("gpt-4o-mini")).toBeInTheDocument();
  });

  it("P03 — StatusDot active when provider.status=active AND model.enabled=true", () => {
    setupMocks({
      data: {
        ...DEFAULT_HOOK_STATE.data!,
        rows: [{ ...MOCK_MODEL_ROW, providerStatus: "active", enabled: true }],
      },
    });
    renderPage();

    // The status dot should show "Activo" label (ES i18n)
    expect(screen.getByText("Activo")).toBeInTheDocument();
  });

  it("P04 — StatusDot inactive when model.enabled=false (modelDisabled label)", () => {
    setupMocks({
      data: {
        ...DEFAULT_HOOK_STATE.data!,
        rows: [{ ...MOCK_MODEL_ROW, providerStatus: "active", enabled: false }],
      },
    });
    renderPage();

    expect(screen.getByText("Modelo desactivado")).toBeInTheDocument();
  });

  it("P05 — empty state: Wordmark + body + Create-model CTA when providers=[]", () => {
    setupMocks({
      isLoading: false,
      isSuccess: true,
      data: { providers: [], models: [], rows: [] },
    });
    renderPage();

    expect(screen.getByTestId("admin-ai-models-empty")).toBeInTheDocument();
    expect(screen.getByTestId("models-empty-body")).toBeInTheDocument();
    expect(screen.getByTestId("models-empty-new-model-cta")).toBeInTheDocument();
    expect(screen.queryByTestId("models-table-section")).not.toBeInTheDocument();
  });

  it("P06 — error_network: NetworkErrorView visible + retry CTA calls refetch", () => {
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

    expect(screen.getByTestId("admin-ai-models-error-network")).toBeInTheDocument();
    expect(screen.getByTestId("models-error-network-title")).toHaveTextContent(
      "No se pudieron cargar los modelos",
    );
    const retryCta = screen.getByTestId("models-error-network-retry-cta");
    expect(retryCta).toBeInTheDocument();

    fireEvent.click(retryCta);
    expect(mockRefetch).toHaveBeenCalledTimes(1);
  });

  it("P07 — permission_denied: ForbiddenView renders when error instanceof AdminAiForbiddenError", () => {
    setupMocks({
      isLoading: false,
      isSuccess: false,
      isError: true,
      error: new AdminAiForbiddenError(),
      data: undefined,
    });
    renderPage();

    expect(screen.getByTestId("admin-ai-models-forbidden")).toBeInTheDocument();
    expect(screen.getByTestId("models-forbidden-title")).toHaveTextContent("Acceso restringido");
    expect(screen.queryByTestId("admin-ai-models-error-network")).not.toBeInTheDocument();
  });

  it("P08 — cost cell: em-dash when pricing={}, formatted currency when pricing.input_per_1k_tokens set", () => {
    const rowWithPricing: AdminAiModelRow = {
      ...MOCK_MODEL_ROW,
      pricing: { input_per_1k_tokens: 0.002, output_per_1k_tokens: 0.006 },
    };
    setupMocks({
      data: {
        ...DEFAULT_HOOK_STATE.data!,
        rows: [MOCK_MODEL_ROW, rowWithPricing],
      },
    });
    renderPage();

    const tableSection = screen.getByTestId("models-table-section");
    // em-dash for empty pricing
    const allCells = within(tableSection).getAllByText("—");
    expect(allCells.length).toBeGreaterThan(0);

    // Formatted cost cell present (contains currency symbol or EUR)
    const cells = within(tableSection).getAllByText(/€|EUR|\//);
    expect(cells.length).toBeGreaterThan(0);
  });
});

// ---------------------------------------------------------------------------
// Unit tests for pure formatters and derivations
// ---------------------------------------------------------------------------

describe("formatCost", () => {
  it("returns em-dash for empty pricing (ASSUMPTION-1)", () => {
    expect(formatCost({}, "es")).toBe("—");
  });

  it("formats input_per_1k_tokens + output_per_1k_tokens (LiteLLM canonical shape)", () => {
    const result = formatCost(
      { input_per_1k_tokens: 0.002, output_per_1k_tokens: 0.006 },
      "en",
    );
    expect(result).toContain("0.002");
    expect(result).toContain("0.006");
  });

  it("formats input + output (fallback shape)", () => {
    const result = formatCost({ input: 0.001, output: 0.003 }, "en");
    expect(result).toContain("0.001");
    expect(result).toContain("0.003");
  });

  it("returns em-dash for unknown pricing shape", () => {
    expect(formatCost({ unknownKey: 99 }, "en")).toBe("—");
  });
});

describe("formatLatency", () => {
  it("returns em-dash for null latency (R-4)", () => {
    expect(formatLatency(null, "es")).toBe("—");
  });

  it("formats integer ms with locale grouping", () => {
    const result = formatLatency(1234, "en");
    expect(result).toContain("ms");
    expect(result).toContain("1,234");
  });
});

describe("deriveStatusDotState", () => {
  it("active + enabled → active", () => {
    expect(deriveStatusDotState("active", true)).toBe("active");
  });

  it("active + disabled → inactive", () => {
    expect(deriveStatusDotState("active", false)).toBe("inactive");
  });

  it("draft + enabled → inactive", () => {
    expect(deriveStatusDotState("draft", true)).toBe("inactive");
  });

  it("unknown → error", () => {
    expect(deriveStatusDotState("unknown", true)).toBe("error");
    expect(deriveStatusDotState("unknown", false)).toBe("error");
  });
});

describe("deriveStatusLabelKey", () => {
  it("active + enabled → models.status.active", () => {
    expect(deriveStatusLabelKey("active", true)).toContain("status.active");
  });

  it("active + disabled → models.status.modelDisabled", () => {
    expect(deriveStatusLabelKey("active", false)).toContain("modelDisabled");
  });

  it("inactive + disabled → models.status.bothInactive", () => {
    expect(deriveStatusLabelKey("inactive", false)).toContain("bothInactive");
  });

  it("unknown → models.status.unknown", () => {
    expect(deriveStatusLabelKey("unknown", false)).toContain("unknown");
  });
});
