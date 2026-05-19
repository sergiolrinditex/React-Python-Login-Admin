/**
 * Hilo People — AuditLogPage filter form sub-component.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Audit filter form bar.
 *   Split from AuditLogPage.tsx to stay within the 300 LoC cap
 *   (one responsibility per file, one component per file).
 *
 * Decisions applied (D-T001-*):
 *   D-T001-FILTER-UX: Two date inputs + free-text actor UUID + action datalist.
 *   D-T001-ACTION-FILTER: Free-text + datalist of AUDIT_KNOWN_ACTIONS.
 *
 * All rendering:
 *   - Uses i18n keys from the "audit" namespace.
 *   - Uses tokens.css custom properties — NO hardcoded colors/fonts.
 *   - a11y: all inputs have labels, 44x44 tap targets.
 *
 * §D-T001-PAGE: Conditional write_set anchor for this file.
 * Source ref: §D-T001-PAGE, task pack §6 allowed_paths.
 */

import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { AUDIT_KNOWN_ACTIONS } from "../../../features/audit/index";
import {
  FILTERS_STYLE,
  FILTER_FIELD_STYLE,
  FILTER_LABEL_STYLE,
  FILTER_INPUT_STYLE,
  FILTER_SUBMIT_STYLE,
  FILTER_RESET_STYLE,
} from "./AuditLogPage.styles";

// ---------------------------------------------------------------------------
// AuditFilters
// ---------------------------------------------------------------------------

export interface AuditFiltersProps {
  fromValue: string;
  toValue: string;
  actorValue: string;
  actionValue: string;
  onFromChange: (v: string) => void;
  onToChange: (v: string) => void;
  onActorChange: (v: string) => void;
  onActionChange: (v: string) => void;
  onSubmit: () => void;
  onReset: () => void;
}

/**
 * Audit filter form (D-T001-FILTER-UX).
 * Two date inputs + free-text actor UUID + action datalist.
 * a11y: all inputs have labels, 44x44 tap targets.
 */
export function AuditFilters({
  fromValue, toValue, actorValue, actionValue,
  onFromChange, onToChange, onActorChange, onActionChange,
  onSubmit, onReset,
}: AuditFiltersProps): ReactNode {
  const { t } = useTranslation("audit");
  const datalistId = "audit-action-datalist";

  const handleSubmit = (e: React.FormEvent): void => {
    e.preventDefault();
    onSubmit();
  };

  return (
    <form onSubmit={handleSubmit} style={FILTERS_STYLE} aria-label={t("table.caption")}>
      {/* From date */}
      <div style={FILTER_FIELD_STYLE}>
        <label htmlFor="audit-from" style={FILTER_LABEL_STYLE}>
          {t("filters.from")}
        </label>
        <input
          id="audit-from"
          type="date"
          value={fromValue}
          onChange={(e) => onFromChange(e.target.value)}
          style={FILTER_INPUT_STYLE}
          data-testid="audit-filter-from"
        />
      </div>

      {/* To date */}
      <div style={FILTER_FIELD_STYLE}>
        <label htmlFor="audit-to" style={FILTER_LABEL_STYLE}>
          {t("filters.to")}
        </label>
        <input
          id="audit-to"
          type="date"
          value={toValue}
          onChange={(e) => onToChange(e.target.value)}
          style={FILTER_INPUT_STYLE}
          data-testid="audit-filter-to"
        />
      </div>

      {/* Actor UUID */}
      <div style={FILTER_FIELD_STYLE}>
        <label htmlFor="audit-actor" style={FILTER_LABEL_STYLE}>
          {t("filters.actor")}
        </label>
        <input
          id="audit-actor"
          type="text"
          value={actorValue}
          onChange={(e) => onActorChange(e.target.value)}
          placeholder={t("filters.actor.placeholder")}
          style={FILTER_INPUT_STYLE}
          data-testid="audit-filter-actor"
        />
      </div>

      {/* Action — free-text + datalist (D-T001-ACTION-FILTER) */}
      <div style={FILTER_FIELD_STYLE}>
        <label htmlFor="audit-action" style={FILTER_LABEL_STYLE}>
          {t("filters.action")}
        </label>
        <input
          id="audit-action"
          type="text"
          list={datalistId}
          value={actionValue}
          onChange={(e) => onActionChange(e.target.value)}
          placeholder={t("filters.action.placeholder")}
          style={FILTER_INPUT_STYLE}
          data-testid="audit-filter-action"
        />
        <datalist id={datalistId}>
          {AUDIT_KNOWN_ACTIONS.map((action) => (
            <option key={action} value={action} />
          ))}
        </datalist>
      </div>

      {/* Submit */}
      <button
        type="submit"
        style={FILTER_SUBMIT_STYLE}
        data-testid="audit-filter-submit"
      >
        {t("filters.submit")}
      </button>

      {/* Reset */}
      <button
        type="button"
        onClick={onReset}
        style={FILTER_RESET_STYLE}
        data-testid="audit-filter-reset"
      >
        {t("filters.reset")}
      </button>
    </form>
  );
}
