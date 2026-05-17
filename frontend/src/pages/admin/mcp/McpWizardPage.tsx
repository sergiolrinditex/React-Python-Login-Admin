/**
 * Hilo People — McpWizardPage.
 *
 * Slice/Phase: P04-S02-T004 — McpWizardPage / Phase 4.
 * Route: /admin/ai/mcp/new — Admin form to register a new MCP server.
 * Consumes POST /api/v1/admin/ai/mcp/servers (createServer).
 * Single-form layout (§D-T004-FORM-SINGLE-PAGE); RequireRole guard at router.
 *
 * §D-T004-PAGE. UX states (§4.2): loading, error_network, error_validation,
 *   permission_denied, success. empty = N/A. All 5 implemented + tested.
 *
 * Security (§D-T004-SECRET-FIELD, §D-T004-SECRET-NEVER-PERSISTED):
 *   secret field type="password" autoComplete="off"; never logged; never
 *   stored in localStorage/sessionStorage; response uses has_credential bool.
 *
 * File-size compliance (§D-T004-PAGE-SPLIT-STYLES, R-6): page composes four
 *   local helpers — `_McpWizardPage.styles.ts`, `_McpWizardPage.select-field.tsx`,
 *   `_McpWizardPage.feedback.tsx`, `_McpWizardPage.form.tsx`.
 *
 * a11y: htmlFor labels, aria-busy on <form>, aria-live polite for async
 *   errors, 44px min tap targets, keyboard tab order matches §3.5 spec.
 *
 * i18n namespace: "mcp" (wizard.* keys — §D-T004-I18N).
 *
 * Key deps beyond imports: react-hook-form ^7, zod ^3, useCreateMcpServer
 *   hook, AdminShell (design system).
 */

import { type ReactNode, useId } from "react";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router";
import AdminShell from "../../../shared/design-system/AdminShell";
import { useAuth } from "../../../features/auth/presentation/AuthProvider";
import { useCreateMcpServer } from "../../../features/mcp/presentation/useCreateMcpServer";
import {
  McpValidationError,
  McpEndpointNotAllowedError,
  McpForbiddenError,
} from "../../../features/mcp/data/errors";
import type { CreateServerRequest } from "../../../features/mcp/domain/types";
import { logVerbose, logWarn } from "../../../features/mcp/data/logger";
import { ROUTE_ADMIN_AI_MCP } from "../../../app/router";
import {
  WIZARD_HEADER_STYLE,
  WIZARD_TITLE_STYLE,
  WIZARD_SUBTITLE_STYLE,
} from "./_McpWizardPage.styles";
import {
  AriaLiveRegion,
  PermissionDeniedBlock,
  SuccessBlock,
} from "./_McpWizardPage.feedback";
import { WizardForm } from "./_McpWizardPage.form";

// ---------------------------------------------------------------------------
// Zod form schema — §D-T004-DOMAIN-TYPES + task pack §8
// Mirrors backend CreateServerRequest (schemas.py:64) exactly.
// stdio excluded per instrucciones §3.1 line 99.
// ---------------------------------------------------------------------------

const McpTransportEnum = z.enum(["http", "sse"]);
const McpAuthTypeEnum = z.enum(["none", "api_key", "bearer", "oauth2"]);

/**
 * Zod schema for the MCP server creation form.
 * Client-side mirror of backend Pydantic CreateServerRequest.
 * Keeps 99% of 422s from reaching the backend.
 */
export const CreateServerFormSchema = z
  .object({
    name: z
      .string()
      .min(1, "wizard.errors.nameRequired")
      .max(200, "wizard.errors.nameMax"),
    transport: McpTransportEnum,
    endpoint: z
      .string()
      .min(1, "wizard.errors.endpointRequired")
      .max(2000)
      .refine(
        (v) => /^https?:\/\//i.test(v) || /^sse:\/\//i.test(v),
        "wizard.errors.endpointInvalid",
      ),
    authType: McpAuthTypeEnum,
    secret: z.string().optional(),
    refreshToken: z.string().optional(),
  })
  .superRefine((val, ctx) => {
    if (val.authType !== "none" && !val.secret) {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["secret"],
        message: "wizard.errors.secretRequired",
      });
    }
  });

export type CreateServerFormValues = z.infer<typeof CreateServerFormSchema>;

// ---------------------------------------------------------------------------
// Nav items
// ---------------------------------------------------------------------------

const ADMIN_NAV_ITEMS = [
  { key: "mcp", label: "MCP Servers", active: true },
];

// ---------------------------------------------------------------------------
// McpWizardPage component
// ---------------------------------------------------------------------------

/**
 * Admin form for registering a new MCP server.
 * §D-T004-PAGE, §D-T004-FORM-SINGLE-PAGE, §D-T004-SECRET-FIELD.
 * @returns The MCP server registration form page.
 */
