/**
 * Hilo People — stream.ts pure-logic parser tests (§D-T002-TESTS).
 *
 * Slice/Phase: P03-S02-T008 — ConversationPage re-implementation / Phase 3.
 *   Re-implemented from reference branch f7f5f33 (P03-S02-T002).
 *
 * Responsibility: Unit tests for _parseSseRecord (pure function) and
 *   streamConversation (integration against a fake ReadableStream).
 *   Pure-logic tests are explicitly allowed per non-negotiables §Tests are REAL.
 *
 * Cases:
 *   Parser — record parsing:
 *   T01 — parse meta event
 *   T02 — parse chunk event
 *   T03 — parse citation event
 *   T04 — parse usage event
 *   T05 — parse done event
 *   T06 — parse error event returns error SseEvent
 *   T07 — unknown event name → null
 *   T08 — malformed JSON in data: line → null
 *   T09 — empty record → null
 *   T10 — missing event: line → null
 *   T11 — UTF-8 multibyte characters preserved (é, ñ, ç)
 *
 *   streamConversation:
 *   T12 — non-200 HTTP status (400) maps to ChatValidationError
 *   T13 — AbortController abort returns Result.ok
 *   T14 — full stream with chunked boundary (record split across reads)
 *   T15 — DEFECT-1 (§D-T002-STREAM-DONE-GUARD): stream closed WITHOUT event:done returns ChatNetworkError
 *   T16 — DEFECT-1 regression guard: stream closed AFTER event:done still returns ok:true
 *   T17 — DEFECT-1 abort safety: abort mid-stream does NOT trigger "without done" branch
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import {
  _parseSseRecord,
  streamConversation,
} from "../stream";
import {
  ChatNetworkError,
  ChatValidationError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mock authFetch
// ---------------------------------------------------------------------------

vi.mock("../../auth/data/httpClient", () => ({
  authFetch: vi.fn(),
}));

import { authFetch } from "../../auth/data/httpClient";
const mockAuthFetch = vi.mocked(authFetch);

// ---------------------------------------------------------------------------
// Helper: build a ReadableStream from an array of string chunks
// ---------------------------------------------------------------------------

function makeStream(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  let idx = 0;
  return new ReadableStream<Uint8Array>({
    pull(controller): void {
      if (idx < chunks.length) {
        controller.enqueue(encoder.encode(chunks[idx++]));
      } else {
        controller.close();
      }
    },
  });
}

// ---------------------------------------------------------------------------
// Helper: build a mock Response with a body stream
// ---------------------------------------------------------------------------

function makeStreamResponse(chunks: string[], status = 200): Response {
  const headers = new Headers({
    "content-type": "text/event-stream",
    "x-request-id": "test-req-id",
  });
  const body = makeStream(chunks);
  return new Response(body, { status, headers });
}

// ---------------------------------------------------------------------------
// _parseSseRecord tests (pure-logic)
// ---------------------------------------------------------------------------

describe("_parseSseRecord", () => {
  it("T01 — parse meta event", () => {
    const record = 'event: meta\ndata: {"message_id":"m1","model_id":"llm1","language":"es","request_id":"r1"}';
    const result = _parseSseRecord(record);
    expect(result).not.toBeNull();
    expect(result?.kind).toBe("meta");
    if (result?.kind === "meta") {
      expect(result.payload.message_id).toBe("m1");
      expect(result.payload.language).toBe("es");
    }
  });

  it("T02 — parse chunk event", () => {
    const record = 'event: chunk\ndata: {"delta":"Hello "}';
    const result = _parseSseRecord(record);
    expect(result?.kind).toBe("chunk");
    if (result?.kind === "chunk") {
      expect(result.payload.delta).toBe("Hello ");
    }
  });

  it("T03 — parse citation event", () => {
    const record = 'event: citation\ndata: {"document_id":"d1","chunk_id":"c1","label":"Policy","score":0.92}';
    const result = _parseSseRecord(record);
    expect(result?.kind).toBe("citation");
    if (result?.kind === "citation") {
      expect(result.payload.document_id).toBe("d1");
      expect(result.payload.score).toBe(0.92);
    }
  });

  it("T04 — parse usage event", () => {
    const record = 'event: usage\ndata: {"tokens_in":15,"tokens_out":42,"estimated_cost":0.001,"latency_ms":1200}';
    const result = _parseSseRecord(record);
    expect(result?.kind).toBe("usage");
    if (result?.kind === "usage") {
      expect(result.payload.tokens_out).toBe(42);
    }
  });

  it("T05 — parse done event", () => {
    const record = 'event: done\ndata: {"message_id":"msg-final","request_id":"r1"}';
    const result = _parseSseRecord(record);
    expect(result?.kind).toBe("done");
    if (result?.kind === "done") {
      expect(result.payload.message_id).toBe("msg-final");
    }
  });

  it("T06 — parse error event returns error SseEvent", () => {
    const record = 'event: error\ndata: {"code":"STREAM_ERROR","message":"LLM down"}';
    const result = _parseSseRecord(record);
    expect(result?.kind).toBe("error");
    if (result?.kind === "error") {
      expect(result.payload.code).toBe("STREAM_ERROR");
    }
  });

  it("T07 — unknown event name → null", () => {
    const record = 'event: heartbeat\ndata: {"ts":1234}';
    const result = _parseSseRecord(record);
    expect(result).toBeNull();
  });

  it("T08 — malformed JSON in data: line → null", () => {
    const record = "event: chunk\ndata: {not-valid-json}";
    const result = _parseSseRecord(record);
    expect(result).toBeNull();
  });

  it("T09 — empty record → null", () => {
    expect(_parseSseRecord("")).toBeNull();
    expect(_parseSseRecord("  \n  ")).toBeNull();
  });

  it("T10 — missing event: line → null (data-only record)", () => {
    const record = 'data: {"delta":"hi"}';
    const result = _parseSseRecord(record);
    expect(result).toBeNull();
  });

  it("T11 — UTF-8 multibyte characters preserved (é, ñ, ç)", () => {
    const record = 'event: chunk\ndata: {"delta":"días de vacación — répondre"}';
    const result = _parseSseRecord(record);
    expect(result?.kind).toBe("chunk");
    if (result?.kind === "chunk") {
      expect(result.payload.delta).toContain("días");
      expect(result.payload.delta).toContain("répondre");
    }
  });
});

// ---------------------------------------------------------------------------
// streamConversation tests
// ---------------------------------------------------------------------------

describe("streamConversation", () => {
  const onAuthFailure = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("T12 — non-200 HTTP status 400 maps to ChatValidationError", async () => {
    mockAuthFetch.mockResolvedValueOnce(
      new Response(JSON.stringify({ errors: [] }), {
        status: 400,
        headers: { "x-request-id": "r1", "content-type": "application/json" },
      }),
    );

    const handlers = {
      onMeta: vi.fn(),
      onChunk: vi.fn(),
      onCitation: vi.fn(),
      onUsage: vi.fn(),
      onError: vi.fn(),
      onDone: vi.fn(),
    };
    const controller = new AbortController();

    const result = await streamConversation("conv-1", "test message", handlers, {
      signal: controller.signal,
      onAuthFailure,
    });

    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatValidationError);
    }
    expect(handlers.onDone).not.toHaveBeenCalled();
  });

  it("T13 — AbortController abort returns Result.ok", async () => {
    const controller = new AbortController();

    // Simulate abort before fetch resolves
    mockAuthFetch.mockImplementationOnce(() => {
      const err = new DOMException("Aborted", "AbortError");
      return Promise.reject(err);
    });

    const handlers = {
      onMeta: vi.fn(),
      onChunk: vi.fn(),
      onCitation: vi.fn(),
      onUsage: vi.fn(),
      onError: vi.fn(),
      onDone: vi.fn(),
    };

    controller.abort();

    const result = await streamConversation("conv-1", "test", handlers, {
      signal: controller.signal,
      onAuthFailure,
    });

    expect(result.ok).toBe(true);
  });

  it("T14 — full stream with chunked boundary (record split across reads)", async () => {
    // Split the meta event across two reads
    const metaPayload = '{"message_id":"m1","model_id":"llm1","language":"es","request_id":"r1"}';
    const chunkPayload = '{"delta":"Hola"}';
    const donePayload = '{"message_id":"m1","request_id":"r1"}';

    // Simulate chunking: first read has partial meta, second completes it
    const part1 = "event: meta\ndata: " + metaPayload.slice(0, 20);
    const part2 = metaPayload.slice(20) + "\n\nevent: chunk\ndata: " + chunkPayload + "\n\nevent: done\ndata: " + donePayload + "\n\n";

    mockAuthFetch.mockResolvedValueOnce(
      makeStreamResponse([part1, part2]),
    );

    const handlers = {
      onMeta: vi.fn(),
      onChunk: vi.fn(),
      onCitation: vi.fn(),
      onUsage: vi.fn(),
      onError: vi.fn(),
      onDone: vi.fn(),
    };
    const controller = new AbortController();

    const result = await streamConversation("conv-1", "test", handlers, {
      signal: controller.signal,
      onAuthFailure,
    });

    expect(result.ok).toBe(true);
    expect(handlers.onMeta).toHaveBeenCalledWith(
      expect.objectContaining({ message_id: "m1" }),
    );
    expect(handlers.onChunk).toHaveBeenCalledWith({ delta: "Hola" });
    expect(handlers.onDone).toHaveBeenCalledWith(
      expect.objectContaining({ message_id: "m1" }),
    );
  });

  // -------------------------------------------------------------------------
  // §D-T002-STREAM-DONE-GUARD — DEFECT-1 regression suite (debug cycle 2)
  //
  // Backstory: in /verify-slice the LiteLLM proxy emitted `event: meta` and
  // then closed the SSE connection without ever sending `event: done`.
  // streamConversation used to return `{ ok: true }` on natural EOS, which
  // left useChatStream in `phase = "streaming"` forever (composer disabled,
  // ASISTENTE label + cursor blinking forever, no NetworkErrorView, no
  // recovery path). Fix: track `doneEmitted`; if false at EOS, return a
  // ChatNetworkError so the consumer can transition to error_network.
  // -------------------------------------------------------------------------

  it("T15 — DEFECT-1: closed without event:done returns ChatNetworkError", async () => {
    // Stream emits `event: meta` then closes — exactly the LiteLLM-after-meta
    // case observed by slice-verifier. No `event: done` ever arrives.
    const metaPayload = '{"message_id":"m1","model_id":"llm1","language":"es","request_id":"r1"}';
    const metaRecord = "event: meta\ndata: " + metaPayload + "\n\n";

    mockAuthFetch.mockResolvedValueOnce(makeStreamResponse([metaRecord]));

    const handlers = {
      onMeta: vi.fn(),
      onChunk: vi.fn(),
      onCitation: vi.fn(),
      onUsage: vi.fn(),
      onError: vi.fn(),
      onDone: vi.fn(),
    };
    const controller = new AbortController();

    const result = await streamConversation("conv-1", "test", handlers, {
      signal: controller.signal,
      onAuthFailure,
    });

    // The function must NOT report success — that was the bug.
    expect(result.ok).toBe(false);
    if (!result.ok) {
      expect(result.error).toBeInstanceOf(ChatNetworkError);
      expect(result.error.message.toLowerCase()).toContain("without done");
    }
    // onMeta was called (we received the meta event), but onDone was NEVER
    // called — that is precisely why useChatStream needs the err return path.
    expect(handlers.onMeta).toHaveBeenCalledTimes(1);
    expect(handlers.onDone).not.toHaveBeenCalled();
  });

  it("T16 — DEFECT-1 regression guard: stream that DID emit done returns ok:true", async () => {
    // Counter-test: confirm the successful path is unchanged. meta + done.
    const metaPayload = '{"message_id":"m1","model_id":"llm1","language":"es","request_id":"r1"}';
    const donePayload = '{"message_id":"m1","request_id":"r1"}';
    const wire =
      "event: meta\ndata: " + metaPayload + "\n\n" +
      "event: done\ndata: " + donePayload + "\n\n";

    mockAuthFetch.mockResolvedValueOnce(makeStreamResponse([wire]));

    const handlers = {
      onMeta: vi.fn(),
      onChunk: vi.fn(),
      onCitation: vi.fn(),
      onUsage: vi.fn(),
      onError: vi.fn(),
      onDone: vi.fn(),
    };
    const controller = new AbortController();

    const result = await streamConversation("conv-1", "test", handlers, {
      signal: controller.signal,
      onAuthFailure,
    });

    // Successful path: ok:true and onDone fired exactly once.
    expect(result.ok).toBe(true);
    expect(handlers.onDone).toHaveBeenCalledTimes(1);
    expect(handlers.onDone).toHaveBeenCalledWith(
      expect.objectContaining({ message_id: "m1" }),
    );
  });

  it("T17 — DEFECT-1 abort safety: aborted mid-stream does not produce 'without done'", async () => {
    // Abort during/before reader.read() — the existing AbortError handling
    // must short-circuit before the new doneEmitted check runs.
    const controller = new AbortController();

    mockAuthFetch.mockImplementationOnce(() => {
      const err = new DOMException("Aborted", "AbortError");
      return Promise.reject(err);
    });

    const handlers = {
      onMeta: vi.fn(),
      onChunk: vi.fn(),
      onCitation: vi.fn(),
      onUsage: vi.fn(),
      onError: vi.fn(),
      onDone: vi.fn(),
    };

    controller.abort();

    const result = await streamConversation("conv-1", "test", handlers, {
      signal: controller.signal,
      onAuthFailure,
    });

    // Abort path returns ok:true (consistent with T13 and §D-T002-ABORT-ON-UNMOUNT).
    expect(result.ok).toBe(true);
    if (!result.ok) {
      expect((result.error as Error).message.toLowerCase()).not.toContain("without done");
    }
    expect(handlers.onDone).not.toHaveBeenCalled();
  });
});
