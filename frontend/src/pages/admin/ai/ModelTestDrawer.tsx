/**
 * Hilo People — ModelTestDrawer page.
 *
 * Slice/Phase: P04-S01-T004 — ModelTestDrawer / Phase 4.
 * Write-set anchor: §D-T004-PAGE (canonical Coverage Registry anchor file).
 *
 * Responsibility: Admin AI model test "playground" page at /admin/ai/models/:modelId/test.
 *   Implements 5 required UI states (UX_CONTRACT L31):
 *     loading (submitting), error_network, error_validation, permission_denied, success.
 *   Additionally: error_upstream (502 sub-state) + activate flow (idle/pending/success/error).
 *   Allows admin to type a prompt, submit to POST /models/{id}/test, view output/latency/cost,
 *   and optionally activate the model as default via PATCH /models/{id}.
 *   Navigates back to /admin/ai/models on "Volver a modelos" or close.
 *
 * Architecture decision §D-T004-DRAWER-AS-PAGE:
 *   Route /admin/ai/models/:modelId/test is a full page (not an overlay portal).
 *   Deep-links work; auth guard applies. The "drawer" naming is aesthetic/UX (panel layout).
 *
 * Non-negotiables §logging: BEFORE+AFTER+ERROR via logVerbose/logWarn/logError.
 * PII contract (§D-T004-PII): NEVER log prompt or output content.
 * Accessibility: all inputs labelled; aria-required; aria-describedby; role=alert on errors;
 *   aria-live=polite on result panel; min tap targets 44px.
 *
 * Route: /admin/ai/models/:modelId/test (RequireRole['people_admin','super_admin']).
 * Journey refs: J103 (participates — step 3: prompt→activate; does NOT close J103).
 */

import type { ReactNode } from "react";
import { useParams, useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import AdminShell from "../../../shared/design-system/AdminShell";
import type { AdminNavItem } from "../../../shared/design-system/AdminShell";
import SolidCTA from "../../../shared/design-system/SolidCTA";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { useModelTest, formatLatencyMs, formatCostUsd } from "../../../features/admin-ai/presentation/useModelTest";
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
  FORM_SECTION,
  FIELD_ROW,
  FORM_ACTIONS,
  PROMPT_TEXTAREA,
  PROMPT_TEXTAREA_ERROR,
  RESULT_PANEL,
  RESULT_OUTPUT,
  RESULT_META_ROW,
  RESULT_META_ITEM,
  ACTIVATE_CONFIRM,
  BODY_TEXT,
  ERROR_TEXT,
  ERROR_BANNER,
  SECTION_HEADING,
} from "./ModelTestDrawer.styles";

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * ModelTestDrawer page — model test playground for admin role.
 *
 * Route param: :modelId (UUID). Reads from useParams.
 * Guards: RequireRole in router.tsx (upstream). Defensive 403 rendered page-level.
 *
 * @returns The model test drawer page.
 */
export default function ModelTestDrawer(): ReactNode {
  const { t } = useTranslation(["admin-ai"]);
  const navigate = useNavigate();
  const { modelId } = useParams<{ modelId: string }>();

  logVerbose("admin-ai.page.ModelTestDrawer.render.start", {
    has_model_id: Boolean(modelId),
  });

  // ---- Guard: missing modelId (should never happen via router) ------------

  if (!modelId) {
    logWarn("admin-ai.page.ModelTestDrawer.missing_model_id", {});
    return (
      <AdminShell navItems={[]} data-testid="model-test-shell">
        <div style={FORM_SECTION} data-testid="model-test-error-network">
          <h1 style={PAGE_TITLE}>{t("admin-ai:modelTest.title")}</h1>
          <p role="alert" style={BODY_TEXT}>
            {t("admin-ai:modelTest.errors.notFound")}
          </p>
          <SolidCTA
            onClick={() => navigate(ROUTE_ADMIN_AI_MODELS)}
            aria-label={t("admin-ai:modelTest.actions.back")}
            width="auto"
            style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
          >
            {t("admin-ai:modelTest.actions.back")}
          </SolidCTA>
        </div>
      </AdminShell>
    );
  }

  return <ModelTestDrawerInner modelId={modelId} />;
}

