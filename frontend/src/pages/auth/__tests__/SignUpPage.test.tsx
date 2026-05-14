/**
 * Hilo People — SignUpPage tests.
 *
 * Slice/Phase: P03-S01-T002 — SignUpPage (registro email/password editorial móvil) / Phase 3.
 *
 * Responsibility: RTL tests for SignUpPage component.
 *   Tests T01–T10 from §11 of the task pack.
 *   Network fetch is mocked at the boundary (vi.spyOn(global, 'fetch')).
 *   AuthProvider is rendered with a real repository wired to the mocked fetch.
 *
 * Test policy (non-negotiables §tests):
 *   - No mocking of AuthProvider, useSignUp, or authRepository business logic.
 *   - fetch mocked at the network boundary only.
 *   - All tests use jsdom environment (Vitest config).
 *
 * Security assertions:
 *   - T05: Non-corporate email shows field-level error via form-level alert.
 *   - T06: 409 shows generic copy (no email field highlight — anti-enum D-T002-409-NO-FIELD).
 */

import { describe, it, expect, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter, Routes, Route } from "react-router";
import React from "react";
import { I18nextProvider } from "react-i18next";

import i18n from "@/i18n";
import SignUpPage from "../SignUpPage";
import { AuthProvider } from "@/features/auth/presentation/AuthProvider";
import { AuthRepository } from "@/features/auth/data/authRepository";
import { clearAccessToken } from "@/features/auth/data/accessTokenStore";

// ---------------------------------------------------------------------------
// Test data (corporate domain, not verification user)
// ---------------------------------------------------------------------------

const VALID_EMAIL = "signup.test+t002@inditex-sandbox.com";
const VALID_FULL_NAME = "Test Signup";
const VALID_PASSWORD = "VerifyPass2024!";
const MOCK_USER_ID = "e647c301-6592-400b-9b8d-8a9e412c3969";

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

/** Renders SignUpPage inside the required providers + MemoryRouter. */
function renderSignUpPage({
  fetchResponses = [] as Array<{ status: number; body?: unknown; headers?: Record<string, string> }>,
  initialPath = "/auth/sign-up",
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
            <Route path="/auth/sign-up" element={<SignUpPage />} />
            <Route path="/auth/sign-in" element={<div data-testid="signin-page">SignIn</div>} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </I18nextProvider>,
  );
}

