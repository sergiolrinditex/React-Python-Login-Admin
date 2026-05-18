/**
 * Hilo People — AgentsPage run launcher.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Inline agent run launcher per agent row.
 *   Input + SolidCTA "Run" flat surface — NO modal, NO drawer overlay.
 *   §D-T005-RUN-LAUNCHER-FORM: editorial flat surface.
 *
 * §D-T005-RUN-LAUNCHER (P04-S02-T005 task pack §8.3)
 * §D-T005-RUN-VALIDATION-AND-DISABLED: client-side validation for empty/>4000 input;
 *   409 AGENT_DISABLED rendered inline near launcher.
 * §D-T005-502-INTENT: 502 mapped to retryable AGENT_RUN_FAILED error.
 *
 * Security: input text never logged (§D-T005-LOGS-PII-CLEAN).
 *
 * a11y: §D-T005-A11Y: aria-live region for run status; aria-label on CTA with agent.name.
 *   Tap target ≥ 44px on CTA.
 */

import type { ReactNode } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import {
  AgentsAgentDisabledError,
  AgentsRunUnreachableError,
  AgentsRateLimitedError,
} from "../../../features/agents/data/errors";
import type { AgentsError } from "../../../features/agents/data/errors";
import type { StartAgentRunResult } from "../../../features/agents/domain/types";
import {
  RUN_FORM_STYLE,
  RUN_INPUT_STYLE,
  RUN_RESULT_STYLE,
  INLINE_ERROR_STYLE,
} from "./AgentsPage.styles";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentRunLauncherProps {
  agentId: string;
  agentName: string;
  isPending: boolean;
  onRun: (agentId: string, input: string) => void;
  lastError: AgentsError | null;
  lastResult: StartAgentRunResult | null;
}

// ---------------------------------------------------------------------------
// AgentRunLauncher
// ---------------------------------------------------------------------------

/**
 * Inline run launcher for a single agent.
 *
 * Flat form: input + run button. Shows result status or error inline.
 * §D-T005-RUN-LAUNCHER-FORM: no modal, no drawer overlay.
 *
 * @param props - {@link AgentRunLauncherProps}
 * @returns Inline run launcher.
 */
export function AgentRunLauncher({
  agentId,
  agentName,
  isPending,
  onRun,
  lastError,
  lastResult,
}: AgentRunLauncherProps): ReactNode {
  const { t } = useTranslation("agents");
  const { t: tErrors } = useTranslation("errors");
  const [input, setInput] = useState("");
  const [validationError, setValidationError] = useState<string | null>(null);

  const MAX_INPUT = 4000;

  /** §D-T005-RUN-VALIDATION-AND-DISABLED: client-side validation. */
  function handleRun(): void {
    setValidationError(null);

    if (input.trim().length === 0) {
      setValidationError(t("run.errors.empty"));
      return;
    }

    if (input.length > MAX_INPUT) {
      setValidationError(t("run.errors.tooLong", { max: MAX_INPUT }));
      return;
    }

    onRun(agentId, input);
  }

  /** Derive inline error message from the last mutation error. */
  function getErrorMessage(): string | null {
    if (validationError) return validationError;
    if (!lastError) return null;

    if (lastError instanceof AgentsAgentDisabledError) {
      return t("run.errors.disabled");
    }

    if (lastError instanceof AgentsRunUnreachableError) {
      return tErrors("AGENT_RUN_FAILED");
    }

    if (lastError instanceof AgentsRateLimitedError) {
      return t("errors.run_rate_limited");
    }

    return tErrors("UNKNOWN");
  }

  const errorMessage = getErrorMessage();
  const buttonLabel = isPending ? t("actions.running") : t("actions.run");

  return (
    <div>
      {/* §D-T005-A11Y: aria-live region for run status */}
      <div aria-live="polite" aria-atomic="true" className="sr-only" data-testid={`agents-run-aria-live-${agentId}`} />

      <div style={RUN_FORM_STYLE}>
        <input
          type="text"
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setValidationError(null);
          }}
          placeholder={t("run.inputPlaceholder")}
          aria-label={t("run.title")}
          disabled={isPending}
          maxLength={MAX_INPUT}
          style={RUN_INPUT_STYLE}
          data-testid={`agents-run-input-${agentId}`}
        />
        <SolidCTA
          onClick={handleRun}
          disabled={isPending}
          aria-label={`${buttonLabel}: ${agentName}`}
          width="auto"
          style={{ padding: "0.5rem 1rem", minHeight: "44px", fontSize: "0.8125rem" }}
          data-testid={`agents-run-btn-${agentId}`}
        >
          {buttonLabel}
        </SolidCTA>
      </div>

      {/* §D-T005-VALIDATION-INLINE-PER-ROW: inline error near launcher */}
      {errorMessage && (
        <p
          style={INLINE_ERROR_STYLE}
          role="alert"
          data-testid={`agents-run-error-${agentId}`}
        >
          {errorMessage}
        </p>
      )}

      {/* Success: show run_id + status */}
      {lastResult && !lastError && (
        <p style={RUN_RESULT_STYLE} data-testid={`agents-run-result-${agentId}`}>
          {t("run.success", { status: lastResult.status })}
        </p>
      )}
    </div>
  );
}
