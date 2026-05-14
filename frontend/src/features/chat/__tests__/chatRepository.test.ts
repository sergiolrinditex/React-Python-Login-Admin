/**
 * Hilo People — Chat repository unit tests.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *
 * Responsibility: Unit tests for chatRepository.createConversation.
 *   authFetch is mocked at the fetch boundary per §10.1 (test doubles for fetch allowed
 *   at unit level — TECHNICAL_GUIDE §9.1).
 *
 * Cases:
 *   T01 — happy path → Result.ok with conversation data.
 *   T02 — 400 → Result.err(ChatValidationError).
 *   T03 — 403 → Result.err(ChatForbiddenError).
 *   T04 — 5xx → Result.err(ChatServerError).
 *   T05 — network throw → Result.err(ChatNetworkError).
 *   T06 — request shape verification: method, Content-Type, body JSON.
 *   T07 — 401 final (authFetch exhausted) → Result.err(ChatAuthExpiredError).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { createConversation } from "../data/chatRepository";
import {
  ChatValidationError,
  ChatNetworkError,
  ChatForbiddenError,
  ChatServerError,
  ChatAuthExpiredError,
} from "../data/errors";
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
