/**
 * Hilo People — RagCollectionsPage.
 *
 * Slice/Phase: P04-S02-T002 — RagCollectionsPage / Phase 4 Complete Features.
 * Route: /admin/rag/collections | Auth: RequireRole(['people_admin','super_admin'])
 * Journey: J104 — RagDocumentsPage → RagCollectionsPage.
 *
 * Responsibility: Admin page to view and inline-edit RAG collections.
 *   Implements 6 mandatory UX states (UX_CONTRACT §3 row 33):
 *     1. loading — initial list fetch (aria-busy skeleton)
 *     2. empty — no collections (Wordmark + body, no CTA per §D-T002-EMPTY-NO-CTA)
 *     3. error_network — GET failed (NetworkErrorView + retry)
 *     4. error_validation — PATCH 400 (inline ValidationErrorInline per field)
 *     5. permission_denied — 403 (ForbiddenView)
 *     6. success — table with inline-editable rows
 *
 * Split companions (§D-T002-FILESIZE-*):
 *   - RagCollectionsPage.styles.ts (CSSProperties consts)
 *   - _RagCollectionsPage.row.tsx (editable collection table row)
 *   Reused from T001:
 *   - _RagDocumentsPage.error-views.tsx (LoadingSkeletonView, NetworkErrorView,
 *     ForbiddenView, ValidationErrorInline) per §D-T002-REUSE-ERROR-VIEWS
 *
 * §D-T002-ROUTER: route wired in app/router.tsx single-Route line.
 * §D-T002-A11Y-CAPTION: <table> includes sr-only <caption> (T001 missed this).
 * §D-T002-REUSE-LOADING-SKELETON: reuses LoadingSkeletonView from T001 error-views.
 *
 * Key deps: AdminShell, useRagCollections (REUSED), useUpdateCollection,
 *   i18n namespace "rag" (collections.*).
 */

import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import AdminShell from "../../../shared/design-system/AdminShell";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import Wordmark from "../../../shared/design-system/Wordmark";
import { useRagCollections } from "../../../features/rag/presentation/useRagCollections";
import { useUpdateCollection } from "../../../features/rag/presentation/useUpdateCollection";
import { RagPermissionDeniedError } from "../../../features/rag/data/errors";
import { logVerbose } from "../../../features/rag/data/logger";
import {
  LoadingSkeletonView,
  NetworkErrorView,
  ForbiddenView,
} from "./_RagDocumentsPage.error-views";
import { CollectionRow } from "./_RagCollectionsPage.row";
import {
  PAGE_HEADER_STYLE,
  PAGE_TITLE_STYLE,
  PAGE_SUBTITLE_STYLE,
  DOCUMENTS_LINK_STYLE,
  LIST_SECTION_TITLE_STYLE,
  TABLE_STYLE,
  TH_STYLE,
  LIVE_REGION_STYLE,
} from "./RagCollectionsPage.styles";

// ---------------------------------------------------------------------------
// Route constants (§D-T002-ROUTER)
// ---------------------------------------------------------------------------

/** Back-link route — documents page (P04-S02-T001). */
const ROUTE_ADMIN_RAG_DOCUMENTS = "/admin/rag/documents";

// ---------------------------------------------------------------------------
// Admin nav items (mirror T001 NAV_ITEMS with reversed active)
// ---------------------------------------------------------------------------

const NAV_ITEMS = [
  { key: "documents", label: "Documentos" },
  { key: "collections", label: "Colecciones", active: true },
];

// ---------------------------------------------------------------------------
// Empty view (local — no CTA per §D-T002-EMPTY-NO-CTA)
// ---------------------------------------------------------------------------

/**
 * Empty state — no collections. No CTA (creation out of scope).
 * §D-T002-EMPTY-NO-CTA: title + body only.
 */
function CollectionsEmptyView(): ReactNode {
  const { t } = useTranslation("rag");

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        padding: "4rem 2rem",
        textAlign: "center",
      }}
      data-testid="collections-empty-view"
    >
      <Wordmark size="1.5rem" />
      <TrackedLabel variant="active" style={{ marginTop: "1.5rem" }}>
        {t("collections.empty")}
      </TrackedLabel>
      <p
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.9375rem",
          color: "var(--color-ink)",
          opacity: 0.7,
          marginTop: "0.75rem",
          marginBottom: 0,
          maxWidth: "32rem",
          lineHeight: 1.5,
        }}
        data-testid="collections-empty-body"
      >
        {t("collections.empty.body")}
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Admin RAG collections page — view and inline-edit RAG collection settings.
 *
 * @returns The RagCollectionsPage React element.
 */
