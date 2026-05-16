/**
 * Hilo People — RAG documents domain errors.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Typed error classes for RAG document operations.
 *   ragRepository.ts returns these via Result<T,E> patterns.
 *   Mirrors the pattern from features/chat/data/errors.ts.
 *
 * Source refs: TECHNICAL_GUIDE §6.2 (error codes), §6.4 (error envelope shapes).
 *   Error codes: RAG_DOCUMENT_INVALID (400/404/422), RAG_INDEX_IN_PROGRESS (409),
 *   RAG_DOCUMENT_TOO_LARGE (413), RAG_STORAGE_FAILED (500), RAG_INTERNAL_ERROR (500),
 *   RAG_RATE_LIMITED (429).
 */

// ---------------------------------------------------------------------------
// Typed error classes
// ---------------------------------------------------------------------------

/**
 * Validation error — 400 or 422 from server.
 * field is the offending form field (title, language, collection_id, file, etc.).
 */
export class RagDocumentInvalidError extends Error {
  public readonly code = "RAG_DOCUMENT_INVALID";
  public readonly field?: string;

  constructor(message = "Document validation failed.", field?: string) {
    super(message);
    this.name = "RagDocumentInvalidError";
    this.field = field;
  }
}

/** File too large — 413 RAG_DOCUMENT_TOO_LARGE. */
export class RagDocumentTooLargeError extends Error {
  public readonly code = "RAG_DOCUMENT_TOO_LARGE";

  constructor(message = "Document exceeds maximum file size.") {
    super(message);
    this.name = "RagDocumentTooLargeError";
  }
}

/** Unsupported MIME type — 415. */
export class RagDocumentUnsupportedMimeError extends Error {
  public readonly code = "RAG_DOCUMENT_UNSUPPORTED_MIME";

  constructor(message = "Unsupported file type. Upload PDF or DOCX only.") {
    super(message);
    this.name = "RagDocumentUnsupportedMimeError";
  }
}

/** Forbidden — 403 (role insufficient). */
export class RagPermissionDeniedError extends Error {
  public readonly code = "RAG_PERMISSION_DENIED";

  constructor(message = "You do not have permission to manage documents.") {
    super(message);
    this.name = "RagPermissionDeniedError";
  }
}

/** Not found — 404 RAG_DOCUMENT_INVALID with field=id. */
export class RagDocumentNotFoundError extends Error {
  public readonly code = "RAG_DOCUMENT_NOT_FOUND";

  constructor(message = "Document not found.") {
    super(message);
    this.name = "RagDocumentNotFoundError";
  }
}

/** Rate limited — 429. */
export class RagDocumentRateLimitedError extends Error {
  public readonly code = "RAG_RATE_LIMITED";

  constructor(message = "Too many requests. Please try again later.") {
    super(message);
    this.name = "RagDocumentRateLimitedError";
  }
}

/**
 * Index job already in progress — 409 RAG_INDEX_IN_PROGRESS.
 * Contains job_id and status of the existing job.
 */
export class RagIndexInProgressError extends Error {
  public readonly code = "RAG_INDEX_IN_PROGRESS";
  public readonly job_id: string;
  public readonly job_status: string;

  constructor(job_id: string, job_status: string, message = "Index job already in progress.") {
    super(message);
    this.name = "RagIndexInProgressError";
    this.job_id = job_id;
    this.job_status = job_status;
  }
}

/** Internal server error — 5xx. */
export class RagInternalError extends Error {
  public readonly code = "RAG_INTERNAL_ERROR";
  public readonly status: number;

  constructor(status: number, message = "Internal server error.") {
    super(message);
    this.name = "RagInternalError";
    this.status = status;
  }
}

/** Network error — fetch rejected (offline, DNS failure, CORS). */
export class RagNetworkError extends Error {
  public readonly code = "RAG_NETWORK_ERROR";

  constructor(message = "Network request failed.", public readonly cause?: unknown) {
    super(message);
    this.name = "RagNetworkError";
  }
}

/** Union of all typed RAG errors. */
export type RagError =
  | RagDocumentInvalidError
  | RagDocumentTooLargeError
  | RagDocumentUnsupportedMimeError
  | RagPermissionDeniedError
  | RagDocumentNotFoundError
  | RagDocumentRateLimitedError
  | RagIndexInProgressError
  | RagInternalError
  | RagNetworkError;

// ---------------------------------------------------------------------------
// Error mapper
// ---------------------------------------------------------------------------

/**
 * Maps an unknown fetch/domain error to a typed RagError.
 *
 * @param err - Raw caught value from a try/catch block.
 * @returns A typed domain error.
 */
export function mapRagError(err: unknown): RagError {
  if (err instanceof RagDocumentInvalidError) return err;
  if (err instanceof RagDocumentTooLargeError) return err;
  if (err instanceof RagDocumentUnsupportedMimeError) return err;
  if (err instanceof RagPermissionDeniedError) return err;
  if (err instanceof RagDocumentNotFoundError) return err;
  if (err instanceof RagDocumentRateLimitedError) return err;
  if (err instanceof RagIndexInProgressError) return err;
  if (err instanceof RagInternalError) return err;
  if (err instanceof RagNetworkError) return err;
  if (err instanceof TypeError) return new RagNetworkError(err.message, err);
  if (err instanceof Error) return new RagNetworkError(err.message, err);
  return new RagNetworkError("Unknown error");
}
