/**
 * ModelWizardPage — 3-step discover-models wizard at /admin/ai/models/new.
 *
 * What: MVP wizard that lets an admin discover models from an existing
 *       ai_provider by entering its UUID, invoking the FU-X1 endpoint,
 *       and reviewing the diff result (added / existing / skipped).
 *
 * 3 logical steps:
 *   1. Provider input — Step1ProviderInput (UUID + zod validation)
 *   2. Discovering   — spinner while POST is in flight
 *   3. Diff review   — DiffReviewTable + "Approve & return" CTA
 *
 * UX states (UX_CONTRACT §3 row 2 — all required states implemented):
 *   loading          — step 2 spinner
 *   empty            — step 3 when total_seen=0 (DiffReviewTable handles)
 *   error_network    — step 2 → shows error_network message
 *   error_validation — step 1 (zod) OR step 2 (backend 404/422)
 *   permission_denied — step 2 (backend 401/403)
 *   success          — step 3 with models present
 *
 * Auth guard: NOT implemented — TODO(P01-S03-T001).
 *
 * Zod: uses z.uuid() — canonical Zod v4 form (NOT z.string().uuid()).
 *   RESOLVED per: orchestrator-state/memory/official-doc-notes/
 *                 P00-S02-T007-zod-v4-uuid-deprecation.md
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   - react — useState
 *   - react-router-dom — useNavigate, Link
 *   - react-i18next — useTranslation('admin-ai')
 *   - zod — z.uuid() (v4 canonical)
 *   - @/shared/design-system/AdminShell, Wordmark, TrackedLabel, SolidCTA
 *   - ./components/StepIndicator
 *   - ./components/DiffReviewTable
 *   - ./components/Step1ProviderInput
 *   - ../data/discoverModels
 *   - ../data/types — DiscoverModelsData, AdminAiError
 *
 * Source-of-truth refs:
 *   - TECHNICAL_GUIDE §6.1 (route /admin/ai/models/new, ModelWizardPage)
 *   - task-pack P00-S02-T007.md §5.2 + §1.1
 *   - UX_CONTRACT.md §3 row 2 + §6 (a11y)
 *
 * Logging:
 *   discoverModels.ts emits BEFORE/AFTER/ERROR structured logs.
 *   This page logs step transitions at console.info level.
 *
 * Accessibility:
 *   - Spinner region: role="status" + aria-live="polite".
 *   - Error region: role="alert" + aria-live="assertive".
 *   - Tab order: input → submit → approve CTA.
 */

import { useState, type CSSProperties } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { z } from 'zod';
import { AdminShell } from '@/shared/design-system/AdminShell';
import { Wordmark } from '@/shared/design-system/Wordmark';
import { TrackedLabel } from '@/shared/design-system/TrackedLabel';
import { SolidCTA } from '@/shared/design-system/SolidCTA';
import { StepIndicator } from './components/StepIndicator';
import { DiffReviewTable } from './components/DiffReviewTable';
import { Step1ProviderInput } from './components/Step1ProviderInput';
import { discoverModels } from '../data/discoverModels';
import type { DiscoverModelsData, AdminAiError } from '../data/types';

// ── Zod schema — z.uuid() is Zod v4 canonical (NOT z.string().uuid()) ─────────
const providerIdSchema = z.uuid();

type WizardStep = 1 | 2 | 3;

type WizardError =
  | { kind: 'validation'; message: string }
  | { kind: 'network' | 'upstream'; message: string }
  | { kind: 'permission_denied'; message: string };

// ── Styles ────────────────────────────────────────────────────────────────────

const pageContentStyle: CSSProperties = {
  display: 'flex', flexDirection: 'column', gap: 'var(--space-8)', maxWidth: '640px',
};

const headerStyle: CSSProperties = {
  borderBottom: 'var(--hairline)', paddingBottom: 'var(--space-6)', marginBottom: 'var(--space-6)',
};

const spinnerContainerStyle: CSSProperties = {
  display: 'flex', alignItems: 'center', gap: 'var(--space-3)', padding: 'var(--space-8) 0',
};

const errorContainerStyle: CSSProperties = {
  border: 'var(--hairline)', padding: 'var(--space-6)',
  display: 'flex', flexDirection: 'column', gap: 'var(--space-4)',
};

const ctaRowStyle: CSSProperties = {
  display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap',
};

// ── Helpers ────────────────────────────────────────────────────────────────────

