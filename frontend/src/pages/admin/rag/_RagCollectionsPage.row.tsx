/**
 * Hilo People — RagCollectionsPage collection row.
 *
 * Slice/Phase: P04-S02-T002 — RagCollectionsPage / Phase 4 Complete Features.
 *
 * Responsibility: A single editable row in the collections table.
 *   Inline-editable fields: vertical (text input), language (select), enabled (toggle).
 *   Name is read-only (editing out of scope per acceptance criteria).
 *   Fires PATCH per field on commit:
 *     - vertical: onBlur + Enter
 *     - language: onChange
 *     - enabled: onClick toggle
 *
 * §D-T002-FILESIZE-ROW: extracted to keep RagCollectionsPage.tsx under cap.
 * §D-T002-INLINE-EDIT: commit policy per field type.
 * §D-T002-VERTICAL-FREE-INPUT: free text input for vertical.
 * §D-T002-LANGUAGE-NULL-READ-ONLY-CLEAR: null lang shown as "—"; cannot PATCH to null.
 * §D-T002-LOGS-PII-CLEAN: logs field keys only, never values.
 *
 * Token compliance: NO hex literals, NO border-radius, NO decorative shadows.
 * Accessibility: toggle is role="switch" with aria-checked; inputs are labeled.
 */

import { useState, useCallback, type ReactNode, type KeyboardEvent } from "react";
import { useTranslation } from "react-i18next";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { ValidationErrorInline } from "./_RagDocumentsPage.error-views";
import type { RagCollection } from "../../../features/rag/domain/types";
import type { UseMutationResult } from "@tanstack/react-query";
import type { UpdateCollectionRequest, UpdateCollectionOutcome } from "../../../features/rag/domain/types";
import type { RagError } from "../../../features/rag/data/errors";
import { RagDocumentInvalidError } from "../../../features/rag/data/errors";
import {
  TD_STYLE,
  FIELD_INPUT_STYLE,
  FIELD_SELECT_STYLE,
  TOGGLE_BTN_STYLE,
} from "./RagCollectionsPage.styles";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface CollectionRowProps {
  /** Collection data to display. */
  collection: RagCollection;
  /** Update mutation to fire on field commit. */
  updateMutation: UseMutationResult<
    UpdateCollectionOutcome,
    RagError,
    UpdateCollectionRequest,
    unknown
  >;
  /** Called when a mutation begins — for aria-live announcements. */
  onUpdateStart?: () => void;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Single editable collection row in the HairlineTable.
 *
 * Accessibility:
 *   - Vertical input has aria-label.
 *   - Language select has aria-label.
 *   - Enabled toggle is role="switch" with aria-checked.
 *
 * @param props - {@link CollectionRowProps}
 */
export function CollectionRow({ collection, updateMutation, onUpdateStart }: CollectionRowProps): ReactNode {
  const { t } = useTranslation("rag");

  // Local state for the vertical text input (controlled).
  const [verticalDraft, setVerticalDraft] = useState(collection.vertical);
  // Per-field error state (only one field at a time).
  const [fieldError, setFieldError] = useState<{ field?: string; message: string } | null>(null);

  // ---------------------------------------------------------------------------
  // Helpers
  // ---------------------------------------------------------------------------

  const handleMutate = useCallback(
    (patch: UpdateCollectionRequest["patch"]) => {
      setFieldError(null);
      onUpdateStart?.();
      updateMutation.mutate(
        { id: collection.id, patch },
        {
          onError: (err: RagError) => {
            if (err instanceof RagDocumentInvalidError) {
              setFieldError({
                field: err.field,
                message: err.field
                  ? t(`collections.error.validation.${err.field}`, {
                      defaultValue: t("collections.error.validation.body"),
                    })
                  : t("collections.error.validation.body"),
              });
            }
          },
        },
      );
    },
    [collection.id, updateMutation, t, onUpdateStart],
  );

  // ---------------------------------------------------------------------------
  // Vertical handlers (free text input)
  // ---------------------------------------------------------------------------

  const handleVerticalBlur = useCallback(() => {
    const trimmed = verticalDraft.trim();
    if (!trimmed || trimmed === collection.vertical) {
      setVerticalDraft(collection.vertical);
      return;
    }
    handleMutate({ vertical: trimmed });
  }, [verticalDraft, collection.vertical, handleMutate]);

  const handleVerticalKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === "Enter") {
        e.currentTarget.blur();
      }
    },
    [],
  );

  // ---------------------------------------------------------------------------
  // Language handler (select onChange)
  // ---------------------------------------------------------------------------

  const handleLanguageChange = useCallback(
    (value: string) => {
      if (value === "" || value === collection.language) return;
      const lang = value as "es" | "en" | "fr";
      handleMutate({ language: lang });
    },
    [collection.language, handleMutate],
  );

  // ---------------------------------------------------------------------------
  // Enabled toggle
  // ---------------------------------------------------------------------------

  const handleToggle = useCallback(() => {
    handleMutate({ enabled: !collection.enabled });
  }, [collection.enabled, handleMutate]);

  // ---------------------------------------------------------------------------
  // Derived
  // ---------------------------------------------------------------------------

  const isPending = updateMutation.isPending && updateMutation.variables?.id === collection.id;
  const languageDisplay = collection.language ?? "null";
  const languageLabel = t(`collections.language.${languageDisplay}`, { defaultValue: "—" });

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  const verticalErrorId = `vertical-error-${collection.id}`;
  const languageErrorId = `language-error-${collection.id}`;

  return (
    <>
      {/* Name — read-only */}
      <td style={TD_STYLE} data-testid={`coll-row-name-${collection.id}`}>
        <TrackedLabel variant="muted">{collection.name}</TrackedLabel>
      </td>

      {/* Vertical — free text input */}
      <td style={TD_STYLE} data-testid={`coll-row-vertical-${collection.id}`}>
        <input
          type="text"
          value={verticalDraft}
          maxLength={64}
          style={FIELD_INPUT_STYLE}
          aria-label={t("collections.table.col.vertical")}
          aria-describedby={fieldError?.field === "vertical" ? verticalErrorId : undefined}
          onChange={(e) => setVerticalDraft(e.target.value)}
          onBlur={handleVerticalBlur}
          onKeyDown={handleVerticalKeyDown}
          disabled={isPending}
          data-testid={`coll-row-vertical-input-${collection.id}`}
        />
        {fieldError?.field === "vertical" && (
          <ValidationErrorInline
            id={verticalErrorId}
            message={fieldError.message}
          />
        )}
        {!fieldError?.field && fieldError && (
          <ValidationErrorInline
            id={`body-error-${collection.id}`}
            message={fieldError.message}
          />
        )}
      </td>

      {/* Language — select (es|en|fr; null shown as — but cannot be sent) */}
      <td style={TD_STYLE} data-testid={`coll-row-language-${collection.id}`}>
        <select
          style={FIELD_SELECT_STYLE}
          value={collection.language ?? ""}
          aria-label={t("collections.table.col.language")}
          aria-describedby={fieldError?.field === "language" ? languageErrorId : undefined}
          onChange={(e) => handleLanguageChange(e.target.value)}
          disabled={isPending}
          data-testid={`coll-row-language-select-${collection.id}`}
        >
          {/* If currently null, show — as a display-only option */}
          {collection.language === null && (
            <option value="">{t("collections.language.null", { defaultValue: "—" })}</option>
          )}
          <option value="es">{t("collections.language.es")}</option>
          <option value="en">{t("collections.language.en")}</option>
          <option value="fr">{t("collections.language.fr")}</option>
        </select>
        {fieldError?.field === "language" && (
          <ValidationErrorInline
            id={languageErrorId}
            message={fieldError.message}
          />
        )}
        {/* Display label for screenreaders */}
        <span className="sr-only">{languageLabel}</span>
      </td>

      {/* Enabled — toggle switch */}
      <td style={TD_STYLE} data-testid={`coll-row-enabled-${collection.id}`}>
        <button
          type="button"
          role="switch"
          aria-checked={collection.enabled}
          aria-label={t("collections.aria.enabled_toggle", { name: collection.id })}
          style={TOGGLE_BTN_STYLE}
          onClick={handleToggle}
          disabled={isPending}
          data-testid={`coll-row-toggle-${collection.id}`}
        >
          {collection.enabled
            ? t("collections.enabled.on")
            : t("collections.enabled.off")}
        </button>
      </td>
    </>
  );
}
