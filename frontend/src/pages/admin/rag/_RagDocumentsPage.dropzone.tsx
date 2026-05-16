/**
 * Hilo People — RagDocumentsPage upload dropzone.
 *
 * Slice/Phase: P04-S02-T001 — RagDocumentsPage / Phase 4 Complete Features.
 *
 * Responsibility: HTML5 native file dropzone + input for PDF/DOCX uploads.
 *   NO react-dropzone — doable in <20 lines per §01-non-negotiables §Dependencies.
 *   Accepts .pdf, .docx (MIME: application/pdf, application/vnd.openxmlformats-...).
 *   Shows drag-over visual state. Accessible: labelled file input + aria-label on zone.
 *
 * §D-RAGDOC-FILESIZE-DROPZONE: extracted to keep RagDocumentsPage.tsx under cap.
 *
 * Token compliance: NO hex literals, NO border-radius, NO box-shadow.
 */

import type { CSSProperties, DragEvent, ChangeEvent, ReactNode } from "react";
import { useState, useRef } from "react";
import { useTranslation } from "react-i18next";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";

// ---------------------------------------------------------------------------
// Accepted MIME types
// ---------------------------------------------------------------------------

const ACCEPTED_MIMES =
  ".pdf,.docx,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document";

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const DROPZONE_BASE_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  justifyContent: "center",
  padding: "1.5rem",
  border: "var(--hairline)",
  cursor: "pointer",
  textAlign: "center",
  gap: "0.5rem",
  background: "var(--color-paper)",
  transition: "opacity 150ms",
};

const DROPZONE_DRAG_OVER_STYLE: CSSProperties = {
  opacity: 0.6,
};

const HINT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.75rem",
  color: "var(--color-ink)",
  opacity: 0.5,
};

const SELECTED_FILENAME_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.8125rem",
  color: "var(--color-ink)",
  opacity: 0.8,
};

const VISUALLY_HIDDEN: CSSProperties = {
  position: "absolute",
  width: "1px",
  height: "1px",
  padding: 0,
  margin: "-1px",
  overflow: "hidden",
  clip: "rect(0,0,0,0)",
  whiteSpace: "nowrap",
  border: 0,
};

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface DropzoneProps {
  /** Current selected file (controlled). */
  file: File | null;
  /** Called when the user selects or drops a file. */
  onFile: (file: File) => void;
  /** Validation error message for this field. */
  errorId?: string;
  /** Whether the dropzone is disabled (during upload). */
  disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * HTML5 native file dropzone for PDF/DOCX uploads.
 *
 * Accessible:
 *   - Visible <label> htmlFor the hidden <input>.
 *   - aria-label on the drag zone.
 *   - Focus + Enter/Space activates the file picker via ref click.
 *   - aria-describedby links to validation error when present.
 *
 * @param props - {@link DropzoneProps}
 */
export function Dropzone({ file, onFile, errorId, disabled = false }: DropzoneProps): ReactNode {
  const { t } = useTranslation("rag");
  const [isDragOver, setIsDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  function handleDragOver(e: DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    if (!disabled) setIsDragOver(true);
  }

  function handleDragLeave(): void {
    setIsDragOver(false);
  }

  function handleDrop(e: DragEvent<HTMLDivElement>): void {
    e.preventDefault();
    setIsDragOver(false);
    if (disabled) return;
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFile(dropped);
  }

  function handleChange(e: ChangeEvent<HTMLInputElement>): void {
    const selected = e.target.files?.[0];
    if (selected) onFile(selected);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLDivElement>): void {
    if ((e.key === "Enter" || e.key === " ") && !disabled) {
      e.preventDefault();
      inputRef.current?.click();
    }
  }

  const zoneStyle: CSSProperties = {
    ...DROPZONE_BASE_STYLE,
    ...(isDragOver && !disabled ? DROPZONE_DRAG_OVER_STYLE : {}),
    ...(disabled ? { opacity: 0.38, cursor: "not-allowed" } : {}),
  };

  return (
    <div>
      {/* Visually hidden label — screen readers announce this */}
      <label
        htmlFor="rag-file-input"
        style={VISUALLY_HIDDEN}
      >
        {t("documents.upload.fields.file")}
      </label>

      {/* Visible dropzone area */}
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-label={t("documents.upload.fields.file")}
        aria-describedby={errorId}
        aria-disabled={disabled ? "true" : undefined}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => !disabled && inputRef.current?.click()}
        onKeyDown={handleKeyDown}
        style={zoneStyle}
        data-testid="rag-dropzone"
      >
        <TrackedLabel variant={file ? "active" : "muted"}>
          {file ? "" : t("documents.upload.fields.file")}
        </TrackedLabel>

        {file ? (
          <span style={SELECTED_FILENAME_STYLE} data-testid="rag-selected-filename">
            {/* Only show filename length and type — not full name for PII safety */}
            {file.name}
          </span>
        ) : (
          <span style={HINT_STYLE} data-testid="rag-dropzone-hint">
            {t("documents.upload.fields.file.hint")}
          </span>
        )}
      </div>

      {/* Hidden native file input */}
      <input
        id="rag-file-input"
        ref={inputRef}
        type="file"
        accept={ACCEPTED_MIMES}
        onChange={handleChange}
        disabled={disabled}
        style={VISUALLY_HIDDEN}
        data-testid="rag-file-input"
        aria-hidden="true"
      />
    </div>
  );
}
