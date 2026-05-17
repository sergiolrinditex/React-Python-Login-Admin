/**
 * Hilo People — useAdminAiModels hook tests.
 *
 * Slice/Phase: P04-S01-T002 — AdminAiModelsPage / Phase 4.
 * Write-set anchor: §D-T002-TESTS
 *
 * Responsibility: Tests for the useAdminAiModels presentation hook.
 *   getProviders and getModels repositories are mocked (fetch boundary).
 *   useAuth is mocked. TanStack Query client is real (QueryClientProvider).
 *
 * Cases:
 *   H01 — loading state on mount (isLoading=true, data=undefined).
 *   H02 — success: joins providers+models into rows with derived providerName/providerStatus.
 *   H03 — empty: providers=[] and models=[] → data.rows=[].
 *   H04 — error_network: getModels rejects → isError=true, error instanceof AdminAiNetworkError.
 *   H05 — permission_denied: getProviders returns 403 → AdminAiForbiddenError surfaces.
 *   H06 — refetch invalidates query and re-runs both fetches.
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { renderHook, waitFor, act } from "@testing-library/react";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useAdminAiModels } from "../presentation/useAdminAiModels";
import {
  AdminAiNetworkError,
  AdminAiForbiddenError,
} from "../data/errors";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../data/adminAiRepository", () => ({
  getProviders: vi.fn(),
  getModels: vi.fn(),
}));

vi.mock("../../auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

import { getProviders, getModels } from "../data/adminAiRepository";
import { useAuth } from "../../auth/presentation/AuthProvider";

const mockGetProviders = vi.mocked(getProviders);
const mockGetModels = vi.mocked(getModels);
const mockUseAuth = vi.mocked(useAuth);

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------

const MOCK_PROVIDER = {
  id: "prov-uuid-1",
  name: "litellm_verification_sandbox",
  provider_type: "litellm" as const,
  base_url: "http://localhost:4000",
  status: "active" as const,
  created_by: null,
  has_credentials: false,
  credential_auth_type: null,
  expires_at: null,
};

const MOCK_MODEL = {
  id: "model-uuid-1",
  provider_id: "prov-uuid-1",
  model_id: "gpt-4o-mini",
  model_type: "chat",
  capabilities: ["chat", "streaming"],
  enabled: true,
  is_default: true,
  pricing: {},
  latency_ms_avg: null,
};

// ---------------------------------------------------------------------------
// Wrapper
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        {children}
      </QueryClientProvider>
    );
  };
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("useAdminAiModels", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    mockUseAuth.mockReturnValue({
      status: "authenticated",
      user: null,
      signInAccepted: vi.fn(),
      logout: vi.fn().mockResolvedValue(undefined),
    });
  });

  it("H01 — loading state on mount: isLoading=true, data=undefined", () => {
    // Do NOT resolve so we can observe loading state
    mockGetProviders.mockReturnValue(new Promise(() => {}));
    mockGetModels.mockReturnValue(new Promise(() => {}));

    const { result } = renderHook(() => useAdminAiModels(), {
      wrapper: makeWrapper(),
    });

    expect(result.current.isLoading).toBe(true);
    expect(result.current.data).toBeUndefined();
    expect(result.current.isError).toBe(false);
  });

  it("H02 — success: joins providers+models into rows with derived providerName+providerStatus", async () => {
    mockGetProviders.mockResolvedValueOnce({ ok: true, value: [MOCK_PROVIDER] });
    mockGetModels.mockResolvedValueOnce({ ok: true, value: [MOCK_MODEL] });

    const { result } = renderHook(() => useAdminAiModels(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data).toBeDefined();
    expect(result.current.data?.providers).toHaveLength(1);
    expect(result.current.data?.models).toHaveLength(1);
    expect(result.current.data?.rows).toHaveLength(1);

    const row = result.current.data?.rows[0];
    expect(row?.model_id).toBe("gpt-4o-mini");
    expect(row?.providerName).toBe("litellm_verification_sandbox");
    expect(row?.providerStatus).toBe("active");
    expect(result.current.isError).toBe(false);
    expect(result.current.error).toBeNull();
  });

  it("H03 — empty: providers=[] → data.rows=[] (D-T002-EMPTY-STATE)", async () => {
    mockGetProviders.mockResolvedValueOnce({ ok: true, value: [] });
    mockGetModels.mockResolvedValueOnce({ ok: true, value: [] });

    const { result } = renderHook(() => useAdminAiModels(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    expect(result.current.data?.providers).toHaveLength(0);
    expect(result.current.data?.models).toHaveLength(0);
    expect(result.current.data?.rows).toHaveLength(0);
  });

  it("H04 — error_network: getModels rejects → isError=true, error instanceof AdminAiNetworkError", async () => {
    mockGetProviders.mockResolvedValueOnce({ ok: true, value: [MOCK_PROVIDER] });
    mockGetModels.mockResolvedValueOnce({
      ok: false,
      error: new AdminAiNetworkError("Network failed"),
    });

    const { result } = renderHook(() => useAdminAiModels(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.isSuccess).toBe(false);
    expect(result.current.error).toBeInstanceOf(AdminAiNetworkError);
    expect(result.current.data).toBeUndefined();
  });

  it("H05 — permission_denied: getProviders returns 403 → AdminAiForbiddenError surfaces", async () => {
    mockGetProviders.mockResolvedValueOnce({
      ok: false,
      error: new AdminAiForbiddenError(),
    });
    mockGetModels.mockResolvedValueOnce({ ok: true, value: [] });

    const { result } = renderHook(() => useAdminAiModels(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));

    expect(result.current.error).toBeInstanceOf(AdminAiForbiddenError);
  });

  it("H06 — refetch invalidates query and re-runs both fetches", async () => {
    mockGetProviders
      .mockResolvedValueOnce({ ok: true, value: [MOCK_PROVIDER] })
      .mockResolvedValueOnce({ ok: true, value: [MOCK_PROVIDER] });
    mockGetModels
      .mockResolvedValueOnce({ ok: true, value: [MOCK_MODEL] })
      .mockResolvedValueOnce({ ok: true, value: [MOCK_MODEL] });

    const { result } = renderHook(() => useAdminAiModels(), {
      wrapper: makeWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const callCountBefore = mockGetProviders.mock.calls.length;

    act(() => {
      result.current.refetch();
    });

    await waitFor(() =>
      expect(mockGetProviders.mock.calls.length).toBeGreaterThan(callCountBefore),
    );
  });
});
