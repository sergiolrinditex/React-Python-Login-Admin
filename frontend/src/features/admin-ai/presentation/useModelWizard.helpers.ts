/**
 * Hilo People — useModelWizard pure helpers.
 *
 * Slice/Phase: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Write-set anchor: §D-T003-WIZARD-HOOK-HELPERS
 *
 * Responsibility: Pure helpers (validators + masked secret formatter) extracted
 *   from useModelWizard.ts to keep the hook within the ~200-line file-size
 *   target declared in `.claude/rules/01-non-negotiables.md §file-size`.
 *
 *   These are pure, deterministic functions — no React, no side effects, no
 *   network. They are unit-tested in isolation under
 *   features/admin-ai/__tests__/useModelWizard.test.tsx (suite W-validators-*).
 *
 * Consumers: useModelWizard.ts (this slice). Not re-exported elsewhere.
 *
 * Security: validators inspect a live `secret_plain` only by length / non-blank
 *   check. The value is NEVER returned, NEVER logged, NEVER reflected outside.
 *   formatMaskedSecret returns at most the last 4 characters of the secret for
 *   safe UI display — see §D-T003-LOGS-PII-CLEAN.
 *
 * Key deps: none (zero external dependencies — pure TypeScript).
 */

// ---------------------------------------------------------------------------
// Domain enum mirrors (kept identical to backend ProviderType / CredentialAuthType)
// ---------------------------------------------------------------------------

const VALID_PROVIDER_TYPES = [
  "openai",
  "anthropic",
  "azure",
  "litellm",
  "ollama",
  "google",
  "custom",
] as const;

const VALID_AUTH_TYPES = ["api_key", "oauth2", "bearer"] as const;

// ---------------------------------------------------------------------------
// Validators — pure functions (testable in isolation)
// ---------------------------------------------------------------------------

/**
 * Validates provider_type field.
 * Returns null if valid, or an i18n key string if invalid.
 */
export function validateProviderType(value: string): string | null {
  if (!value || !(VALID_PROVIDER_TYPES as readonly string[]).includes(value)) {
    return "admin-ai:modelsNew.errors.validation.providerTypeRequired";
  }
  return null;
}

/**
 * Validates provider name field.
 * Returns null if valid, or an i18n key string if invalid.
 */
export function validateName(value: string): string | null {
  const trimmed = value.trim();
  if (!trimmed) return "admin-ai:modelsNew.errors.validation.nameRequired";
  if (trimmed.length > 200) return "admin-ai:modelsNew.errors.validation.nameTooLong";
  return null;
}

/**
 * Validates secret_plain field.
 * Returns null if valid, or an i18n key string if invalid.
 * SECURITY: value is a live secret — only emptiness is inspected, never logged.
 */
export function validateSecret(value: string): string | null {
  if (!value || value.trim().length === 0) {
    return "admin-ai:modelsNew.errors.validation.secretRequired";
  }
  return null;
}

/**
 * Validates auth_type field.
 * Returns null if valid, or an i18n key string if invalid.
 */
export function validateAuthType(value: string): string | null {
  if (!value || !(VALID_AUTH_TYPES as readonly string[]).includes(value)) {
    return "admin-ai:modelsNew.errors.validation.authTypeRequired";
  }
  return null;
}

// ---------------------------------------------------------------------------
// Masked secret formatter
// ---------------------------------------------------------------------------

/**
 * Formats a secret for masked display.
 * Returns '••••• {last4}' or '•••••' when too short.
 * SECURITY: only the last 4 chars of the secret are returned (for display only).
 */
export function formatMaskedSecret(secret: string): string {
  if (secret.length <= 4) return "•••••";
  const last4 = secret.slice(-4);
  return `••••• ${last4}`;
}
