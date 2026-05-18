/**
 * Hilo People — AgentsPage agent row component.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 *
 * Responsibility: Single agent row with per-row tools editor and run launcher.
 *   Extracted from AgentsPage.tsx to keep parent under the ~300-line cap.
 *   §D-T005-PAGE-SPLIT-ROW.
 *
 * §D-T005-PAGE-SPLIT-ROW (P04-S02-T005 task pack §8.3)
 * §D-T005-PER-ROW-MUTATION-STATE: renders pending state via useMutationState.
 * §D-T005-OPTIMISTIC-TOOLS: shows pending tool update via optimistic cache.
 * §D-T005-VALIDATION-INLINE-PER-ROW: PATCH 400 errors rendered inline below the row.
 * §D-T005-A11Y: aria-busy on row while PATCH pending; aria-label on all CTAs.
 *   Tap target ≥ 44px on all CTAs.
 *
 * Security: agent.name rendered as React children (auto-escaped — no XSS risk).
 *   agent.config is NEVER rendered (R-6 PII risk).
 */

import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { useMutationState } from "@tanstack/react-query";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import StatusDot from "../../../shared/design-system/StatusDot";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import type { Agent, BoundTool, StartAgentRunResult } from "../../../features/agents/domain/types";
import type { AgentsError } from "../../../features/agents/data/errors";
import {
  AgentsToolNotFoundError,
  AgentsToolNotApprovedError,
  AgentsAgentNotFoundError,
} from "../../../features/agents/data/errors";
import { UPDATE_AGENT_TOOLS_MUTATION_KEY } from "../../../features/agents/presentation/useUpdateAgentTools";
import { AgentRunLauncher } from "./_AgentsPage.runDrawer";
import {
  TD_FIRST_STYLE,
  TD_STYLE,
  TD_LAST_STYLE,
  AGENT_NAME_STYLE,
  AGENT_DESC_STYLE,
  EM_DASH_STYLE,
  INLINE_ERROR_STYLE,
} from "./AgentsPage.styles";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AgentRowProps {
  agent: Agent;
  availableTools: BoundTool[];
  onUpdateTools: (agentId: string, toolIds: string[]) => void;
  updateError: AgentsError | null;
  /** Run launcher state */
  runIsPending: boolean;
  onRun: (agentId: string, input: string) => void;
  runLastError: AgentsError | null;
  runLastResult: StartAgentRunResult | null;
}

// ---------------------------------------------------------------------------
// AgentRow
// ---------------------------------------------------------------------------

/**
 * Single agent row with per-row tools editor and run launcher.
 *
 * §D-T005-PER-ROW-MUTATION-STATE: uses useMutationState to derive per-row pending state.
 * §D-T005-A11Y: aria-busy on row while PATCH pending; per-tool toggle aria-label.
 *
 * @param props - {@link AgentRowProps}
 */
