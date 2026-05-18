/**
 * Hilo People — AgentsPage.
 *
 * Slice/Phase: P04-S02-T005 — AgentsPage / Phase 4.
 * Route: /admin/ai/agents
 *
 * Responsibility: Admin page listing AI agents with per-row tool binding editor
 *   and inline agent run launcher.
 *   Consumes GET /api/v1/admin/ai/agents (list),
 *            PATCH /api/v1/admin/ai/agents/{id}/tools (set-replace tools),
 *            POST /api/v1/agents/runs (start run).
 *   Protected by RequireRole(['people_admin','super_admin']) at router level.
 *
 * §D-T005-PAGE (P04-S02-T005 task pack §8.3)
 *
 * UX states: loading, empty, error_network, error_validation, permission_denied, success.
 *
 * §D-T005-PER-ROW-MUTATION-STATE: ONE shared useMutation per operation + useMutationState.
 * §D-T005-OPTIMISTIC-TOOLS: optimistic cache updates on tool toggle.
 * §D-T005-502-INTENT: POST /runs 502 = expected dev sandbox evidence.
 * §D-T005-EMPTY-STATE: Wordmark + body, NO CTA (agents not user-created in v1).
 * §D-T005-FILESIZE-PROACTIVE: splits created proactively (styles + error-views + row + runDrawer).
 *
 * Design tokens: --color-bg, --color-ink, --color-paper, --font-display,
 *   --font-sans, --hairline, --tracking-label, --radius 0.
 * Components: AdminShell, HairlineTable, TrackedLabel, SolidCTA, StatusDot.
 *
 * Split files:
 *   AgentsPage.styles.ts — CSSProperties constants
 *   _AgentsPage.error-views.tsx — LoadingSkeletonView, EmptyView, NetworkErrorView, ForbiddenView
 *   _AgentsPage.row.tsx — AgentRow component with per-row tool editor
 *   _AgentsPage.runDrawer.tsx — AgentRunLauncher inline run form
 *
 * a11y: <table> with sr-only caption; every <th scope="col">; aria-busy on pending rows;
 *   aria-live region for run status; tap targets ≥ 44px.
 *
 * Security: React auto-escapes all agent.name renders. Never render agent.config (R-6).
 *
 * Non-negotiables §logging: BEFORE + AFTER on page render (verbose-gated).
 * Key deps: useAgents, useUpdateAgentTools, useStartAgentRun, AdminShell, HairlineTable, i18n.
 */

import type { ReactNode } from "react";
import { useState } from "react";
import { useTranslation } from "react-i18next";
import AdminShell from "../../../shared/design-system/AdminShell";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { useAuth } from "../../../features/auth/presentation/AuthProvider";
import { useAgents } from "../../../features/agents/presentation/useAgents";
import { useUpdateAgentTools } from "../../../features/agents/presentation/useUpdateAgentTools";
import { useStartAgentRun } from "../../../features/agents/presentation/useStartAgentRun";
import { AgentsForbiddenError } from "../../../features/agents/data/errors";
import type { AgentsError } from "../../../features/agents/data/errors";
import type { StartAgentRunResult } from "../../../features/agents/domain/types";
import { AgentRow } from "./_AgentsPage.row";
import {
  LoadingSkeletonView,
  EmptyView,
  NetworkErrorView,
  ForbiddenView,
} from "./_AgentsPage.error-views";
import {
  PAGE_HEADER_STYLE,
  PAGE_TITLE_STYLE,
  PAGE_SUBTITLE_STYLE,
  TABLE_STYLE,
  TH_STYLE,
  TH_FIRST_STYLE,
  TH_LAST_STYLE,
} from "./AgentsPage.styles";

// ---------------------------------------------------------------------------
// Nav items for AdminShell
// ---------------------------------------------------------------------------

const ADMIN_NAV_ITEMS = [
  { key: "agents", label: "AI Agents", active: true },
];

// ---------------------------------------------------------------------------
// AgentsPage
// ---------------------------------------------------------------------------

/**
 * Admin page for AI agent management.
 *
 * Protected by RequireRole(['people_admin','super_admin']) at router level.
 * Implements: loading, empty, error_network, error_validation, permission_denied, success.
 *
 * §D-T005-PAGE, §D-T005-PER-ROW-MUTATION-STATE, §D-T005-OPTIMISTIC-TOOLS
 *
 * @returns The AI agents admin page.
 */
