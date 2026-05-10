/**
 * DiffReviewTable — Discover-models diff result display.
 *
 * What: Renders the three sub-sections of a DiscoverModelsData payload:
 *   - Added   — new models persisted (auto_discovered=true)
 *   - Existing — models already present, untouched
 *   - Skipped  — models seen but not persisted, with reason
 *   Plus a summary counts block.
 *
 * Does NOT render a reject button per-model — that belongs to PATCH
 * /admin/ai/models/{id} which lands in P02-S05-T001. A TODO label is
 * shown instead so verify-slice human can see the deferred scope.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   - @/shared/design-system/TrackedLabel
 *   - @/shared/design-system/HairlineTable
 *   - ../data/types — DiscoverModelsData, AiModelOut, SkippedModel
 *   - ../../domain/diffSummary — diffSummary()
 *   - react-i18next — useTranslation('admin-ai')
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §5.2 Step 3
 *   - task-pack P00-S02-T007.md §1.1 Approve/reject reality
 *   - instrucciones.md §7 (editorial identity)
 *   - UX_CONTRACT.md §3 (success, empty states for ModelWizardPage)
 *
 * Logging:
 *   Pure presentational — no action handlers. BEFORE/AFTER logs belong
 *   to the parent ModelWizardPage which owns the fetch action.
 *
 * Accessibility:
 *   - Section headings use <h3> with TrackedLabel styling.
 *   - Tables have captions.
 *   - Summary region has role="region" with aria-label.
 */

import type { CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';
import { TrackedLabel } from '@/shared/design-system/TrackedLabel';
import { HairlineTable } from '@/shared/design-system/HairlineTable';
import type { DiscoverModelsData } from '../../data/types';
import { diffSummary } from '../../domain/diffSummary';

interface DiffReviewTableProps {
  data: DiscoverModelsData;
}

const sectionStyle: CSSProperties = {
  marginBottom: 'var(--space-8)',
};

const summaryGridStyle: CSSProperties = {
  display:             'grid',
  gridTemplateColumns: 'repeat(3, 1fr)',
  gap:                 'var(--space-4)',
  marginTop:           'var(--space-4)',
};

const summaryCardStyle: CSSProperties = {
  border:          'var(--hairline)',
  padding:         'var(--space-4)',
  textAlign:       'center',
  backgroundColor: 'var(--color-paper)',
};

const summaryNumberStyle: CSSProperties = {
  fontFamily:  'var(--font-display)',
  fontSize:    'var(--text-2xl)',
  fontWeight:  'var(--weight-bold)' as string,
  color:       'var(--color-text-primary)',
  display:     'block',
  marginBottom: 'var(--space-1)',
};

const emptyStateStyle: CSSProperties = {
  padding:     'var(--space-4)',
  border:      'var(--hairline)',
  fontFamily:  'var(--font-sans)',
  fontSize:    'var(--text-sm)',
  color:       'var(--color-text-secondary)',
  textAlign:   'center',
};

const todoLabelStyle: CSSProperties = {
  fontFamily:    'var(--font-sans)',
  fontSize:      'var(--text-xs)',
  letterSpacing: 'var(--tracking-label)',
  textTransform: 'uppercase',
  color:         'var(--color-text-disabled)',
};

const headingStyle: CSSProperties = {
  marginBottom: 'var(--space-3)',
  color:        'var(--color-text-primary)',
};

/**
 * Renders the three-section diff review (added / existing / skipped) plus
 * summary counts for the discover-models response.
 *
 * @param data - DiscoverModelsData from the POST discover-models response.
 */
export function DiffReviewTable({ data }: DiffReviewTableProps) {
  const { t } = useTranslation('admin-ai');
  const summary = diffSummary(data);

  const rejectPendingLabel = t('wizard.step3.rejectPending');

  const addedColumns = [
    { key: 'model_id', header: t('wizard.step3.columns.modelId') },
    { key: 'model_type', header: t('wizard.step3.columns.type') },
    { key: 'reject', header: '' },
  ];

  const addedRows = data.added.map((m) => ({
    model_id: m.model_id,
    model_type: m.model_type,
    reject: (
      <span style={todoLabelStyle} aria-label={rejectPendingLabel}>
        {/* TODO(P02-S05-T001): per-model reject via PATCH /admin/ai/models/{id} */}
        {rejectPendingLabel}
      </span>
    ),
  }));

  const existingColumns = [
    { key: 'model_id', header: t('wizard.step3.columns.modelId') },
    { key: 'model_type', header: t('wizard.step3.columns.type') },
  ];

  const existingRows = data.existing.map((m) => ({
    model_id: m.model_id,
    model_type: m.model_type,
  }));

  const skippedColumns = [
    { key: 'model_id', header: t('wizard.step3.columns.modelId') },
    { key: 'reason', header: t('wizard.step3.columns.reason') },
  ];

  const skippedRows = data.skipped.map((s) => ({
    model_id: s.model_id,
    reason: s.reason,
  }));

  return (
    <div>
      {/* Summary counts */}
      <section
        aria-label={t('wizard.step3.title')}
        role="region"
        style={sectionStyle}
      >
        <div style={summaryGridStyle}>
          <div style={summaryCardStyle}>
            <span style={summaryNumberStyle}>{summary.totalSeen}</span>
            <TrackedLabel>{t('wizard.step3.summary.totalSeen')}</TrackedLabel>
          </div>
          <div style={summaryCardStyle}>
            <span style={summaryNumberStyle}>{summary.totalPersisted}</span>
            <TrackedLabel>{t('wizard.step3.summary.totalPersisted')}</TrackedLabel>
          </div>
          <div style={summaryCardStyle}>
            <span style={summaryNumberStyle}>{summary.totalSkipped}</span>
            <TrackedLabel>{t('wizard.step3.summary.totalSkipped')}</TrackedLabel>
          </div>
        </div>
      </section>

      {/* Empty state — no models exposed by provider */}
      {data.total_seen === 0 && (
        <div style={emptyStateStyle} role="status">
          {t('wizard.step3.providerEmpty')}
        </div>
      )}

      {/* Added (new, persisted) */}
      {data.added.length > 0 && (
        <section style={sectionStyle}>
          <TrackedLabel size="sm" style={headingStyle}>
            {t('wizard.step3.added')}
          </TrackedLabel>
          <HairlineTable
            columns={addedColumns}
            rows={addedRows}
            caption={t('wizard.step3.added')}
          />
        </section>
      )}

      {/* Existing (already present) */}
      {data.existing.length > 0 && (
        <section style={sectionStyle}>
          <TrackedLabel size="sm" style={headingStyle}>
            {t('wizard.step3.existing')}
          </TrackedLabel>
          <HairlineTable
            columns={existingColumns}
            rows={existingRows}
            caption={t('wizard.step3.existing')}
          />
        </section>
      )}

      {/* Skipped */}
      {data.skipped.length > 0 && (
        <section style={sectionStyle}>
          <TrackedLabel size="sm" style={headingStyle}>
            {t('wizard.step3.skipped')}
          </TrackedLabel>
          <HairlineTable
            columns={skippedColumns}
            rows={skippedRows}
            caption={t('wizard.step3.skipped')}
          />
        </section>
      )}
    </div>
  );
}
