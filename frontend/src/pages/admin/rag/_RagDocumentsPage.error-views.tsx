/**
 * Hilo People — RagDocumentsPage error/empty sub-views.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Self-contained error/empty view components for RagDocumentsPage.
 *   Extracted proactively to keep RagDocumentsPage.tsx under the ~250 LOC target.
 *   Pattern from _HistoryPage.error-views.tsx (P03-S02-T003 §D-T003-PAGE-SPLIT-ERRORVIEWS)
 *   and _AccountPage.error-views.tsx (P03-S02-T004 §D-T004-FILESIZE-EXTRACT-SUBCOMPONENT).
 *
 * §D-RAGDOC-FILESIZE-ERRORVIEWS: internal to the page module (not a route).
 *
 * Token compliance: NO hex literals, NO border-radius > 0, NO decorative shadows.
 */

import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import Wordmark from "../../../shared/design-system/Wordmark";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  padding: "4rem 2rem",
  textAlign: "center",
};

const BODY_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.9375rem",
  color: "var(--color-ink)",
  opacity: 0.7,
  marginBottom: "1.5rem",
  maxWidth: "32rem",
  lineHeight: 1.5,
};

const BODY_P_STYLE: CSSProperties = {
  ...BODY_STYLE,
  marginTop: "0.75rem",
  marginBottom: "1.5rem",
};

const ERROR_CONTAINER_STYLE: CSSProperties = {
  padding: "2rem",
  border: "var(--hairline)",
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
};

// ---------------------------------------------------------------------------
// EmptyView
// ---------------------------------------------------------------------------

/**
 * Empty state — no documents yet.
 * Wordmark + body + upload CTA.
 * §D-RAGDOC-EMPTY-BODY: must include explanatory body paragraph (lesson from T003 debug cycle 2).
 *
 * @param onUploadCta - Called when the CTA is clicked.
 */
export function EmptyView({ onUploadCta }: { onUploadCta: () => void }): ReactNode {
  const { t } = useTranslation("rag");

  return (
    <div style={CONTAINER_STYLE} data-testid="rag-empty-view">
      <Wordmark size="1.5rem" />
      <TrackedLabel variant="active" style={{ marginTop: "1.5rem" }}>
        {t("documents.empty")}
      </TrackedLabel>
      <p style={BODY_P_STYLE} data-testid="rag-empty-body">
        {t("documents.empty.body")}
      </p>
      <SolidCTA onClick={onUploadCta} width="auto" style={{ padding: "0.75rem 2rem" }}>
        {t("documents.empty.cta")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// NetworkErrorView
// ---------------------------------------------------------------------------

/**
 * Network error state — fetch failed.
 * Inline retry CTA.
 *
 * @param onRetry - Called when the retry button is clicked.
 * @param message - Optional custom error message.
 */
export function NetworkErrorView({
  onRetry,
  message,
}: {
  onRetry: () => void;
  message?: string;
}): ReactNode {
  const { t } = useTranslation("rag");
  const displayMessage = message ?? t("documents.error.network");

  return (
    <div
      role="alert"
      aria-live="assertive"
      style={ERROR_CONTAINER_STYLE}
      data-testid="rag-network-error-view"
    >
      <TrackedLabel variant="active">{displayMessage}</TrackedLabel>
      <SolidCTA onClick={onRetry} width="auto" style={{ padding: "0.5rem 1.5rem" }}>
        {t("common:actions.retry", { defaultValue: "Reintentar" })}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ForbiddenView
// ---------------------------------------------------------------------------

/**
 * Permission denied state — 403 from backend.
 * Admin role was missing or revoked.
 */
export function ForbiddenView(): ReactNode {
  const { t } = useTranslation("rag");

  return (
    <div
      role="alert"
      style={CONTAINER_STYLE}
      data-testid="rag-forbidden-view"
    >
      <TrackedLabel variant="muted">
        {t("documents.error.permission")}
      </TrackedLabel>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ValidationErrorInline
// ---------------------------------------------------------------------------

/**
 * Inline validation error message for the upload form.
 *
 * @param message - Error message to display.
 * @param id - HTML id for aria-describedby association.
 */
export function ValidationErrorInline({
  message,
  id,
}: {
  message: string;
  id: string;
}): ReactNode {
  return (
    <span
      id={id}
      role="alert"
      style={{
        fontFamily: "var(--font-sans)",
        fontSize: "0.75rem",
        color: "var(--color-ink)",
        opacity: 0.85,
        display: "block",
        marginTop: "0.25rem",
      }}
      data-testid={`validation-error-${id}`}
    >
      {message}
    </span>
  );
}

// ---------------------------------------------------------------------------
// LoadingSkeletonView
// ---------------------------------------------------------------------------

const SKELETON_ROW_STYLE: CSSProperties = {
  height: "2.5rem",
  background: "var(--color-bg)",
  borderBottom: "var(--hairline)",
  opacity: 0.5,
};

/**
 * Loading skeleton placeholder for the document list.
 * Uses aria-busy="true" live region for accessibility.
 */
export function LoadingSkeletonView(): ReactNode {
  return (
    <div
      aria-busy="true"
      aria-label="Cargando documentos"
      data-testid="rag-loading-skeleton"
    >
      {[1, 2, 3].map((i) => (
        <div key={i} style={SKELETON_ROW_STYLE} />
      ))}
    </div>
  );
}
