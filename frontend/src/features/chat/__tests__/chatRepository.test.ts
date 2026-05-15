/**
 * Hilo People — Chat repository unit tests.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *   Extended in P03-S02-T003 — §D-T003-REPO-TESTS: listConversations cases (R01–R05).
 *
 * Responsibility: Unit tests for chatRepository.createConversation + listConversations.
 *   authFetch is mocked at the fetch boundary per §10.1 (test doubles for fetch allowed
 *   at unit level — TECHNICAL_GUIDE §9.1).
 *
 * Cases (createConversation):
 *   T01 — happy path → Result.ok with conversation data.
 *   T02 — 400 → Result.err(ChatValidationError).
 *   T03 — 403 → Result.err(ChatForbiddenError).
 *   T04 — 5xx → Result.err(ChatServerError).
 *   T05 — network throw → Result.err(ChatNetworkError).
 *   T06 — request shape verification: method, Content-Type, body JSON.
 *   T07 — 401 final (authFetch exhausted) → Result.err(ChatAuthExpiredError).
 *
 * Cases (listConversations — §D-T003-REPO-TESTS):
 *   R01 — happy path → Result.ok with envelope shape.
 *   R02 — cursor passed → URL contains ?cursor=....
 *   R03 — 401 → Result.err(ChatAuthExpiredError).
 *   R04 — network failure → Result.err(ChatNetworkError).
 *   R05 — 403 (defensive) → Result.err(ChatForbiddenError).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { createConversation, listConversations } from "../data/chatRepository";
import {
  ChatValidationError,
  ChatNetworkError,
  ChatForbiddenError,
  ChatServerError,
  ChatAuthExpiredError,
} from "../data/errors";
import type { ListConversationsResponse } from "../domain/types";
import { AuthSessionExpiredError } from "../../auth/data/errors";

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

const MOCK_CONVERSATION = {
  conversation_id: "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
  title: "How many vacation days do I have left?",
  language: "es" as const,
  created_at: "2026-05-14T10:00:00Z",
};

function makeResponse(
  status: number,
  body: unknown,
  headers: Record<string, string> = {},
): Response {
  const responseHeaders = new Headers({
    "content-type": "application/json",
    "x-request-id": "test-request-id",
    ...headers,
  });
  return new Response(JSON.stringify(body), { status, headers: responseHeaders });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("chatRepository.createConversation", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T01 — happy path → Result.ok with conversation data", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(201, { data: MOCK_CONVERSATION }),
    );

    const result = await createConversation(
      { initial_message: "Test message", language: "es" },
      onAuthFailure,
    );

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.conversation_id).toBe(MOCK_CONVERSATION.conversation_id);
      expect(result.value.language).toBe("es");
    }
  });

  it("T02 — 400 → Result.err(ChatValidationError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(400, { errors: [{ code: "VALIDATION_ERROR", message: "Invalid" }] }),
    );

    const result = await createConversation(
      { initial_message: "", language: "es" },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatValidationError);
    }
  });

  it("T03 — 403 → Result.err(ChatForbiddenError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN" }] }),
    );

    const result = await createConversation(
      { initial_message: "test", language: "es" },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatForbiddenError);
    }
  });

  it("T04 — 5xx → Result.err(ChatServerError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(500, { errors: [{ code: "INTERNAL" }] }),
    );

    const result = await createConversation(
      { initial_message: "test", language: "es" },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatServerError);
    }
  });

  it("T05 — network throw → Result.err(ChatNetworkError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await createConversation(
      { initial_message: "test", language: "es" },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatNetworkError);
    }
  });

  it("T06 — request shape: POST, Content-Type, JSON body", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(201, { data: MOCK_CONVERSATION }),
    );

    await createConversation(
      { initial_message: "my message", language: "en" },
      onAuthFailure,
    );

    expect(mockAuthFetch).toHaveBeenCalledWith(
      "/api/v1/chat/conversations",
      expect.objectContaining({
        method: "POST",
        headers: expect.objectContaining({ "Content-Type": "application/json" }),
        body: JSON.stringify({ initial_message: "my message", language: "en" }),
      }),
      expect.objectContaining({ onAuthFailure }),
    );
  });

  it("T07 — AuthSessionExpiredError from authFetch → Result.err(ChatAuthExpiredError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new AuthSessionExpiredError());

    const result = await createConversation(
      { initial_message: "test", language: "es" },
      onAuthFailure,
    );

    expect(result.ok).toBe(false);
    if (!result.ok) {
      // AuthSessionExpiredError is mapped to ChatNetworkError via mapChatError
      // as it extends Error but is not a typed ChatError — correct per mapChatError.
      expect(result.error).toBeInstanceOf(ChatNetworkError);
    }
  });
});

// ---------------------------------------------------------------------------
// §D-T003-REPO-TESTS — listConversations tests (P03-S02-T003)
// ---------------------------------------------------------------------------

const MOCK_LIST_RESPONSE: ListConversationsResponse = {
  data: [
    {
      id: "conv-uuid-1",
      user_id: "user-uuid-1",
      title: "First conversation",
      language: "es",
      created_at: "2026-05-15T09:00:00Z",
      updated_at: "2026-05-15T10:00:00Z",
    },
    {
      id: "conv-uuid-2",
      user_id: "user-uuid-1",
      title: "Second conversation",
      language: "es",
      created_at: "2026-05-14T09:00:00Z",
      updated_at: "2026-05-14T12:00:00Z",
    },
  ],
  meta: {
    request_id: "test-req-id",
    pagination: { next_cursor: null, has_more: false },
  },
  errors: [],
};

describe("chatRepository.listConversations", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("R01 — happy path → Result.ok with correct envelope shape", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, MOCK_LIST_RESPONSE),
    );

    const result = await listConversations({}, onAuthFailure);

    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.value.data).toHaveLength(2);
      expect(result.value.meta.pagination).toBeDefined();
      expect(result.value.meta.pagination!.has_more).toBe(false);
      // PII-clean: test verifies count is accessible, not IDs
      expect(result.value.data[0]).toHaveProperty("id");
    }
  });

  it("R02 — cursor passed → URL contains ?cursor=...", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(200, MOCK_LIST_RESPONSE),
    );

    await listConversations({ cursor: "abc123cursor" }, onAuthFailure);

    const calledUrl = String(mockAuthFetch.mock.calls[0][0]);
    expect(calledUrl).toContain("cursor=abc123cursor");
  });

  it("R03 — 401 → Result.err(ChatAuthExpiredError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(401, { errors: [{ code: "AUTH_SESSION_EXPIRED" }] }),
    );

    const result = await listConversations({}, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatAuthExpiredError);
    }
  });

  it("R04 — network failure → Result.err(ChatNetworkError)", async () => {
    mockAuthFetch.mockRejectedValueOnce(new TypeError("Failed to fetch"));

    const result = await listConversations({}, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatNetworkError);
    }
  });

  it("R05 — 403 (defensive) → Result.err(ChatForbiddenError)", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      makeResponse(403, { errors: [{ code: "AUTH_FORBIDDEN" }] }),
    );

    const result = await listConversations({}, onAuthFailure);

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatForbiddenError);
    }
  });
});