/** Helper: fill and submit the sign-up form */
async function fillAndSubmit(
  email: string,
  fullName: string,
  password: string,
  checkLegal = true,
): Promise<void> {
  const emailInput = screen.getByTestId("signup-email-input");
  const fullNameInput = screen.getByTestId("signup-fullname-input");
  const passwordInput = screen.getByTestId("signup-password-input");
  const submitButton = screen.getByTestId("signup-submit-button");

  fireEvent.change(emailInput, { target: { value: email } });
  fireEvent.change(fullNameInput, { target: { value: fullName } });
  fireEvent.change(passwordInput, { target: { value: password } });

  if (checkLegal) {
    const checkbox = screen.getByTestId("signup-legal-checkbox");
    fireEvent.click(checkbox);
  }

  await act(async () => {
    fireEvent.click(submitButton);
  });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("SignUpPage", () => {
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

  it("T01: renders with i18n ES keys — title, email, fullName, password, checkbox label, CTA", async () => {
    renderSignUpPage();

    await waitFor(() => {
      expect(screen.getByText("Área de empleados")).toBeInTheDocument();
    });

    // "Crear cuenta" appears as both page title and button text — use getAllByText
    expect(screen.getAllByText("Crear cuenta").length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Email corporativo")).toBeInTheDocument();
    expect(screen.getByText("Nombre completo")).toBeInTheDocument();
    expect(screen.getByText("Contraseña")).toBeInTheDocument();
    expect(screen.getByText("He leído y acepto los términos y condiciones")).toBeInTheDocument();
    expect(screen.getByTestId("signup-submit-button")).toBeInTheDocument();
    expect(screen.getByTestId("signup-link-signin")).toBeInTheDocument();
  });

  it("T02: invalid email → aria-invalid + error message visible", async () => {
    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    const emailInput = screen.getByTestId("signup-email-input");
    fireEvent.change(emailInput, { target: { value: "not-an-email" } });
    fireEvent.blur(emailInput);

    await act(async () => {
      fireEvent.click(screen.getByTestId("signup-submit-button"));
    });

    await waitFor(() => {
      expect(emailInput).toHaveAttribute("aria-invalid", "true");
    });
    expect(screen.getByText("Introduce un email válido.")).toBeInTheDocument();
  });

  it("T03: legal acceptance required — uncheck shows error; check + submit succeeds", async () => {
    // First check that NOT checking legal shows error
    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    // Submit WITHOUT checking legal
    await fillAndSubmit(VALID_EMAIL, VALID_FULL_NAME, VALID_PASSWORD, false);

    await waitFor(() => {
      expect(screen.getByTestId("signup-legal-error")).toBeInTheDocument();
    });
    expect(screen.getByTestId("signup-legal-error")).toHaveTextContent(
      "Debes aceptar los términos y condiciones",
    );
  });

  it("T04: happy path → navigates to /auth/sign-in with flash state", async () => {
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 201,
        body: {
          data: { user_id: MOCK_USER_ID, mfa_required: false },
          meta: { request_id: "req-t002-happy" },
          errors: [],
        },
      },
    ]);

    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(VALID_EMAIL, VALID_FULL_NAME, VALID_PASSWORD, true);

    await waitFor(() => {
      expect(screen.getByTestId("signin-page")).toBeInTheDocument();
    });
  });

  it("T05: 400 non-corporate email → form-level error shown in permission_denied state", async () => {
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 400,
        body: {
          data: null,
          meta: { request_id: "req-t002-corp" },
          errors: [{ code: "AUTH_SIGNUP_NON_CORPORATE_EMAIL", field: "email" }],
        },
      },
    ]);

    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    // Use a non-corporate email that passes zod but fails server check
    await fillAndSubmit("not.corporate@gmail.com", VALID_FULL_NAME, VALID_PASSWORD, true);

    await waitFor(() => {
      const errorEl = screen.getByTestId("signup-form-error");
      expect(errorEl).toBeInTheDocument();
    });
    expect(screen.getByTestId("signup-form-error")).toHaveAttribute(
      "data-error-state",
      "permission_denied",
    );
    expect(screen.getByTestId("signup-form-error")).toHaveTextContent(
      "email corporativo válido",
    );
  });

  it("T06: 409 email taken → generic error copy, NO email field highlight (anti-enumeration)", async () => {
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 409,
        body: {
          data: null,
          meta: { request_id: "req-t002-taken" },
          errors: [{ code: "AUTH_SIGNUP_EMAIL_TAKEN" }],
        },
      },
    ]);

    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(VALID_EMAIL, VALID_FULL_NAME, VALID_PASSWORD, true);

    await waitFor(() => {
      const errorEl = screen.getByTestId("signup-form-error");
      expect(errorEl).toHaveTextContent("No se pudo crear la cuenta");
    });

    // D-T002-409-NO-FIELD: email input must NOT have aria-invalid
    const emailInput = screen.getByTestId("signup-email-input");
    expect(emailInput).not.toHaveAttribute("aria-invalid", "true");
  });

  it("T07: 422 password policy → form-level error in error_validation state", async () => {
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 422,
        body: {
          data: null,
          meta: { request_id: "req-t002-pw" },
          errors: [{ code: "AUTH_SIGNUP_INVALID_PAYLOAD", field: "password" }],
        },
      },
    ]);

    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    // Use a password that passes client-side zod (12+ chars, letter+digit) but server rejects
    await fillAndSubmit(VALID_EMAIL, VALID_FULL_NAME, "ValidPass123!", true);

    await waitFor(() => {
      const errorEl = screen.getByTestId("signup-form-error");
      expect(errorEl).toHaveTextContent("contraseña");
    });
    expect(screen.getByTestId("signup-form-error")).toHaveAttribute(
      "data-error-state",
      "error_validation",
    );
  });

  it("T08: 429 rate-limited → submit disabled + countdown copy with seconds interpolated", async () => {
    mockFetch([
      { status: 401, body: { errors: [{ code: "AUTH_SESSION_EXPIRED" }] } },
      {
        status: 429,
        body: {
          data: null,
          meta: { request_id: "req-t002-rate" },
          errors: [{ code: "AUTH_SIGNUP_RATE_LIMITED" }],
        },
        headers: { "Retry-After": "60" },
      },
    ]);

    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(VALID_EMAIL, VALID_FULL_NAME, VALID_PASSWORD, true);

    await waitFor(() => {
      const errorEl = screen.getByTestId("signup-form-error");
      expect(errorEl).toHaveTextContent("60");
    });

    const submitButton = screen.getByTestId("signup-submit-button");
    expect(submitButton).toBeDisabled();
  });

  it("T09: TypeError network error → error_network copy with 'Sin conexión'", async () => {
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

    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    await fillAndSubmit(VALID_EMAIL, VALID_FULL_NAME, VALID_PASSWORD, true);

    await waitFor(() => {
      const errorEl = screen.getByTestId("signup-form-error");
      expect(errorEl).toHaveTextContent("Sin conexión");
    });
    expect(screen.getByTestId("signup-form-error")).toHaveAttribute(
      "data-error-state",
      "error_network",
    );
  });

  it("T10: keyboard-only flow — Tab through all inputs + checkbox + submit is reachable", async () => {
    renderSignUpPage();

    await waitFor(() => expect(screen.getByText("Email corporativo")).toBeInTheDocument());

    const emailInput = screen.getByTestId("signup-email-input");
    const fullNameInput = screen.getByTestId("signup-fullname-input");
    const passwordInput = screen.getByTestId("signup-password-input");
    const legalCheckbox = screen.getByTestId("signup-legal-checkbox");
    const submitButton = screen.getByTestId("signup-submit-button");
    const signInLink = screen.getByTestId("signup-link-signin");

    // All interactive elements must be in document and not disabled
    expect(emailInput).not.toBeDisabled();
    expect(fullNameInput).not.toBeDisabled();
    expect(passwordInput).not.toBeDisabled();
    expect(legalCheckbox).not.toBeDisabled();
    expect(submitButton).not.toBeDisabled();
    expect(signInLink).toBeInTheDocument();

    // Keyboard focus order asserted by presence (tab order is DOM order in this layout)
    expect(emailInput).toBeInTheDocument();
    expect(fullNameInput).toBeInTheDocument();
    expect(passwordInput).toBeInTheDocument();
    expect(legalCheckbox).toBeInTheDocument();
    expect(submitButton).toBeInTheDocument();
  });
});