export default function AgentsPage(): ReactNode {
  const { t } = useTranslation("agents");
  const { logout } = useAuth();

  /* BEFORE render log — §D-T005-PAGE */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("AgentsPage.render.start", {
      phase: "P04",
      slice: "P04-S02-T005",
      route: "/admin/ai/agents",
    });
  }

  const onAuthFailure = logout;

  // Per-row PATCH error tracking
  const [patchErrors, setPatchErrors] = useState<Record<string, AgentsError | null>>({});
  // Per-agent run error/result tracking
  const [runErrors, setRunErrors] = useState<Record<string, AgentsError | null>>({});
  const [runResults, setRunResults] = useState<Record<string, StartAgentRunResult | null>>({});

  const { data: agents, isLoading, isError, error, refetch } = useAgents(onAuthFailure);
  const { mutate: updateTools } = useUpdateAgentTools(onAuthFailure);
  const { mutate: startRun, isPending: runIsPending } = useStartAgentRun(onAuthFailure);

  /** Derive table state from query results. */
  function getTableState() {
    if (isLoading) return "loading";
    if (isError) {
      if (error instanceof AgentsForbiddenError) return "permission_denied";
      return "error_network";
    }
    if (!agents || agents.length === 0) return "empty";
    return "populated";
  }

  const tableState = getTableState();

  /** Handle per-row tool update. §D-T005-OPTIMISTIC-TOOLS */
  function handleUpdateTools(agentId: string, toolIds: string[]): void {
    setPatchErrors((prev) => ({ ...prev, [agentId]: null }));

    updateTools(
      { agentId, request: { tool_ids: toolIds } },
      {
        onError: (err) => {
          setPatchErrors((prev) => ({ ...prev, [agentId]: err as AgentsError }));
        },
      },
    );
  }

  /** Handle run launcher submission. §D-T005-RUN-LAUNCHER */
  function handleRun(agentId: string, input: string): void {
    setRunErrors((prev) => ({ ...prev, [agentId]: null }));
    setRunResults((prev) => ({ ...prev, [agentId]: null }));

    startRun(
      { agent_id: agentId, input },
      {
        onSuccess: (result: StartAgentRunResult) => {
          setRunResults((prev) => ({ ...prev, [agentId]: result }));
        },
        onError: (err) => {
          setRunErrors((prev) => ({ ...prev, [agentId]: err as AgentsError }));
        },
      },
    );
  }

  /* AFTER render log — verbose only */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("AgentsPage.render.state", {
      tableState,
      agentCount: agents?.length ?? 0,
      isLoading,
      isError,
    });
  }

  return (
    <AdminShell navItems={ADMIN_NAV_ITEMS} navAriaLabel={t("title")}>
      {/* aria-live region for run status — §D-T005-A11Y */}
      <div aria-live="polite" aria-atomic="false" className="sr-only" data-testid="agents-aria-live" />

      {/* Page header */}
      <header style={PAGE_HEADER_STYLE}>
        <h1 style={PAGE_TITLE_STYLE}>{t("title")}</h1>
        <p style={PAGE_SUBTITLE_STYLE}>{t("subtitle")}</p>
      </header>

      {/* Loading state */}
      {tableState === "loading" && <LoadingSkeletonView />}

      {/* Permission denied */}
      {tableState === "permission_denied" && <ForbiddenView />}

      {/* Error network with retry */}
      {tableState === "error_network" && (
        <NetworkErrorView onRetry={() => void refetch()} />
      )}

      {/* Empty state — §D-T005-EMPTY-STATE: no CTA */}
      {tableState === "empty" && <EmptyView />}

      {/* Populated table */}
      {tableState === "populated" && agents && (
        <table style={TABLE_STYLE} aria-label={t("title")}>
          <caption className="sr-only">{t("title")}</caption>
          <thead>
            <tr>
              <th scope="col" style={TH_FIRST_STYLE}>
                <TrackedLabel variant="muted">{t("columns.name")}</TrackedLabel>
              </th>
              <th scope="col" style={TH_STYLE}>
                <TrackedLabel variant="muted">{t("columns.enabled")}</TrackedLabel>
              </th>
              <th scope="col" style={TH_STYLE}>
                <TrackedLabel variant="muted">{t("columns.toolCount")}</TrackedLabel>
              </th>
              <th scope="col" style={TH_STYLE}>
                <TrackedLabel variant="muted">{t("columns.actions")}</TrackedLabel>
              </th>
              <th scope="col" style={TH_LAST_STYLE}>
                <TrackedLabel variant="muted">{t("run.title")}</TrackedLabel>
              </th>
            </tr>
          </thead>
          <tbody>
            {agents.map((agent) => (
              <AgentRow
                key={agent.id}
                agent={agent}
                availableTools={agent.bound_tools}
                onUpdateTools={handleUpdateTools}
                updateError={patchErrors[agent.id] ?? null}
                runIsPending={runIsPending}
                onRun={handleRun}
                runLastError={runErrors[agent.id] ?? null}
                runLastResult={runResults[agent.id] ?? null}
              />
            ))}
          </tbody>
        </table>
      )}
    </AdminShell>
  );
}
