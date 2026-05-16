/**
 * Hilo People — RagDocumentsPage.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 * Route: /admin/rag/documents | Auth: RequireRole(['people_admin','super_admin'])
 * Journey: J104 — RagDocumentsPage → RagCollectionsPage.
 *
 * Responsibility: Admin page to upload, list and manage RAG documents.
 *   Implements 8 mandatory UX states (§D-RAGDOC-STATES-EIGHT):
 *     1. loading — initial list fetch
 *     2. empty — no documents yet
 *     3. uploading — POST /admin/rag/documents in flight
 *     4. indexing — at least one doc in {uploaded|pending|processing}
 *     5. error_network — list or upload network failure
 *     6. error_validation — 422/400 field-level errors
 *     7. permission_denied — 403 surfaced after login
 *     8. success — list visible, rows with status + actions
 *
 * Split companions (§D-RAGDOC-FILESIZE-*):
 *   - RagDocumentsPage.styles.ts (CSSProperties consts)
 *   - _RagDocumentsPage.error-views.tsx (EmptyView, NetworkErrorView, ForbiddenView)
 *   - _RagDocumentsPage.form.tsx (upload form section)
 *   - _RagDocumentsPage.dropzone.tsx (HTML5 native dropzone)
 *   - _RagDocumentsPage.row.tsx (document table row)
 *
 * Key deps: AdminShell, HairlineTable, useRagDocuments, useUploadDocument,
 *   useIndexDocument, useRagCollections, i18n namespace "rag".
 */

import type { ReactNode } from "react";
import { useState } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import AdminShell from "../../../shared/design-system/AdminShell";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { useRagDocuments } from "../../../features/rag/presentation/useRagDocuments";
import { useRagCollections } from "../../../features/rag/presentation/useRagCollections";
import { useUploadDocument } from "../../../features/rag/presentation/useUploadDocument";
import { useIndexDocument } from "../../../features/rag/presentation/useIndexDocument";
import { RagPermissionDeniedError } from "../../../features/rag/data/errors";
import { logVerbose } from "../../../features/rag/data/logger";
import {
  EmptyView,
  NetworkErrorView,
  ForbiddenView,
  LoadingSkeletonView,
} from "./_RagDocumentsPage.error-views";
import { UploadForm } from "./_RagDocumentsPage.form";
import { DocumentRow } from "./_RagDocumentsPage.row";
import {
  PAGE_HEADER_STYLE,
  PAGE_TITLE_STYLE,
  PAGE_SUBTITLE_STYLE,
  COLLECTIONS_LINK_STYLE,
  LIST_SECTION_TITLE_STYLE,
  LIVE_REGION_STYLE,
} from "./RagDocumentsPage.styles";

// ---------------------------------------------------------------------------
// Route constants (§D-RAGDOC-ROUTER)
// ---------------------------------------------------------------------------

/** Next action route — collections page (P04-S02-T002). */
const ROUTE_ADMIN_RAG_COLLECTIONS = "/admin/rag/collections";

// ---------------------------------------------------------------------------
// Admin nav items
// ---------------------------------------------------------------------------

