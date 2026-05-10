/**
 * Step1ProviderInput — Step 1 form for the ModelWizardPage.
 *
 * What: Renders the provider UUID input, help text, and the Discover CTA.
 *       UUID validation is done in the parent via z.uuid() before calling
 *       onSubmit. This component is purely presentational.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   - react-i18next — useTranslation('admin-ai')
 *   - @/shared/design-system/EditorialInput
 *   - @/shared/design-system/SolidCTA
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §5.2 Step 1
 *   - UX_CONTRACT.md §6 (a11y: label + aria-describedby)
 *
 * Accessibility:
 *   - EditorialInput provides label + aria-describedby on error.
 *   - SolidCTA has accessible name via children text.
 */

import type { CSSProperties, ChangeEvent } from 'react';
import { useTranslation } from 'react-i18next';
import { EditorialInput } from '@/shared/design-system/EditorialInput';
import { SolidCTA } from '@/shared/design-system/SolidCTA';

interface Step1ProviderInputProps {
  value: string;
  onChange: (e: ChangeEvent<HTMLInputElement>) => void;
  onSubmit: () => void;
  errorMessage?: string;
}

const formStyle: CSSProperties = {
  display:       'flex',
  flexDirection: 'column',
  gap:           'var(--space-6)',
};

const helpTextStyle: CSSProperties = {
  fontFamily: 'var(--font-sans)',
  fontSize:   'var(--text-xs)',
  color:      'var(--color-text-secondary)',
  lineHeight: 'var(--leading-normal)',
  margin:     0,
};

/**
 * Step 1: Provider UUID input form.
 *
 * @param value - Current input value.
 * @param onChange - Change handler.
 * @param onSubmit - Called when Discover CTA is clicked.
 * @param errorMessage - Validation error from parent (zod result).
 */
export function Step1ProviderInput({
  value,
  onChange,
  onSubmit,
  errorMessage,
}: Step1ProviderInputProps) {
  const { t } = useTranslation('admin-ai');

  return (
    <div style={formStyle}>
      <EditorialInput
        id="provider-id"
        label={t('wizard.step1.input.label')}
        placeholder="xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
        value={value}
        onChange={onChange}
        errorMessage={errorMessage}
        autoComplete="off"
        spellCheck={false}
      />
      <p style={helpTextStyle}>{t('wizard.step1.input.help')}</p>
      <div>
        <SolidCTA onClick={onSubmit}>{t('wizard.step1.submit')}</SolidCTA>
      </div>
    </div>
  );
}
