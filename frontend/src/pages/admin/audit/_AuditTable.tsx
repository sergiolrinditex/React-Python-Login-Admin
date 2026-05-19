/**
 * Hilo People — AuditLogPage table sub-component.
 *
 * Slice/Phase: P04-S03-T001 — AuditLogPage / Phase 4 Complete Features.
 *
 * Responsibility: Renders the audit log table in the success state.
 *   Split from AuditLogPage.tsx to stay within the 300 LoC cap
 *   (one responsibility per file, one component per file).
 *
 * Decisions applied (D-T001-*):
 *   D-T001-METADATA-RENDER: Only request_id shown from metadata JSONB.
 *   D-T001-ACTOR-RENDER: actor_user_id rendered as xxxxxxxx… with full UUID in aria-label.
 *   D-T001-NO-COLOR: Monochrome only — audit rows have no status color.
 *   D-T001-A11Y: table+caption(sr-only)+th[scope=col].
 *
 * All rendering:
 *   - Uses i18n keys from the "audit" namespace.
 *   - Uses tokens.css custom properties — NO hardcoded colors/fonts.
 *
 * §D-T001-PAGE: Conditional write_set anchor for this file.
 * Source ref: §D-T001-PAGE, task pack §6 allowed_paths.
 */

import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import type { AuditLog } from "../../../features/audit/domain/types";
import {
  TABLE_WRAPPER_STYLE,
  TABLE_STYLE,
  THEAD_TR_STYLE,
  TH_STYLE,
  TD_STYLE,
  TD_MONO_STYLE,
  SR_ONLY_STYLE,
} from "./AuditLogPage.styles";

// ---------------------------------------------------------------------------
// Actor rendering (D-T001-ACTOR-RENDER)
// ---------------------------------------------------------------------------

/**
 * Renders actor_user_id as "xxxxxxxx…" (first 8 hex chars) with full UUID in aria-label.
 * PII safe: UUID is not PII; email is.
 * @param actorId - Full UUID string or null.
 * @returns Rendered actor element.
 */
function renderActor(actorId: string | null): ReactNode {
  if (!actorId) return <span aria-label="deleted user">—</span>;
  const short = actorId.replace(/-/g, "").slice(0, 8);
  return (
    <abbr title={actorId} aria-label={`Actor UUID: ${actorId}`} style={{ textDecoration: "none" }}>
      {short}…
    </abbr>
  );
}

// ---------------------------------------------------------------------------
// Metadata rendering (D-T001-METADATA-RENDER)
// ---------------------------------------------------------------------------

/**
 * Renders only the request_id from a metadata blob.
 * Full metadata expansion is v2 ("abrir detalle").
 * @param metadata - Raw JSONB metadata from the backend.
 * @returns request_id string or "—".
 */
function renderMetadata(metadata: Record<string, unknown>): string {
  const rid = metadata["request_id"];
  if (typeof rid === "string" && rid.length > 0) return rid.slice(0, 8) + "…";
  return "—";
}

// ---------------------------------------------------------------------------
// AuditTable
// ---------------------------------------------------------------------------

export interface AuditTableProps {
  rows: AuditLog[];
}

/**
 * Renders the audit log table with rows.
 * D-T001-A11Y: <table>+<caption>(sr-only)+<th scope="col">.
 */
export function AuditTable({ rows }: AuditTableProps): ReactNode {
  const { t } = useTranslation("audit");
  return (
    <div style={TABLE_WRAPPER_STYLE}>
      <table style={TABLE_STYLE} data-testid="audit-table">
        {/* sr-only caption for screen readers (D-T001-A11Y) */}
        <caption style={SR_ONLY_STYLE}>{t("table.caption")}</caption>
        <thead>
          <tr style={THEAD_TR_STYLE}>
            <th scope="col" style={TH_STYLE}>{t("table.col.timestamp")}</th>
            <th scope="col" style={TH_STYLE}>{t("table.col.actor")}</th>
            <th scope="col" style={TH_STYLE}>{t("table.col.action")}</th>
            <th scope="col" style={TH_STYLE}>{t("table.col.entityType")}</th>
            <th scope="col" style={TH_STYLE}>{t("table.col.entityId")}</th>
            <th scope="col" style={TH_STYLE}>{t("table.col.requestId")}</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.id}>
              <td style={TD_MONO_STYLE}>
                {new Date(row.created_at).toLocaleString()}
              </td>
              <td style={TD_STYLE}>{renderActor(row.actor_user_id)}</td>
              <td style={TD_STYLE}>{row.action}</td>
              <td style={TD_STYLE}>{row.entity_type ?? "—"}</td>
              <td style={TD_MONO_STYLE}>
                {row.entity_id ? row.entity_id.slice(0, 8) + "…" : "—"}
              </td>
              <td style={TD_MONO_STYLE}>{renderMetadata(row.metadata)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
