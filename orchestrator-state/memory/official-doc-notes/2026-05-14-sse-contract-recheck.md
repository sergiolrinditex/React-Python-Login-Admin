# Official Doc Note — P03-S02-T002 SSE Contract Recheck + Frontend Stack Q1–Q5
Date: 2026-05-14
Task: P03-S02-T002 (ConversationPage — frontend SSE consumer)
Sources:
  - backend/app/chat/streaming/sse.py (internal, authoritative)
  - backend/app/chat/streaming/service.py (internal, authoritative)
  - backend/app/chat/streaming/router.py (internal, authoritative)
  - backend/app/chat/streaming/persistence.py (internal, authoritative)
  - https://github.com/vitejs/vite/blob/v8.0.0/docs/config/server-options.md (Context7 /vitejs/vite v8.0.0)
  - https://tanstack.com/query/v5/docs (Context7 /tanstack/query v5_84_1)
  - https://developer.mozilla.org/en-US/docs/Web/API/ReadableStream/getReader
  - https://developer.mozilla.org/en-US/docs/Web/API/AbortController
  - https://developer.mozilla.org/en-US/docs/Web/API/TextDecoder/decode
  - https://encoding.spec.whatwg.org/#dom-textdecoder-decode
  - https://react.dev/reference/react/StrictMode

---

## Q1 — Backend SSE wire contract (INTERNAL, authoritative)

### Exact event emission order (service.py lines 246–385)

The runtime order is **strictly**:
```
meta → citation* → chunk* → usage → done   (happy path)
meta → citation* → chunk* → error          (LLM error mid-stream)
```

Step-by-step from `run_stream()`:
1. `sse_meta` emitted **once** after RAG retrieval but before LLM streaming starts (line 246).
2. All `sse_citation` events emitted in a loop **before** the LLM generator starts (lines 254–261). **Citations are always BEFORE any chunk — not interleaved.** This is documented as `D-CHATSTREAM-CITORDER` in the service.py docstring.
3. `sse_chunk` events emitted inside the `async for event in stream_chat(...)` loop (line 291).
4. After the LLM stream completes and persistence runs: `sse_usage` then `sse_done` emitted together (lines 379–385).
5. On mid-stream LLM error: `sse_error` emitted, `persist_partial_turn` called, then `return` (lines 295–311). No `usage` or `done` follows an `error`.

### DISCREPANCY NOTE (minor — task pack wording, not wire format)
The task pack §E.2 table describes `citation` events as arriving "0..N times, **interleaved before/around** `chunk` events." The actual implementation in `service.py` emits ALL citations **before** the first chunk. The pack's §N and router docstring both say `meta → citation* → chunk* → usage → done`, which IS correct. The word "interleaved" in the §E.2 table description is misleading but the overall order listed in §N is accurate. This is a documentation inconsistency within the task pack itself, not a backend mismatch.

**Impact on developer**: The frontend parser must handle citations arriving before any chunks, not scattered between them. Holding citations in a list and attaching them to the assistant message as they arrive is safe for both V1 (pre-chunk) and any future change to interleaved order (the parser already yields them separately).

TODO: `RESOLVED: The word "interleaved" in §E.2 table is cosmetic — the binding sequence is meta→citation*→chunk*→usage→done per service.py. Frontend parser handles both orders correctly since citations are appended to a list.`

### JSON shapes (confirmed from sse.py)

| Event | Fields | Types |
|---|---|---|
| `meta` | `message_id, model_id, language, request_id` | all `str` |
| `citation` | `document_id, chunk_id, label, score` | `str, str, str, float` |
| `chunk` | `delta` | `str` |
| `usage` | `tokens_in, tokens_out, estimated_cost, latency_ms` | `int, int, float, int` |
| `error` | `code, message` | `str, str` |
| `done` | `message_id, request_id` | `str, str` |

### Wire format (sse.py make_sse_bytes, line 57)
```
event: <name>\n
data: <json-single-line>\n
\n
```
JSON serialized with `ensure_ascii=False` (D-SSE2) → UTF-8 multibyte preserved.

### HTTP response headers (router.py lines 192–198)
```
Content-Type: text/event-stream; charset=utf-8
X-Request-ID: <uuid>
Cache-Control: no-cache
Connection: keep-alive
```

### Request body
`POST .../stream` body: `{"message": "<1..8000 chars>"}` (Pydantic `StreamRequest`). No `language` field. Confirmed in `streaming/schemas.py` and task pack §D-T002-LANGUAGE-FROM-USER.