export function AgentRow({
  agent,
  availableTools,
  onUpdateTools,
  updateError,
  runIsPending,
  onRun,
  runLastError,
  runLastResult,
}: AgentRowProps): ReactNode {
  const { t } = useTranslation("agents");
  const { t: tErrors } = useTranslation("errors");

  // §D-T005-PER-ROW-MUTATION-STATE: derive pending state for THIS row from shared mutation
  const mutationStates = useMutationState({
    filters: {
      mutationKey: UPDATE_AGENT_TOOLS_MUTATION_KEY,
      status: "pending",
    },
    select: (mutation) => mutation.state.variables,
  });

  const isRowPending = mutationStates.some(
    (vars) => (vars as { agentId?: string })?.agentId === agent.id,
  );

  const boundToolIds = new Set(agent.bound_tools.map((t) => t.id));

  /** Handle tool checkbox toggle — commits set-replace immediately. */
  function handleToolToggle(toolId: string, checked: boolean): void {
    const newIds = new Set(boundToolIds);
    if (checked) {
      newIds.add(toolId);
    } else {
      newIds.delete(toolId);
    }
    onUpdateTools(agent.id, Array.from(newIds));
  }

  /** Derive inline error message for PATCH errors. */
  function getPatchErrorMessage(): string | null {
    if (!updateError) return null;
    if (updateError instanceof AgentsToolNotFoundError) {
      return tErrors("AGENT_TOOL_NOT_FOUND");
    }
    if (updateError instanceof AgentsToolNotApprovedError) {
      return tErrors("AGENT_TOOL_NOT_APPROVED");
    }
    if (updateError instanceof AgentsAgentNotFoundError) {
      return tErrors("AGENT_NOT_FOUND");
    }
    return null;
  }

  const patchErrorMessage = getPatchErrorMessage();
  const toolCount = agent.bound_tools.length;
  const enabledStatus: "active" | "inactive" = agent.enabled ? "active" : "inactive";

  return (
    <>
      <tr
        aria-busy={isRowPending ? "true" : undefined}
        data-testid={`agent-row-${agent.id}`}
      >
        {/* Agent name + description — R-6: never render agent.config */}
        <td style={TD_FIRST_STYLE}>
          <span style={AGENT_NAME_STYLE}>{agent.name}</span>
          {agent.description && (
            <p style={AGENT_DESC_STYLE}>{agent.description}</p>
          )}
        </td>

        {/* Enabled status */}
        <td style={TD_STYLE}>
          <StatusDot
            state={enabledStatus}
            label={agent.enabled ? t("columns.enabled") : "—"}
          />
        </td>

        {/* Tool count */}
        <td style={TD_STYLE}>
          {toolCount > 0 ? (
            <TrackedLabel variant="muted">{toolCount}</TrackedLabel>
          ) : (
            <span style={EM_DASH_STYLE} aria-label={t("tools.none")}>—</span>
          )}
        </td>

        {/* Tools editor — per-row multi-select committed on change (set-replace) */}
        <td style={TD_STYLE}>
          {availableTools.length > 0 ? (
            <div role="group" aria-label={t("tools.add")}>
              {availableTools.map((tool) => (
                <label
                  key={tool.id}
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: "0.375rem",
                    minHeight: "44px",
                    cursor: isRowPending ? "not-allowed" : "pointer",
                    fontFamily: "var(--font-sans)",
                    fontSize: "0.875rem",
                    color: "var(--color-ink)",
                  }}
                >
                  <input
                    type="checkbox"
                    checked={boundToolIds.has(tool.id)}
                    disabled={isRowPending}
                    onChange={(e) => handleToolToggle(tool.id, e.target.checked)}
                    aria-label={`${t("tools.add")}: ${tool.name} (${agent.name})`}
                    data-testid={`agent-tool-toggle-${agent.id}-${tool.id}`}
                    style={{ width: "1rem", height: "1rem" }}
                  />
                  {tool.name}
                </label>
              ))}
            </div>
          ) : (
            <span style={EM_DASH_STYLE} aria-label={t("tools.none")}>—</span>
          )}
        </td>

        {/* Run launcher */}
        <td style={TD_LAST_STYLE}>
          <AgentRunLauncher
            agentId={agent.id}
            agentName={agent.name}
            isPending={runIsPending}
            onRun={onRun}
            lastError={runLastError}
            lastResult={runLastResult}
          />
        </td>
      </tr>

      {/* §D-T005-VALIDATION-INLINE-PER-ROW: PATCH error row */}
      {patchErrorMessage && (
        <tr data-testid={`agent-patch-error-${agent.id}`}>
          <td colSpan={5} style={{ padding: "0 0 0.5rem 0", borderBottom: "none" }}>
            <span style={INLINE_ERROR_STYLE} role="alert">{patchErrorMessage}</span>
          </td>
        </tr>
      )}
    </>
  );
}

// ---------------------------------------------------------------------------
// Helper: derive available tools from agent list (passed from page)
// ---------------------------------------------------------------------------

/**
 * Utility to extract all unique approved tools available from all agents.
 * Used by AgentsPage to pass to each row.
 */
export function extractAvailableTools(agents: Agent[]): BoundTool[] {
  const seen = new Set<string>();
  const tools: BoundTool[] = [];

  for (const agent of agents) {
    for (const tool of agent.bound_tools) {
      if (!seen.has(tool.id)) {
        seen.add(tool.id);
        tools.push(tool);
      }
    }
  }

  return tools;
}
