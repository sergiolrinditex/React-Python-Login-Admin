/**
 * Tests for DiffReviewTable — diff sections and summary counts.
 *
 * What: Verifies:
 *   - Renders the 3 summary count cards (seen, persisted, skipped).
 *   - Renders the added, existing, and skipped sections.
 *   - Empty state when total_seen=0.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Mock strategy:
 *   Pure props component — no fetch mock, no router needed.
 *   I18nextProvider wraps for t() calls.
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §7 (A3 acceptance criterion)
 *   - task-pack P00-S02-T007.md §12.2 (diff table rendering with fixture)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n';
import { DiffReviewTable } from '../components/DiffReviewTable';
import type { DiscoverModelsData } from '../../data/types';

// ── Fixtures ──────────────────────────────────────────────────────────────────

const PROVIDER_ID = '12345678-1234-4234-8234-123456789abc';

const FULL_DATA: DiscoverModelsData = {
  added: [
    {
      id: 'aaa-1',
      provider_id: PROVIDER_ID,
      model_id: 'gemini-1.5-pro',
      model_type: 'chat',
      capabilities: ['chat'],
      enabled: true,
      is_default: false,
      auto_discovered: true,
    },
    {
      id: 'aaa-2',
      provider_id: PROVIDER_ID,
      model_id: 'gemini-embed',
      model_type: 'embedding',
      capabilities: ['embeddings'],
      enabled: true,
      is_default: false,
      auto_discovered: true,
    },
  ],
  existing: [
    {
      id: 'bbb-1',
      provider_id: PROVIDER_ID,
      model_id: 'gemini-1.0-pro',
      model_type: 'chat',
      capabilities: ['chat'],
      enabled: true,
      is_default: false,
      auto_discovered: true,
    },
  ],
  skipped: [
    { model_id: 'unknown-model', reason: 'unsupported_model_type' },
  ],
  total_seen: 4,
};

const EMPTY_DATA: DiscoverModelsData = {
  added: [],
  existing: [],
  skipped: [],
  total_seen: 0,
};

function renderTable(data: DiscoverModelsData) {
  return render(
    <I18nextProvider i18n={i18n}>
      <DiffReviewTable data={data} />
    </I18nextProvider>,
  );
}

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('admin_ai / DiffReviewTable', () => {
  it('renders summary counts for full data', () => {
    renderTable(FULL_DATA);

    // total_seen = 4
    expect(screen.getByText('4')).toBeInTheDocument();
    // totalPersisted = added.length = 2
    expect(screen.getByText('2')).toBeInTheDocument();
    // totalSkipped = skipped.length = 1
    expect(screen.getByText('1')).toBeInTheDocument();
  });

  it('renders added section with model IDs', () => {
    renderTable(FULL_DATA);
    expect(screen.getByText('gemini-1.5-pro')).toBeInTheDocument();
    expect(screen.getByText('gemini-embed')).toBeInTheDocument();
  });

  it('renders existing section with model ID', () => {
    renderTable(FULL_DATA);
    expect(screen.getByText('gemini-1.0-pro')).toBeInTheDocument();
  });

  it('renders skipped section with reason', () => {
    renderTable(FULL_DATA);
    expect(screen.getByText('unknown-model')).toBeInTheDocument();
    expect(screen.getByText('unsupported_model_type')).toBeInTheDocument();
  });

  it('renders TODO reject label for added models', () => {
    renderTable(FULL_DATA);
    // The reject pending label is localized via t('wizard.step3.rejectPending');
    // ES default locale: "Rechazo pendiente P02-S05" (rendered text + aria-label).
    const rejectLabels = screen.getAllByText(/Rechazo pendiente P02-S05/i);
    expect(rejectLabels).toHaveLength(2); // one per added model
  });

  it('shows empty state message when total_seen=0', () => {
    renderTable(EMPTY_DATA);
    // Empty state is localized via t('wizard.step3.providerEmpty');
    // ES default locale: "El proveedor no expone modelos".
    expect(
      screen.getByRole('status'),
    ).toHaveTextContent(/El proveedor no expone modelos/i);
  });

  it('does not render added section when added is empty', () => {
    renderTable(EMPTY_DATA);
    // "Nuevo (persistido)" section header should not appear
    expect(screen.queryByText(/nuevo/i)).not.toBeInTheDocument();
  });

  it('summary counts show 0 for empty data', () => {
    renderTable(EMPTY_DATA);
    // All three summary cards should show 0
    const zeros = screen.getAllByText('0');
    expect(zeros.length).toBeGreaterThanOrEqual(3);
  });
});
