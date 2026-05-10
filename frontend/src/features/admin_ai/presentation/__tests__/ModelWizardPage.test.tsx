/**
 * Tests for ModelWizardPage — step transitions and error state rendering.
 *
 * What: Verifies:
 *   - Step 1 renders the provider UUID input and submit CTA.
 *   - Submitting with an invalid UUID shows the validation error (stays on step 1).
 *   - Submitting with a valid UUID + mocked 200 response advances to step 3.
 *   - Mocked 401 response shows permission_denied message on step 2.
 *   - Mocked 502 response shows upstream error message on step 2.
 *   - Mocked network failure shows network error message on step 2.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Mock strategy:
 *   vi.spyOn(globalThis, 'fetch') per test for wizard submit scenarios.
 *   MemoryRouter wraps the component.
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §7 (A2, A4 acceptance criteria)
 *   - task-pack P00-S02-T007.md §12.2 (wizard step transitions)
 */

import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n';
import { ModelWizardPage } from '../ModelWizardPage';
import type { DiscoverModelsResponse } from '../../data/types';

// ── Fixtures ─────────────────────────────────────────────────────────────────

const VALID_UUID = '12345678-1234-4234-8234-123456789abc';

const HAPPY_RESPONSE: DiscoverModelsResponse = {
  data: {
    added: [
      {
        id: 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
        provider_id: VALID_UUID,
        model_id: 'gemini-1.5-pro',
        model_type: 'chat',
        capabilities: [],
        enabled: true,
        is_default: false,
        auto_discovered: true,
      },
    ],
    existing: [],
    skipped: [],
    total_seen: 1,
  },
};

// ── Helper ────────────────────────────────────────────────────────────────────

function renderWizard() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={['/admin/ai/models/new']}>
        <ModelWizardPage />
      </MemoryRouter>
    </I18nextProvider>,
  );
}

function mockFetch(status: number, body: unknown) {
  return vi.spyOn(globalThis, 'fetch').mockResolvedValueOnce({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
  } as Response);
}

function mockFetchNetworkError() {
  return vi
    .spyOn(globalThis, 'fetch')
    .mockRejectedValueOnce(new Error('Network failed'));
}

afterEach(() => {
  vi.restoreAllMocks();
});

// ── Tests ─────────────────────────────────────────────────────────────────────

describe('admin_ai / ModelWizardPage step transitions', () => {
  it('renders step 1 with provider UUID input on initial mount', () => {
    renderWizard();
    expect(screen.getByLabelText(/UUID del proveedor/i)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /descubrir/i })).toBeInTheDocument();
  });

  it('shows validation error for empty input without calling fetch', async () => {
    const spy = vi.spyOn(globalThis, 'fetch');
    renderWizard();

    const btn = screen.getByRole('button', { name: /descubrir/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByRole('alert').textContent).toMatch(/UUID/i);
    });
    expect(spy).not.toHaveBeenCalled();
  });

  it('shows validation error for malformed UUID input', async () => {
    const spy = vi.spyOn(globalThis, 'fetch');
    renderWizard();

    const input = screen.getByLabelText(/UUID del proveedor/i);
    fireEvent.change(input, { target: { value: 'not-a-uuid' } });

    const btn = screen.getByRole('button', { name: /descubrir/i });
    fireEvent.click(btn);

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
    });
    expect(spy).not.toHaveBeenCalled();
  });

  it('advances to step 3 (diff review) on 200 response', async () => {
    mockFetch(200, HAPPY_RESPONSE);
    renderWizard();

    const input = screen.getByLabelText(/UUID del proveedor/i);
    fireEvent.change(input, { target: { value: VALID_UUID } });

    const btn = screen.getByRole('button', { name: /descubrir/i });
    fireEvent.click(btn);

    // Step 2 spinner should appear first
    await waitFor(() => {
      expect(screen.getByRole('status')).toBeInTheDocument();
    });

    // Then step 3 should render with Approve & return CTA
    await waitFor(() => {
      expect(
        screen.getByRole('button', { name: /aprobar y volver/i }),
      ).toBeInTheDocument();
    });
  });

  it('shows permission_denied message on 401 response (stays on step 2)', async () => {
    mockFetch(401, {
      detail: { error: { code: 'require_admin', message: 'Unauthorized' } },
    });
    renderWizard();

    const input = screen.getByLabelText(/UUID del proveedor/i);
    fireEvent.change(input, { target: { value: VALID_UUID } });
    fireEvent.click(screen.getByRole('button', { name: /descubrir/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert')).toBeInTheDocument();
      expect(screen.getByRole('alert').textContent).toMatch(
        /acceso de administrador/i,
      );
    });
  });

  it('shows upstream error message on 502 response', async () => {
    mockFetch(502, {
      detail: { error: { code: 'upstream_provider_error', message: 'Bad gateway' } },
    });
    renderWizard();

    const input = screen.getByLabelText(/UUID del proveedor/i);
    fireEvent.change(input, { target: { value: VALID_UUID } });
    fireEvent.click(screen.getByRole('button', { name: /descubrir/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/proveedor externo/i);
    });
  });

  it('shows network error message on transport failure', async () => {
    mockFetchNetworkError();
    renderWizard();

    const input = screen.getByLabelText(/UUID del proveedor/i);
    fireEvent.change(input, { target: { value: VALID_UUID } });
    fireEvent.click(screen.getByRole('button', { name: /descubrir/i }));

    await waitFor(() => {
      expect(screen.getByRole('alert').textContent).toMatch(/error de red/i);
    });
  });
});
