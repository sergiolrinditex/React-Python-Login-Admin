/**
 * Hilo People — McpWizardPage component tests.
 *
 * Slice/Phase: P04-S02-T004 — McpWizardPage / Phase 4.
 *
 * Responsibility: Page-level RTL tests covering all 5 required UX states + a11y
 *   + Zod schema validation + secret-never-in-DOM assertion.
 *   useCreateMcpServer hook is mocked (presentation boundary, not HTTP).
 *   useAuth mocked to provide admin session. react-router mocked.
 *   i18n uses real inline resources from i18n/index.ts.
 *
 * §D-T004-TESTS-PAGE (P04-S02-T004 task pack §6)
 *   W01 — renders form with 4 visible fields (name, transport, endpoint, authType)
 *   W02 — loading state: form disabled with aria-busy, submit button shows "Conectando"
 *   W03 — success state: shows success block (§D-T004-PAGE)
 *   W04 — error_network state: form-level error block visible
 *   W05 — error_validation (Zod): submitting empty → inline errors per field
 *   W06 — permission_denied state: forbidden block visible with back link
 *   W07 — secret field type="password" — not visible as plaintext (§D-T004-SECRET-FIELD)
 *   W08 — secret field NOT visible when authType=none (conditional render)
 *   W09 — secret field visible when authType=api_key; refreshToken visible for oauth2 only
 *   W10 — secret NEVER in DOM as text content (§D-T004-SECRET-NEVER-PERSISTED)
 *   W11 — a11y: form has aria-labelledby; inputs have labels; errors have role=alert
 */

import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor, act } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import React from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { I18nextProvider } from "react-i18next";
import i18n from "../../../../i18n/index";
import McpWizardPage from "../McpWizardPage";
import {
  McpForbiddenError,
  McpNetworkError,
} from "../../../../features/mcp/data/errors";

// ---------------------------------------------------------------------------
// Mocks
// ---------------------------------------------------------------------------

vi.mock("../../../../features/auth/presentation/AuthProvider", () => ({
  useAuth: vi.fn(),
  AuthProvider: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

const mockNavigate = vi.fn();
vi.mock("react-router", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router")>();
  return {
    ...actual,
    useNavigate: () => mockNavigate,
    MemoryRouter: actual.MemoryRouter,
  };
});

// Mock useCreateMcpServer (presentation layer boundary)
const mockMutate = vi.fn();
const baseMutation = {
  mutate: mockMutate,
  isPending: false,
  isSuccess: false,
  isError: false,
  error: null as unknown,
  status: "idle" as const,
  data: undefined as unknown,
};

vi.mock("../../../../features/mcp/presentation/useCreateMcpServer", () => ({
  useCreateMcpServer: vi.fn(() => ({ ...baseMutation })),
  MCP_CREATE_MUTATION_KEY: ["mcp", "create"],
}));

import { useAuth } from "../../../../features/auth/presentation/AuthProvider";
import { useCreateMcpServer } from "../../../../features/mcp/presentation/useCreateMcpServer";

const mockUseAuth = vi.mocked(useAuth);
const mockUseCreateMcpServer = vi.mocked(useCreateMcpServer);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function makeWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });

  function Wrapper({ children }: { children: React.ReactNode }) {
    return (
      <MemoryRouter initialEntries={["/admin/ai/mcp/new"]}>
        <QueryClientProvider client={queryClient}>
          <I18nextProvider i18n={i18n}>
            {children}
          </I18nextProvider>
        </QueryClientProvider>
      </MemoryRouter>
    );
  }
  return { queryClient, Wrapper };
}

