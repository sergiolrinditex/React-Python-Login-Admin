/**
 * Hilo People — ModelWizardPage.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-PAGE (canonical Coverage Registry write target)
 *
 * Responsibility: Admin AI wizard — "Nuevo modelo" at /admin/ai/models/new.
 *   Steps: 1) select provider + name, 2) enter credentials, 3) models list post-create.
 *   Renders all 6 required UX states:
 *     loading (submitting), empty (models=[]), error_network, error_validation,
 *     permission_denied, success.
 *
 *   Step renderers (ProviderStep, CredentialsStep, ModelsStep) live in
 *   sibling files (./_ModelWizardPage.provider-step.tsx,
 *   ./_ModelWizardPage.credentials-step.tsx, ./_ModelWizardPage.models-step.tsx)
 *   to keep this orchestrator within the ~300-line cap
 *   (`.claude/rules/01-non-negotiables.md §file-size`).
 *
 * Decisions applied:
 *   D-T003-STEP-MACHINE: provider → credentials → submitting → models (success|empty)
 *   D-T003-SECRET-SECURITY: secret_plain lives only in hook state; cleared on submit/unmount.
 *   D-T003-LOGS-PII-CLEAN: provider_type, auth_type, name_len only — never secret or name.
 *   D-T003-NO-MOBILE-FRAME: admin pages are desktop-only (AdminShell direct).
 *   D-T003-ACCESSIBILITY: labels, aria-live, focus, keyboard nav, WCAG AA.
 *   D-T003-ROUTER: wired in router.tsx inside RequireRole block (§D-T003-ROUTER).
 *   D-T003-INVALIDATE-CACHE: invalidates ["admin","ai","models"] on success.
 *   D-T003-NEXT-ACTION: after success → test model or back to /admin/ai/models.
 *   D-T003-422-FIELD-ERRORS: surfaces field-level backend errors per input.
 *   D-T003-FILESIZE-SPLIT-STEPS: step views extracted to _ModelWizardPage.steps.tsx.
 *
 * Route: /admin/ai/models/new (RequireRole — people_admin|super_admin).
 * Journey refs: J103 (participates; does NOT close — T004 and e2e remain).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 * Security: secret_plain NEVER in DOM (type=password), logs, or storage.
 *
 * Key deps: useModelWizard (hook), AdminShell, ./_ModelWizardPage.provider-step,
 *   ./_ModelWizardPage.credentials-step, ./_ModelWizardPage.models-step,
 *   react-i18next, react-router.
 */

import { useState, type ReactNode } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import AdminShell from "../../../shared/design-system/AdminShell";
import type { AdminNavItem } from "../../../shared/design-system/AdminShell";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { useModelWizard } from "../../../features/admin-ai/presentation/useModelWizard";
import { logVerbose, logWarn } from "../../../features/admin-ai/data/logger";
import {
  ROUTE_ADMIN,
  ROUTE_ADMIN_AI_MODELS,
  ROUTE_ADMIN_AI_MODELS_NEW,
  ROUTE_ADMIN_RAG_DOCUMENTS,
  ROUTE_ADMIN_RAG_COLLECTIONS,
  ROUTE_ADMIN_AI_MCP,
  ROUTE_ADMIN_AI_MCP_NEW,
  ROUTE_ADMIN_AI_AGENTS,
  ROUTE_ADMIN_AUDIT,
  ROUTE_ADMIN_USAGE,
} from "../../../app/router";
import {
  PAGE_TITLE,
  PAGE_SUBTITLE,
  CENTER_BLOCK,
  BODY_TEXT,
  STEP_INDICATOR,
} from "./ModelWizardPage.styles";
import { ProviderStep } from "./_ModelWizardPage.provider-step";
import { CredentialsStep } from "./_ModelWizardPage.credentials-step";
import { ModelsStep } from "./_ModelWizardPage.models-step";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * ModelWizardPage — multi-step wizard to create a new AI provider + credentials.
 *
 * Renders AdminShell with 10 nav items. Steps: provider → credentials → models.
 * Handles all 6 UX states: loading, empty, error_network, error_validation,
 * permission_denied, success. Step views are extracted to
 * ./_ModelWizardPage.steps.tsx; this file owns the state-machine wiring,
 * navigation and the accessibility container.
 *
 * @returns The model wizard page.
 */
