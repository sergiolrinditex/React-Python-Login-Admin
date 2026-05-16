/**
 * Hilo People — RagDocumentsPage tap-target regression (cycle 2).
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Why this file exists (and not an extension of RagDocumentsPage.test.tsx):
 *   The page-level test file already exceeds the ~300-line hard cap declared in
 *   `.claude/rules/01-non-negotiables.md`, so per the rule "extend, do not create
 *   a new file unless that file is over the size cap" we split this regression
 *   into a focused companion file (§D-RAGDOC-PAGE-TESTS family).
 *
 * §D-T001-DEBUG-C2-TAP-TARGET — debugger cycle 2 regression test:
 *   `screen-journey-reviewer` measured the "Ver colecciones →" button at 36px
 *   tall in browser, violating UX_CONTRACT §7 and the task pack §Accessibility
 *   invariant "Tap targets ≥ 44×44 px". Root cause: COLLECTIONS_LINK_STYLE was
 *   `display:"inline-block"` + `padding:0` without a `minHeight` floor.
 *
 * Strategy:
 *   - jsdom does NOT compute layout (offsetHeight is always 0 in jsdom), so we
 *     cannot assert the rendered pixel height. We assert the contract at the
 *     declarative style layer: the element rendered for data-testid
 *     "nav-to-collections" must have an inline style with
 *     minHeight: "44px" and an inline-flex display so the floor actually applies.
 *   - We also assert directly against the exported COLLECTIONS_LINK_STYLE
 *     constant — this guards the contract even if the page stops applying the
 *     constant correctly.
 *
 * NOTE: presentation hooks and i18n setup are mocked exactly like the page-level
 *   test so the rendered tree is deterministic.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../../i18n/index";
import RagDocumentsPage from "../RagDocumentsPage";
import { COLLECTIONS_LINK_STYLE } from "../RagDocumentsPage.styles";
import type { RagCollection, ListDocumentsResponse } from "../../../../features/rag/domain/types";

// ---------------------------------------------------------------------------
// Mocks (mirror RagDocumentsPage.test.tsx so the page renders the success path)
// ---------------------------------------------------------------------------

vi.mock("../../../../features/auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(() => ({
    status: "authenticated",
    user: {
      id: "admin-001",
      email: "admin@test.com",
      full_name: "Admin User",
      roles: ["people_admin"],
      preferred_language: "es",
    },
    logout: vi.fn(),
    signInAccepted: vi.fn(),
  })),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

vi.mock("../../../../features/rag/presentation/useRagDocuments", () => ({
  useRagDocuments: vi.fn(),
}));

vi.mock("../../../../features/rag/presentation/useRagCollections", () => ({
  useRagCollections: vi.fn(),
}));

vi.mock("../../../../features/rag/presentation/useUploadDocument", () => ({
  useUploadDocument: vi.fn(),
}));

vi.mock("../../../../features/rag/presentation/useIndexDocument", () => ({
  useIndexDocument: vi.fn(),
}));

import { useRagDocuments } from "../../../../features/rag/presentation/useRagDocuments";
import { useRagCollections } from "../../../../features/rag/presentation/useRagCollections";
import { useUploadDocument } from "../../../../features/rag/presentation/useUploadDocument";
import { useIndexDocument } from "../../../../features/rag/presentation/useIndexDocument";

const mockUseRagDocuments = vi.mocked(useRagDocuments);
const mockUseRagCollections = vi.mocked(useRagCollections);
const mockUseUploadDocument = vi.mocked(useUploadDocument);
const mockUseIndexDocument = vi.mocked(useIndexDocument);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_COLLECTION: RagCollection = {
  id: "coll-001",
  name: "Políticas Tienda",
  vertical: "retail",
  language: "es",
  enabled: true,
};

const EMPTY_DOCS_RESPONSE: ListDocumentsResponse = {
  data: [],
  meta: { pagination: { cursor: null, limit: 50 }, request_id: "req-tap" },
};

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <MemoryRouter initialEntries={["/admin/rag/documents"]}>
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={i18n}>
          <RagDocumentsPage />
        </I18nextProvider>
      </QueryClientProvider>
    </MemoryRouter>,
  );
}

// ---------------------------------------------------------------------------
// Tests — §D-T001-DEBUG-C2-TAP-TARGET
// ---------------------------------------------------------------------------

describe("RagDocumentsPage — collections nav tap target (§D-T001-DEBUG-C2-TAP-TARGET)", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRagDocuments.mockReturnValue({
      data: EMPTY_DOCS_RESPONSE,
      isLoading: false,
      isError: false,
      isSuccess: true,
      error: null,
      refetch: vi.fn(),
      status: "success",
    } as unknown as ReturnType<typeof useRagDocuments>);
    mockUseRagCollections.mockReturnValue({
      data: [MOCK_COLLECTION],
      isLoading: false,
      isError: false,
      isSuccess: true,
      error: null,
      refetch: vi.fn(),
      status: "success",
    } as unknown as ReturnType<typeof useRagCollections>);
    mockUseUploadDocument.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      data: undefined,
      reset: vi.fn(),
      variables: undefined,
    } as unknown as ReturnType<typeof useUploadDocument>);
    mockUseIndexDocument.mockReturnValue({
      mutate: vi.fn(),
      mutateAsync: vi.fn(),
      isPending: false,
      isError: false,
      isSuccess: false,
      error: null,
      data: undefined,
      variables: undefined,
    } as unknown as ReturnType<typeof useIndexDocument>);
  });

  it("T-DBG2-TAP1 — COLLECTIONS_LINK_STYLE constant declares minHeight ≥ 44px", () => {
    // Guards the contract at the style source. UX_CONTRACT §7 / task pack §Accessibility.
    expect(COLLECTIONS_LINK_STYLE.minHeight).toBe("44px");
    // The minHeight floor only works when the box is flex/grid/block — `inline-block`
    // with padding:0 does NOT honor minHeight on every browser engine. We require an
    // inline-flex (or flex) display so the 44px floor actually applies and the content
    // stays vertically centered.
    expect(COLLECTIONS_LINK_STYLE.display).toMatch(/^inline-flex|flex$/);
    expect(COLLECTIONS_LINK_STYLE.alignItems).toBe("center");
  });

  it("T-DBG2-TAP2 — rendered nav-to-collections button carries the 44px floor inline", () => {
    renderPage();

    const btn = screen.getByTestId("nav-to-collections") as HTMLButtonElement;
    expect(btn).toBeInTheDocument();
    // React applies the style object as inline style. jsdom does not compute layout,
    // so we assert the declarative contract on the element directly.
    expect(btn.style.minHeight).toBe("44px");
    expect(btn.style.display).toMatch(/^inline-flex|flex$/);
    expect(btn.style.alignItems).toBe("center");
  });
});
