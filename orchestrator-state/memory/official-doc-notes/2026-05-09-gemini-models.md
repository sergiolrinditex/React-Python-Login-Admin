# Gemini Model IDs — Verification Note (P00-S02-T005)

**Date**: 2026-05-09
**Task**: P00-S02-T005
**Severity**: MEDIUM (model IDs verified OK, one NEW finding on embedding model upgrade path)
**Sources**:
- https://ai.google.dev/gemini-api/docs/models (WebFetch — official Google AI docs)
- https://ai.google.dev/gemini-api/docs/models/gemini (WebFetch — official model catalog)
- https://ai.google.dev/api/generate-content (WebFetch — API reference)
- Context7 /googleapis/python-genai (Google Gen AI Python SDK docs, v1.33.0)

---

## Findings

### 1. `gemini-2.5-flash` — VERIFIED CURRENT

**Task pack says**: `gemini-2.5-flash` as the primary chat model.
**Official docs say**: `gemini-2.5-flash` is listed as "Our best price-performance model for
low-latency, high-volume tasks". Confirmed current and NOT deprecated.
**Verdict**: CORRECT. Use as-is.

### 2. `gemini-2.5-flash-lite` — VERIFIED CURRENT

**Task pack says**: variant cheap/fast.
**Official docs say**: `gemini-2.5-flash-lite` is listed as "The fastest and most
budget-friendly multimodal model". Confirmed present and valid.
**Verdict**: CORRECT. Use as-is.

### 3. `gemini-embedding-001` — VERIFIED CURRENT (but newer alternative exists)

**Task pack says**: `gemini-embedding-001` for RAG embeddings.
**Official docs say**:
- `gemini-embedding-001` — listed for "text classification, and RAG systems" — ACTIVE, not deprecated.
- `gemini-embedding-2` — "Our first multimodal embedding model" — NEWER, supports text, images,
  video, audio, PDFs.

**Verdict**: `gemini-embedding-001` is CORRECT and current for the T005 bundle. It is the
right choice for a text-only RAG system. `gemini-embedding-2` is a newer multimodal variant —
developer may choose to use it for future-proofing, but `gemini-embedding-001` is NOT deprecated
and is the canonical text-embedding model. No change required for T005 JSON.

**NOTE**: The deprecated variant `text-embedding-004` does NOT appear in current docs. It is
not listed. Do NOT use it. `gemini-embedding-001` is the correct name.

### 4. API Base Endpoint — `v1beta` CONFIRMED (not `v1` stable)

**Task pack says**: `https://generativelanguage.googleapis.com/v1beta`.
**Official API reference docs say**: The Gemini API content generation endpoint is explicitly
documented as `https://generativelanguage.googleapis.com/v1beta/{model=models/*}:generateContent`.
`v1beta` is the current active version for the Gemini Developer API.
**Verdict**: CORRECT. `v1beta` is still the endpoint to use. No drift.

### 5. Gemini 3 models — context

The deepagents docs show model strings like `google_genai:gemini-3.1-pro-preview`.
"Gemini 3 Pro Preview has been shut down March 9, 2026" — users directed to `gemini-3.1-pro-preview`.
This is a Vertex AI / advanced preview model, NOT the standard Gemini Developer API models.
**No impact on T005 bundle** which uses `gemini-2.5-flash` (Developer API, current).

---

## Summary verdict

ALL model IDs in the task pack are CORRECT as of 2026-05-09:
- `gemini-2.5-flash` — current chat model ✓
- `gemini-2.5-flash-lite` — current fast/cheap variant ✓
- `gemini-embedding-001` — current text embedding model for RAG ✓
- `v1beta` endpoint — confirmed active ✓

No developer action required. Note is informational only.

RESOLVED: n/a — no discrepancy. All model IDs confirmed valid.
