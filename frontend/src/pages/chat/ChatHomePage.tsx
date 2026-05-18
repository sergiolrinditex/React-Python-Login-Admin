/**
 * Hilo People — ChatHomePage.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *   Updated P03-S02-T009: mounts ChatNavbar as first child of MobileFrame
 *   (§D-T009-NAVBAR-PLACEMENT-INSIDE-PAGE, §D-T009-NAVBAR-VISIBILITY).
 *
 * Responsibility: Employee chat home page — the post-login default destination.
 *   Orchestrates the 6 required UX states: loading, empty, error_network,
 *   error_validation, permission_denied, success.
 *   Routes to /chat/:conversationId on successful POST /chat/conversations.
 *
 * Decisions applied (D-T001-*):
 *   D-T001-AUTH-FROM-HOOK: uses useAuth().user — AuthProvider already hydrated.
 *   D-T001-CHAT-REPO-LAYER: mutation via useCreateConversation hook.
 *   D-T001-PROMPT-CHIP-BEHAVIOR: chips directly submit (one-tap UX).
 *   D-T001-TANSTACK-MUTATION: uses useMutation from TanStack Query.
 *   D-T001-COMPOSER-MAX: 4000 chars enforced in Composer.
 *   D-T001-ROUTE: /chat wired via §D-T001-ROUTE in router.tsx.
 *   D-T001-VALIDATION-STATE: error_validation implemented (form submission).
 *   D-T001-NETWORK-RETRY: error_network state has retry CTA.
 *   D-T001-OUTAGE-OF-CHAT-T002: navigates /chat/:id even before T002 is done.
 *
 * Security:
 *   - Token NEVER in localStorage. Uses useAuth() which reads in-memory accessTokenStore.
 *   - No PII in logs (no email, no full_name, no prompt content).
 *
 * Route: /chat (RequireAuth — authenticated employee only).
 * Journey refs: J100 (terminal screen after login flow), J101 (triggers conversation creation).
 *
 * Non-negotiables §logging: BEFORE + AFTER + ERROR gated by VITE_ENABLE_VERBOSE_LOGGING.
 */

import { type CSSProperties, type ReactNode, useState, useCallback } from "react";
import { useNavigate } from "react-router";
import { useTranslation } from "react-i18next";
import MobileFrame from "../../shared/design-system/MobileFrame";
import SolidCTA from "../../shared/design-system/SolidCTA";
import EmptyPrompts from "../../features/chat/presentation/EmptyPrompts";
import Composer from "../../features/chat/presentation/Composer";
import { useAuth } from "../../features/auth/presentation/AuthProvider";
import { useCreateConversation } from "../../features/chat/presentation/useCreateConversation";
import { ChatForbiddenError } from "../../features/chat/data/errors";
import { logVerbose, logWarn, logError } from "../../features/chat/data/logger";
import ChatNavbar from "./_ChatNavbar";

// ---------------------------------------------------------------------------
// Styles (tokens only)
// ---------------------------------------------------------------------------

const PAGE_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "2rem",
};

const ERROR_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "1rem",
  padding: "1rem 0",
};

const ERROR_TEXT_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.85,
};

// ---------------------------------------------------------------------------
// Forbidden error sub-view
// ---------------------------------------------------------------------------

interface ForbiddenViewProps {
  message: string;
  onSignIn: () => void;
}

/**
 * permission_denied state: shown when a 403 is returned.
 * For 401 final, RequireAuth already redirects — this handles 403.
 */
