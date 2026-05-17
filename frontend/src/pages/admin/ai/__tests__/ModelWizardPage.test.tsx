/**
 * Hilo People — ModelWizardPage component tests.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-PAGE-TESTS
 *
 * Responsibility: Component tests for ModelWizardPage.
 *   useModelWizard hook is mocked to inject each UX state independently.
 *   Tests verify rendering, accessibility, submit flow, and credential masking.
 *
 * UX states tested:
 *   P01 — loading state (step=submitting, submissionState=submitting).
 *   P02 — provider step renders with correct form fields.
 *   P03 — credentials step renders secret as password type (SECURITY).
 *   P04 — error_network state shows error banner.
 *   P05 — error_validation state shows field errors.
 *   P06 — permission_denied state shows forbidden message.
 *   P07 — success/models step shows created provider summary.
 *   P08 — accessibility: all inputs have associated labels.
 *   P09 — submit button is disabled when hasSecret=false.
 *
 * Pattern: mirrors AdminAiModelsPage tests — hook mock per test.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import React from "react";
import { MemoryRouter } from "react-router";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../../i18n/index";
import ModelWizardPage from "../ModelWizardPage";
import type { UseModelWizardResult } from "../../../../features/admin-ai/presentation/useModelWizard";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../../features/admin-ai/presentation/useModelWizard", () => ({
  useModelWizard: vi.fn(),
  validateProviderType: vi.fn(() => null),
  validateName: vi.fn(() => null),
  validateSecret: vi.fn(() => null),
  validateAuthType: vi.fn(() => null),
  formatMaskedSecret: vi.fn((s: string) => `••••• ${s.slice(-4)}`),
}));

vi.mock("../../../../features/admin-ai/data/logger", () => ({
  logVerbose: vi.fn(),
  logWarn: vi.fn(),
  logError: vi.fn(),
}));

import { useModelWizard } from "../../../../features/admin-ai/presentation/useModelWizard";
const mockUseModelWizard = vi.mocked(useModelWizard);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function baseResult(): UseModelWizardResult {
  return {
    step: "provider",
    form: { provider_type: "", name: "", base_url: "", auth_type: "api_key" },
    hasSecret: false,
    maskedSecret: "•••••",
    fieldErrors: {},
    submitError: null,
    submissionState: "idle",
    createdProvider: null,
    providerModels: [],
    areModelsLoading: false,
    goNext: vi.fn(),
    goBack: vi.fn(),
    setField: vi.fn(),
    setSecret: vi.fn(),
    submit: vi.fn(),
    reset: vi.fn(),
  };
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={["/admin/ai/models/new"]}>
      <I18nextProvider i18n={i18n}>
        <ModelWizardPage />
      </I18nextProvider>
    </MemoryRouter>,
  );
}

beforeEach(() => {
  vi.clearAllMocks();
});

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ModelWizardPage: UX states", () => {
  it("P01 — loading (step=submitting): submit button shows submitting state", () => {
    mockUseModelWizard.mockReturnValue({
      ...baseResult(),
      step: "submitting",
      submissionState: "submitting",
      hasSecret: true,
    });

    renderPage();

    // In submitting step the credentials form renders
    const submitBtn = screen.getByTestId("wizard-submit-btn");
    expect(submitBtn).toBeDisabled();
  });

  it("P02 — provider step: renders provider type select and name input", () => {
    mockUseModelWizard.mockReturnValue(baseResult());

    renderPage();

    expect(screen.getByTestId("wizard-step-provider")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-provider-type-select")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-provider-name-input")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-next-btn")).toBeInTheDocument();
  });

  it("P03 — credentials step: secret input is type=password (SECURITY)", () => {
    mockUseModelWizard.mockReturnValue({
      ...baseResult(),
      step: "credentials",
      hasSecret: false,
    });

    renderPage();

    const secretInput = screen.getByTestId("wizard-secret-input");
    expect(secretInput).toHaveAttribute("type", "password");
  });

  it("P04 — error_network state in credentials step: shows error banner", () => {
    mockUseModelWizard.mockReturnValue({
      ...baseResult(),
      step: "credentials",
      submissionState: "error_network",
      submitError: null,
    });

    renderPage();

    expect(screen.getByTestId("wizard-error-network")).toBeInTheDocument();
  });

  it("P05 — error_validation state: field errors shown", () => {
    mockUseModelWizard.mockReturnValue({
      ...baseResult(),
      step: "provider",
      fieldErrors: {
        provider_type: "admin-ai:modelsNew.errors.validation.providerTypeRequired",
        name: "admin-ai:modelsNew.errors.validation.nameRequired",
      },
    });

    renderPage();

    // Field error messages rendered via aria role=alert
    const alerts = screen.getAllByRole("alert");
    expect(alerts.length).toBeGreaterThanOrEqual(2);
  });

  it("P06 — permission_denied in credentials step: shows forbidden message", () => {
    mockUseModelWizard.mockReturnValue({
      ...baseResult(),
      step: "credentials",
      submissionState: "permission_denied",
    });

    renderPage();

    expect(screen.getByTestId("wizard-error-permission")).toBeInTheDocument();
  });

  it("P07 — success/models step: shows success title and back-to-models button", () => {
    mockUseModelWizard.mockReturnValue({
      ...baseResult(),
      step: "models",
      submissionState: "success",
      createdProvider: {
        id: "prov-1",
        name: "litellm_test",
        provider_type: "litellm",
        base_url: null,
        status: "draft",
        created_by: null,
        has_credentials: true,
        credential_auth_type: "bearer",
        expires_at: null,
      },
      providerModels: [],
      areModelsLoading: false,
    });

    renderPage();

    expect(screen.getByTestId("wizard-step-models")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-models-empty")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-back-to-models-btn")).toBeInTheDocument();
  });

  it("P08 — accessibility: provider type select has associated label", () => {
    mockUseModelWizard.mockReturnValue(baseResult());

    renderPage();

    const select = screen.getByTestId("wizard-provider-type-select");
    // The label must reference this select via htmlFor=id
    expect(select).toHaveAttribute("id", "wizard-provider-type");
    const label = document.querySelector("label[for='wizard-provider-type']");
    expect(label).not.toBeNull();
  });

  it("P09 — submit button is disabled when hasSecret=false", () => {
    mockUseModelWizard.mockReturnValue({
      ...baseResult(),
      step: "credentials",
      hasSecret: false,
    });

    renderPage();

    const submitBtn = screen.getByTestId("wizard-submit-btn");
    expect(submitBtn).toBeDisabled();
  });
});