### Auth
Bearer `Authorization` header required (injected by `authFetch`). No `credentials: include` needed for this POST (the refresh cookie is for `/auth/refresh`, not `/chat/...`). `authFetch` injects both Bearer + X-Request-ID.

### Retry/duplication behavior (persistence.py)
`persist_user_message` is called at **Step 2**, BEFORE any LLM call, with an immediate `session.commit()` (persistence.py line 91). This means on retry after network failure, if Step 2 already committed, the same POST will INSERT a SECOND user message row. The frontend should NOT attempt to deduplicate — this is a server-side concern. Documented in task pack §D-T002-RETRY-SAME-PROMPT as out-of-scope.

---

## Q2 — Vite v8.0.12 proxy + SSE/chunked transfer

### Answer
Vite v8.0.0 (confirmed via Context7 `/vitejs/vite/v8.0.0`) `server.proxy` extends `http-proxy-3` (the maintained fork of `http-proxy`). The current `vite.config.ts` config:
```ts
proxy: { "/api": { target: "http://localhost:8000", changeOrigin: false, secure: false } }
```
is correct and complete for SSE.

**`http-proxy-3` preserves `Content-Type: text/event-stream` and chunked transfer by default** — it pipes the response stream without buffering. No `selfHandleResponse`, `proxyTimeout`, or `ws` flags are needed for HTTP SSE (those are for WebSocket or custom response handling).

The Vite v8 docs explicitly state: "Note that if you are using non-relative `base`, you must prefix each key with that `base`." No other SSE-specific configuration is required.

**Gotcha (EventSource vs fetch through proxy)**: `EventSource` from a browser cannot send custom headers and requires GET — it cannot POST through the Vite proxy. The project's choice of `fetch + ReadableStream` (ADR-002) is correct and avoids this limitation.

Source: https://github.com/vitejs/vite/blob/v8.0.0/docs/config/server-options.md

**Pattern to apply**: Current `vite.config.ts` is complete. No changes needed for SSE streaming.

RESOLVED: N/A — no discrepancy.

---

## Q3 — TanStack Query v5 + streaming mutation cache integration

### Answer
TanStack Query v5 (`^5.100.9`) has no built-in "streaming query" primitive. The recommended pattern for long-running streaming operations that must integrate with a `useQuery` cache key is:

**Pattern: Local state for streaming + single `setQueryData` at `done`**

- During streaming: accumulate chunks in local React state (`useState`). Do NOT call `setQueryData` on every chunk — this triggers re-renders for all cache subscribers and is inefficient.
- At `done` (or on error, to show partial): call `queryClient.setQueryData(['conversation', id], updater)` **once** with the complete assembled `ConversationDetail` shape. This writes the final persisted state from the backend into the cache.
- The `useQuery` `['conversation', id]` already has `staleTime: 30s` — so after `setQueryData`, a subsequent mount/re-focus will use the cached value and not refetch.
- For optimistic pre-stream user message: use `queryClient.cancelQueries` + `setQueryData` in `onMutate` style (without `useMutation`) to append the user turn to the cached transcript before the stream opens.
- `useMutation` is **not required** for the streaming side. The `useChatStream` hook owns the `AbortController` and state machine directly, bypassing `useMutation`. This is consistent with the TanStack v5 pattern of "manual streaming hooks."

**Race condition with in-flight `useQuery`**: If `useQuery(['conversation', id])` is fetching and `setQueryData` is called, TanStack Query v5 keeps the `setQueryData` value and **cancels the outgoing refetch** (or ignores its result). This is the correct behavior — call `queryClient.cancelQueries(['conversation', id])` before starting the stream to prevent a GET response from overwriting the optimistic user-turn.

Source: https://tanstack.com/query/v5/docs (Context7 /tanstack/query v5_84_1 — optimistic-updates.md, updates-from-mutation-responses.md)

**Pattern to apply** (excerpt):
```ts
// In useChatStream, before calling streamConversation:
await queryClient.cancelQueries({ queryKey: ['conversation', id] })
// Optimistically append user turn:
queryClient.setQueryData(['conversation', id], (old) =>
  old ? { ...old, data: { ...old.data, messages: [...old.data.messages, userMsg] } } : old
)
// ... stream ...
// On 'done':
queryClient.setQueryData(['conversation', id], (old) =>
  old ? { ...old, data: { ...old.data, messages: [...old.data.messages, finalAssistantMsg] } } : old
)
```

RESOLVED: N/A — no discrepancy with task pack §D-T002-TANSTACK-CACHE.

---

## Q4 — fetch + ReadableStream + TextDecoder canonical SSE parser pattern

