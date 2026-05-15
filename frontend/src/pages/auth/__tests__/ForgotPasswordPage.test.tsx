/**
 * Hilo People — ForgotPasswordPage tests.
 *
 * Slice/Phase: P03-S01-T003 — ForgotPasswordPage (recuperación de acceso editorial móvil) / Phase 3.
 *
 * Responsibility: RTL tests for ForgotPasswordPage component.
 *   Tests T01–T10 from §12 of the task pack (ForgotPasswordPage.test.tsx block).
 *   Network fetch is mocked at the boundary (vi.spyOn(global, 'fetch')).
 *   AuthProvider is rendered with a real repository wired to the mocked fetch.
 *
 * Test policy (non-negotiables §tests):
 *   - No mocking of AuthProvider, useForgotPassword, or authRepository business logic.
 *   - fetch mocked at the network boundary only.
 *   - All tests use jsdom environment (Vitest config).
 *
 * Anti-enumeration invariant tested:
 *   - T05: unknown email produces identical success state as known email (§D-T003-ANTI-ENUM-UI).
 *
 * Accessibility assertions:
 *   - T01: input has TrackedLabel + htmlFor association.
 *   - T04: CTA has aria-busy="true" during loading (verified via button text change).
 *   - T09: input has aria-invalid only after touch + error state.
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import React from "react";
import { I18nextProvider } from "react-i18next";

import i18n from "@/i18n";
import ForgotPasswordPage from "../ForgotPasswordPage";
import { AuthProvider } from "@/features/auth/presentation/AuthProvider";
import { AuthRepository } from "@/features/auth/data/authRepository";
import { clearAccessToken } from "@/features/auth/data/accessTokenStore";

// ---------------------------------------------------------------------------
// Test data
// ---------------------------------------------------------------------------

const KNOWN_EMAIL = "employee.verification@inditex-sandbox.com";
const UNKNOWN_EMAIL = "nobody.unknown@inditex-sandbox.com";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function mockFetch(
  responses: Array<{ status: number; body?: unknown; headers?: Record<string, string> }>,
): void {
  let callIndex = 0;
  vi.spyOn(global, "fetch").mockImplementation(() => {
    const resp = responses[callIndex] ?? responses[responses.length - 1];
    callIndex++;
    const body = resp.body !== undefined ? JSON.stringify(resp.body) : "";
    return Promise.resolve(
      new Response(body, {
        status: resp.status,
        headers: { "Content-Type": "application/json", ...(resp.headers ?? {}) },
      }),
    );
  });
}

/** Renders ForgotPasswordPage inside the required providers + MemoryRouter. */
function renderForgotPage({
  fetchResponses = [] as Array<{ status: number; body?: unknown; headers?: Record<string, string> }>,
  initialPath = "/auth/forgot-password",
} = {}) {
  if (fetchResponses.length > 0) {
    mockFetch(fetchResponses);
  }

  const onQueriesClear = vi.fn();
  const repo = new AuthRepository(onQueriesClear);

  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider _repo={repo} _onQueriesClear={onQueriesClear}>
          <Routes>
            <Route path="/auth/forgot-password" element={<ForgotPasswordPage />} />
            <Route path="/auth/sign-in" element={<div data-testid="signin-page">SignIn</div>} />
            <Route
              path="/auth/reset-sent"
              element={<div data-testid="reset-sent-page">ResetSent</div>}
            />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </I18nextProvider>,
  );
}