const NAV_ITEMS = [
  { key: "documents", label: "Documentos", active: true },
  { key: "collections", label: "Colecciones" },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Admin RAG documents page — upload, list and index RAG documents.
 *
 * @returns The RagDocumentsPage React element.
 */
export default function RagDocumentsPage(): ReactNode {
  const { t } = useTranslation("rag");
  const navigate = useNavigate();
  const [liveMessage, setLiveMessage] = useState("");

  // Query and mutation hooks
  const docsQuery = useRagDocuments();
  const collectionsQuery = useRagCollections();
  const uploadMutation = useUploadDocument();
  const indexMutation = useIndexDocument();

  logVerbose("rag.page.RagDocumentsPage.render", {
    docs_status: docsQuery.status,
    upload_pending: uploadMutation.isPending,
  });

  // ---------------------------------------------------------------------------
  // Nav handlers
  // ---------------------------------------------------------------------------

  function handleNavClick(key: string): void {
    if (key === "collections") void navigate(ROUTE_ADMIN_RAG_COLLECTIONS);
  }

  // ---------------------------------------------------------------------------
  // Index handler
  // ---------------------------------------------------------------------------

  function handleIndex(docId: string): void {
    logVerbose("rag.page.RagDocumentsPage.index", { doc_id: docId });
    setLiveMessage(t("documents.aria.indexing"));
    indexMutation.mutate(docId);
  }

  // ---------------------------------------------------------------------------
  // Derived state
  // ---------------------------------------------------------------------------

  const isPermissionDenied = docsQuery.error instanceof RagPermissionDeniedError;
  const isNetworkError =
    !isPermissionDenied && docsQuery.isError;
  const isLoading = docsQuery.isLoading;
  const docs = docsQuery.data?.data ?? [];
  const isEmpty = !isLoading && !docsQuery.isError && docs.length === 0;
  const collections = collectionsQuery.data ?? [];

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <AdminShell
      navItems={NAV_ITEMS.map((item) => ({
        ...item,
        onClick: () => handleNavClick(item.key),
      }))}
      navAriaLabel={t("documents.aria.list")}
    >
      {/* Aria-live region for status announcements */}
      <div
        aria-live="polite"
        aria-atomic="true"
        style={LIVE_REGION_STYLE}
        data-testid="rag-live-region"
      >
        {liveMessage}
      </div>

      {/* Page header */}
      <header style={PAGE_HEADER_STYLE}>
        <h1 style={PAGE_TITLE_STYLE}>{t("documents.heading")}</h1>
        <p style={PAGE_SUBTITLE_STYLE}>{t("documents.subtitle")}</p>
        <button
          type="button"
          style={COLLECTIONS_LINK_STYLE}
          onClick={() => void navigate(ROUTE_ADMIN_RAG_COLLECTIONS)}
          data-testid="nav-to-collections"
        >
          {t("documents.nav.collections")}
        </button>
      </header>

      {/* Permission denied — 403 */}
      {isPermissionDenied && <ForbiddenView />}

      {/* Upload form section — always visible to admitted admins */}
      {!isPermissionDenied && (
        <UploadForm
          uploadMutation={uploadMutation}
          collectionsQuery={collectionsQuery}
          onUploadSuccess={(_kind) => {
            /* list refetches automatically via invalidateQueries in useUploadDocument */
          }}
          onStatusMessage={setLiveMessage}
        />
      )}

      {/* Document list section */}
      {!isPermissionDenied && (
        <section
          aria-label={t("documents.aria.list")}
          aria-busy={isLoading ? "true" : undefined}
        >
          <h2 style={LIST_SECTION_TITLE_STYLE}>{t("documents.title")}</h2>

          {isLoading && <LoadingSkeletonView />}

          {isNetworkError && !isLoading && (
            <NetworkErrorView
              onRetry={() => void docsQuery.refetch()}
              message={t("documents.error.network")}
            />
          )}

          {isEmpty && !isNetworkError && (
            <EmptyView onUploadCta={() => window.scrollTo({ top: 0, behavior: "smooth" })} />
          )}

          {!isLoading && !isNetworkError && docs.length > 0 && (
            <table
              style={{
                width: "100%",
                borderCollapse: "collapse",
                fontFamily: "var(--font-sans)",
              }}
              data-testid="rag-docs-table"
            >
              <thead>
                <tr>
                  {[
                    t("documents.table.col.title"),
                    t("documents.table.col.language"),
                    t("documents.table.col.collection"),
                    t("documents.table.col.status"),
                    t("documents.table.col.actions"),
                  ].map((col) => (
                    <th
                      key={col}
                      scope="col"
                      style={{
                        borderBottom: "var(--hairline)",
                        padding: "0.5rem 0",
                        textAlign: "left",
                        fontWeight: "inherit",
                      }}
                    >
                      <TrackedLabel variant="muted">{col}</TrackedLabel>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {docs.map((doc) => (
                  <tr key={doc.id} data-testid={`doc-row-${doc.id}`}>
                    <DocumentRow
                      document={doc}
                      collectionName={
                        collections.find((c) => c.id === doc.collection_id)?.name
                      }
                      onIndex={handleIndex}
                      isIndexing={
                        indexMutation.isPending && indexMutation.variables === doc.id
                      }
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
