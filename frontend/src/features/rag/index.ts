/**
 * Hilo People — RAG feature barrel export.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Public API for the RAG feature module.
 *   Only exports symbols used by outside modules (pages, router).
 *   §D-RAGDOC-FEATURE-BARREL: follows features/chat and features/auth barrel pattern.
 */

// Domain types
export type {
  RagDocument,
  RagCollection,
  DocumentStatus,
  UploadDocumentRequest,
  UploadDocumentOutcome,
  IndexDocumentOutcome,
  ListDocumentsRequest,
  ListDocumentsResponse,
} from "./domain/types";
export { INFLIGHT_STATUSES, TERMINAL_STATUSES } from "./domain/types";

// Domain port
export type { IRagDocumentsRepository } from "./domain/RagDocumentsRepository";

// Data layer
export { ragRepository, RagRepository } from "./data/ragRepository";
export type { RagError } from "./data/errors";
export {
  RagDocumentInvalidError,
  RagDocumentTooLargeError,
  RagDocumentUnsupportedMimeError,
  RagPermissionDeniedError,
  RagDocumentNotFoundError,
  RagDocumentRateLimitedError,
  RagIndexInProgressError,
  RagInternalError,
  RagNetworkError,
  mapRagError,
} from "./data/errors";

// Presentation hooks
export { useRagDocuments } from "./presentation/useRagDocuments";
export { useRagCollections } from "./presentation/useRagCollections";
export { useUploadDocument } from "./presentation/useUploadDocument";
export { useIndexDocument } from "./presentation/useIndexDocument";
