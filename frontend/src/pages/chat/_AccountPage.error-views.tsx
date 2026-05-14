/**
 * Hilo People — AccountPage error-view subcomponents.
 *
 * Slice/Phase: P03-S02-T004 — AccountPage / Phase 3 (debugger cycle 1).
 *
 * Responsibility: Presentational subcomponents for the non-success states
 *   rendered by `AccountPage.tsx`:
 *     - ForbiddenView      — permission_denied (403 from useMe).
 *     - NetworkErrorView   — error_network (5xx / fetch failure from useMe).
 *
 *   Extracted verbatim from AccountPage.tsx to honor the file-size non-negotiable
 *   (`.claude/rules/01-non-negotiables.md §File size`).
 *
 * Anchor: §D-T004-FILESIZE-EXTRACT-SUBCOMPONENT (debugger cycle 1).
 *
 * Behavior, props, ids, role/aria-live and data-testid attributes are preserved
 * bit-for-bit. No business logic; both views are pure props-in / JSX-out.
 */

import { type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import SolidCTA from "../../shared/design-system/SolidCTA";
import { ERROR_CONTAINER_STYLE, ERROR_TEXT_STYLE } from "./AccountPage.styles";

interface ForbiddenViewProps {
  message: string;
  onSignIn: () => void;
}

/**
 * permission_denied state: 403 from getMe or RequireAuth redirect for 401.
 */
export function ForbiddenView({ message, onSignIn }: ForbiddenViewProps): ReactNode {
  const { t } = useTranslation(["common"]);
  return (
    <div
      style={ERROR_CONTAINER_STYLE}
      role="status"
      aria-live="assertive"
      data-testid="forbidden-view"
    >
      <p style={ERROR_TEXT_STYLE}>{message}</p>
      <SolidCTA
        onClick={onSignIn}
        aria-label={t("common:actions.back")}
        data-testid="forbidden-sign-in-cta"
      >
        {t("common:actions.back")}
      </SolidCTA>
    </div>
  );
}

interface NetworkErrorViewProps {
  message: string;
  onRetry: () => void;
  loading: boolean;
}

/**
 * error_network state: 5xx or fetch failure from getMe.
 */
export function NetworkErrorView({ message, onRetry, loading }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation(["common"]);
  return (
    <div
      style={ERROR_CONTAINER_STYLE}
      role="status"
      aria-live="assertive"
      data-testid="network-error-view"
    >
      <p style={ERROR_TEXT_STYLE}>{message}</p>
      <SolidCTA
        onClick={onRetry}
        loading={loading}
        loadingLabel="…"
        aria-label={t("common:actions.retry")}
        data-testid="network-error-retry-cta"
      >
        {t("common:actions.retry")}
      </SolidCTA>
    </div>
  );
}