### TextDecoder `{stream:true}` UTF-8 multibyte safety
**Confirmed safe.** Per the WHATWG Encoding specification (https://encoding.spec.whatwg.org/#dom-textdecoder-decode):
> When `stream:true` is passed, the decoder maintains its internal state between calls, buffering any incomplete multibyte byte sequence at a chunk boundary. The next `decode()` call continues from that buffered state.

This means `TextDecoder('utf-8', { fatal: false }).decode(value, { stream: true })` is correct and safe for UTF-8 including Spanish/French characters (which can be 2–3 bytes) split across network chunk boundaries.

### `reader.releaseLock()` — where to put it
Always in a `finally` block:
```ts
const reader = response.body!.getReader()
try {
  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    // process value
  }
} finally {
  reader.releaseLock()  // releases the lock even on abort or throw
}
```
Source: https://developer.mozilla.org/en-US/docs/Web/API/ReadableStream/getReader — the lock must be released before the stream can be re-read or closed by anyone else.

### AbortController abort detection
```ts
try {
  // ...fetch loop...
} catch (err) {
  if (err instanceof DOMException && err.name === 'AbortError') {
    return  // expected clean cancel — do not propagate
  }
  throw err  // real network error — propagate to error state
}
```
Source: https://developer.mozilla.org/en-US/docs/Web/API/AbortController — DOMException with name `'AbortError'` is thrown when `controller.abort()` is called.

### Browser support matrix
- `ReadableStream.getReader()`: Baseline Widely Available since January 2019. Works in Chrome 43+, Firefox 65+, Safari 10.1+.
- `TextDecoder` with `stream:true`: Widely Available since January 2020. Chrome 38+, Firefox 38+, Safari 10.1+.
- `AbortController`: Widely Available. Chrome 66+, Firefox 57+, Safari 11.1+.
- All targets met by `vite build target: "es2022"` (evergreen browsers only).

Source: MDN Baseline indicators (retrieved 2026-05-14).

RESOLVED: N/A — no discrepancy. Task pack §D-T002-SSE-PARSE and §D-T002-NO-EVENTSOURCE patterns are confirmed correct.

---

## Q5 — React 19 StrictMode + fetch streams double-invocation

### Answer
**React 18/19 StrictMode in development runs `useEffect` twice**: mount → cleanup → mount. This means any `useEffect` that opens a streaming fetch will fire twice in dev.

From https://react.dev/reference/react/StrictMode:
> "When Strict Mode is on, React will also run one extra setup+cleanup cycle in development for every Effect."

**AbortController cleanup correctly handles this.** The pattern:
```ts
useEffect(() => {
  const controller = new AbortController()
  startStream(controller.signal)  // POST .../stream
  return () => controller.abort() // StrictMode cleanup aborts the first fetch
}, [conversationId])
```
The first invocation's cleanup calls `controller.abort()`, which cancels the in-flight POST fetch with a `DOMException { name: 'AbortError' }`. The catch block should detect this and return cleanly (not set error state). The second invocation opens a fresh `AbortController` and a new POST.

**Backend impact**: Since `persist_user_message` commits BEFORE LLM streaming, if the first abort happens AFTER the user message was committed but before the LLM starts, there will be a dangling user message row. The backend's `asyncio.CancelledError` handler calls `persist_partial_turn` with an empty buffer in this case (service.py lines 321–338). This means the DB will have one user message + one empty assistant message from the aborted first request, and then another user message + complete assistant from the second. This is the known retry duplication risk in §D-T002-RETRY-SAME-PROMPT and is out of scope for the frontend.

**Mitigation in dev**: Use a `useRef` "already-started" guard to suppress the second StrictMode invocation:
```ts
const startedRef = useRef(false)
useEffect(() => {
  if (startedRef.current) return  // StrictMode suppression in dev
  startedRef.current = true
  const controller = new AbortController()
  startStream(controller.signal)
  return () => controller.abort()
}, [conversationId])
```
**However**: This pattern suppresses the second run in BOTH dev AND prod. In prod there is no double-invocation, so `startedRef.current = true` is set exactly once and behaves correctly. In dev it prevents the double POST. This is the recommended approach when the side-effect (POST stream) has observable server-side consequences.

**Alternative**: The simpler approach (no ref) works if the backend tolerates the double-message duplication in dev mode. Given the known caveat in §D-T002-RETRY-SAME-PROMPT, the `useRef` guard is recommended for dev cleanliness, but is not strictly required for correctness.

Source: https://react.dev/reference/react/StrictMode ("Extra setup+cleanup cycle in development")

RESOLVED: N/A — no discrepancy with task pack §D-T002-ABORT-ON-UNMOUNT. Developer should consider `useRef` guard for StrictMode dev.
