/**
 * Hilo People — updateCollection HTTP adapter unit tests.
 *
 * Slice/Phase: P04-S02-T002 — RagCollectionsPage / Phase 4 Complete Features.
 *
 * Responsibility: Unit tests for updateCollectionHttp adapter.
 *   authFetch is mocked at the fetch boundary.
 *   Mirrors ragRepository.test.ts pattern (P04-S02-T001).
 *
 * Cases:
 *   U01 — PATCH 200 → Result.ok {kind:"updated", collection}.
 *   U02 — PATCH 400 with field=name → RagDocumentInvalidError with .field === "name".
 *   U03 — PATCH 400 RAG_INVALID_PAYLOAD body (empty patch) → RagDocumentInvalidError field undefined.
 *   U04 — PATCH 401 → authFetch onAuthFailure invoked; repo returns RagNetworkError.
 *   U05 — PATCH 403 → RagPermissionDeniedError.
 *   U06 — PATCH 404 → RagDocumentNotFoundError.
 *   U07 — PATCH network reject → RagNetworkError.
 *   U08 — PATCH sets Content-Type: application/json (JSON body, NOT FormData).
 *
 * §D-T002-TEST-REPO: new test file for updateCollection adapter.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { RagRepository } from "../data/ragRepository";
import {
  RagPermissionDeniedError,
  RagNetworkError,
  RagDocumentInvalidError,
  RagDocumentNotFoundError,
} from "../data/errors";
import type { RagCollection, UpdateCollectionRequest } from "../domain/types";

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
    headers: {
      "Content-Type": "application/json",
      "x-request-id": "req-001",
      ...headers,
    },
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("RagRepository.updateCollection", () => {
  let repo: RagRepository;
  const mockLogout = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    repo = new RagRepository();
  });

  it("U01 — PATCH 200 → Result.ok {kind: 'updated', collection}", async () => {
    const req: UpdateCollectionRequest = {
      id: MOCK_COLLECTION.id,
      patch: { enabled: false },
    };
    const updated = { ...MOCK_COLLECTION, enabled: false };

    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: updated, meta: { request_id: "req-u01" } }),
    );

    const result = await repo.updateCollection(req, mockLogout);

    expect(result.ok).toBe(true);
    if (!result.ok) return;
    expect(result.value.kind).toBe("updated");
    expect(result.value.collection.enabled).toBe(false);
    expect(result.value.collection.id).toBe(MOCK_COLLECTION.id);
  });

  it("U02 — PATCH 400 with field=name → RagDocumentInvalidError with .field === 'name'", async () => {
    const req: UpdateCollectionRequest = {
      id: MOCK_COLLECTION.id,
      patch: { name: "" },
    };

    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(400, {
        errors: [{ code: "RAG_INVALID_PAYLOAD", field: "name", message: "Name is required." }],
      }),
    );

    const result = await repo.updateCollection(req, mockLogout);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toBeInstanceOf(RagDocumentInvalidError);
    expect((result.error as RagDocumentInvalidError).field).toBe("name");
  });

  it("U03 — PATCH 400 empty body → RagDocumentInvalidError field undefined/body", async () => {
    const req: UpdateCollectionRequest = {
      id: MOCK_COLLECTION.id,
      patch: {},
    };

    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(400, {
        errors: [{ code: "RAG_INVALID_PAYLOAD", message: "At least one field required." }],
      }),
    );

    const result = await repo.updateCollection(req, mockLogout);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toBeInstanceOf(RagDocumentInvalidError);
    // field is undefined when not provided by server
    expect((result.error as RagDocumentInvalidError).field).toBeUndefined();
  });

  it("U04 — PATCH 401 → onAuthFailure invoked", async () => {
    const req: UpdateCollectionRequest = {
      id: MOCK_COLLECTION.id,
      patch: { enabled: true },
    };

    // authFetch calls onAuthFailure and throws a network-like error
    mockAuthFetch.mockImplementationOnce(async (_url, _opts, authOpts) => {
      authOpts?.onAuthFailure?.();
      throw new TypeError("Unauthorized");
    });

    const result = await repo.updateCollection(req, mockLogout);

    expect(mockLogout).toHaveBeenCalled();
    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toBeInstanceOf(RagNetworkError);
  });

  it("U05 — PATCH 403 → RagPermissionDeniedError", async () => {
    const req: UpdateCollectionRequest = {
      id: MOCK_COLLECTION.id,
      patch: { enabled: false },
    };

    mockAuthFetch.mockResolvedValueOnce(makeResponse(403, { error: "Forbidden" }));

    const result = await repo.updateCollection(req, mockLogout);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toBeInstanceOf(RagPermissionDeniedError);
  });

  it("U06 — PATCH 404 → RagDocumentNotFoundError", async () => {
    const req: UpdateCollectionRequest = {
      id: "00000000-0000-0000-0000-000000000000",
      patch: { enabled: true },
    };

    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(404, {
        errors: [{ code: "RAG_COLLECTION_NOT_FOUND" }],
      }),
    );

    const result = await repo.updateCollection(req, mockLogout);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toBeInstanceOf(RagDocumentNotFoundError);
  });

  it("U07 — PATCH network reject → RagNetworkError", async () => {
    const req: UpdateCollectionRequest = {
      id: MOCK_COLLECTION.id,
      patch: { vertical: "hr_policies" },
    };

    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await repo.updateCollection(req, mockLogout);

    expect(result.ok).toBe(false);
    if (result.ok) return;
    expect(result.error).toBeInstanceOf(RagNetworkError);
  });

  it("U08 — PATCH sets Content-Type: application/json (JSON body, NOT FormData)", async () => {
    const req: UpdateCollectionRequest = {
      id: MOCK_COLLECTION.id,
      patch: { enabled: false },
    };
    const updated = { ...MOCK_COLLECTION, enabled: false };

    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, { data: updated, meta: { request_id: "req-u08" } }),
    );

    await repo.updateCollection(req, mockLogout);

    const [_url, fetchOpts] = mockAuthFetch.mock.calls[0];
    const headers = fetchOpts?.headers as Record<string, string> | undefined;
    expect(headers?.["Content-Type"]).toBe("application/json");
    expect(fetchOpts?.method).toBe("PATCH");
  });
});