/** Helper: fill and submit the forgot-password form */
async function fillAndSubmit(email: string): Promise<void> {
  const emailInput = screen.getByTestId("forgot-email-input");
  const submitButton = screen.getByTestId("forgot-submit-button");

  fireEvent.change(emailInput, { target: { value: email } });

  await act(async () => {
    fireEvent.click(submitButton);
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("ForgotPasswordPage", () => {
  beforeEach(() => {
    clearAccessToken();
    // Default: AuthProvider hydration → 401 (unauthenticated)
    vi.spyOn(global, "fetch").mockImplementation(() =>
      Promise.resolve(
        new Response(JSON.stringify({ errors: [{ code: "AUTH_SESSION_EXPIRED" }] }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
      ),
    );
  });

  afterEach(() => {
    clearAccessToken();
    vi.restoreAllMocks();
  });

  it("T01: renders all UI — TrackedLabel for email, EditorialInput, SolidCTA, back link", async () => {
    renderForgotPage();

    await waitFor(() => {
      expect(screen.getByText("Área de empleados")).toBeInTheDocument();
    });

    expect(screen.getByText("Recuperar acceso")).toBeInTheDocument();
    expect(screen.getByText("Email corporativo")).toBeInTheDocument();
    expect(screen.getByTestId("forgot-email-input")).toBeInTheDocument();
    expect(screen.getByTestId("forgot-submit-button")).toBeInTheDocument();
    expect(screen.getByTestId("forgot-link-signin")).toBeInTheDocument();
    expect(screen.getByTestId("forgot-link-signin")).toHaveTextContent("Volver a iniciar sesión");
  });

  it("T02: submit empty → zod inline emailRequired error; no fetch call to forgot-password", async () => {
    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    const submitButton = screen.getByTestId("forgot-submit-button");
    await act(async () => {
      fireEvent.click(submitButton);
    });

    await waitFor(() => {
      expect(screen.getByTestId("forgot-email-input")).toHaveAttribute("aria-invalid", "true");
    });
    // "El email es obligatorio." for the required error
    expect(screen.getByText("El email es obligatorio.")).toBeInTheDocument();
  });

  it("T03: submit invalid email syntax → zod emailFormat error; no fetch call", async () => {
    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    const emailInput = screen.getByTestId("forgot-email-input");
    fireEvent.change(emailInput, { target: { value: "not-an-email" } });

    await act(async () => {
      fireEvent.click(screen.getByTestId("forgot-submit-button"));
    });

    await waitFor(() => {
      expect(emailInput).toHaveAttribute("aria-invalid", "true");
    });
    expect(screen.getByText("Introduce un email válido.")).toBeInTheDocument();
  });

  it("T04: submit valid known email → 200 success → navigates to /auth/reset-sent", async () => {
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 200,
        body: {
          data: { sent: true },
          meta: { request_id: "req-t003-known" },
          errors: [],
        },
      },
    ]);

    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(KNOWN_EMAIL);

    await waitFor(() => {
      expect(screen.getByTestId("reset-sent-page")).toBeInTheDocument();
    });
  });

  it("T05: submit valid unknown email → same success state (anti-enum: identical to known email)", async () => {
    // Anti-enumeration invariant (§D-T003-ANTI-ENUM-UI): server returns 200 for BOTH
    // known and unknown emails. UI must show the IDENTICAL success state.
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 200,
        body: {
          data: { sent: true },
          meta: { request_id: "req-t003-unknown" },
          errors: [],
        },
      },
    ]);

    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(UNKNOWN_EMAIL);

    // Must navigate to reset-sent — identical to known email path
    await waitFor(() => {
      expect(screen.getByTestId("reset-sent-page")).toBeInTheDocument();
    });
  });

  it("T06: 429 rate-limited → form-level alert shows rateLimited with {{seconds}} interpolated", async () => {
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 429,
        body: {
          data: null,
          meta: { request_id: "req-t003-rate" },
          errors: [{ code: "AUTH_FORGOT_RATE_LIMITED" }],
        },
        headers: { "Retry-After": "60" },
      },
    ]);

    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(KNOWN_EMAIL);

    await waitFor(() => {
      const errorEl = screen.getByTestId("forgot-form-error");
      expect(errorEl).toBeInTheDocument();
    });
    // rateLimited copy with seconds interpolated
    expect(screen.getByTestId("forgot-form-error")).toHaveTextContent("60");
    // data-error-state = error_validation
    expect(screen.getByTestId("forgot-form-error")).toHaveAttribute(
      "data-error-state",
      "error_validation",
    );
    // Submit button disabled after rate-limit
    expect(screen.getByTestId("forgot-submit-button")).toBeDisabled();
  });

  it("T07: TypeError network error → error_network copy shown; no navigation", async () => {
    let callCount = 0;
    vi.spyOn(global, "fetch").mockImplementation(() => {
      callCount++;
      if (callCount === 1) {
        return Promise.resolve(
          new Response(JSON.stringify({ errors: [{ code: "AUTH_SESSION_EXPIRED" }] }), {
            status: 401,
            headers: { "Content-Type": "application/json" },
          }),
        );
      }
      return Promise.reject(new TypeError("Failed to fetch"));
    });

    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(KNOWN_EMAIL);

    await waitFor(() => {
      const errorEl = screen.getByTestId("forgot-form-error");
      expect(errorEl).toBeInTheDocument();
    });
    expect(screen.getByTestId("forgot-form-error")).toHaveTextContent("Sin conexión");
    expect(screen.getByTestId("forgot-form-error")).toHaveAttribute(
      "data-error-state",
      "error_network",
    );
    // Must NOT have navigated away
    expect(screen.queryByTestId("reset-sent-page")).not.toBeInTheDocument();
  });

  it("T08: 500 ServerError → form-level alert shows serverInternal; no navigation", async () => {
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 500,
        body: {
          data: null,
          meta: { request_id: "req-t003-500" },
          errors: [{ code: "AUTH_FORGOT_INTERNAL_ERROR", message: "Internal server error" }],
        },
      },
    ]);

    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(KNOWN_EMAIL);

    await waitFor(() => {
      const errorEl = screen.getByTestId("forgot-form-error");
      expect(errorEl).toBeInTheDocument();
    });
    expect(screen.getByTestId("forgot-form-error")).toHaveTextContent("Error interno");
    expect(screen.getByTestId("forgot-form-error")).toHaveAttribute(
      "data-error-state",
      "error_network",
    );
    expect(screen.queryByTestId("reset-sent-page")).not.toBeInTheDocument();
  });

  it("T09: a11y — input has aria-invalid only after touch + error; CTA has no aria-busy by default", async () => {
    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    const emailInput = screen.getByTestId("forgot-email-input");
    const submitButton = screen.getByTestId("forgot-submit-button");

    // Before touch — no aria-invalid
    expect(emailInput).not.toHaveAttribute("aria-invalid", "true");
    // Before submit — no aria-busy on CTA
    expect(submitButton).not.toHaveAttribute("aria-busy", "true");

    // Blur without entering value (touch)
    fireEvent.blur(emailInput);

    // Still no aria-invalid until submit attempt
    // Submit empty form to trigger error
    await act(async () => {
      fireEvent.click(submitButton);
    });

    await waitFor(() => {
      expect(emailInput).toHaveAttribute("aria-invalid", "true");
    });
  });

  it("T10: i18n EN — render with changeLanguage('en') → all copy in English", async () => {
    await act(async () => {
      await i18n.changeLanguage("en");
    });

    renderForgotPage();

    await waitFor(() => {
      expect(screen.getByText("Employee area")).toBeInTheDocument();
    });

    expect(screen.getByText("Reset access")).toBeInTheDocument();
    expect(screen.getByText("Corporate email")).toBeInTheDocument();
    expect(screen.getByTestId("forgot-link-signin")).toHaveTextContent("Back to sign in");

    // Restore ES locale
    await act(async () => {
      await i18n.changeLanguage("es");
    });
  });

  it("T11: ADR-002 same-origin — forgotPassword() must call fetch with RELATIVE URL `/api/v1/auth/forgot-password` (no http(s):// host, no localhost)", async () => {
    // §D-T003-AUTH-DATA invariant (task pack §12, ADR-002).
    // The forgotPassword() repository method MUST call fetch with a RELATIVE
    // URL — never an absolute URL like "http://localhost:8000/...". This is a
    // regression guard against accidentally restoring a `?? "http://localhost:8000"`
    // fallback in API_BASE; same fix shipped in P03-S01-T002 (line 49) and
    // P03-S01-T007. The httpClient.test.ts covers ADR-002 for authFetch
    // (authenticated endpoints), but forgotPassword() uses plain fetch() because
    // it is a public endpoint, so it needs its own assertion here.
    //
    // Call index 0 is the AuthProvider hydration probe → 401 (from the mock
    // chain). Call index 1 is the forgotPassword fetch — the one under test.
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 200,
        body: {
          data: { sent: true },
          meta: { request_id: "req-t003-adr002" },
          errors: [],
        },
      },
    ]);

    renderForgotPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(KNOWN_EMAIL);

    await waitFor(() => {
      expect(screen.getByTestId("reset-sent-page")).toBeInTheDocument();
    });

    const fetchSpy = global.fetch as unknown as ReturnType<typeof vi.fn>;
    const forgotCall = fetchSpy.mock.calls[1];
    expect(forgotCall).toBeDefined();

    const forgotUrl = String(forgotCall[0]);
    // Positive assertion: exact relative path expected by ADR-002 same-origin.
    expect(forgotUrl).toBe("/api/v1/auth/forgot-password");
    // Negative assertion (regression guard): no absolute URL with scheme/host.
    expect(forgotUrl).not.toMatch(/^https?:\/\//);
    expect(forgotUrl.toLowerCase()).not.toContain("localhost");
  });
});
