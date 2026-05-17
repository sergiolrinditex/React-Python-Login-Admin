/**
 * Hilo People — ModelWizardPage models (success) step.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-FILESIZE-SPLIT-STEPS
 *
 * Responsibility: Step 3 of the model wizard — success summary + models list
 *   (or empty state). Renders the post-create UX:
 *     - loading: spinner while GET /admin/ai/models?provider_id resolves
 *     - empty: "no models yet" notice
 *     - success: list of models for the newly created provider
 *
 *   Provides "Back to models" and (conditional) "Test model" CTAs. The "Test
 *   model" CTA is a graceful fallback to ROUTE_ADMIN_AI_MODELS until
 *   P04-S01-T004 (ModelTestDrawer) is wired.
 *
 * Consumers: ModelWizardPage.tsx only.
 * Design: token-only styles from ./ModelWizardPage.styles.ts.
 * Accessibility: aria-live="polite" on the section, role="status" on the
 *   loading/empty branches, aria-labels on the CTAs.
 *
 * Key deps: useModelWizard (hook result type), shared/design-system primitives,
 *   ../../../features/admin-ai/data/logger (verbose log gating),
 *   react-i18next.
 */

import type { ReactNode } from "react";
import type { TFunction } from "i18next";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { logVerbose } from "../../../features/admin-ai/data/logger";
import type { UseModelWizardResult } from "../../../features/admin-ai/presentation/useModelWizard";
import {
  FORM_ACTIONS,
  BODY_TEXT,
  SUCCESS_SECTION,
  MODELS_TABLE_WRAPPER,
  STEP_HEADING_TIGHT,
} from "./ModelWizardPage.styles";
import { routeAdminAiModelsTestFor } from "../../../app/router";

interface ModelsStepProps {
  wizard: UseModelWizardResult;
  t: TFunction;
  navigate: (route: string) => void;
  routeAdminAiModels: string;
}

/**
 * Renders step 3: success summary + models list (or loading / empty state).
 */
export function ModelsStep({
  wizard,
  t,
  navigate,
  routeAdminAiModels,
}: ModelsStepProps): ReactNode {
  const { createdProvider, providerModels, areModelsLoading } = wizard;
  const isEmpty = !areModelsLoading && providerModels.length === 0;

  logVerbose("admin-ai.page.ModelWizardPage.models.render", {
    are_models_loading: areModelsLoading,
    model_count: providerModels.length,
  });

  return (
    <section
      aria-labelledby="wizard-models-heading"
      aria-live="polite"
      data-testid="wizard-step-models"
    >
      <h2 id="wizard-models-heading" style={STEP_HEADING_TIGHT}>
        {t("admin-ai:modelsNew.success.title")}
      </h2>
      <p style={{ ...BODY_TEXT, marginBottom: "1.5rem" }}>
        {t("admin-ai:modelsNew.success.body")}
      </p>

      {areModelsLoading && (
        <div
          role="status"
          aria-busy="true"
          aria-label={t("admin-ai:modelsNew.success.loadingModels")}
          data-testid="wizard-models-loading"
          style={{ ...BODY_TEXT, fontStyle: "italic" }}
        >
          {t("admin-ai:modelsNew.success.loadingModels")}
        </div>
      )}

      {isEmpty && (
        <div
          role="status"
          aria-live="polite"
          style={SUCCESS_SECTION}
          data-testid="wizard-models-empty"
        >
          <p style={BODY_TEXT}>{t("admin-ai:modelsNew.success.noModels")}</p>
        </div>
      )}

      {!areModelsLoading && providerModels.length > 0 && (
        <div style={MODELS_TABLE_WRAPPER} data-testid="wizard-models-list">
          <TrackedLabel as="p" variant="muted">
            {t("admin-ai:modelsNew.success.modelCount", { count: providerModels.length })}
          </TrackedLabel>
          <ul
            aria-label={t("admin-ai:modelsNew.success.modelsListLabel")}
            style={{ listStyle: "none", padding: 0, margin: "0.75rem 0" }}
          >
            {providerModels.map((model) => (
              <li
                key={model.id}
                style={{
                  borderBottom: "var(--hairline)",
                  padding: "0.75rem 0",
                  fontFamily: "var(--font-sans)",
                  fontSize: "0.9375rem",
                  color: "var(--color-ink)",
                }}
                data-testid={`wizard-model-item-${model.model_id}`}
              >
                {model.model_id}
                {model.is_default && (
                  <TrackedLabel
                    as="span"
                    variant="muted"
                    style={{ marginLeft: "0.75rem" }}
                  >
                    {t("admin-ai:modelsNew.success.defaultBadge")}
                  </TrackedLabel>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      <div style={FORM_ACTIONS}>
        <SolidCTA
          onClick={() => navigate(routeAdminAiModels)}
          aria-label={t("admin-ai:modelsNew.actions.backToModels")}
          data-testid="wizard-back-to-models-btn"
          width="auto"
          style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
        >
          {t("admin-ai:modelsNew.actions.backToModels")}
        </SolidCTA>
        {providerModels.length > 0 && createdProvider && (
          <SolidCTA
            onClick={() => {
              // §D-T004-WIZARD-CTA-WIRING: navigate to ModelTestDrawer for the first model.
              // Wired in P04-S01-T004 (WRITE_SET_DRIFT documented in handoff).
              logVerbose("admin-ai.page.ModelWizardPage.testModel.click", {});
              navigate(routeAdminAiModelsTestFor(providerModels[0].id));
            }}
            aria-label={t("admin-ai:modelsNew.actions.testModel")}
            data-testid="wizard-test-model-btn"
            width="auto"
            style={{
              padding: "0.75rem 1.5rem",
              minHeight: "44px",
              background: "transparent",
              color: "var(--color-ink)",
              border: "var(--hairline)",
            }}
          >
            {t("admin-ai:modelsNew.actions.testModel")}
          </SolidCTA>
        )}
      </div>
    </section>
  );
}
