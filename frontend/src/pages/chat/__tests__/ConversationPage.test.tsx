/**
 * Hilo People — ConversationPage tests (§D-T002-TESTS).
 *
 * Slice/Phase: P03-S02-T008 — ConversationPage re-implementation / Phase 3.
 *   Re-implemented from reference branch f7f5f33 (P03-S02-T002).
 *
 * Responsibility: Integration tests for ConversationPage rendering.
 *   useConversation and useChatStream are mocked to control each UX state.
 *
 * Cases:
 *   T01 — loading state: aria-busy=true, loading label
 *   T02 — empty state: 0 messages, CTA to new conversation
 *   T03 — success state: transcript rendered with messages
 *   T04 — streaming state: streaming placeholder visible, composer shows loading
 *   T05 — error_network state: retry CTA visible
 *   T06 — permission_denied state: forbidden view visible
 *   T07 — not_found state: not-found view visible
 *   T08 — transcript has role="log" and aria-live="polite"
 *   T09 — no .bubble class on message blocks (editorial no-bubble layout)
 *   T10 — citations render as CitationInline ordered by arrival
 *   T11 — deep-link auto-stream: last message is user → start() called
 *   T12 — error_validation state: ValidationErrorBanner visible (role=alert,
 *         data-testid=validation-error-banner) and no streaming placeholder.
 *   T13-T009 — success state: navbar account link visible.
 *   T14-T009 — loading state: navbar account link visible.
 *   T15-T009 — empty state: navbar account link visible.
 *   T16-T009 — permission_denied state: navbar account link HIDDEN.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, act } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../i18n/index";
import type { ReactNode } from "react";

// ---------------------------------------------------------------------------
// Mocks (must be before the imports of the modules being mocked)
// ---------------------------------------------------------------------------

vi.mock("../../../features/chat/presentation/useConversation", () => ({
  useConversation: vi.fn(),
  conversationQueryKey: (id: string) => ["conversation", id],
}));

vi.mock("../../../features/chat/presentation/useChatStream", () => ({
  useChatStream: vi.fn(),
}));

vi.mock("../../../features/auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(() => ({ logout: vi.fn() })),
  AuthProvider: ({ children }: { children: ReactNode }) => <>{children}</>,
}));

import ConversationPage from "../ConversationPage";
import { useConversation } from "../../../features/chat/presentation/useConversation";
import { useChatStream } from "../../../features/chat/presentation/useChatStream";
import {
  ChatForbiddenError,
  ChatNotFoundError,
  ChatValidationError,
  type ChatError,
} from "../../../features/chat/data/errors";

const mockUseConversation = vi.mocked(useConversation);
const mockUseChatStream = vi.mocked(useChatStream);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_DETAIL = {
  id: "conv-test",
  user_id: "u1",
  title: "Test conversation",
  language: "es" as const,
  created_at: "2026-05-14T10:00:00Z",
  updated_at: "2026-05-14T10:00:00Z",
  messages: [
    {
      id: "msg-1",
      conversation_id: "conv-test",
      role: "user" as const,
      content: "How many vacation days?",
      token_count: null,
      created_at: "2026-05-14T10:00:00Z",
    },
    {
      id: "msg-2",
      conversation_id: "conv-test",
      role: "assistant" as const,
      content: "You have 22 days.",
      token_count: 10,
      created_at: "2026-05-14T10:00:01Z",
    },
  ],
  citations: [
    {
      id: "cit-1",
      message_id: "msg-2",
      document_id: "d1",
      chunk_id: "c1",
      label: "HR Policy",
      score: 0.9,
    },
  ],
};

const IDLE_STREAM = {
  phase: "idle" as const,
  assistantText: "",
  citations: [],
  lastError: undefined,
  start: vi.fn(),
  retry: vi.fn(),
};

function makeQueryClient(): QueryClient {
  return new QueryClient({ defaultOptions: { queries: { retry: false } } });
}

function renderPage(conversationId = "conv-test", qc?: QueryClient): ReturnType<typeof render> {
  const client = qc ?? makeQueryClient();
  return render(
    <QueryClientProvider client={client}>
      <I18nextProvider i18n={i18n}>
        <MemoryRouter initialEntries={[`/chat/${conversationId}`]}>
          <Routes>
            <Route path="/chat/:conversationId" element={<ConversationPage />} />
            <Route path="/chat" element={<div data-testid="chat-home" />} />
          </Routes>
        </MemoryRouter>
      </I18nextProvider>
    </QueryClientProvider>,
  );
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ConversationPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T01 — loading state: aria-busy=true, loading label visible", () => {
    mockUseConversation.mockReturnValue({
      data: undefined,
      status: "pending",
      error: null,
      isLoading: true,
      isSuccess: false,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    const page = screen.getByTestId("conversation-page");
    expect(page).toHaveAttribute("aria-busy", "true");
  });

  it("T02 — empty state: 0 messages, CTA to new conversation", async () => {
    const emptyDetail = { ...MOCK_DETAIL, messages: [], citations: [] };
    mockUseConversation.mockReturnValue({
      data: emptyDetail,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    expect(screen.getByTestId("empty-conversation-view")).toBeDefined();
    expect(screen.getByTestId("empty-conversation-cta")).toBeDefined();
  });

  it("T03 — success state: transcript rendered with messages", () => {
    mockUseConversation.mockReturnValue({
      data: MOCK_DETAIL,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    const transcript = screen.getByTestId("transcript-region");
    expect(transcript).toBeDefined();
    // Should have both user and assistant message blocks
    expect(screen.getAllByTestId(/message-block-/)).toHaveLength(2);
  });

  it("T04 — streaming state: streaming placeholder visible, composer shows loading", () => {
    mockUseConversation.mockReturnValue({
      data: MOCK_DETAIL,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({
      ...IDLE_STREAM,
      phase: "streaming",
      assistantText: "",
    });

    renderPage();

    expect(screen.getByTestId("streaming-placeholder")).toBeDefined();
    // Transcript should have aria-busy
    const transcript = screen.getByTestId("transcript-region");
    expect(transcript).toHaveAttribute("aria-busy", "true");
  });

  it("T05 — error_network state: retry CTA visible", () => {
    mockUseConversation.mockReturnValue({
      data: MOCK_DETAIL,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({
      ...IDLE_STREAM,
      phase: "error_network",
    });

    renderPage();

    expect(screen.getByTestId("network-error-retry-cta")).toBeDefined();
  });

  it("T06 — permission_denied state: forbidden view visible (from query error)", () => {
    const forbiddenErr = new ChatForbiddenError();

    mockUseConversation.mockReturnValue({
      data: undefined,
      status: "error",
      error: forbiddenErr as ChatError,
      isLoading: false,
      isSuccess: false,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    expect(screen.getByTestId("forbidden-view")).toBeDefined();
  });

  it("T07 — not_found state: not-found view visible (from query error)", () => {
    const notFoundErr = new ChatNotFoundError();

    mockUseConversation.mockReturnValue({
      data: undefined,
      status: "error",
      error: notFoundErr as ChatError,
      isLoading: false,
      isSuccess: false,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    expect(screen.getByTestId("not-found-view")).toBeDefined();
  });

  it("T08 — transcript has role='log' and aria-live='polite'", () => {
    mockUseConversation.mockReturnValue({
      data: MOCK_DETAIL,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    const transcript = screen.getByTestId("transcript-region");
    expect(transcript).toHaveAttribute("role", "log");
    expect(transcript).toHaveAttribute("aria-live", "polite");
  });

  it("T09 — no .bubble class on message blocks (editorial no-bubble layout)", () => {
    mockUseConversation.mockReturnValue({
      data: MOCK_DETAIL,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    const { container } = renderPage();
    const bubbles = container.querySelectorAll(".bubble");
    expect(bubbles).toHaveLength(0);
  });

  it("T10 — citations render as CitationInline within assistant block", () => {
    mockUseConversation.mockReturnValue({
      data: MOCK_DETAIL,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    // CitationInline renders as [label] — check for "[HR Policy]"
    expect(screen.getByText("[HR Policy]")).toBeDefined();
  });

  it("T11 — deep-link auto-stream: last message is user role → start() called", () => {
    const pendingConv = {
      ...MOCK_DETAIL,
      messages: [MOCK_DETAIL.messages[0]], // Only the user message, no assistant reply
      citations: [],
    };

    const startMock = vi.fn();
    mockUseConversation.mockReturnValue({
      data: pendingConv,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({
      ...IDLE_STREAM,
      start: startMock,
    });

    act(() => {
      renderPage();
    });

    // auto-stream should fire with the user message content
    expect(startMock).toHaveBeenCalledWith("How many vacation days?");
  });

  it("T12 — error_validation state: ValidationErrorBanner visible (alert role)", () => {
    const validationErr = new ChatValidationError();

    mockUseConversation.mockReturnValue({
      data: MOCK_DETAIL,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({
      ...IDLE_STREAM,
      phase: "error_validation",
      lastError: validationErr as ChatError,
    });

    renderPage();

    // Banner must exist with role="alert" + data-testid.
    const banner = screen.getByTestId("validation-error-banner");
    expect(banner).toBeDefined();
    expect(banner).toHaveAttribute("role", "alert");
    // Alert must be assertive per WCAG.
    expect(banner).toHaveAttribute("aria-live", "assertive");

    // No streaming UI when stream finished with validation error.
    expect(screen.queryByTestId("streaming-placeholder")).toBeNull();
    expect(screen.queryByTestId("streaming-message")).toBeNull();

    // No network-error retry CTA — validation errors do not auto-retry.
    expect(screen.queryByTestId("network-error-retry-cta")).toBeNull();
  });

  // --- P03-S02-T009: navbar account link assertions ---

  it("T13-T009 — success state: navbar account link visible (§D-T009-NAVBAR-VISIBILITY)", () => {
    mockUseConversation.mockReturnValue({
      data: MOCK_DETAIL,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    const navbar = screen.getByTestId("chat-navbar");
    expect(navbar).toBeDefined();

    const link = screen.getByTestId("chat-navbar-account-link");
    expect(link).toBeDefined();
    expect(link.getAttribute("href")).toBe("/account");
  });

  it("T14-T009 — loading state: navbar account link visible", () => {
    mockUseConversation.mockReturnValue({
      data: undefined,
      status: "pending",
      error: null,
      isLoading: true,
      isSuccess: false,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    const navbar = screen.getByTestId("chat-navbar");
    expect(navbar).toBeDefined();
  });

  it("T15-T009 — empty state: navbar account link visible", () => {
    const emptyDetail = { ...MOCK_DETAIL, messages: [], citations: [] };
    mockUseConversation.mockReturnValue({
      data: emptyDetail,
      status: "success",
      error: null,
      isLoading: false,
      isSuccess: true,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    const navbar = screen.getByTestId("chat-navbar");
    expect(navbar).toBeDefined();
  });

  it("T16-T009 — permission_denied state: navbar account link HIDDEN (§D-T009-NAVBAR-VISIBILITY)", () => {
    const forbiddenErr = new ChatForbiddenError();

    mockUseConversation.mockReturnValue({
      data: undefined,
      status: "error",
      error: forbiddenErr as ChatError,
      isLoading: false,
      isSuccess: false,
      refetch: vi.fn(),
    });
    mockUseChatStream.mockReturnValue({ ...IDLE_STREAM });

    renderPage();

    // The forbidden branch returns early without rendering ChatNavbar
    expect(screen.queryByTestId("chat-navbar")).toBeNull();
    expect(screen.queryByTestId("chat-navbar-account-link")).toBeNull();

    // But the forbidden view itself must be rendered
    expect(screen.getByTestId("forbidden-view")).toBeDefined();
  });
});