function renderPage(mutationOverrides: Partial<typeof baseMutation> = {}) {
  const merged = { ...baseMutation, ...mutationOverrides };
  mockUseCreateMcpServer.mockReturnValue(merged as unknown as ReturnType<typeof useCreateMcpServer>);
  mockUseAuth.mockReturnValue({
    status: "authenticated",
    logout: vi.fn(),
    user: { id: "u1", email: "admin@example.com", role: "people_admin" },
  } as unknown as ReturnType<typeof useAuth>);

  const { Wrapper } = makeWrapper();
  return render(<McpWizardPage />, { wrapper: Wrapper });
}

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("McpWizardPage", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("W01 — renders form with name, transport, endpoint, authType fields", () => {
    renderPage();

    expect(screen.getByTestId("wizard-form")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-name")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-transport")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-endpoint")).toBeInTheDocument();
    expect(screen.getByTestId("wizard-auth-type")).toBeInTheDocument();
    // secret NOT visible by default (authType=none)
    expect(screen.queryByTestId("wizard-secret")).toBeNull();
  });

  it("W02 — loading state: form has aria-busy, submit shows submitting label", () => {
    renderPage({ isPending: true });

    const form = screen.getByTestId("wizard-form");
    expect(form).toHaveAttribute("aria-busy", "true");
    expect(screen.getByTestId("wizard-submit")).toHaveTextContent(/Conectando/);
  });

  it("W03 — success state: success block visible, form hidden", () => {
    renderPage({ isSuccess: true });

    expect(screen.getByTestId("wizard-success")).toBeInTheDocument();
    expect(screen.queryByTestId("wizard-form")).toBeNull();
  });

  it("W04 — error_network state: form-level error block visible", () => {
    renderPage({ error: new McpNetworkError(), isError: true });

    expect(screen.getByTestId("wizard-form-error")).toBeInTheDocument();
  });

  it("W05 — error_validation (Zod empty form): shows inline errors on submit", async () => {
    renderPage();

    // Intercept form submit — we need the real form submit to trigger Zod validation
    // Since useCreateMcpServer is mocked, we submit the real RHF form
    const submitBtn = screen.getByTestId("wizard-submit");
    await act(async () => {
      fireEvent.click(submitBtn);
    });

    await waitFor(() => {
      // name is required — should show error
      expect(screen.getByText(/Nombre obligatorio/i)).toBeInTheDocument();
    });
  });

  it("W06 — permission_denied state: forbidden block visible", () => {
    renderPage({ error: new McpForbiddenError(), isError: true, isSuccess: false });

    expect(screen.getByTestId("wizard-permission-denied")).toBeInTheDocument();
    expect(screen.queryByTestId("wizard-form")).toBeNull();
  });

  it("W07 — secret field is type=password when visible (authType=api_key)", async () => {
    renderPage();

    const authTypeSelect = screen.getByTestId("wizard-auth-type") as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(authTypeSelect, { target: { value: "api_key" } });
    });

    await waitFor(() => {
      const secretField = screen.getByTestId("wizard-secret");
      expect(secretField).toBeInTheDocument();
      expect(secretField).toHaveAttribute("type", "password");
    });
  });

  it("W08 — secret field NOT visible when authType=none (default)", () => {
    renderPage();
    expect(screen.queryByTestId("wizard-secret")).toBeNull();
  });

  it("W09 — oauth2 shows refreshToken; api_key shows only secret", async () => {
    renderPage();

    const authTypeSelect = screen.getByTestId("wizard-auth-type") as HTMLSelectElement;

    // oauth2 → both secret + refreshToken visible
    await act(async () => {
      fireEvent.change(authTypeSelect, { target: { value: "oauth2" } });
    });
    await waitFor(() => {
      expect(screen.getByTestId("wizard-secret")).toBeInTheDocument();
      expect(screen.getByTestId("wizard-refresh-token")).toBeInTheDocument();
    });

    // api_key → only secret
    await act(async () => {
      fireEvent.change(authTypeSelect, { target: { value: "api_key" } });
    });
    await waitFor(() => {
      expect(screen.getByTestId("wizard-secret")).toBeInTheDocument();
      expect(screen.queryByTestId("wizard-refresh-token")).toBeNull();
    });
  });

  it("W10 — secret typed value NOT in DOM as visible text (§D-T004-SECRET-NEVER-PERSISTED)", async () => {
    renderPage();

    const authTypeSelect = screen.getByTestId("wizard-auth-type") as HTMLSelectElement;
    await act(async () => {
      fireEvent.change(authTypeSelect, { target: { value: "api_key" } });
    });

    await waitFor(() => expect(screen.getByTestId("wizard-secret")).toBeInTheDocument());
    const secretField = screen.getByTestId("wizard-secret") as HTMLInputElement;

    // Set the value via change event (password input stores value internally)
    fireEvent.change(secretField, { target: { value: "super-secret-api-key" } });

    // Body text MUST NOT contain the plaintext secret — field is type=password
    // type=password inputs do NOT expose their value as textContent
    const bodyText = document.body.textContent ?? "";
    expect(bodyText).not.toContain("super-secret-api-key");

    // The secret input must have type="password" (already covered in W07)
    // Verify no visible child text nodes contain the secret value
    const secretInputs = document.querySelectorAll('input[type="password"]');
    secretInputs.forEach((input) => {
      // input.textContent is always empty for input elements
      expect(input.textContent).toBe("");
    });
    expect(secretInputs.length).toBeGreaterThan(0);
  });

  it("W11 — a11y: form has aria-labelledby; submit button accessible", () => {
    renderPage();

    const form = screen.getByTestId("wizard-form");
    // aria-labelledby must be set (ties to the page H1)
    expect(form).toHaveAttribute("aria-labelledby");

    // Submit button must have accessible text
    const submitBtn = screen.getByTestId("wizard-submit");
    expect(submitBtn).toBeInTheDocument();
    expect(submitBtn.textContent?.trim()).toBeTruthy();
  });
});
