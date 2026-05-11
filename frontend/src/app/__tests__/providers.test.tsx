/**
 * Hilo People — Providers smoke test.
 *
 * Slice/Phase: P00-S01-T002 — Frontend dependency pack / Phase 0 Scaffold.
 *   WRITE_SET_DRIFT (3rd candidate extension): direct proof that the Providers
 *   composition root renders without throwing (Acceptance A7).
 *
 * Test strategy: real React render via @testing-library/react in jsdom.
 *   - No mocking of QueryClient or i18n — real instances constructed inside.
 *   - Uses fresh QueryClient injected via ProvidersProps seam to avoid
 *     cross-test cache bleed.
 *   - Uses the default i18n bootstrap instance (resource-less, lng="es").
 *
 * Key deps: vitest ^3.0.0, @testing-library/react ^16.3.2, jsdom ^25.0.0.
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { QueryClient } from "@tanstack/react-query";
import { Providers, createDefaultQueryClient } from "../providers";

// Ensure DOM is cleaned between tests (RTL does this automatically with
// @testing-library/react 16, but explicit cleanup is harmless).
afterEach(cleanup);

// ---------------------------------------------------------------------------
// Helper: fresh QueryClient per test to prevent cache bleed.
// ---------------------------------------------------------------------------
function freshClient(): QueryClient {
  return createDefaultQueryClient();
}

// ---------------------------------------------------------------------------
// Suite: Providers composition root
// ---------------------------------------------------------------------------
describe("Providers", () => {
  it("renders children without throwing (A7 — smoke render)", () => {
    render(
      <Providers queryClient={freshClient()}>
        <div data-testid="ok">child</div>
      </Providers>,
    );
    expect(screen.getByTestId("ok")).toBeInTheDocument();
  });

  it("renders children when no queryClient or i18n is injected (defaults used)", () => {
    render(
      <Providers>
        <span data-testid="default-child">default</span>
      </Providers>,
    );
    expect(screen.getByTestId("default-child")).toBeInTheDocument();
  });

  it("emits BEFORE and AFTER console.info logs when VITE_ENABLE_VERBOSE_LOGGING=true (A8)", () => {
    const originalEnv = import.meta.env.VITE_ENABLE_VERBOSE_LOGGING;
    // Temporarily enable verbose logging for this test.
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", "true");

    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => {
      // no-op: suppress output in test runner
    });

    render(
      <Providers queryClient={freshClient()}>
        <div data-testid="log-child" />
      </Providers>,
    );

    const calls = infoSpy.mock.calls.map((c) => String(c[0]));
    expect(calls.some((m) => m.includes("providers.init.start"))).toBe(true);
    expect(calls.some((m) => m.includes("providers.init.ok"))).toBe(true);

    infoSpy.mockRestore();
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", originalEnv ?? "false");
    // Restore original value
    cleanup();
  });

  it("emits NO console.info logs when VITE_ENABLE_VERBOSE_LOGGING=false (A8 silent mode)", () => {
    vi.stubEnv("VITE_ENABLE_VERBOSE_LOGGING", "false");

    const infoSpy = vi.spyOn(console, "info").mockImplementation(() => {
      // no-op
    });

    render(
      <Providers queryClient={freshClient()}>
        <div data-testid="silent-child" />
      </Providers>,
    );

    const calls = infoSpy.mock.calls.map((c) => String(c[0]));
    const hasVerbose = calls.some(
      (m) =>
        m.includes("providers.init.start") || m.includes("providers.init.ok"),
    );
    expect(hasVerbose).toBe(false);

    infoSpy.mockRestore();
    cleanup();
  });
});