export default function McpWizardPage(): ReactNode {
  const { t } = useTranslation("mcp");
  const navigate = useNavigate();
  const { logout } = useAuth();

  const formAriaLabelId = useId();

  // BEFORE render log
  logVerbose("McpWizardPage.render.start", {
    phase: "P04",
    slice: "P04-S02-T004",
    route: "/admin/ai/mcp/new",
  });

  const onAuthFailure = logout;
  const mutation = useCreateMcpServer(onAuthFailure);

  const {
    register,
    handleSubmit,
    watch,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<CreateServerFormValues>({
    resolver: zodResolver(CreateServerFormSchema),
    defaultValues: {
      name: "",
      transport: "http",
      authType: "none",
      endpoint: "",
      secret: "",
      refreshToken: "",
    },
  });

  const watchedAuthType = watch("authType");
  const showSecret = watchedAuthType !== "none";
  const showRefreshToken = watchedAuthType === "oauth2";

  const isLoading = mutation.isPending || isSubmitting;
  const isSuccess = mutation.isSuccess;

  // Derive page-level error kind
  const mutationError = mutation.error;
  const isPermissionDenied = mutationError instanceof McpForbiddenError;
  const isFormLevelError =
    mutationError !== null &&
    mutationError !== undefined &&
    !isPermissionDenied &&
    !(mutationError instanceof McpValidationError) &&
    !(mutationError instanceof McpEndpointNotAllowedError);

  // Localized message for the form-level error block — picked by error code.
  const formLevelErrorMessage = isFormLevelError
    ? t(
        (mutationError as { code?: string }).code === "MCP_RATE_LIMITED"
          ? "wizard.errors.rateLimited"
          : "wizard.errors.network",
      )
    : "";

  // ---------------------------------------------------------------------------
  // Submit handler
  // ---------------------------------------------------------------------------

  /**
   * Handles form submit — builds wire DTO and fires the mutation.
   *
   * §D-T004-RHF-VALIDATION-WIRING (R-3 mitigation):
   *   On McpValidationError / McpEndpointNotAllowedError, calls setError per field.
   */
  const onSubmit = handleSubmit((formValues: CreateServerFormValues) => {
    logVerbose("McpWizardPage.onSubmit.start", {
      transport: formValues.transport,
      auth_type: formValues.authType,
      // secret NEVER logged (§D-T004-SECRET-NEVER-PERSISTED)
    });

    const wireBody: CreateServerRequest = {
      name: formValues.name,
      transport: formValues.transport,
      endpoint: formValues.endpoint,
      auth: {
        type: formValues.authType,
        secret: formValues.authType === "none" ? null : (formValues.secret ?? null),
        refresh_token:
          formValues.authType === "oauth2" ? (formValues.refreshToken ?? null) : null,
      },
    };

    mutation.mutate(wireBody, {
      onError: (err) => {
        // §D-T004-RHF-VALIDATION-WIRING: map field errors to RHF
        if (err instanceof McpValidationError) {
          logWarn("McpWizardPage.onSubmit.validation_error", {
            field_count: Object.keys(err.fieldErrors).length,
          });
          for (const [field, message] of Object.entries(err.fieldErrors)) {
            setError(field as keyof CreateServerFormValues, {
              type: "server",
              message,
            });
          }
        } else if (err instanceof McpEndpointNotAllowedError) {
          logWarn("McpWizardPage.onSubmit.endpoint_not_allowed");
          setError("endpoint", {
            type: "server",
            message: t("wizard.errors.endpointNotAllowed"),
          });
        }
      },
    });
  });

  // AFTER render log
  logVerbose("McpWizardPage.render.state", {
    isLoading,
    isSuccess,
    mutationStatus: mutation.status,
    hasError: Boolean(mutationError),
  });

  return (
    <AdminShell navItems={ADMIN_NAV_ITEMS} navAriaLabel={t("servers.title")}>
      <AriaLiveRegion
        message={isFormLevelError ? t("wizard.errors.network") : ""}
      />

      {/* Page header */}
      <header style={WIZARD_HEADER_STYLE}>
        <h1 style={WIZARD_TITLE_STYLE} id={formAriaLabelId}>
          {t("wizard.title")}
        </h1>
        <p style={WIZARD_SUBTITLE_STYLE}>{t("wizard.subtitle")}</p>
      </header>

      {isPermissionDenied && (
        <PermissionDeniedBlock
          title={t("wizard.permissionDenied.title")}
          body={t("wizard.permissionDenied.body")}
          backLabel={t("wizard.permissionDenied.back")}
          onBack={() => void navigate(ROUTE_ADMIN_AI_MCP)}
        />
      )}

      {isSuccess && !isPermissionDenied && (
        <SuccessBlock
          title={t("wizard.success.title")}
          body={t("wizard.success.body")}
        />
      )}

      {/* Main form — shown unless permission denied or success */}
      {!isPermissionDenied && !isSuccess && (
        <WizardForm
          formAriaLabelId={formAriaLabelId}
          isLoading={isLoading}
          onSubmit={onSubmit}
          register={register}
          errors={errors}
          showSecret={showSecret}
          showRefreshToken={showRefreshToken}
          isFormLevelError={isFormLevelError}
          formLevelErrorMessage={formLevelErrorMessage}
          t={t}
          onCancel={() => void navigate(ROUTE_ADMIN_AI_MCP)}
        />
      )}
    </AdminShell>
  );
}
