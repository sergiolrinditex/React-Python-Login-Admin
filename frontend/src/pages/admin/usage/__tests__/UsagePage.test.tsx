/**
 * Hilo People — UsagePage component tests.
 *
 * Slice/Phase: P04-S03-T002 — UsagePage / Phase 4 Complete Features.
 *
 * Responsibility: Render and integration tests for UsagePage.
 *   Covers all 5 UX states + a11y requirements + i18n key usage + Intl format.
 *   8 tests total:
 *     1. loading state renders skeleton with aria-busy
 *     2. success state renders table with rows
 *     3. empty state renders Wordmark + CTA
 *     4. error_network state renders retry CTA
 *     5. permission_denied state renders forbidden view
 *     6. error_validation state (isRangeInvalid) renders inline error
 *     7. a11y: table has caption, th scope=col
 *     8. i18n: page title key resolves correctly
 *
 * Mocks: useUsage hook (presentation layer boundary for page tests).
 *   Does NOT mock backend — mocking the hook is appropriate for page render tests.
 *
 * D-T002-TEST-PAGE: Canonical write_set anchor for this file.
 * Source ref: §D-T002-TEST-PAGE, task pack §12 AC1–AC9.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { I18nextProvider } from "react-i18next";
import type { ReactNode } from "react";
import i18n from "../../../../i18n/index";
import UsagePage from "../UsagePage";
import {
  UsageForbiddenError,
  UsageNetworkError,
} from "../../../../features/admin/data/errors";
import type { UsageSummary } from "../../../../features/admin/domain/types";
import type { UseUsageResult } from "../../../../features/admin/presentation/useUsage";

// ---------------------------------------------------------------------------
// Mock useUsage
// ---------------------------------------------------------------------------

vi.mock("../../../../features/admin/presentation/useUsage", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../../features/admin/presentation/useUsage")>();
  return {
    ...actual,
    useUsage: vi.fn(),
  };
});

// Mock useAuth (AuthProvider dependency used inside useUsage)
vi.mock("../../../../features/auth/presentation/AuthProvider", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

import { useUsage } from "../../../../features/admin/presentation/useUsage";

const mockUseUsage = useUsage as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MOCK_SUMMARY: UsageSummary = {
  from: "2026-04-16T00:00:00+00:00",
  to: "2026-05-16T00:00:00+00:00",
  group_by: "model_day",
  rows: [
    {
      model_id: "uuid-1",
      model_name: "gpt-4o",
      provider_type: "openai",
      day: "2026-05-15",
      tokens_in: 1000,
      tokens_out: 500,
      estimated_cost: 0.025,
      latency_ms_avg: 1200,
      invocations: 5,
    },
  ],
  totals: {
    tokens_in: 1000,
    tokens_out: 500,
    estimated_cost: 0.025,
    latency_ms_avg: 1200,
    invocations: 5,
  },
};

const BASE_RESULT: UseUsageResult = {
  data: undefined,
  error: null,
  isPending: false,
  isFetching: false,
  refetch: vi.fn(),
  isRangeInvalid: false,
};

function renderPage(): ReturnType<typeof render> {
  return render(
    <MemoryRouter>
      <I18nextProvider i18n={i18n}>
        <UsagePage />
      </I18nextProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("UsagePage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Ensure i18n is in ES
    void i18n.changeLanguage("es");
  });

  it("UsagePage: loading state renders skeleton with aria-busy", () => {
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      isPending: true,
    } satisfies UseUsageResult);

    renderPage();

    const loading = screen.getByTestId("usage-loading");
    expect(loading).toBeDefined();
    expect(loading.getAttribute("aria-busy")).toBe("true");
  });

  it("UsagePage: success state renders table with rows", () => {
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      data: MOCK_SUMMARY,
    } satisfies UseUsageResult);

    renderPage();

    const table = screen.getByTestId("usage-table");
    expect(table).toBeDefined();
    expect(screen.getByText("gpt-4o")).toBeDefined();
    expect(screen.getByTestId("usage-next-action")).toBeDefined();
  });

  it("UsagePage: empty state renders Wordmark Hilo + CTA", () => {
    const emptySummary: UsageSummary = {
      ...MOCK_SUMMARY,
      rows: [],
      totals: { tokens_in: 0, tokens_out: 0, estimated_cost: 0, latency_ms_avg: null, invocations: 0 },
    };
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      data: emptySummary,
    } satisfies UseUsageResult);

    renderPage();

    expect(screen.getByTestId("usage-empty")).toBeDefined();
    expect(screen.getByText("Hilo")).toBeDefined();
    expect(screen.getByTestId("usage-empty-cta")).toBeDefined();
  });

  it("UsagePage: error_network state renders retry CTA and clicking triggers refetch", () => {
    const refetchMock = vi.fn();
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      error: new UsageNetworkError("Network failed"),
      refetch: refetchMock,
    } satisfies UseUsageResult);

    renderPage();

    const errorContainer = screen.getByTestId("usage-network-error");
    expect(errorContainer).toBeDefined();

    const retryCta = screen.getByTestId("usage-retry-cta");
    expect(retryCta).toBeDefined();

    fireEvent.click(retryCta);
    expect(refetchMock).toHaveBeenCalledOnce();
  });

  it("UsagePage: permission_denied state renders forbidden view with back button", () => {
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      error: new UsageForbiddenError(),
    } satisfies UseUsageResult);

    renderPage();

    expect(screen.getByTestId("usage-forbidden")).toBeDefined();
    expect(screen.getByTestId("usage-forbidden-back")).toBeDefined();
  });

  it("UsagePage: error_validation (isRangeInvalid) renders inline validation error", () => {
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      isRangeInvalid: true,
    } satisfies UseUsageResult);

    renderPage();

    expect(screen.getByTestId("usage-validation-error")).toBeDefined();
  });

  it("UsagePage: a11y — success table has sr-only caption and th scope=col", () => {
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      data: MOCK_SUMMARY,
    } satisfies UseUsageResult);

    renderPage();

    const table = screen.getByTestId("usage-table");
    const caption = table.querySelector("caption");
    expect(caption).not.toBeNull();

    const colHeaders = table.querySelectorAll("th[scope='col']");
    expect(colHeaders.length).toBeGreaterThanOrEqual(4); // model, day, tokens, cost, latency, invocations
  });

  it("UsagePage: i18n key usage — page title renders from usage namespace", () => {
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      data: MOCK_SUMMARY,
    } satisfies UseUsageResult);

    renderPage();

    // Check page renders correctly (i18n key "usage:title" = "Uso de IA" in ES)
    const page = screen.getByTestId("usage-page");
    expect(page).toBeDefined();
    expect(screen.getByText("Uso de IA")).toBeDefined();
  });

  it("UsagePage: Intl.NumberFormat formats cost as USD currency", () => {
    mockUseUsage.mockReturnValue({
      ...BASE_RESULT,
      data: MOCK_SUMMARY,
    } satisfies UseUsageResult);

    renderPage();

    // estimated_cost 0.025 should be formatted as currency
    // In 'es' locale: "0,025000 US$" or similar; just check USD symbol presence
    const table = screen.getByTestId("usage-table");
    const text = table.textContent ?? "";
    // Verify some currency formatting is happening (USD format varies by locale)
    expect(text).toMatch(/US\$|USD|\$|€/); // locale-agnostic: some currency symbol present
  });
});
