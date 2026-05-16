/**
 * Hilo People — RagDocumentsPage document row.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: A single row in the HairlineTable for a RAG document.
 *   Shows title, language, collection, status (StatusDot + TrackedLabel),
 *   and the "Index" / "Re-index" action button.
 *
 * §D-RAGDOC-FILESIZE-ROW: extracted to keep RagDocumentsPage.tsx under cap.
 *
 * Token compliance: NO hex literals, NO border-radius, NO decorative shadows.
 * Accessibility: status described by text + dot; action button has descriptive label.
 */

import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import StatusDot from "../../../shared/design-system/StatusDot";
import type { StatusDotState } from "../../../shared/design-system/StatusDot";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import type { RagDocument, DocumentStatus } from "../../../features/rag/domain/types";

// ---------------------------------------------------------------------------
// Status → StatusDot mapping
// ---------------------------------------------------------------------------

function getStatusDotState(status: DocumentStatus): StatusDotState {
  switch (status) {
    case "indexed":
      return "active";
    case "failed":
      return "error";
    case "processing":
    case "pending":
      return "syncing";
    case "uploaded":
    default:
      return "inactive";
  }
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const ACTION_BTN_STYLE: CSSProperties = {
  background: "transparent",
  border: "var(--hairline)",
  borderRadius: 0,
  padding: "0.25rem 0.75rem",
  fontFamily: "var(--font-sans)",
  fontSize: "0.6875rem",
  letterSpacing: "var(--tracking-label)",
  textTransform: "uppercase",
  color: "var(--color-ink)",
  cursor: "pointer",
  minHeight: "44px",
};

const ACTION_BTN_DISABLED_STYLE: CSSProperties = {
  ...ACTION_BTN_STYLE,
  opacity: 0.38,
  cursor: "not-allowed",
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface DocumentRowProps {
  /** The document data to display. */
  document: RagDocument;
  /** Collection name for display. */
  collectionName: string | undefined;
  /** Called when the index/re-index action is triggered. */
  onIndex: (id: string) => void;
  /** Whether the index action is currently pending for this document. */
  isIndexing: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Single document row for the HairlineTable.
 *
 * Accessibility:
 *   - Index/re-index button has descriptive aria-label including document id (not title).
 *   - Status communicated via StatusDot (dot + text — never color alone).
 *
 * @param props - {@link DocumentRowProps}
 */
export function DocumentRow({
  document,
  collectionName,
  onIndex,
  isIndexing,
}: DocumentRowProps): ReactNode {
  const { t } = useTranslation("rag");

  // §D-T001-DEBUG-C1-ROW-PREDICATE: the Index CTA must be enabled whenever the
  // document is NOT actively being indexed AND a collection_id is bound. The
  // previous predicate tied `canIndex` to `isTerminal` (status ∈ {indexed,
  // failed}), which permanently disabled the button for status="uploaded" —
  // the canonical happy-path state right after upload per backend
  // `service_upload.py` and accepted by `service_index.py`. Now we disable
  // only for in-flight states (pending|processing) or while the local mutation
  // is in flight.
  const isInFlight =
    document.status === "processing" || document.status === "pending" || isIndexing;
  const canIndex = !!document.collection_id && !isInFlight;

  const statusDotState = getStatusDotState(document.status);
  const statusLabel = t(`documents.status.${document.status}`, {
    defaultValue: document.status,
  });

  // §D-T001-DEBUG-C1-LABEL: keep the button label as a single i18n key
  // ("documents.action.index"). The previous code inverted the label by
  // showing `index.inProgress` for already-indexed (terminal) rows. We now
  // surface progress purely via `aria-busy` + the in-flight TrackedLabel in
  // the status cell, which is what assistive tech announces. KISS over
  // adding a separate "reindex" key set per locale.
  const indexLabel = t("documents.action.index");

  return (
    <>
      <td
        style={{
          borderBottom: "var(--hairline)",
          padding: "0.75rem 0",
          fontFamily: "var(--font-sans)",
          fontSize: "0.875rem",
        }}
        data-testid={`doc-row-title-${document.id}`}
      >
        {document.title}
      </td>
      <td
        style={{ borderBottom: "var(--hairline)", padding: "0.75rem 0" }}
        data-testid={`doc-row-lang-${document.id}`}
      >
        <TrackedLabel variant="muted">
          {t(`common:language.${document.language}`, { defaultValue: document.language })}
        </TrackedLabel>
      </td>
      <td
        style={{ borderBottom: "var(--hairline)", padding: "0.75rem 0" }}
        data-testid={`doc-row-collection-${document.id}`}
      >
        <span style={{ fontFamily: "var(--font-sans)", fontSize: "0.875rem", opacity: 0.7 }}>
          {collectionName ?? "—"}
        </span>
      </td>
      <td
        style={{ borderBottom: "var(--hairline)", padding: "0.75rem 0" }}
        data-testid={`doc-row-status-${document.id}`}
      >
        <StatusDot
          state={statusDotState}
          label={statusLabel}
          aria-label={`Estado: ${statusLabel}`}
        />
        {isInFlight && (
          <TrackedLabel
            variant="muted"
            style={{ display: "block", marginTop: "0.25rem" }}
            aria-live="polite"
          >
            {t("documents.action.index.inProgress")}
          </TrackedLabel>
        )}
      </td>
      <td style={{ borderBottom: "var(--hairline)", padding: "0.75rem 0" }}>
        <button
          type="button"
          disabled={!canIndex || isInFlight}
          style={canIndex && !isInFlight ? ACTION_BTN_STYLE : ACTION_BTN_DISABLED_STYLE}
          aria-label={`${indexLabel} doc ${document.id}`}
          aria-busy={isInFlight ? "true" : undefined}
          onClick={() => canIndex && !isInFlight && onIndex(document.id)}
          data-testid={`doc-row-index-btn-${document.id}`}
        >
          {isInFlight ? t("documents.action.index.inProgress") : indexLabel}
        </button>
      </td>
    </>
  );
}