function errorFromAdminAiError(err: AdminAiError, t: (key: string) => string): WizardError {
  switch (err.code) {
    case 'unauthorized':
    case 'forbidden':
      return { kind: 'permission_denied', message: t('wizard.errors.unauthorized') };
    case 'provider_not_found':
    case 'validation_error':
      return { kind: 'validation', message: t('wizard.errors.providerNotFound') };
    case 'upstream_error':
      return { kind: 'upstream', message: t('wizard.errors.upstream') };
    default:
      return { kind: 'network', message: t('wizard.errors.network') };
  }
}

// ── Component ─────────────────────────────────────────────────────────────────

/**
 * 3-step discover-models wizard page.
 *
 * Step 1: Provider UUID input + zod validation (Step1ProviderInput).
 * Step 2: POST in flight — spinner; error states rendered here.
 * Step 3: DiffReviewTable + Approve & return CTA.
 */
export function ModelWizardPage() {
  const { t } = useTranslation('admin-ai');
  const navigate = useNavigate();

  const [step, setStep] = useState<WizardStep>(1);
  const [providerId, setProviderId] = useState('');
  const [inputError, setInputError] = useState<string | undefined>(undefined);
  const [wizardError, setWizardError] = useState<WizardError | undefined>(undefined);
  const [diffData, setDiffData] = useState<DiscoverModelsData | undefined>(undefined);

  const steps = [
    { number: 1, label: t('wizard.step1.title') },
    { number: 2, label: t('wizard.step2.spinner') },
    { number: 3, label: t('wizard.step3.title') },
  ];

  function handleProviderIdChange(e: React.ChangeEvent<HTMLInputElement>) {
    setProviderId(e.target.value);
    if (inputError !== undefined) setInputError(undefined);
  }

  async function handleDiscover() {
    const parseResult = providerIdSchema.safeParse(providerId.trim());
    if (!parseResult.success) {
      setInputError(t('wizard.errors.invalidUuid'));
      return;
    }
    console.info({ event: 'wizard.step_transition', from: 1, to: 2 });
    setStep(2);
    setWizardError(undefined);

    const result = await discoverModels(parseResult.data);
    if (result.ok) {
      console.info({ event: 'wizard.step_transition', from: 2, to: 3 });
      setDiffData(result.value);
      setStep(3);
    } else {
      const mapped = errorFromAdminAiError(result.error, t);
      console.warn({ event: 'wizard.error', kind: mapped.kind });
      setWizardError(mapped);
      // Stay on step 2 to show error inline
    }
  }

  function handleTryAgain() { setWizardError(undefined); setStep(1); }

  function handleApprove() {
    console.info({ event: 'wizard.approve', action: 'navigate_to_models_list' });
    navigate('/admin/ai/models');
  }

  return (
    <AdminShell sidebar={<Wordmark />}>
      <div style={pageContentStyle}>
        <header style={headerStyle}>
          <TrackedLabel size="sm">/admin/ai/models/new</TrackedLabel>
          <h1 style={{
            fontFamily: 'var(--font-display)', fontSize: 'var(--text-2xl)',
            fontWeight: 'var(--weight-bold)' as string, color: 'var(--color-text-primary)',
            margin: 'var(--space-4) 0 var(--space-6)', lineHeight: 'var(--leading-tight)',
          }}>
            {t('wizard.title')}
          </h1>
          <StepIndicator steps={steps} current={step} />
        </header>

        {/* Step 1 — provider input */}
        {step === 1 && (
          <Step1ProviderInput
            value={providerId}
            onChange={handleProviderIdChange}
            onSubmit={() => { void handleDiscover(); }}
            errorMessage={inputError}
          />
        )}

        {/* Step 2 — discovering / error */}
        {step === 2 && wizardError === undefined && (
          <div style={spinnerContainerStyle} role="status" aria-live="polite">
            <span aria-hidden="true">⋯</span>
            <TrackedLabel>{t('wizard.step2.spinner')}</TrackedLabel>
          </div>
        )}

        {step === 2 && wizardError !== undefined && (
          <div style={errorContainerStyle} role="alert" aria-live="assertive">
            <TrackedLabel>{wizardError.message}</TrackedLabel>
            <div style={ctaRowStyle}>
              <SolidCTA onClick={handleTryAgain}>{t('wizard.step1.submit')}</SolidCTA>
              <Link to="/admin/ai/models" style={{ textDecoration: 'none' }}>
                <SolidCTA>{t('wizard.step3.approve')}</SolidCTA>
              </Link>
            </div>
          </div>
        )}

        {/* Step 3 — diff review */}
        {step === 3 && diffData !== undefined && (
          <div>
            <DiffReviewTable data={diffData} />
            <div style={{ ...ctaRowStyle, marginTop: 'var(--space-6)' }}>
              <SolidCTA onClick={handleApprove}>{t('wizard.step3.approve')}</SolidCTA>
            </div>
          </div>
        )}
      </div>
    </AdminShell>
  );
}
