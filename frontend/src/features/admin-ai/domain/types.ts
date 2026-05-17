/**
 * Hilo People — Admin AI domain types.
 *
 * Slice/Phase: P04-S01-T001 — AdminDashboardPage / Phase 4.
 * Write-set anchor: §D-T001-ADMINAI-FEATURE
 *
 * Responsibility: Pure domain types for the admin-ai feature module.
 *   No framework imports. No external lib imports. Domain-only.
 *   Consumed by adminAiRepository, useDashboardUsage, and downstream slices
 *   (P04-S01-T002 AdminAiModelsPage, T003 ModelWizardPage, T004 ModelTestDrawer).
 *
 * Source: TECHNICAL_GUIDE §6.2 backend response shape (read from HEAD
 *   backend/app/admin/usage.py + _usage_aggregator.py).
 *
 * Clean Architecture: domain imports nothing external.
 */

// ---------------------------------------------------------------------------
// Usage domain types
// ---------------------------------------------------------------------------

/**
 * A single row in the usage summary — represents one model (or one day, or
 * one model-day combination depending on group_by).
 *
 * group_by=model: model_name present, day absent.
 * group_by=day:   day present, model_name absent.
 * group_by=model_day: both present.
 *
 * Source: backend/app/admin/_usage_aggregator.py shape.
 */
export interface UsageRow {
  /** Total input tokens. */
  tokens_in: number;
  /** Total output tokens. */
  tokens_out: number;
  /** Estimated cost in USD. */
  estimated_cost: number;
  /** Average latency in milliseconds. */
  latency_ms_avg: number;
  /** Number of invocations in the window. */
  invocations: number;
  /** Model display name — present when group_by in {model, model_day}. */
  model_name?: string;
  /** ISO-8601 date string — present when group_by in {day, model_day}. */
  day?: string;
}

/**
 * Aggregated totals across all rows in the window.
 * Source: backend UsageSummary.totals schema.
 */
export interface UsageTotals {
  tokens_in: number;
  tokens_out: number;
  estimated_cost: number;
  invocations: number;
  latency_ms_avg: number;
}

/**
 * Full usage summary returned by GET /api/v1/admin/usage.
 * Source: backend UsageSummary schema (data envelope).
 */
export interface UsageSummary {
  /** ISO-8601 start of the window. */
  from: string;
  /** ISO-8601 end of the window. */
  to: string;
  /** Grouping mode used for this query. */
  group_by: "model" | "day" | "model_day";
  /** Per-group rows. Empty array when no usage in the window. */
  rows: UsageRow[];
  /** Cross-row totals. All zeros when rows is empty. */
  totals: UsageTotals;
}

/**
 * Request parameters for getUsage.
 * Source: TECHNICAL_GUIDE §6.2 query params for GET /api/v1/admin/usage.
 */
export interface GetUsageRequest {
  /** ISO-8601 start datetime (inclusive). */
  from: string;
  /** ISO-8601 end datetime (exclusive). */
  to: string;
  /** Grouping mode. Default: "model". */
  group_by?: "model" | "day" | "model_day";
  /** Optional UUID to filter by a specific AI model. */
  model_id?: string;
  /** Optional UUID to filter by a specific provider. */
  provider_id?: string;
}

// ---------------------------------------------------------------------------
// AI Providers and Models domain types (§D-T002-FEATURE-DOMAIN)
// ---------------------------------------------------------------------------

/**
 * Provider list item from GET /api/v1/admin/ai/providers.
 * Source: backend ProviderOut (backend/app/admin/providers/schemas.py HEAD).
 * Slice: P04-S01-T002 — AdminAiModelsPage / Phase 4.
 */
export interface AiProvider {
  id: string;
  name: string;
  provider_type: "openai" | "anthropic" | "azure" | "litellm" | "ollama" | "google" | "custom";
  base_url: string | null;
  /** "draft" | "active" | "inactive" */
  status: "draft" | "active" | "inactive";
  created_by: string | null;
  has_credentials: boolean;
  credential_auth_type: "api_key" | "oauth2" | "bearer" | null;
  /** ISO-8601 datetime string or null. */
  expires_at: string | null;
}

// ---------------------------------------------------------------------------
// Wizard domain types (§D-T003-WIZARD-TYPES)
// ---------------------------------------------------------------------------

/**
 * Provider type enum — must match backend Literal[7 enum] from
 * backend/app/admin/providers/schemas.py CreateProviderRequest.
 * Slice: P04-S01-T003 — ModelWizardPage / Phase 4.
 */
export type ProviderType =
  | "openai"
  | "anthropic"
  | "azure"
  | "litellm"
  | "ollama"
  | "google"
  | "custom";

/**
 * Auth type enum — mirrors backend ProviderCredentialsInput.auth_type.
 * Slice: P04-S01-T003 — ModelWizardPage / Phase 4.
 */
export type CredentialAuthType = "api_key" | "oauth2" | "bearer";

