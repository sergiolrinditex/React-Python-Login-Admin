/**
 * Tests for AdminAiModelsPage shell.
 *
 * What: Verifies the shell renders with the expected CTA linking to
 *       /admin/ai/models/new, and that the i18n key for models.title
 *       is present in the output.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Mock strategy:
 *   MemoryRouter from react-router-dom wraps the component so Link works
 *   without a real browser URL. No fetch mocking needed — shell does no fetch.
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §7 (A1 acceptance criterion)
 *   - task-pack P00-S02-T007.md §12.2 (shell rendering test)
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { I18nextProvider } from 'react-i18next';
import i18n from '@/i18n';
import { AdminAiModelsPage } from '../AdminAiModelsPage';

function renderPage() {
  return render(
    <I18nextProvider i18n={i18n}>
      <MemoryRouter initialEntries={['/admin/ai/models']}>
        <AdminAiModelsPage />
      </MemoryRouter>
    </I18nextProvider>,
  );
}

describe('admin_ai / AdminAiModelsPage shell', () => {
  it('renders without crashing', () => {
    renderPage();
    // If we reach here the page rendered without throwing
  });

  it('renders the models title from i18n admin-ai namespace', () => {
    renderPage();
    // The ES locale title from admin-ai.models.title
    expect(screen.getByText('Modelos LiteLLM')).toBeInTheDocument();
  });

  it('renders a CTA that links to /admin/ai/models/new', () => {
    renderPage();
    // Wizard title is the CTA label (Descubrir modelos in ES locale)
    const link = screen.getByRole('link', { name: /descubrir modelos/i });
    expect(link).toBeInTheDocument();
    expect(link).toHaveAttribute('href', '/admin/ai/models/new');
  });

  it('renders the route breadcrumb TrackedLabel', () => {
    renderPage();
    expect(screen.getByText('/admin/ai/models')).toBeInTheDocument();
  });

  it('renders the deferred scope notice', () => {
    renderPage();
    expect(screen.getByText(/MVP.*P04-S01-T002/i)).toBeInTheDocument();
  });
});