export default function RagCollectionsPage(): ReactNode {
  const { t } = useTranslation("rag");
  const navigate = useNavigate();
  const [liveMessage, setLiveMessage] = useState("");

  // Query and mutation hooks
  const collectionsQuery = useRagCollections();
  const updateMutation = useUpdateCollection();

  logVerbose("rag.page.RagCollectionsPage.render", {
    collections_status: collectionsQuery.status,
    update_pending: updateMutation.isPending,
  });

  // ---------------------------------------------------------------------------
  // Nav handlers
  // ---------------------------------------------------------------------------

  function handleNavClick(key: string): void {
    if (key === "documents") void navigate(ROUTE_ADMIN_RAG_DOCUMENTS);
  }

  // ---------------------------------------------------------------------------
  // Derived state
  // ---------------------------------------------------------------------------

  const isPermissionDenied = collectionsQuery.error instanceof RagPermissionDeniedError;
  const isNetworkError = !isPermissionDenied && collectionsQuery.isError;
  const isLoading = collectionsQuery.isLoading;
  const collections = collectionsQuery.data ?? [];
  const isEmpty = !isLoading && !collectionsQuery.isError && collections.length === 0;

  // ---------------------------------------------------------------------------
  // Update handler (fires live region announcement)
  // ---------------------------------------------------------------------------

  function handleUpdateStart(): void {
    setLiveMessage(t("collections.aria.updating"));
  }

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <AdminShell
      navItems={NAV_ITEMS.map((item) => ({
        ...item,
        onClick: () => handleNavClick(item.key),
      }))}
      navAriaLabel={t("collections.aria.list")}
    >
      {/* Aria-live region for status announcements */}
      <div
        aria-live="polite"
        aria-atomic="true"
        style={LIVE_REGION_STYLE}
        data-testid="collections-live-region"
      >
        {liveMessage}
      </div>

      {/* Page header */}
      <header style={PAGE_HEADER_STYLE}>
        <h1 style={PAGE_TITLE_STYLE}>{t("collections.heading")}</h1>
        <p style={PAGE_SUBTITLE_STYLE}>{t("collections.subtitle")}</p>
        <button
          type="button"
          style={DOCUMENTS_LINK_STYLE}
          onClick={() => void navigate(ROUTE_ADMIN_RAG_DOCUMENTS)}
          data-testid="nav-to-documents"
        >
          {t("collections.nav.documents")}
        </button>
      </header>

      {/* Permission denied — 403 */}
      {isPermissionDenied && <ForbiddenView />}

      {/* Collections list section */}
      {!isPermissionDenied && (
        <section
          aria-label={t("collections.aria.list")}
          aria-busy={isLoading ? "true" : undefined}
        >
          <h2 style={LIST_SECTION_TITLE_STYLE}>{t("collections.title")}</h2>

          {isLoading && <LoadingSkeletonView />}

          {isNetworkError && !isLoading && (
            <NetworkErrorView
              onRetry={() => void collectionsQuery.refetch()}
              message={t("collections.error.network")}
            />
          )}

          {isEmpty && !isNetworkError && <CollectionsEmptyView />}

          {!isLoading && !isNetworkError && collections.length > 0 && (
            <table
              style={TABLE_STYLE}
              data-testid="rag-collections-table"
            >
              {/* §D-T002-A11Y-CAPTION: sr-only caption improves screen-reader experience */}
              <caption className="sr-only">
                {t("collections.table.caption")}
              </caption>
              <thead>
                <tr>
                  {[
                    t("collections.table.col.name"),
                    t("collections.table.col.vertical"),
                    t("collections.table.col.language"),
                    t("collections.table.col.enabled"),
                  ].map((col) => (
                    <th key={col} scope="col" style={TH_STYLE}>
                      <TrackedLabel variant="muted">{col}</TrackedLabel>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {collections.map((collection) => (
                  <tr key={collection.id} data-testid={`coll-row-${collection.id}`}>
                    <CollectionRow
                      collection={collection}
                      updateMutation={updateMutation}
                      onUpdateStart={handleUpdateStart}
                    />
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </section>
      )}
    </AdminShell>
  );
}
