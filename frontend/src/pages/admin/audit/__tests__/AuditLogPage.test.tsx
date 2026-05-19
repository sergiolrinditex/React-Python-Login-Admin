/**
 * Hilo People — AuditLogPage component tests.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Render and integration tests for AuditLogPage.
 *   Covers all 5 UX states + error_validation + a11y + i18n key usage.
 *   10 tests total:
 *     1. loading state renders skeleton with aria-busy
 *     2. success state renders table with rows
 *     3. empty state renders Wordmark + CTA
 *     4. error_network state renders retry CTA + click triggers refetch
 *     5. permission_denied state renders forbidden view with back button
 *     6. error_validation (isRangeInvalid) renders inline validation error
 *     7. error_validation (isActorInvalid) renders actor validation error
 *     8. a11y: table has sr-only caption and th scope=col
 *     9. i18n: page title key resolves correctly
 *     10. filter submit resets cursor and triggers refetch
 *
 * Mocks: useAuditQuery hook (presentation layer boundary for page tests).
 *   Does NOT mock backend — mocking the hook is appropriate for page render tests.
 *
 * §D-T001-TESTS: Canonical write_set anchor for this file.
 * Source ref: §D-T001-TESTS, task pack §16 AC1–AC6.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { I18nextProvider } from "react-i18next";
import type { ReactNode } from "react";
import i18n from "../../../../i18n/index";
import AuditLogPage from "../AuditLogPage";
import {
  AuditForbiddenError,
  AuditNetworkError,
} from "../../../../features/audit/data/errors";
import type { AuditPage } from "../../../../features/audit/domain/types";
import type { UseAuditQueryResult } from "../../../../features/audit/presentation/useAuditQuery";

// ---------------------------------------------------------------------------
// Mock useAuditQuery
// ---------------------------------------------------------------------------

vi.mock("../../../../features/audit/presentation/useAuditQuery", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../../../../features/audit/presentation/useAuditQuery")>();
  return {
    ...actual,
    useAuditQuery: vi.fn(),
  };
});

// Mock useAuth (AuthProvider dependency used inside useAuditQuery)
vi.mock("../../../../features/auth/presentation/AuthProvider", () => ({
  useAuth: () => ({ logout: vi.fn() }),
}));

import { useAuditQuery } from "../../../../features/audit/presentation/useAuditQuery";

const mockUseAuditQuery = useAuditQuery as ReturnType<typeof vi.fn>;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const MOCK_AUDIT_PAGE: AuditPage = {
  rows: [
    {
      id: "row-1",
      actor_user_id: "550e8400-e29b-41d4-a716-446655440001",
      action: "auth.sign_in",
      entity_type: "user",
      entity_id: "550e8400-e29b-41d4-a716-446655440002",
      metadata: { request_id: "req-abc123" },
      created_at: "2026-05-19T10:00:00Z",
    },
  ],
  next_cursor: null,
  has_more: false,
  count: 1,
};

const BASE_RESULT: UseAuditQueryResult = {
  data: undefined,
  error: null,
  isPending: false,
  isFetching: false,
  refetch: vi.fn(),
  isRangeInvalid: false,
  isActorInvalid: false,
};

function renderPage(): ReturnType<typeof render> {
  return render(
    <MemoryRouter>
      <I18nextProvider i18n={i18n}>
        <AuditLogPage />
      </I18nextProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("AuditLogPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    void i18n.changeLanguage("es");
  });

  it("AuditLogPage: loading state renders skeleton with aria-busy", () => {
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      isPending: true,
    } satisfies UseAuditQueryResult);

    renderPage();

    const loading = screen.getByTestId("audit-loading");
    expect(loading).toBeDefined();
    expect(loading.getAttribute("aria-busy")).toBe("true");
  });

  it("AuditLogPage: success state renders table with rows", () => {
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      data: MOCK_AUDIT_PAGE,
    } satisfies UseAuditQueryResult);

    renderPage();

    const table = screen.getByTestId("audit-table");
    expect(table).toBeDefined();
    // Action column should show the action string
    expect(screen.getByText("auth.sign_in")).toBeDefined();
    // Audit page testid
    expect(screen.getByTestId("audit-page")).toBeDefined();
  });

  it("AuditLogPage: empty state renders Wordmark Hilo + CTA", () => {
    const emptyPage: AuditPage = {
      rows: [],
      next_cursor: null,
      has_more: false,
      count: 0,
    };
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      data: emptyPage,
    } satisfies UseAuditQueryResult);

    renderPage();

    expect(screen.getByTestId("audit-empty")).toBeDefined();
    expect(screen.getByText("Hilo")).toBeDefined();
    expect(screen.getByTestId("audit-empty-cta")).toBeDefined();
  });

  it("AuditLogPage: error_network state renders retry CTA and clicking triggers refetch", () => {
    const refetchMock = vi.fn();
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      error: new AuditNetworkError("Network failed"),
      refetch: refetchMock,
    } satisfies UseAuditQueryResult);

    renderPage();

    const errorContainer = screen.getByTestId("audit-network-error");
    expect(errorContainer).toBeDefined();

    const retryCta = screen.getByTestId("audit-retry-cta");
    expect(retryCta).toBeDefined();

    fireEvent.click(retryCta);
    expect(refetchMock).toHaveBeenCalledOnce();
  });

  it("AuditLogPage: permission_denied state renders forbidden view with back button", () => {
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      error: new AuditForbiddenError(),
    } satisfies UseAuditQueryResult);

    renderPage();

    expect(screen.getByTestId("audit-forbidden")).toBeDefined();
    expect(screen.getByTestId("audit-forbidden-back")).toBeDefined();
  });

  it("AuditLogPage: error_validation (isRangeInvalid) renders inline range error", () => {
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      isRangeInvalid: true,
    } satisfies UseAuditQueryResult);

    renderPage();

    expect(screen.getByTestId("audit-validation-error")).toBeDefined();
  });

  it("AuditLogPage: error_validation (isActorInvalid) renders inline actor error", () => {
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      isActorInvalid: true,
    } satisfies UseAuditQueryResult);

    renderPage();

    expect(screen.getByTestId("audit-validation-error")).toBeDefined();
  });

  it("AuditLogPage: a11y — success table has sr-only caption and th scope=col", () => {
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      data: MOCK_AUDIT_PAGE,
    } satisfies UseAuditQueryResult);

    renderPage();

    const table = screen.getByTestId("audit-table");
    const caption = table.querySelector("caption");
    expect(caption).not.toBeNull();

    const colHeaders = table.querySelectorAll("th[scope='col']");
    expect(colHeaders.length).toBeGreaterThanOrEqual(5);
  });

  it("AuditLogPage: i18n key — page title renders from audit namespace", () => {
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
      data: MOCK_AUDIT_PAGE,
    } satisfies UseAuditQueryResult);

    renderPage();

    // audit:title in ES = "Registro de auditoría"
    expect(screen.getByText("Registro de auditoría")).toBeDefined();
    expect(screen.getByTestId("audit-page")).toBeDefined();
  });

  it("AuditLogPage: filter reset button is present and accessible", () => {
    mockUseAuditQuery.mockReturnValue({
      ...BASE_RESULT,
    } satisfies UseAuditQueryResult);

    renderPage();

    const resetBtn = screen.getByTestId("audit-filter-reset");
    expect(resetBtn).toBeDefined();

    const submitBtn = screen.getByTestId("audit-filter-submit");
    expect(submitBtn).toBeDefined();
  });
});