function ForbiddenView({ message, onSignIn }: ForbiddenViewProps): ReactNode {
  const { t } = useTranslation(["common"]);
  return (
    <div
      style={ERROR_CONTAINER_STYLE}
      role="status"
      aria-live="assertive"
      data-testid="forbidden-view"
    >
      <p style={ERROR_TEXT_STYLE}>{message}</p>
      <SolidCTA
        onClick={onSignIn}
        aria-label={t("common:actions.back")}
        data-testid="forbidden-sign-in-cta"
      >
        {t("common:actions.back")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Network error sub-view
// ---------------------------------------------------------------------------

interface NetworkErrorViewProps {
  message: string;
  onRetry: () => void;
  loading: boolean;
}

/**
 * error_network state: shown on 5xx or fetch failure.
 * Provides retry CTA per D-T001-NETWORK-RETRY.
 */
function NetworkErrorView({ message, onRetry, loading }: NetworkErrorViewProps): ReactNode {
  const { t } = useTranslation(["common"]);
  return (
    <div
      style={ERROR_CONTAINER_STYLE}
      role="status"
      aria-live="assertive"
      data-testid="network-error-view"
    >
      <p style={ERROR_TEXT_STYLE}>{message}</p>
      <SolidCTA
        onClick={onRetry}
        loading={loading}
        loadingLabel="…"
        aria-label={t("common:actions.retry")}
        data-testid="network-error-retry-cta"
      >
        {t("common:actions.retry")}
      </SolidCTA>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ChatHomePage
// ---------------------------------------------------------------------------

/**
 * Employee chat home — post-login default destination.
 * Wraps MobileFrame + EmptyPrompts + Composer + error states.
 *
 * @returns The chat home page element.
 */
export default function ChatHomePage(): ReactNode {
  const { t } = useTranslation(["chat", "errors", "common"]);
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [composerValue, setComposerValue] = useState("");
  const [lastPrompt, setLastPrompt] = useState<string | null>(null);

  logVerbose("chat.home.render.start");

  // onAuthFailure: used by the mutation to handle 401 exhausted
  const handleAuthFailure = useCallback((): void => {
    logWarn("chat.home.auth_failure_triggered");
    void logout();
  }, [logout]);

  const { mutate, isPending, error, reset } = useCreateConversation(handleAuthFailure);

  // Determine which error type is active
  const isForbidden = error instanceof ChatForbiddenError;
  const isNetworkError = error !== null && !isForbidden;

  // ---------------------------------------------------------------------------
  // Handlers
  // ---------------------------------------------------------------------------

  const handleSubmit = useCallback(
    (message: string): void => {
      logVerbose("chat.home.submit.start", { prompt_len: message.length });
      setLastPrompt(message);
      reset(); // Clear previous error before retry

      mutate(
        { initial_message: message, language: undefined },
        {
          onSuccess: (data) => {
            logVerbose("chat.home.submit.success", {
              conversation_id: data.conversation_id,
            });
            // D-T001-OUTAGE-OF-CHAT-T002: navigate even if /chat/:id not yet implemented.
            void navigate(`/chat/${data.conversation_id}`);
          },
          onError: (err) => {
            logError("chat.home.submit.error", { error: err.code });
          },
        },
      );
    },
    [mutate, navigate, reset],
  );

  const handlePromptSelect = useCallback(
    (prompt: string): void => {
      logVerbose("chat.home.prompt_selected", { prompt_len: prompt.length });
      setComposerValue(prompt);
      handleSubmit(prompt);
    },
    [handleSubmit],
  );

  const handleRetry = useCallback((): void => {
    if (lastPrompt !== null) {
      logVerbose("chat.home.retry", { prompt_len: lastPrompt.length });
      handleSubmit(lastPrompt);
    }
  }, [lastPrompt, handleSubmit]);

  const handleSignIn = useCallback((): void => {
    logVerbose("chat.home.permission_denied.sign_in_cta");
    void logout().then(() => {
      void navigate("/auth/sign-in");
    });
  }, [logout, navigate]);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <MobileFrame asMain fullHeight>
      {/* §D-T009-NAVBAR-PLACEMENT-INSIDE-PAGE: account link in all non-forbidden states */}
      {!isForbidden && <ChatNavbar />}
      <div style={PAGE_STYLE} data-testid="chat-home-page">
        {/* Empty state (always visible as baseline behind errors) */}
        {!isForbidden && (
          <EmptyPrompts
            onPromptSelect={handlePromptSelect}
            disabled={isPending}
          />
        )}

        {/* permission_denied state (403) */}
        {isForbidden && (
          <ForbiddenView
            message={t("errors:AUTH_FORBIDDEN")}
            onSignIn={handleSignIn}
          />
        )}

        {/* error_network state (5xx/network failure, not forbidden) */}
        {isNetworkError && (
          <NetworkErrorView
            message={t("errors:NETWORK")}
            onRetry={handleRetry}
            loading={isPending}
          />
        )}

        {/* Composer — shows in empty, validation_error, and retry states */}
        {!isForbidden && (
          <Composer
            onSubmit={handleSubmit}
            disabled={isPending}
            loading={isPending}
            value={composerValue}
            onChange={setComposerValue}
          />
        )}
      </div>
    </MobileFrame>
  );
}
