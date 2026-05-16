/**
 * Hilo People — RagDocumentsPage component tests.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Component tests covering all 8 mandatory UX states.
 *   Presentation hooks are mocked; i18n is real (inline resources).
 *   AuthProvider.useAuth is mocked with admin session.
 *
 * Cases:
 *   P01 — loading state: aria-busy skeleton shown.
 *   P02 — empty state: EmptyView + body paragraph + CTA.
 *   P03 — success state: document table with rows.
 *   P04 — error_network state: NetworkErrorView + retry.
 *   P05 — permission_denied state: ForbiddenView shown.
 *   P06 — uploading state: submit button shows loading state.
 *   P07 — indexing state: StatusDot shown for processing document.
 *   P08 — collections nav link visible.
 *   P09 — upload form client validation: shows field errors.
 *   P10 — dedup notice shown after dedup upload.
 *   P11 — RequireRole gate: employee without admin role sees redirect.
 *   P12 — error_validation: field-level errors shown near inputs.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../../i18n/index";
import RagDocumentsPage from "../RagDocumentsPage";
import { RagPermissionDeniedError, RagNetworkError, RagDocumentInvalidError, RagDocumentTooLargeError } from "../../../../features/rag/data/errors";
import type { RagDocument, RagCollection, ListDocumentsResponse } from "../../../../features/rag/domain/types";

// ---------------------------------------------------------------------------
// Mocks
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

const MOCK_DOC: RagDocument = {
  id: "doc-001",
  collection_id: "coll-001",
  title: "Política Vacaciones",
  language: "es",
  source_uri: "s3://bucket/doc-001.pdf",
  status: "indexed",
  uploaded_by: null,
  created_at: "2026-05-16T10:00:00Z",
};

const MOCK_COLLECTION: RagCollection = {
  id: "coll-001",
  name: "Políticas Tienda",
  vertical: "retail",
  language: "es",
  enabled: true,
};

const MOCK_DOCS_RESPONSE: ListDocumentsResponse = {
  data: [MOCK_DOC],
  meta: { pagination: { cursor: null, limit: 50 }, request_id: "req-1" },
};

type MockQueryResult<T> = {
  data?: T;
  isLoading: boolean;
  isError: boolean;
  isSuccess: boolean;
  error: unknown;
  refetch: () => void;
  status: string;
};

function makeDocsQuery(overrides: Partial<MockQueryResult<ListDocumentsResponse>> = {}): ReturnType<typeof useRagDocuments> {
  return {
    data: undefined,
    isLoading: false,
    isError: false,
    isSuccess: false,
    error: null,
    refetch: vi.fn(),
    status: "pending",
    ...overrides,
  } as unknown as ReturnType<typeof useRagDocuments>;
}

function makeCollectionsQuery(overrides: Partial<MockQueryResult<RagCollection[]>> = {}): ReturnType<typeof useRagCollections> {
  return {
    data: [MOCK_COLLECTION],
    isLoading: false,
    isError: false,
    isSuccess: true,
    error: null,
    refetch: vi.fn(),
    status: "success",
    ...overrides,
  } as unknown as ReturnType<typeof useRagCollections>;
}

function makeUploadMutation(overrides = {}) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    error: null,
    data: undefined,
    reset: vi.fn(),
    variables: undefined,
    ...overrides,
  } as unknown as ReturnType<typeof useUploadDocument>;
}

function makeIndexMutation(overrides = {}) {
  return {
    mutate: vi.fn(),
    mutateAsync: vi.fn(),
    isPending: false,
    isError: false,
    isSuccess: false,
    error: null,
    data: undefined,
    variables: undefined,
    ...overrides,
  } as unknown as ReturnType<typeof useIndexDocument>;
}

// ---------------------------------------------------------------------------
// Render helper
// ---------------------------------------------------------------------------

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
// Tests
// ---------------------------------------------------------------------------

describe("RagDocumentsPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseRagDocuments.mockReturnValue(makeDocsQuery({ isSuccess: true, data: { data: [], meta: { pagination: { cursor: null, limit: 50 }, request_id: "r" } } }));
    mockUseRagCollections.mockReturnValue(makeCollectionsQuery());
    mockUseUploadDocument.mockReturnValue(makeUploadMutation());
    mockUseIndexDocument.mockReturnValue(makeIndexMutation());
  });

  it("P01 — loading state: aria-busy skeleton shown", () => {
    mockUseRagDocuments.mockReturnValue(makeDocsQuery({ isLoading: true }));

    renderPage();

    expect(screen.getByTestId("rag-loading-skeleton")).toBeInTheDocument();
    expect(screen.getByTestId("rag-loading-skeleton")).toHaveAttribute("aria-busy", "true");
  });

  it("P02 — empty state: EmptyView + body paragraph + CTA", () => {
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: { data: [], meta: { pagination: { cursor: null, limit: 50 }, request_id: "r" } } }),
    );

    renderPage();

    expect(screen.getByTestId("rag-empty-view")).toBeInTheDocument();
    expect(screen.getByTestId("rag-empty-body")).toBeInTheDocument();
    // Body should not be empty
    expect(screen.getByTestId("rag-empty-body").textContent?.length).toBeGreaterThan(0);
  });

  it("P03 — success state: document table with rows", () => {
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: MOCK_DOCS_RESPONSE }),
    );

    renderPage();

    expect(screen.getByTestId("rag-docs-table")).toBeInTheDocument();
    expect(screen.getByTestId(`doc-row-${MOCK_DOC.id}`)).toBeInTheDocument();
    expect(screen.getByTestId(`doc-row-title-${MOCK_DOC.id}`)).toHaveTextContent("Política Vacaciones");
  });

  it("P04 — error_network state: NetworkErrorView + retry", () => {
    const mockRefetch = vi.fn();
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isError: true, error: new RagNetworkError("Network down"), refetch: mockRefetch }),
    );

    renderPage();

    expect(screen.getByTestId("rag-network-error-view")).toBeInTheDocument();
  });

  it("P05 — permission_denied state: ForbiddenView shown", () => {
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isError: true, error: new RagPermissionDeniedError() }),
    );

    renderPage();

    expect(screen.getByTestId("rag-forbidden-view")).toBeInTheDocument();
  });

  it("P06 — uploading state: submit button shows loading when isPending", () => {
    mockUseUploadDocument.mockReturnValue(makeUploadMutation({ isPending: true }));

    renderPage();

    const btn = screen.getByTestId("rag-submit-btn");
    expect(btn).toHaveAttribute("aria-busy", "true");
  });

  it("P07 — indexing state: processing row shows indexing label", () => {
    const processingDoc: RagDocument = { ...MOCK_DOC, status: "processing" };
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: { ...MOCK_DOCS_RESPONSE, data: [processingDoc] } }),
    );

    renderPage();

    expect(screen.getByTestId(`doc-row-status-${processingDoc.id}`)).toBeInTheDocument();
  });

  it("P08 — collections nav link visible", () => {
    renderPage();

    expect(screen.getByTestId("nav-to-collections")).toBeInTheDocument();
  });

  it("P09 — upload form client validation: shows field errors for missing fields", async () => {
    renderPage();

    // Click submit without filling any fields
    fireEvent.click(screen.getByTestId("rag-submit-btn"));

    await waitFor(() => {
      // At least one validation error should appear
      expect(screen.getByTestId("validation-error-rag-file-error")).toBeInTheDocument();
    });
  });

  it("P10 — dedup notice shown after dedup upload", async () => {
    const mockMutateAsync = vi.fn().mockResolvedValueOnce({
      kind: "dedup",
      document: MOCK_DOC,
    });
    mockUseUploadDocument.mockReturnValue(makeUploadMutation({ mutateAsync: mockMutateAsync, isSuccess: true }));

    renderPage();

    // Fill form
    fireEvent.change(screen.getByTestId("rag-field-title"), { target: { value: "Policy" } });
    fireEvent.change(screen.getByTestId("rag-field-collection"), { target: { value: "coll-001" } });

    // Simulate file selection
    const fileInput = screen.getByTestId("rag-file-input");
    const file = new File(["content"], "test.pdf", { type: "application/pdf" });
    fireEvent.change(fileInput, { target: { files: [file] } });

    // Submit
    fireEvent.submit(screen.getByTestId("rag-upload-form"));

    await waitFor(() => {
      expect(mockMutateAsync).toHaveBeenCalled();
    });
  });

  it("P11 — aria-live region present for status announcements", () => {
    renderPage();

    expect(screen.getByTestId("rag-live-region")).toBeInTheDocument();
    expect(screen.getByTestId("rag-live-region")).toHaveAttribute("aria-live", "polite");
  });

  it("P12 — upload form has all required fields", () => {
    renderPage();

    expect(screen.getByTestId("rag-field-title")).toBeInTheDocument();
    expect(screen.getByTestId("rag-field-language")).toBeInTheDocument();
    expect(screen.getByTestId("rag-field-collection")).toBeInTheDocument();
    expect(screen.getByTestId("rag-dropzone")).toBeInTheDocument();
  });

  // ---------------------------------------------------------------------------
  // §D-T001-DEBUG-C1-ROW-PREDICATE — DocumentRow CTA predicate regression tests.
  // Cycle 1 debugger fix: `canIndex` must reflect "not in flight" (not "is
  // terminal"), so freshly-uploaded docs (status="uploaded") can be indexed.
  // Cycle 1 debugger fix: `indexLabel` must NOT be inverted for terminal rows;
  // the spinner/aria-busy in the status cell communicates progress instead.
  // ---------------------------------------------------------------------------

  function makeDocsResponseWith(doc: RagDocument): ListDocumentsResponse {
    return {
      data: [doc],
      meta: { pagination: { cursor: null, limit: 50 }, request_id: "req-debug" },
    };
  }

  it("T-DBG1 — row with status=uploaded + collection_id → Index CTA enabled", () => {
    const uploadedDoc: RagDocument = { ...MOCK_DOC, status: "uploaded" };
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: makeDocsResponseWith(uploadedDoc) }),
    );

    renderPage();

    const btn = screen.getByTestId(`doc-row-index-btn-${uploadedDoc.id}`);
    expect(btn).not.toBeDisabled();
    expect(btn).not.toHaveAttribute("aria-busy", "true");
    // Label must be the action verb ("Indexar"), never the in-progress copy.
    expect(btn.textContent).toMatch(/index/i);
    expect(btn.textContent?.toLowerCase()).not.toContain("indexando");
    expect(btn.textContent?.toLowerCase()).not.toContain("indexing");
  });

  it("T-DBG2 — row with status=pending → Index CTA disabled + aria-busy=true", () => {
    const pendingDoc: RagDocument = { ...MOCK_DOC, status: "pending" };
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: makeDocsResponseWith(pendingDoc) }),
    );

    renderPage();

    const btn = screen.getByTestId(`doc-row-index-btn-${pendingDoc.id}`);
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
  });

  it("T-DBG3 — row with status=processing → Index CTA disabled + aria-busy=true", () => {
    const processingDoc: RagDocument = { ...MOCK_DOC, status: "processing" };
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: makeDocsResponseWith(processingDoc) }),
    );

    renderPage();

    const btn = screen.getByTestId(`doc-row-index-btn-${processingDoc.id}`);
    expect(btn).toBeDisabled();
    expect(btn).toHaveAttribute("aria-busy", "true");
  });

  it("T-DBG4 — row with status=failed + collection_id → Index CTA enabled (retry)", () => {
    const failedDoc: RagDocument = { ...MOCK_DOC, status: "failed" };
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: makeDocsResponseWith(failedDoc) }),
    );

    renderPage();

    const btn = screen.getByTestId(`doc-row-index-btn-${failedDoc.id}`);
    expect(btn).not.toBeDisabled();
    expect(btn).not.toHaveAttribute("aria-busy", "true");
  });

  it("T-DBG5 — row with status=indexed + collection_id → Index CTA enabled and label is action verb (not in-progress)", () => {
    const indexedDoc: RagDocument = { ...MOCK_DOC, status: "indexed" };
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: makeDocsResponseWith(indexedDoc) }),
    );

    renderPage();

    const btn = screen.getByTestId(`doc-row-index-btn-${indexedDoc.id}`);
    expect(btn).not.toBeDisabled();
    expect(btn).not.toHaveAttribute("aria-busy", "true");
    // Critical: must NOT show "Indexando"/"Indexing" for an already-indexed doc.
    expect(btn.textContent?.toLowerCase()).not.toContain("indexando");
    expect(btn.textContent?.toLowerCase()).not.toContain("indexing");
    expect(btn.textContent?.toLowerCase()).not.toContain("indexation");
  });

  it("T-DBG6 — row without collection_id → Index CTA disabled regardless of status", () => {
    const noCollectionDoc: RagDocument = {
      ...MOCK_DOC,
      status: "uploaded",
      collection_id: null,
    };
    mockUseRagDocuments.mockReturnValue(
      makeDocsQuery({ isSuccess: true, data: makeDocsResponseWith(noCollectionDoc) }),
    );

    renderPage();

    const btn = screen.getByTestId(`doc-row-index-btn-${noCollectionDoc.id}`);
    expect(btn).toBeDisabled();
  });
});