/**
 * Credential input shape — mirrors backend ProviderCredentialsInput.
 * SECURITY: secret_plain is a live secret. NEVER serialize to localStorage/logs.
 * The field is typed as plain string to avoid cross-module unique symbol incompatibility.
 * Security enforcement is enforced by convention (PII-clean logs) and test T26.
 * Slice: P04-S01-T003 — ModelWizardPage / Phase 4.
 */
export interface ProviderCredentialsInput {
  auth_type: CredentialAuthType;
  /** SECURITY: NEVER LOG THIS FIELD — live API key/token. Backend encrypts on write. */
  secret_plain: string;
  refresh_token_plain?: string | null;
  expires_at?: string | null;
}

/**
 * Create provider request body — mirrors backend CreateProviderRequest.
 * Slice: P04-S01-T003 — ModelWizardPage / Phase 4.
 * Source: TECHNICAL_GUIDE §6.2, backend/app/admin/providers/schemas.py.
 *
 * SECURITY: credentials.secret_plain is a live secret. Backend encrypts it with
 * Fernet on write. The frontend never persists or logs this field.
 */
export interface CreateProviderRequest {
  provider_type: ProviderType;
  /** 1–200 chars non-blank. */
  name: string;
  base_url?: string | null;
  credentials: ProviderCredentialsInput;
}

/**
 * Wizard step machine state.
 * Slice: P04-S01-T003 — ModelWizardPage / Phase 4.
 */
export type WizardStep =
  | "provider"
  | "credentials"
  | "submitting"
  | "models"
  | "success";

/**
 * Wizard form state managed by useModelWizard.
 * Slice: P04-S01-T003 — ModelWizardPage / Phase 4.
 * All fields are optional at init; validation runs on submit.
 */
export interface WizardFormState {
  provider_type: ProviderType | "";
  name: string;
  base_url: string;
  auth_type: CredentialAuthType;
  /** Kept in React state only — discarded after submit or unmount. */
  secret_plain: string;
}

/**
 * Per-field validation errors from client-side validators.
 * Slice: P04-S01-T003 — ModelWizardPage / Phase 4.
 */
export interface WizardFieldErrors {
  provider_type?: string;
  name?: string;
  secret_plain?: string;
  auth_type?: string;
  base_url?: string;
}

// ---------------------------------------------------------------------------
// Model Test domain types (§D-T004-MODELTEST-TYPES)
// ---------------------------------------------------------------------------

/**
 * Request body for POST /api/v1/admin/ai/models/{id}/test.
 * Source: TECHNICAL_GUIDE §6.2, task pack §5.
 * Slice: P04-S01-T004 — ModelTestDrawer / Phase 4.
 *
 * PII note: prompt may contain sensitive user data.
 * NEVER log the full prompt value — only prompt_len.
 */
export interface TestModelRequest {
  /** 1–4000 chars. Validated on both frontend (useModelTest) and backend (Pydantic). */
  prompt: string;
}

/**
 * Response data from POST /api/v1/admin/ai/models/{id}/test.
 * Source: TECHNICAL_GUIDE §6.2, task pack §5.
 * Slice: P04-S01-T004 — ModelTestDrawer / Phase 4.
 *
 * PII note: output may contain sensitive model-generated content.
 * NEVER log the full output value — only output_length.
 */
export interface TestModelResponse {
  /** Model-generated text output. */
  output: string;
  /** End-to-end latency in milliseconds. */
  latency_ms: number;
  /** Estimated USD cost; 0 if pricing is empty (see D-T002-COST-FORMAT). */
  cost: number;
}

/**
 * Request body for PATCH /api/v1/admin/ai/models/{id}.
 * Source: TECHNICAL_GUIDE §6.2, task pack §5.
 * Slice: P04-S01-T004 — ModelTestDrawer / Phase 4.
 */
export interface UpdateModelRequest {
  enabled?: boolean;
  is_default?: boolean;
}

// ---------------------------------------------------------------------------
// AI Provider list item (re-exported from P04-S01-T002)
// ---------------------------------------------------------------------------

/**
 * Model list item from GET /api/v1/admin/ai/models.
 * Source: backend ModelOut (backend/app/admin/model_catalog/schemas.py HEAD).
 * Slice: P04-S01-T002 — AdminAiModelsPage / Phase 4.
 *
 * ASSUMPTION-1 (pricing shape): verification seed has empty pricing ({}).
 * The formatter handles this and the canonical LiteLLM/OpenAI shape
 * (input_per_1k_tokens / output_per_1k_tokens). See task pack §13 + §6.5.
 */
export interface AiModel {
  id: string;
  provider_id: string;
  model_id: string;
  /** "chat" | "embeddings" | other */
  model_type: string;
  /** Backend types as list[Any]; narrowed to string[]. See R-5. */
  capabilities: string[];
  enabled: boolean;
  is_default: boolean;
  /**
   * Pricing JSONB — shape NOT contractually fixed by source-of-truth.
   * Current verification seed has pricing: {} (empty). Treat as opaque dict;
   * format helper must handle empty and unknown shapes gracefully (display em-dash).
   * See ASSUMPTION-1 and D-T002-COST-FORMAT.
   */
  pricing: Record<string, unknown>;
  latency_ms_avg: number | null;
}
