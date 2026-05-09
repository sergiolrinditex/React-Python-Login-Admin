/**
 * Showcase page smoke test.
 *
 * What: Verifies that ShowcasePage renders without errors and contains the
 * expected design-system sections. This is a developer-verification test to
 * confirm that the /showcase route is functional before /verify-slice.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Test type: component (jsdom + Testing Library — no backend, no API).
 * ShowcasePage is a static render; no mocks required.
 */

import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ShowcasePage } from './ShowcasePage';

describe('ShowcasePage', () => {
  it('renders without throwing', () => {
    expect(() => render(<ShowcasePage />)).not.toThrow();
  });

  it('has a data-testid="showcase-page" root element', () => {
    render(<ShowcasePage />);
    expect(screen.getByTestId('showcase-page')).toBeInTheDocument();
  });

  it('renders the HILO wordmark', () => {
    render(<ShowcasePage />);
    // Multiple Wordmark instances — at minimum one should have the accessible label
    expect(screen.getAllByRole('img', { name: /hilo people/i }).length).toBeGreaterThan(0);
  });

  it('renders the HairlineTable with component registry', () => {
    render(<ShowcasePage />);
    expect(screen.getByRole('table')).toBeInTheDocument();
    // Table has cells with component names — use getAllByText since "Wordmark"
    // also appears as a section header elsewhere on the showcase page.
    expect(screen.getAllByText('Wordmark').length).toBeGreaterThan(0);
    expect(screen.getAllByText('SolidCTA').length).toBeGreaterThan(0);
    // Check table column headers
    expect(screen.getByRole('columnheader', { name: /component/i })).toBeInTheDocument();
  });

  it('renders StatusDot variants', () => {
    render(<ShowcasePage />);
    // Use exact name match to avoid "Active" regex matching "Inactive".
    expect(screen.getByRole('status', { name: 'Active' })).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Inactive' })).toBeInTheDocument();
    expect(screen.getByRole('status', { name: 'Pending' })).toBeInTheDocument();
  });

  it('renders EditorialInput fields', () => {
    render(<ShowcasePage />);
    const inputs = screen.getAllByRole('textbox');
    expect(inputs.length).toBeGreaterThan(0);
  });

  it('renders SolidCTA buttons', () => {
    render(<ShowcasePage />);
    const buttons = screen.getAllByRole('button');
    expect(buttons.length).toBeGreaterThan(0);
  });

  it('renders AdminShell nav landmark', () => {
    render(<ShowcasePage />);
    expect(screen.getByRole('navigation', { name: /admin navigation/i })).toBeInTheDocument();
  });
});