export default function ModelWizardPage(): ReactNode {
  const { t } = useTranslation(["admin-ai"]);
  const navigate = useNavigate();
  const wizard = useModelWizard();
  const [showSecret, setShowSecret] = useState(false);

  logVerbose("admin-ai.page.ModelWizardPage.render.start", {
    step: wizard.step,
    submission_state: wizard.submissionState,
  });

  // ---------------------------------------------------------------------------
  // Nav items
  // ---------------------------------------------------------------------------

  const navItems: AdminNavItem[] = [
    { key: "dashboard", label: t("admin-ai:nav.dashboard"), onClick: () => navigate(ROUTE_ADMIN) },
    { key: "models", label: t("admin-ai:nav.models"), onClick: () => navigate(ROUTE_ADMIN_AI_MODELS) },
    { key: "modelsNew", label: t("admin-ai:nav.modelsNew"), active: true, onClick: () => navigate(ROUTE_ADMIN_AI_MODELS_NEW) },
    { key: "ragDocuments", label: t("admin-ai:nav.ragDocuments"), onClick: () => navigate(ROUTE_ADMIN_RAG_DOCUMENTS) },
    { key: "ragCollections", label: t("admin-ai:nav.ragCollections"), onClick: () => navigate(ROUTE_ADMIN_RAG_COLLECTIONS) },
    { key: "mcpServers", label: t("admin-ai:nav.mcpServers"), onClick: () => navigate(ROUTE_ADMIN_AI_MCP) },
    { key: "mcpNew", label: t("admin-ai:nav.mcpNew"), onClick: () => navigate(ROUTE_ADMIN_AI_MCP_NEW) },
    { key: "agents", label: t("admin-ai:nav.agents"), onClick: () => navigate(ROUTE_ADMIN_AI_AGENTS) },
    { key: "audit", label: t("admin-ai:nav.audit"), onClick: () => navigate(ROUTE_ADMIN_AUDIT) },
    { key: "usage", label: t("admin-ai:nav.usage"), onClick: () => navigate(ROUTE_ADMIN_USAGE) },
  ];

  // ---------------------------------------------------------------------------
  // Step indicator
  // ---------------------------------------------------------------------------

  function renderStepIndicator(): ReactNode {
    const labels: Record<string, string> = {
      provider: "1 / 2",
      credentials: "2 / 2",
      submitting: "2 / 2",
      models: t("admin-ai:modelsNew.steps.modelsLabel"),
      success: t("admin-ai:modelsNew.steps.modelsLabel"),
    };
    return (
      <div style={STEP_INDICATOR} aria-live="polite" aria-label={t("admin-ai:modelsNew.steps.aria")}>
        {labels[wizard.step] ?? ""}
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Main content switch (step machine)
  // ---------------------------------------------------------------------------

  function renderContent(): ReactNode {
    const { step, submissionState } = wizard;

    if (step === "provider") {
      return <ProviderStep wizard={wizard} t={t} />;
    }

    if (step === "credentials" || step === "submitting") {
      return (
        <CredentialsStep
          wizard={wizard}
          t={t}
          showSecret={showSecret}
          onToggleShowSecret={() => setShowSecret((v) => !v)}
        />
      );
    }

    if (step === "models" || step === "success") {
      return (
        <ModelsStep
          wizard={wizard}
          t={t}
          navigate={navigate}
          routeAdminAiModels={ROUTE_ADMIN_AI_MODELS}
        />
      );
    }

    // Defensive fallback — permission_denied at page level (not in step)
    if (submissionState === "permission_denied") {
      logWarn("admin-ai.page.ModelWizardPage.permission_denied");
      return (
        <div
          role="alert"
          aria-live="assertive"
          style={CENTER_BLOCK}
          data-testid="wizard-permission-denied"
        >
          <TrackedLabel as="h2" variant="default">
            {t("admin-ai:modelsNew.errors.permissionDenied.title")}
          </TrackedLabel>
          <p style={BODY_TEXT}>{t("admin-ai:modelsNew.errors.permissionDenied.body")}</p>
        </div>
      );
    }

    return null;
  }

  return (
    <AdminShell navItems={navItems} data-testid="model-wizard-shell">
      <h1 style={PAGE_TITLE} data-testid="wizard-page-title">
        {t("admin-ai:modelsNew.title")}
      </h1>
      <p style={PAGE_SUBTITLE} data-testid="wizard-page-subtitle">
        {t("admin-ai:modelsNew.subtitle")}
      </p>
      {renderStepIndicator()}
      {renderContent()}
    </AdminShell>
  );
}