// ---------------------------------------------------------------------------
// Inner component — receives validated modelId
// ---------------------------------------------------------------------------

function ModelTestDrawerInner({ modelId }: { modelId: string }): ReactNode {
  const { t } = useTranslation(["admin-ai"]);
  const navigate = useNavigate();
  const hook = useModelTest(modelId);

  const {
    prompt,
    setPrompt,
    isSubmitting,
    submissionState,
    testResult,
    fieldErrors,
    submit,
    reset,
    isActivating,
    activateState,
    activate,
  } = hook;

  const navItems: AdminNavItem[] = [
    { key: "dashboard", label: t("admin-ai:nav.dashboard"), onClick: () => navigate(ROUTE_ADMIN) },
    { key: "models", label: t("admin-ai:nav.models"), active: true, onClick: () => navigate(ROUTE_ADMIN_AI_MODELS) },
    { key: "modelsNew", label: t("admin-ai:nav.modelsNew"), onClick: () => navigate(ROUTE_ADMIN_AI_MODELS_NEW) },
    { key: "ragDocuments", label: t("admin-ai:nav.ragDocuments"), onClick: () => navigate(ROUTE_ADMIN_RAG_DOCUMENTS) },
    { key: "ragCollections", label: t("admin-ai:nav.ragCollections"), onClick: () => navigate(ROUTE_ADMIN_RAG_COLLECTIONS) },
    { key: "mcpServers", label: t("admin-ai:nav.mcpServers"), onClick: () => navigate(ROUTE_ADMIN_AI_MCP) },
    { key: "mcpNew", label: t("admin-ai:nav.mcpNew"), onClick: () => navigate(ROUTE_ADMIN_AI_MCP_NEW) },
    { key: "agents", label: t("admin-ai:nav.agents"), onClick: () => navigate(ROUTE_ADMIN_AI_AGENTS) },
    { key: "audit", label: t("admin-ai:nav.audit"), onClick: () => navigate(ROUTE_ADMIN_AUDIT) },
    { key: "usage", label: t("admin-ai:nav.usage"), onClick: () => navigate(ROUTE_ADMIN_USAGE) },
  ];

  logVerbose("admin-ai.page.ModelTestDrawer.inner.render", {
    submission_state: submissionState,
    activate_state: activateState,
    has_result: Boolean(testResult),
  });

  // ---- Permission denied --------------------------------------------------

  if (submissionState === "permission_denied") {
    logWarn("admin-ai.page.ModelTestDrawer.permission_denied", {});
    return (
      <AdminShell navItems={navItems} data-testid="model-test-shell">
        <div data-testid="model-test-error-permission" style={FORM_SECTION}>
          <h1 style={PAGE_TITLE}>{t("admin-ai:modelTest.title")}</h1>
          <p role="alert" aria-live="assertive" style={BODY_TEXT}>
            {t("admin-ai:modelTest.errors.permissionDenied")}
          </p>
          <SolidCTA
            onClick={() => navigate(ROUTE_ADMIN_AI_MODELS)}
            aria-label={t("admin-ai:modelTest.actions.back")}
            width="auto"
            style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
          >
            {t("admin-ai:modelTest.actions.back")}
          </SolidCTA>
        </div>
      </AdminShell>
    );
  }

  const hasPromptError = Boolean(fieldErrors.prompt);
  const isValidationError = submissionState === "error_validation";
  const isNetworkError = submissionState === "error_network";
  const isUpstreamError = submissionState === "error_upstream";
  const isSuccess = submissionState === "success";
  const isLoading = isSubmitting;

  const promptTextareaId = "model-test-prompt-input";
  const promptDescId = "model-test-prompt-desc";

  return (
    <AdminShell navItems={navItems} data-testid="model-test-shell">
      <h1 style={PAGE_TITLE} data-testid="model-test-page-title">
        {t("admin-ai:modelTest.title")}
      </h1>
      <p style={PAGE_SUBTITLE} data-testid="model-test-page-subtitle">
        {t("admin-ai:modelTest.subtitle")}
      </p>

      {/* ---- Prompt form ------------------------------------------------- */}
      <section
        aria-labelledby="model-test-form-heading"
        style={FORM_SECTION}
      >
        <h2 id="model-test-form-heading" style={SECTION_HEADING}>
          {t("admin-ai:modelTest.promptLabel")}
        </h2>

        <div style={FIELD_ROW}>
          <label
            htmlFor={promptTextareaId}
            style={{
              fontFamily: "var(--font-sans)",
              fontSize: "0.8125rem",
              color: "var(--color-ink)",
              letterSpacing: "var(--tracking-label)",
              textTransform: "uppercase",
            }}
          >
            {t("admin-ai:modelTest.promptLabel")}
          </label>
          <textarea
            id={promptTextareaId}
            value={prompt}
            onChange={(e) => setPrompt(e.target.value)}
            disabled={isSubmitting}
            placeholder={t("admin-ai:modelTest.promptPlaceholder")}
            aria-required="true"
            aria-invalid={hasPromptError ? "true" : undefined}
            aria-describedby={hasPromptError ? promptDescId : undefined}
            maxLength={4000}
            style={hasPromptError ? PROMPT_TEXTAREA_ERROR : PROMPT_TEXTAREA}
          />
          {hasPromptError && (
            <p
              id={promptDescId}
              role="alert"
              style={ERROR_TEXT}
              data-testid="model-test-prompt-error"
            >
              {fieldErrors.prompt}
            </p>
          )}
        </div>

        {/* ---- Validation error banner ------------------------------------- */}
        {isValidationError && !hasPromptError && (
          <div
            role="alert"
            aria-live="assertive"
            style={ERROR_BANNER}
            data-testid="model-test-error-validation"
          >
            <p style={BODY_TEXT}>{t("admin-ai:modelTest.errors.validation")}</p>
          </div>
        )}

        {/* ---- Network error banner ---------------------------------------- */}
        {isNetworkError && (
          <div
            role="alert"
            aria-live="assertive"
            style={ERROR_BANNER}
            data-testid="model-test-error-network"
          >
            <p style={BODY_TEXT}>{t("admin-ai:modelTest.errors.network")}</p>
          </div>
        )}

        {/* ---- Upstream 502 error banner ----------------------------------- */}
        {isUpstreamError && (
          <div
            role="alert"
            aria-live="assertive"
            style={ERROR_BANNER}
            data-testid="model-test-error-upstream"
          >
            <p style={BODY_TEXT}>{t("admin-ai:modelTest.errors.upstream")}</p>
          </div>
        )}

        {/* ---- Actions ----------------------------------------------------- */}
        <div style={FORM_ACTIONS}>
          {/* Submit CTA */}
          <SolidCTA
            onClick={submit}
            disabled={isSubmitting || !prompt.trim()}
            aria-label={isSubmitting
              ? t("admin-ai:modelTest.actions.submitting")
              : t("admin-ai:modelTest.actions.submit")}
            data-testid={isSubmitting ? "model-test-submitting" : "model-test-submit"}
            width="auto"
            style={{ padding: "0.75rem 1.5rem", minHeight: "44px" }}
          >
            {isSubmitting
              ? t("admin-ai:modelTest.actions.submitting")
              : t("admin-ai:modelTest.actions.submit")}
          </SolidCTA>

          {/* Retry CTA (shown on error states) */}
          {(isNetworkError || isUpstreamError || isValidationError) && (
            <SolidCTA
              onClick={reset}
              aria-label={t("admin-ai:modelTest.actions.retry")}
              data-testid="model-test-retry"
              width="auto"
              style={{
                padding: "0.75rem 1.5rem",
                minHeight: "44px",
                background: "transparent",
                color: "var(--color-ink)",
                border: "var(--hairline)",
              }}
            >
              {t("admin-ai:modelTest.actions.retry")}
            </SolidCTA>
          )}

          {/* Back to models CTA */}
          <SolidCTA
            onClick={() => navigate(ROUTE_ADMIN_AI_MODELS)}
            aria-label={t("admin-ai:modelTest.actions.back")}
            data-testid="model-test-back"
            width="auto"
            style={{
              padding: "0.75rem 1.5rem",
              minHeight: "44px",
              background: "transparent",
              color: "var(--color-ink)",
              border: "var(--hairline)",
            }}
          >
            {t("admin-ai:modelTest.actions.back")}
          </SolidCTA>
        </div>
      </section>

      {/* ---- Loading indicator (while submitting) -------------------------- */}
      {isLoading && (
        <div
          role="status"
          aria-busy="true"
          aria-label={t("admin-ai:modelTest.actions.submitting")}
          data-testid="model-test-loading"
          style={{ ...BODY_TEXT, fontStyle: "italic", marginTop: "1rem" }}
        >
          {t("admin-ai:modelTest.actions.submitting")}
        </div>
      )}

      {/* ---- Success result panel ------------------------------------------ */}
      {isSuccess && testResult && (
        <section
          aria-labelledby="model-test-result-heading"
          aria-live="polite"
          style={RESULT_PANEL}
          data-testid="model-test-success"
        >
          <h2 id="model-test-result-heading" style={SECTION_HEADING}>
            {t("admin-ai:modelTest.success.title")}
          </h2>

          <p
            style={RESULT_OUTPUT}
            data-testid="model-test-result-output"
          >
            {testResult.output}
          </p>

          <div style={RESULT_META_ROW}>
            <span style={RESULT_META_ITEM} data-testid="model-test-result-latency">
              <TrackedLabel as="span" variant="muted">
                {t("admin-ai:modelTest.success.latency")}:{" "}
              </TrackedLabel>
              {formatLatencyMs(testResult.latency_ms)}
            </span>
            <span style={RESULT_META_ITEM} data-testid="model-test-result-cost">
              <TrackedLabel as="span" variant="muted">
                {t("admin-ai:modelTest.success.cost")}:{" "}
              </TrackedLabel>
              {formatCostUsd(testResult.cost)}
            </span>
          </div>

          {/* ---- Activate action ------------------------------------------ */}
          {activateState === "idle" && (
            <div style={{ ...FORM_ACTIONS, marginTop: "1.25rem" }}>
              <SolidCTA
                onClick={() => activate()}
                disabled={isActivating}
                aria-label={t("admin-ai:modelTest.actions.activate")}
                data-testid="model-test-activate"
                width="auto"
                style={{
                  padding: "0.75rem 1.5rem",
                  minHeight: "44px",
                  background: "transparent",
                  color: "var(--color-ink)",
                  border: "var(--hairline)",
                }}
              >
                {t("admin-ai:modelTest.actions.activate")}
              </SolidCTA>
            </div>
          )}

          {activateState === "pending" && (
            <div
              role="status"
              aria-busy="true"
              aria-live="polite"
              data-testid="model-test-activate-pending"
              style={{ ...BODY_TEXT, fontStyle: "italic", marginTop: "1rem" }}
            >
              {t("admin-ai:modelTest.actions.activating")}
            </div>
          )}

          {activateState === "success" && (
            <p
              role="status"
              aria-live="polite"
              style={{ ...ACTIVATE_CONFIRM, marginTop: "1rem" }}
              data-testid="model-test-activate-success"
            >
              {t("admin-ai:modelTest.success.activated")}
            </p>
          )}

          {activateState === "error" && (
            <div
              role="alert"
              aria-live="assertive"
              style={{ ...ERROR_BANNER, marginTop: "1rem" }}
              data-testid="model-test-activate-error"
            >
              <p style={BODY_TEXT}>{t("admin-ai:modelTest.errors.activateFailed")}</p>
            </div>
          )}
        </section>
      )}
    </AdminShell>
  );
}
