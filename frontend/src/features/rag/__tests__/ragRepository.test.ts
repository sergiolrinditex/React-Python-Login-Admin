/**
 * Hilo People — RAG repository unit tests.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Unit tests for RagRepository HTTP adapter.
 *   authFetch is mocked at the fetch boundary.
 *   Mirrors pattern from chatRepository.test.ts (P03-S02-T001).
 *
 * Cases:
 *   R01 — listDocuments 200 → Result.ok with data array.
 *   R02 — listDocuments 403 → Result.err(RagPermissionDeniedError).
 *   R03 — listDocuments network throw → Result.err(RagNetworkError).
 *   R04 — listDocuments includes collection_id query param.
 *   R05 — uploadDocument 201 → Result.ok {kind:'created', document}.
 *   R06 — uploadDocument 200 → Result.ok {kind:'dedup', document}.
 *   R07 — uploadDocument 413 → Result.err(RagDocumentTooLargeError).
 *   R08 — uploadDocument 422 with field → Result.err(RagDocumentInvalidError) with field.
 *   R09 — uploadDocument does NOT set Content-Type (FormData boundary rule).
 *   R10 — uploadDocument network throw → Result.err(RagNetworkError).
 *   R11 — indexDocument 202 → Result.ok {kind:'enqueued'}.
 *   R12 — indexDocument 409 → Result.err(RagIndexInProgressError) with job_id.
 *   R13 — indexDocument 404 → Result.err(RagDocumentNotFoundError).
 *   R14 — indexDocument 403 → Result.err(RagPermissionDeniedError).
 *   R15 — listCollections 200 → Result.ok array.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { RagRepository } from "../data/ragRepository";
import {
  RagPermissionDeniedError,
  RagNetworkError,
  RagDocumentTooLargeError,
  RagDocumentInvalidError,
  RagIndexInProgressError,
  RagDocumentNotFoundError,
} from "../data/errors";
import type { RagDocument, RagCollection } from "../domain/types";

// ---------------------------------------------------------------------------
// Mock authFetch
// ---------------------------------------------------------------------------

vi.mock("../../auth/data/httpClient", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../auth/data/httpClient";
const mockAuthFetch = vi.mocked(authFetch);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_DOCUMENT: RagDocument = {
  id: "doc-uuid-001",
  collection_id: "coll-uuid-001",
  title: "Política de Vacaciones",
  language: "es",
  source_uri: "s3://hilo-docs-dev/doc-uuid-001.pdf",
  status: "uploaded",
  uploaded_by: "user-uuid-001",
  created_at: "2026-05-16T10:00:00Z",
};

const MOCK_COLLECTION: RagCollection = {
  id: "coll-uuid-001",
  name: "Políticas Tienda",
  vertical: "retail",
  language: "es",
  enabled: true,
};

function makeResponse(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: new Headers({
      "content-type": "application/json",
      "x-request-id": "test-req-id",
      ...headers,
    }),
  });
}

// ---------------------------------------------------------------------------
// Test suite
// ---------------------------------------------------------------------------

describe("RagRepository", () => {
  const repo = new RagRepository();
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  // ---- listDocuments ----

  it("R01 — listDocuments 200 → Result.ok with data array", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: [MOCK_DOCUMENT],
        meta: { pagination: { cursor: null, limit: 50 }, request_id: "req1" },
      }),
    );

    const result = await repo.listDocuments({}, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.data).toHaveLength(1);
      expect(result.value.data[0].id).toBe(MOCK_DOCUMENT.id);
    }
  });

  it("R02 — listDocuments 403 → Result.err(RagPermissionDeniedError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN" }] }),
    );

    const result = await repo.listDocuments({}, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBeInstanceOf(RagPermissionDeniedError);
  });

  it("R03 — listDocuments network throw → Result.err(RagNetworkError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await repo.listDocuments({}, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBeInstanceOf(RagNetworkError);
  });

  it("R04 — listDocuments includes collection_id query param", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, {
        data: [],
        meta: { pagination: { cursor: null, limit: 50 }, request_id: "req2" },
      }),
    );

    await repo.listDocuments({ collection_id: "coll-uuid-001" }, onAuthFailure);

    const calledUrl = String(mockAuthFetch.mock.calls[0][0]);
    expect(calledUrl).toContain("collection_id=coll-uuid-001");
  });

  // ---- uploadDocument ----

  it("R05 — uploadDocument 201 → Result.ok {kind:'created'}", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(201, { data: MOCK_DOCUMENT }));

    const file = new File(["pdf bytes"], "policy.pdf", { type: "application/pdf" });
    const result = await repo.uploadDocument(
      { file, title: "Test", language: "es", collection_id: "coll-001" },
      { onAuthFailure },
    );

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.kind).toBe("created");
      expect(result.value.document.id).toBe(MOCK_DOCUMENT.id);
    }
  });

  it("R06 — uploadDocument 200 → Result.ok {kind:'dedup'}", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(200, { data: MOCK_DOCUMENT }));

    const file = new File(["pdf bytes"], "policy.pdf", { type: "application/pdf" });
    const result = await repo.uploadDocument(
      { file, title: "Test", language: "es", collection_id: "coll-001" },
      { onAuthFailure },
    );

    expect(result.ok).toBe(true);
    if (result.ok) expect(result.value.kind).toBe("dedup");
  });

  it("R07 — uploadDocument 413 → Result.err(RagDocumentTooLargeError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(413, { errors: [{ code: "RAG_DOCUMENT_TOO_LARGE" }] }),
    );

    const file = new File(["data"], "big.pdf", { type: "application/pdf" });
    const result = await repo.uploadDocument(
      { file, title: "Big file", language: "es", collection_id: "coll-001" },
      { onAuthFailure },
    );

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBeInstanceOf(RagDocumentTooLargeError);
  });

  it("R08 — uploadDocument 422 with field → Result.err(RagDocumentInvalidError) with field", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(422, {
        errors: [{ code: "RAG_DOCUMENT_INVALID", field: "collection_id", message: "Required" }],
      }),
    );

    const file = new File(["data"], "policy.pdf", { type: "application/pdf" });
    const result = await repo.uploadDocument(
      { file, title: "Doc", language: "es", collection_id: "" },
      { onAuthFailure },
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(RagDocumentInvalidError);
      expect((result.error as RagDocumentInvalidError).field).toBe("collection_id");
    }
  });

  it("R09 — uploadDocument does NOT set Content-Type (FormData boundary rule)", async () => {
    mockAuthFetch.mockResolvedValueOnce(makeResponse(201, { data: MOCK_DOCUMENT }));

    const file = new File(["pdf bytes"], "policy.pdf", { type: "application/pdf" });
    await repo.uploadDocument(
      { file, title: "Test", language: "es", collection_id: "coll-001" },
      { onAuthFailure },
    );

    const initArg = mockAuthFetch.mock.calls[0][1] as RequestInit;
    // headers should be undefined or empty (NOT contain Content-Type)
    const headers = initArg.headers as Record<string, string> | undefined;
    if (headers) {
      expect(headers["Content-Type"]).toBeUndefined();
      expect(headers["content-type"]).toBeUndefined();
    }
    // body must be FormData
    expect(initArg.body).toBeInstanceOf(FormData);
  });

  it("R10 — uploadDocument network throw → Result.err(RagNetworkError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Network error"));

    const file = new File(["data"], "policy.pdf", { type: "application/pdf" });
    const result = await repo.uploadDocument(
      { file, title: "Test", language: "es", collection_id: "coll-001" },
      { onAuthFailure },
    );

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBeInstanceOf(RagNetworkError);
  });

  // ---- indexDocument ----

  it("R11 — indexDocument 202 → Result.ok {kind:'enqueued'}", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(202, { data: { job_id: "job-001", status: "pending" } }),
    );

    const result = await repo.indexDocument("doc-uuid-001", { onAuthFailure });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.kind).toBe("enqueued");
      expect(result.value.job_id).toBe("job-001");
    }
  });

  it("R12 — indexDocument 409 → Result.err(RagIndexInProgressError) with job_id", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(409, {
        errors: [{ code: "RAG_INDEX_IN_PROGRESS" }],
        data: { job_id: "job-existing", status: "processing" },
      }),
    );

    const result = await repo.indexDocument("doc-uuid-001", { onAuthFailure });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(RagIndexInProgressError);
      expect((result.error as RagIndexInProgressError).job_id).toBe("job-existing");
    }
  });

  it("R13 — indexDocument 404 → Result.err(RagDocumentNotFoundError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(404, { errors: [{ code: "RAG_DOCUMENT_INVALID", field: "id" }] }),
    );

    const result = await repo.indexDocument("nonexistent-id", { onAuthFailure });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBeInstanceOf(RagDocumentNotFoundError);
  });

  it("R14 — indexDocument 403 → Result.err(RagPermissionDeniedError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN" }] }),
    );

    const result = await repo.indexDocument("doc-uuid-001", { onAuthFailure });

    expect(result.ok).toBe(false);
    if (!result.ok) expect(result.error).toBeInstanceOf(RagPermissionDeniedError);
  });

  // ---- listCollections ----

  it("R15 — listCollections 200 → Result.ok array", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: [MOCK_COLLECTION] }),
    );

    const result = await repo.listCollections({ onAuthFailure });

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value).toHaveLength(1);
      expect(result.value[0].id).toBe(MOCK_COLLECTION.id);
    }
  });
});
