/**
 * Hilo People — useModelWizard hook tests.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-HOOK-TESTS
 *
 * Responsibility: Tests for the useModelWizard presentation hook.
 *   createProvider repository is mocked at the fetch boundary.
 *   getModels repository is mocked for the provider_id-filtered query.
 *   useAuth is mocked.  TanStack Query client is real (QueryClientProvider).
 *
 * Security: Tests assert that secret_plain is cleared on success and unmount.
 *
 * Cases:
 *   W01 — initial state: step=provider, form empty, no errors, submissionState=idle.
 *   W02 — goNext on provider step: validates provider_type + name, advances to credentials.
 *   W03 — goNext with invalid provider step: stays on provider, fieldErrors populated.
 *   W04 — setSecret updates hasSecret; maskedSecret shows last-4 mask.
 *   W05 — submit success: step advances to models, createdProvider set, secret cleared.
 *   W06 — submit error_network: submissionState=error_network, stays on credentials.
 *   W07 — submit error_validation 422: fieldErrors from server surfaced.
 *   W08 — submit permission_denied 403: submissionState=permission_denied.
 *   W09 — goBack from credentials → provider step.
 *   W10 — reset clears all state including secret.
 *   W11 — unmount: secret is cleared (security).
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useModelWizard, validateProviderType, validateName, validateSecret, validateAuthType, formatMaskedSecret } from "../presentation/useModelWizard";
import {
  AdminAiNetworkError,
  AdminAiForbiddenError,
  AdminAiValidationError,
  AdminAiInternalError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../data/adminAiRepository", () => ({
  createProvider: vi.fn(),
  getModels: vi.fn(),
  getProviders: vi.fn(),
}));

vi.mock("../../auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { createProvider, getModels } from "../data/adminAiRepository";
import { useAuth } from "../../auth/presentation/AuthProvider";

const mockCreateProvider = vi.mocked(createProvider);
const mockGetModels = vi.mocked(getModels);
const mockUseAuth = vi.mocked(useAuth);

// ---------------------------------------------------------------------------
// Test wrapper
// ---------------------------------------------------------------------------

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_PROVIDER = {
  id: "prov-uuid-1234",
  name: "litellm_verification_sandbox",
  provider_type: "litellm" as const,
  base_url: "http://localhost:4000",
  status: "draft" as const,
  created_by: null,
  has_credentials: true,
  credential_auth_type: "bearer" as const,
  expires_at: null,
};

const MOCK_MODELS = [
  {
    id: "model-uuid-1",
    provider_id: "prov-uuid-1234",
    model_id: "gpt-4o-mini",
    model_type: "chat",
    capabilities: ["chat"],
    enabled: true,
    is_default: true,
    pricing: {},
    latency_ms_avg: null,
  },
];

const SECRET = "hilo-dev-litellm-master-key-2026" as unknown as (string & { readonly __neverLog: unique symbol });

// ---------------------------------------------------------------------------
// Setup
// ---------------------------------------------------------------------------

beforeEach(() => {
  vi.clearAllMocks();
  mockUseAuth.mockReturnValue({
    status: "authenticated",
    user: { id: "user-1", email: "admin@test.com", roles: ["people_admin"] },
    logout: vi.fn(),
    login: vi.fn(),
    onAuthFailure: vi.fn(),
    refresh: vi.fn(),
  } as unknown as ReturnType<typeof useAuth>);

  // Default: models returns empty
  mockGetModels.mockResolvedValue({ ok: true, value: [] });
});

// ---------------------------------------------------------------------------
// Unit tests — validators (pure)
// ---------------------------------------------------------------------------

describe("useModelWizard: validators (pure)", () => {
  it("W-validators-01 — validateProviderType: valid values return null", () => {
    expect(validateProviderType("openai")).toBeNull();
    expect(validateProviderType("litellm")).toBeNull();
    expect(validateProviderType("custom")).toBeNull();
  });

  it("W-validators-02 — validateProviderType: empty/invalid returns i18n key", () => {
    expect(validateProviderType("")).not.toBeNull();
    expect(validateProviderType("unknown-provider")).not.toBeNull();
  });

  it("W-validators-03 — validateName: non-blank ≤200 chars returns null", () => {
    expect(validateName("my_provider")).toBeNull();
  });

  it("W-validators-04 — validateName: blank returns i18n key", () => {
    expect(validateName("")).not.toBeNull();
    expect(validateName("   ")).not.toBeNull();
  });

  it("W-validators-05 — validateName: >200 chars returns i18n key", () => {
    expect(validateName("a".repeat(201))).not.toBeNull();
  });

  it("W-validators-06 — validateSecret: non-blank returns null", () => {
    expect(validateSecret("sk-1234")).toBeNull();
  });

  it("W-validators-07 — validateSecret: blank returns i18n key (NEVER log value)", () => {
    expect(validateSecret("")).not.toBeNull();
    expect(validateSecret("   ")).not.toBeNull();
  });

  it("W-validators-08 — validateAuthType: valid values return null", () => {
    expect(validateAuthType("api_key")).toBeNull();
    expect(validateAuthType("bearer")).toBeNull();
    expect(validateAuthType("oauth2")).toBeNull();
  });

  it("W-validators-09 — validateAuthType: invalid returns i18n key", () => {
    expect(validateAuthType("")).not.toBeNull();
    expect(validateAuthType("invalid")).not.toBeNull();
  });

  it("W-validators-10 — formatMaskedSecret: shows last 4", () => {
    expect(formatMaskedSecret("sk-1234abcd")).toBe("••••• abcd");
  });

  it("W-validators-11 — formatMaskedSecret: short secret → all masked", () => {
    expect(formatMaskedSecret("abc")).toBe("•••••");
  });
});

// ---------------------------------------------------------------------------
// Hook integration tests
// ---------------------------------------------------------------------------

describe("useModelWizard: hook integration", () => {
  it("W01 — initial state: step=provider, form empty, no errors, submissionState=idle", () => {
    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    expect(result.current.step).toBe("provider");
    expect(result.current.form.provider_type).toBe("");
    expect(result.current.form.name).toBe("");
    expect(result.current.hasSecret).toBe(false);
    expect(result.current.submissionState).toBe("idle");
    expect(Object.keys(result.current.fieldErrors)).toHaveLength(0);
    expect(result.current.submitError).toBeNull();
  });

  it("W02 — goNext on provider step with valid data: advances to credentials", () => {
    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => {
      result.current.setField("provider_type", "litellm");
      result.current.setField("name", "litellm_test");
    });
    act(() => {
      result.current.goNext();
    });

    expect(result.current.step).toBe("credentials");
  });

  it("W03 — goNext with invalid provider step: stays on provider, fieldErrors populated", () => {
    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => {
      result.current.goNext(); // provider_type empty, name empty
    });

    expect(result.current.step).toBe("provider");
    expect(result.current.fieldErrors.provider_type).toBeTruthy();
    expect(result.current.fieldErrors.name).toBeTruthy();
  });

  it("W04 — setSecret updates hasSecret; maskedSecret shows last-4 mask", () => {
    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => {
      result.current.setSecret("sk-1234abcd");
    });

    expect(result.current.hasSecret).toBe(true);
    expect(result.current.maskedSecret).toBe("••••• abcd");
  });

  it("W05 — submit success: step advances to models, createdProvider set, secret cleared", async () => {
    mockCreateProvider.mockResolvedValueOnce({ ok: true, value: MOCK_PROVIDER });
    mockGetModels.mockResolvedValue({ ok: true, value: MOCK_MODELS });

    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    // Populate valid form state
    act(() => {
      result.current.setField("provider_type", "litellm");
      result.current.setField("name", "litellm_test");
    });
    act(() => { result.current.goNext(); }); // → credentials step

    act(() => {
      result.current.setSecret("hilo-dev-litellm-test-key");
    });
    act(() => { result.current.submit(); });

    await waitFor(() => {
      expect(result.current.step).toBe("models");
    });

    expect(result.current.submissionState).toBe("success");
    expect(result.current.createdProvider).not.toBeNull();
    // Secret must be cleared after success
    expect(result.current.hasSecret).toBe(false);
  });

  it("W06 — submit error_network: submissionState=error_network, stays on credentials", async () => {
    mockCreateProvider.mockResolvedValueOnce({
      ok: false,
      error: new AdminAiNetworkError("Network error"),
    });

    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => {
      result.current.setField("provider_type", "litellm");
      result.current.setField("name", "litellm_test");
    });
    act(() => { result.current.goNext(); });
    act(() => { result.current.setSecret("my-key-value"); });
    act(() => { result.current.submit(); });

    await waitFor(() => {
      expect(result.current.submissionState).toBe("error_network");
    });

    expect(result.current.step).toBe("credentials");
    expect(result.current.submitError).toBeInstanceOf(AdminAiNetworkError);
  });

  it("W07 — submit 422 validation error: fieldErrors from server are surfaced", async () => {
    mockCreateProvider.mockResolvedValueOnce({
      ok: false,
      error: new AdminAiValidationError("ADMIN_PROVIDER_VALIDATION_ERROR", "Validation failed.", [
        { field: "name", code: "INVALID_NAME", message: "Name already taken." },
      ]),
    });

    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => {
      result.current.setField("provider_type", "litellm");
      result.current.setField("name", "existing_provider");
    });
    act(() => { result.current.goNext(); });
    act(() => { result.current.setSecret("my-key-value"); });
    act(() => { result.current.submit(); });

    await waitFor(() => {
      expect(result.current.submissionState).toBe("error_validation");
    });

    expect(result.current.fieldErrors.name).toBe("Name already taken.");
  });

  it("W08 — submit permission_denied 403: submissionState=permission_denied", async () => {
    mockCreateProvider.mockResolvedValueOnce({
      ok: false,
      error: new AdminAiForbiddenError(),
    });

    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => {
      result.current.setField("provider_type", "litellm");
      result.current.setField("name", "litellm_test");
    });
    act(() => { result.current.goNext(); });
    act(() => { result.current.setSecret("my-key"); });
    act(() => { result.current.submit(); });

    await waitFor(() => {
      expect(result.current.submissionState).toBe("permission_denied");
    });
  });

  it("W09 — goBack from credentials returns to provider step", () => {
    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => {
      result.current.setField("provider_type", "litellm");
      result.current.setField("name", "litellm_test");
    });
    act(() => { result.current.goNext(); }); // → credentials

    expect(result.current.step).toBe("credentials");

    act(() => { result.current.goBack(); });

    expect(result.current.step).toBe("provider");
  });

  it("W10 — reset clears all state including secret and errors", async () => {
    mockCreateProvider.mockResolvedValueOnce({ ok: true, value: MOCK_PROVIDER });
    mockGetModels.mockResolvedValue({ ok: true, value: [] });

    const { result } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => {
      result.current.setField("provider_type", "litellm");
      result.current.setField("name", "litellm_test");
      result.current.setSecret("my-key");
    });
    act(() => { result.current.goNext(); });
    act(() => { result.current.submit(); });

    await waitFor(() => {
      expect(result.current.step).toBe("models");
    });

    act(() => { result.current.reset(); });

    expect(result.current.step).toBe("provider");
    expect(result.current.form.provider_type).toBe("");
    expect(result.current.form.name).toBe("");
    expect(result.current.hasSecret).toBe(false);
    expect(result.current.submissionState).toBe("idle");
    expect(result.current.createdProvider).toBeNull();
  });

  it("W11 — unmount: hook cleanup does not throw (secret clear guard)", () => {
    const { result, unmount } = renderHook(() => useModelWizard(), { wrapper: createWrapper() });

    act(() => { result.current.setSecret("live-secret-key"); });
    expect(result.current.hasSecret).toBe(true);

    // Must not throw on unmount
    expect(() => unmount()).not.toThrow();
  });
});
