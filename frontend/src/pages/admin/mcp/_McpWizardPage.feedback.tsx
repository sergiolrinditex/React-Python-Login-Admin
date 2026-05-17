/**
 * Hilo People — McpWizardPage feedback / status blocks.
 *
 * Slice/Phase: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: Presentational sub-components for McpWizardPage.tsx's
 *   non-form UX states — aria-live region, permission_denied block, success
 *   block, and form-level error block. Each is a single-responsibility,
 *   stateless block driven entirely by props. No data fetching, no business
 *   logic, no router calls beyond an injected onBack callback for the
 *   permission_denied state.
 *
 * §D-T004-PAGE-SPLIT-STYLES (R-6 mitigation): proactive helper split to honor
 *   the ~300-line file-size non-negotiable. R-6 in the task pack §11
 *   pre-authorizes `_McpWizardPage.<helper>.tsx` extraction. The blocks here
 *   are independent of the form rendering pipeline, so they live as their
 *   own visual concern.
 *
 * UX states covered (UX_CONTRACT.md /admin/ai/mcp/new row §4.2):
 *   - permission_denied — 403 McpForbiddenError; defensive (router guard
 *     normally catches first). Provides keyboard-accessible back link.
 *   - success — 201; brief block before auto-navigate (~600ms triggered
 *     inside useCreateMcpServer).
 *   - error_network / error_server — form-level inline error block.
 *   - aria-live polite — sr-only region announcing async network errors.
 *
 * a11y: aria-live region uses role="status" aria-live="polite" aria-atomic.
 *   Permission denied block uses role="alert". Success block uses role="status".
 *   Form-level error uses role="alert". All visual feedback also has a
 *   non-color signal (text content + structural separator).
 *
 * Design tokens: imports style constants only; no hardcoded literals.
 *
 * Key deps: style constants from _McpWizardPage.styles.ts; React only — no
 *   router, no i18n, no hooks (parent injects localized strings + handlers).
 */

import type { ReactNode } from "react";
import {
  SUCCESS_BLOCK_STYLE,
  SUCCESS_TITLE_STYLE,
  SUCCESS_BODY_STYLE,
  PERMISSION_DENIED_STYLE,
  PERMISSION_DENIED_TITLE_STYLE,
  FORM_ERROR_STYLE,
  CANCEL_BTN_STYLE,
} from "./_McpWizardPage.styles";

// ---------------------------------------------------------------------------
// AriaLiveRegion
// ---------------------------------------------------------------------------

/** Props for the sr-only aria-live region that announces async errors. */
export interface AriaLiveRegionProps {
  /** Message to announce — empty string means no announcement. */
  message: string;
}

/**
 * Screen-reader-only aria-live polite region.
 *
 * Mirrors the previously inlined block at McpWizardPage.tsx:264-273 — same
 * DOM, same data-testid, same aria attributes.
 */
export function AriaLiveRegion({ message }: AriaLiveRegionProps): ReactNode {
  return (
    <div
      role="status"
      aria-live="polite"
      aria-atomic="true"
      className="sr-only"
      data-testid="wizard-aria-live"
    >
      {message}
    </div>
  );
}

// ---------------------------------------------------------------------------
// PermissionDeniedBlock
// ---------------------------------------------------------------------------

/** Props for the 403 permission_denied UX state block. */
export interface PermissionDeniedBlockProps {
  /** Localized title (e.g. "No tienes permisos"). */
  title: string;
  /** Localized body text. */
  body: string;
  /** Localized label for the back button. */
  backLabel: string;
  /** Click handler firing navigation back to the MCP servers list. */
  onBack: () => void;
}

/**
 * Permission denied feedback block (403 McpForbiddenError).
 *
 * Defensive UI — the router-level `RequireRole` guard normally catches
 * forbidden access first. Provides a single back action so the user is
 * never trapped inside the form. Renders the same DOM previously inlined at
 * McpWizardPage.tsx:283-304.
 */
export function PermissionDeniedBlock({
  title,
  body,
  backLabel,
  onBack,
}: PermissionDeniedBlockProps): ReactNode {
  return (
    <div
      style={PERMISSION_DENIED_STYLE}
      role="alert"
      data-testid="wizard-permission-denied"
    >
      <p style={PERMISSION_DENIED_TITLE_STYLE}>{title}</p>
      <p style={{ margin: "0 0 1rem" }}>{body}</p>
      <button type="button" style={CANCEL_BTN_STYLE} onClick={onBack}>
        {backLabel}
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SuccessBlock
// ---------------------------------------------------------------------------

/** Props for the 201-success feedback block. */
export interface SuccessBlockProps {
  /** Localized success title. */
  title: string;
  /** Localized success body (e.g. "Redirigiendo…"). */
  body: string;
}

/**
 * Success feedback block (post-201).
 *
 * Shown briefly between the 201 response and the auto-navigate
 * (~600ms delay implemented inside useCreateMcpServer). Renders the same
 * DOM previously inlined at McpWizardPage.tsx:307-316.
 */
export function SuccessBlock({ title, body }: SuccessBlockProps): ReactNode {
  return (
    <div style={SUCCESS_BLOCK_STYLE} role="status" data-testid="wizard-success">
      <p style={SUCCESS_TITLE_STYLE}>{title}</p>
      <p style={SUCCESS_BODY_STYLE}>{body}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// FormLevelErrorBlock
// ---------------------------------------------------------------------------

/** Props for the form-level error block (rate-limited / network / 5xx). */
export interface FormLevelErrorBlockProps {
  /** Already-localized message to render. Parent decides rate-limited vs network. */
  message: string;
}

/**
 * Form-level error block rendered above the submit row.
 *
 * Covers the error_network UX state and any 429 rate-limited response. Parent
 * is responsible for choosing the localized message; this component is purely
 * presentational. Renders the same DOM previously inlined at
 * McpWizardPage.tsx:463-477, with the unreachable McpValidationError ternary
 * branch removed (validator KISS finding #2 — isFormLevelError predicate
 * already excludes McpValidationError, so the previous `instanceof` check was
 * dead code).
 */
export function FormLevelErrorBlock({
  message,
}: FormLevelErrorBlockProps): ReactNode {
  return (
    <div role="alert" style={FORM_ERROR_STYLE} data-testid="wizard-form-error">
      {message}
    </div>
  );
}
