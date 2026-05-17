/**
 * Hilo People — useModelTest hook tests.
 *
 * Slice/Phase: P04-S01-T004 — ModelTestDrawer / Phase 4.
 * Write-set anchor: §D-T004-HOOK-TESTS
 *
 * Responsibility: Tests for the useModelTest presentation hook.
 *   testModel and updateModel are mocked at the repo boundary.
 *   useAuth is mocked. TanStack Query client is real (QueryClientProvider).
 *
 * Cases:
 *   U01 — initial state: prompt='', submissionState=idle, no fieldErrors.
 *   U02 — setPrompt updates prompt; clears existing fieldErrors.
 *   U03 — submit with empty prompt → error_validation + fieldErrors.prompt set.
 *   U04 — submit with prompt >4000 chars → error_validation.
 *   U05 — submit success → submissionState=success, testResult populated.
 *   U06 — submit error_network → submissionState=error_network.
 *   U07 — submit 403 → submissionState=permission_denied.
 *   U08 — activate success → activateState=success.
 *   U09 — formatLatencyMs <1000ms → "Xms"; ≥1000ms → "X.Xs".
 *   U10 — formatCostUsd 0 → "—"; >0 → formatted USD string.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import {
  useModelTest,
  formatLatencyMs,
  formatCostUsd,
} from "../presentation/useModelTest";
import {
  AdminAiNetworkError,
  AdminAiForbiddenError,
  AdminAiUpstreamError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../data/adminAiRepository.test-and-update", () => ({
  testModel: vi.fn(),
  updateModel: vi.fn(),
}));

vi.mock("../../auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { testModel, updateModel } from "../data/adminAiRepository.test-and-update";
import { useAuth } from "../../auth/presentation/AuthProvider";

const mockTestModel = vi.mocked(testModel);
const mockUpdateModel = vi.mocked(updateModel);
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

const MOCK_MODEL_ID = "mod-uuid-1";

const MOCK_TEST_RESPONSE = {
  output: "Paris is the capital of France.",
  latency_ms: 342,
  cost: 0.000123,
};

const MOCK_MODEL_OUT = {
  id: MOCK_MODEL_ID,
  provider_id: "prov-uuid-1",
  model_id: "gpt-4o-mini",
  enabled: true,
  is_default: true,
  model_type: "llm",
  capabilities: ["chat"],
  pricing: {},
  latency_ms_avg: null,
  config_json: {},
  created_at: "2026-05-17T00:00:00Z",
  updated_at: "2026-05-17T00:00:00Z",
};

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useModelTest", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      user: null,
      status: "authenticated" as const,
      signInAccepted: vi.fn(),
      logout: vi.fn(),
    } as unknown as ReturnType<typeof useAuth>);
  });

  it("U01 — initial state: prompt empty, submissionState=idle, no fieldErrors", () => {
    const { result } = renderHook(
      () => useModelTest(MOCK_MODEL_ID),
      { wrapper: createWrapper() },
    );

    expect(result.current.prompt).toBe("");
    expect(result.current.submissionState).toBe("idle");
    expect(result.current.fieldErrors).toEqual({});
    expect(result.current.testResult).toBeNull();
    expect(result.current.isSubmitting).toBe(false);
    expect(result.current.activateState).toBe("idle");
  });

  it("U02 — setPrompt updates prompt value", () => {
    const { result } = renderHook(
      () => useModelTest(MOCK_MODEL_ID),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.setPrompt("What is the capital of France?");
    });

    expect(result.current.prompt).toBe("What is the capital of France?");
  });

  it("U03 — submit with empty prompt → error_validation + fieldErrors.prompt set", () => {
    const { result } = renderHook(
      () => useModelTest(MOCK_MODEL_ID),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.submit();
    });

    expect(result.current.submissionState).toBe("error_validation");
    expect(result.current.fieldErrors.prompt).toBeTruthy();
    expect(mockTestModel).not.toHaveBeenCalled();
  });

  it("U04 — submit with prompt >4000 chars → error_validation", () => {
    const { result } = renderHook(
      () => useModelTest(MOCK_MODEL_ID),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.setPrompt("x".repeat(4001));
    });

    act(() => {
      result.current.submit();
    });

    expect(result.current.submissionState).toBe("error_validation");
    expect(result.current.fieldErrors.prompt).toBeTruthy();
    expect(mockTestModel).not.toHaveBeenCalled();
  });

  it("U05 — submit success → submissionState=success, testResult populated", async () => {
    mockTestModel.mockResolvedValueOnce({ ok: true, value: MOCK_TEST_RESPONSE });

    const { result } = renderHook(
      () => useModelTest(MOCK_MODEL_ID),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.setPrompt("What is the capital of France?");
    });

    act(() => {
      result.current.submit();
    });

    await waitFor(() => {
      expect(result.current.submissionState).toBe("success");
    });

    expect(result.current.testResult).not.toBeNull();
    expect(result.current.testResult?.latency_ms).toBe(342);
    expect(result.current.testResult?.cost).toBeCloseTo(0.000123);
    // PII: output content must be accessible but we only check it's present
    expect(result.current.testResult?.output).toBe("Paris is the capital of France.");
  });

  it("U06 — submit returns error_network → submissionState=error_network", async () => {
    mockTestModel.mockResolvedValueOnce({
      ok: false,
      error: new AdminAiNetworkError("Failed to fetch"),
    });

    const { result } = renderHook(
      () => useModelTest(MOCK_MODEL_ID),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.setPrompt("Hello");
    });

    act(() => {
      result.current.submit();
    });

    await waitFor(() => {
      expect(result.current.submissionState).toBe("error_network");
    });
  });

  it("U07 — submit 403 → submissionState=permission_denied", async () => {
    mockTestModel.mockResolvedValueOnce({
      ok: false,
      error: new AdminAiForbiddenError(),
    });

    const { result } = renderHook(
      () => useModelTest(MOCK_MODEL_ID),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.setPrompt("Hello");
    });

    act(() => {
      result.current.submit();
    });

    await waitFor(() => {
      expect(result.current.submissionState).toBe("permission_denied");
    });
  });

  it("U08 — activate success → activateState=success", async () => {
    mockUpdateModel.mockResolvedValueOnce({ ok: true, value: MOCK_MODEL_OUT });

    const { result } = renderHook(
      () => useModelTest(MOCK_MODEL_ID),
      { wrapper: createWrapper() },
    );

    act(() => {
      result.current.activate();
    });

    await waitFor(() => {
      expect(result.current.activateState).toBe("success");
    });
  });
});

describe("useModelTest — pure helpers", () => {
  it("U09 — formatLatencyMs <1000ms → 'Xms'", () => {
    expect(formatLatencyMs(342)).toBe("342ms");
    expect(formatLatencyMs(999)).toBe("999ms");
  });

  it("U09b — formatLatencyMs ≥1000ms → 'X.Xs'", () => {
    expect(formatLatencyMs(1000)).toBe("1.0s");
    expect(formatLatencyMs(1500)).toBe("1.5s");
    expect(formatLatencyMs(2342)).toBe("2.3s");
  });

  it("U10 — formatCostUsd 0 → em-dash", () => {
    expect(formatCostUsd(0)).toBe("—");
  });

  it("U10b — formatCostUsd >0 → formatted USD string", () => {
    const result = formatCostUsd(0.000123);
    expect(result).toContain("$");
    expect(result).toContain("0.000123");
  });
});
