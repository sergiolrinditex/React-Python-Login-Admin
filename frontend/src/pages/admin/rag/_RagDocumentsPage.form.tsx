/**
 * Hilo People — RagDocumentsPage upload form section.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: Self-contained upload form for RagDocumentsPage.
 *   Extracted to keep RagDocumentsPage.tsx under the ~300 substantive line cap.
 *   Handles title, language, collection, file fields + client validation + dedup notice.
 *
 * §D-RAGDOC-FILESIZE-FORM: proactive split to honor file-size non-negotiable.
 *
 * Key deps: Dropzone, ValidationErrorInline, NetworkErrorView, useUploadDocument,
 *   useRagCollections, i18n namespace "rag".
 */

import type { CSSProperties, FormEvent, ReactNode } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { NetworkErrorView, ValidationErrorInline } from "./_RagDocumentsPage.error-views";
import { Dropzone } from "./_RagDocumentsPage.dropzone";
import type { RagCollection } from "../../../features/rag/domain/types";
import type { UseUploadDocumentResult } from "../../../features/rag/presentation/useUploadDocument";
import type { UseRagCollectionsResult } from "../../../features/rag/presentation/useRagCollections";
import {
  RagDocumentInvalidError,
  RagDocumentTooLargeError,
  type RagError,
} from "../../../features/rag/data/errors";
import { logVerbose, logError } from "../../../features/rag/data/logger";
import {
  UPLOAD_SECTION_STYLE,
  UPLOAD_SECTION_TITLE_STYLE,
  UPLOAD_FIELDS_GRID_STYLE,
  FIELD_GROUP_STYLE,
  FIELD_LABEL_STYLE,
  FIELD_INPUT_STYLE,
  FIELD_SELECT_STYLE,
  SUBMIT_ROW_STYLE,
  DEDUP_NOTICE_STYLE,
} from "./RagDocumentsPage.styles";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface UploadFormProps {
  uploadMutation: UseUploadDocumentResult;
  collectionsQuery: UseRagCollectionsResult;
  onUploadSuccess: (kind: "created" | "dedup") => void;
  onStatusMessage: (msg: string) => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Upload form section for RagDocumentsPage.
 *
 * @param props - {@link UploadFormProps}
 */
export function UploadForm({
  uploadMutation,
  collectionsQuery,
  onUploadSuccess,
  onStatusMessage,
}: UploadFormProps): ReactNode {
  const { t } = useTranslation("rag");

  const [file, setFile] = useState<File | null>(null);
  const [titleValue, setTitleValue] = useState("");
  const [language, setLanguage] = useState<"es" | "en" | "fr">("es");
  const [collectionId, setCollectionId] = useState("");
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [dedupNotice, setDedupNotice] = useState<string | null>(null);

  const collections: RagCollection[] = collectionsQuery.data ?? [];

  function validateForm(): boolean {
    const errors: Record<string, string> = {};
    if (!file) errors.file = t("documents.error.validation.file");
    if (!titleValue.trim()) errors.title = t("documents.error.validation.title");
    if (!language) errors.language = t("documents.error.validation.language");
    if (!collectionId) errors.collection = t("documents.error.validation.collection");
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: FormEvent<HTMLFormElement>): Promise<void> {
    e.preventDefault();
    setDedupNotice(null);
    if (!validateForm() || !file) return;

    logVerbose("rag.form.submit", { language, collection_id: collectionId });
    onStatusMessage(t("documents.upload.uploading"));

    try {
      const outcome = await uploadMutation.mutateAsync({
        file,
        title: titleValue.trim(),
        language,
        collection_id: collectionId,
      });

      if (outcome.kind === "dedup") {
        setDedupNotice(t("documents.upload.dedup"));
      }

      onStatusMessage(t("common:states.success", { defaultValue: "Operación completada" }));
      onUploadSuccess(outcome.kind);
      setFile(null);
      setTitleValue("");
      setCollectionId("");
      setFieldErrors({});
    } catch (err: unknown) {
      logError("rag.form.upload_error", { error: String(err) });
      onStatusMessage(t("documents.error.network"));
      _handleUploadError(err as RagError);
    }
  }

  function _handleUploadError(err: RagError): void {
    if (err instanceof RagDocumentInvalidError && err.field) {
      setFieldErrors({ [err.field]: err.message });
    } else if (err instanceof RagDocumentTooLargeError) {
      setFieldErrors({ file: t("documents.error.tooLarge", { maxMb: "25" }) });
    }
  }

  return (
    <section style={UPLOAD_SECTION_STYLE} aria-label={t("documents.upload.cta")}>
      <h2 style={UPLOAD_SECTION_TITLE_STYLE}>{t("documents.upload.cta")}</h2>

      {dedupNotice && (
        <div style={DEDUP_NOTICE_STYLE} role="status" data-testid="rag-dedup-notice">
          <TrackedLabel variant="muted">{dedupNotice}</TrackedLabel>
        </div>
      )}

      {uploadMutation.isError &&
        !(uploadMutation.error instanceof RagDocumentInvalidError) &&
        !(uploadMutation.error instanceof RagDocumentTooLargeError) && (
          <NetworkErrorView
            onRetry={() => uploadMutation.reset()}
            message={t("documents.error.network")}
          />
        )}

      <form onSubmit={(e) => void handleSubmit(e)} noValidate data-testid="rag-upload-form">
        <div style={UPLOAD_FIELDS_GRID_STYLE}>
          <div style={FIELD_GROUP_STYLE}>
            <label htmlFor="rag-title" style={FIELD_LABEL_STYLE}>
              {t("documents.upload.fields.title")}
            </label>
            <input
              id="rag-title"
              type="text"
              value={titleValue}
              onChange={(e) => {
                setTitleValue(e.target.value);
                if (fieldErrors.title) setFieldErrors((p) => ({ ...p, title: "" }));
              }}
              style={FIELD_INPUT_STYLE}
              aria-describedby={fieldErrors.title ? "rag-title-error" : undefined}
              aria-invalid={!!fieldErrors.title}
              disabled={uploadMutation.isPending}
              data-testid="rag-field-title"
            />
            {fieldErrors.title && (
              <ValidationErrorInline message={fieldErrors.title} id="rag-title-error" />
            )}
          </div>

          <div style={FIELD_GROUP_STYLE}>
            <label htmlFor="rag-language" style={FIELD_LABEL_STYLE}>
              {t("documents.upload.fields.language")}
            </label>
            <select
              id="rag-language"
              value={language}
              onChange={(e) => setLanguage(e.target.value as "es" | "en" | "fr")}
              style={FIELD_SELECT_STYLE}
              disabled={uploadMutation.isPending}
              data-testid="rag-field-language"
            >
              <option value="es">{t("documents.upload.fields.language.es")}</option>
              <option value="en">{t("documents.upload.fields.language.en")}</option>
              <option value="fr">{t("documents.upload.fields.language.fr")}</option>
            </select>
            {fieldErrors.language && (
              <ValidationErrorInline message={fieldErrors.language} id="rag-language-error" />
            )}
          </div>

          <div style={FIELD_GROUP_STYLE}>
            <label htmlFor="rag-collection" style={FIELD_LABEL_STYLE}>
              {t("documents.upload.fields.collection")}
            </label>
            <select
              id="rag-collection"
              value={collectionId}
              onChange={(e) => {
                setCollectionId(e.target.value);
                if (fieldErrors.collection) setFieldErrors((p) => ({ ...p, collection: "" }));
              }}
              style={FIELD_SELECT_STYLE}
              aria-describedby={fieldErrors.collection ? "rag-collection-error" : undefined}
              aria-invalid={!!fieldErrors.collection}
              disabled={uploadMutation.isPending || collectionsQuery.isLoading}
              data-testid="rag-field-collection"
            >
              <option value="">{t("documents.upload.fields.collection")}</option>
              {collections.map((col) => (
                <option key={col.id} value={col.id}>
                  {col.name}
                </option>
              ))}
            </select>
            {fieldErrors.collection && (
              <ValidationErrorInline message={fieldErrors.collection} id="rag-collection-error" />
            )}
          </div>
        </div>

        <Dropzone
          file={file}
          onFile={(f) => {
            setFile(f);
            if (fieldErrors.file) setFieldErrors((p) => ({ ...p, file: "" }));
          }}
          errorId={fieldErrors.file ? "rag-file-error" : undefined}
          disabled={uploadMutation.isPending}
        />
        {fieldErrors.file && (
          <ValidationErrorInline message={fieldErrors.file} id="rag-file-error" />
        )}

        <div style={SUBMIT_ROW_STYLE}>
          <SolidCTA
            type="submit"
            loading={uploadMutation.isPending}
            loadingLabel={t("documents.upload.uploading")}
            disabled={uploadMutation.isPending}
            width="auto"
            style={{ padding: "0.75rem 2rem" } as CSSProperties}
            aria-busy={uploadMutation.isPending ? "true" : undefined}
            aria-label={t("documents.upload.submit")}
            data-testid="rag-submit-btn"
          >
            {t("documents.upload.submit")}
          </SolidCTA>
        </div>
      </form>
    </section>
  );
}
