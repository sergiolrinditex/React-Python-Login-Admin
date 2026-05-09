/**
 * Component tests for T004 design-system primitives.
 *
 * What: Verifies mount, accessibility contract, and token usage for each
 * design-system component shipped in T004. Tests use @testing-library/react
 * against real TSX in a jsdom environment — no mocking of components.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Test type: component (jsdom, Testing Library — no backend, no API).
 * Allowed by 01-non-negotiables §Tests: pure presentational logic CAN be isolated.
 */

import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import { Wordmark } from '../Wordmark';
import { TrackedLabel } from '../TrackedLabel';
import { StatusDot } from '../StatusDot';
import { EditorialInput } from '../EditorialInput';
import { SolidCTA } from '../SolidCTA';
import { HairlineTable } from '../HairlineTable';
import { MobileFrame } from '../MobileFrame';
import { AdminShell } from '../AdminShell';

// ── Wordmark ──────────────────────────────────────────────────────────────────

describe('Wordmark', () => {
  it('renders the HILO text', () => {
    render(<Wordmark />);
    expect(screen.getByRole('img', { name: /hilo people/i })).toBeInTheDocument();
  });

  it('has role="img" with accessible label', () => {
    render(<Wordmark label="Hilo People" />);
    const el = screen.getByRole('img', { name: 'Hilo People' });
    expect(el).toBeInTheDocument();
  });

  it('uses the display font token on inline style', () => {
    render(<Wordmark />);
    const el = screen.getByRole('img');
    // Check raw inline style attribute — jsdom does not resolve CSS variables.
    expect(el.getAttribute('style')).toContain('var(--font-display)');
  });

  it('applies border-radius token (= 0)', () => {
    render(<Wordmark />);
    const el = screen.getByRole('img');
    expect(el.getAttribute('style')).toContain('var(--radius)');
  });
});

// ── TrackedLabel ──────────────────────────────────────────────────────────────

describe('TrackedLabel', () => {
  it('renders children text', () => {
    render(<TrackedLabel>Test Label</TrackedLabel>);
    expect(screen.getByText('Test Label')).toBeInTheDocument();
  });

  it('renders as <label> when htmlFor is provided', () => {
    render(<TrackedLabel htmlFor="my-input">Email</TrackedLabel>);
    expect(screen.getByText('Email').tagName).toBe('LABEL');
    expect(screen.getByText('Email')).toHaveAttribute('for', 'my-input');
  });

  it('renders as <span> when htmlFor is absent', () => {
    render(<TrackedLabel>Section</TrackedLabel>);
    expect(screen.getByText('Section').tagName).toBe('SPAN');
  });

  it('applies tracking-label token', () => {
    render(<TrackedLabel>X</TrackedLabel>);
    expect(screen.getByText('X').getAttribute('style')).toContain('var(--tracking-label)');
  });
});

// ── StatusDot ─────────────────────────────────────────────────────────────────

describe('StatusDot', () => {
  it('has role="status" with accessible label', () => {
    render(<StatusDot status="active" label="Active" />);
    expect(screen.getByRole('status', { name: 'Active' })).toBeInTheDocument();
  });

  it('renders the visible label text', () => {
    render(<StatusDot status="inactive" label="Inactive" />);
    expect(screen.getByText('Inactive')).toBeInTheDocument();
  });

  it('uses aria-label derived from status when no label prop', () => {
    render(<StatusDot status="pending" />);
    expect(screen.getByRole('status', { name: 'pending' })).toBeInTheDocument();
  });

  it('renders the decorative dot with aria-hidden', () => {
    const { container } = render(<StatusDot status="active" label="Active" />);
    const dot = container.querySelector('[aria-hidden="true"]');
    expect(dot).not.toBeNull();
  });
});

// ── EditorialInput ────────────────────────────────────────────────────────────

describe('EditorialInput', () => {
  it('renders an input element', () => {
    render(<EditorialInput placeholder="Enter text" />);
    expect(screen.getByRole('textbox')).toBeInTheDocument();
  });

  it('shows label associated with input via htmlFor/id', () => {
    render(<EditorialInput id="email" label="Email" />);
    expect(screen.getByLabelText(/email/i)).toBeInTheDocument();
  });

  it('renders error message and sets aria-invalid', () => {
    render(
      <EditorialInput
        id="email"
        label="Email"
        errorMessage="Required field"
      />,
    );
    const input = screen.getByRole('textbox');
    expect(input).toHaveAttribute('aria-invalid', 'true');
    expect(screen.getByRole('alert')).toHaveTextContent('Required field');
  });

  it('calls onChange when value changes', () => {
    const handler = vi.fn();
    render(<EditorialInput id="test" onChange={handler} />);
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'abc' } });
    expect(handler).toHaveBeenCalled();
  });

  it('applies hairline border token via inline style', () => {
    render(<EditorialInput />);
    expect(screen.getByRole('textbox').getAttribute('style')).toContain('var(--hairline)');
  });

  it('applies zero border-radius token', () => {
    render(<EditorialInput />);
    expect(screen.getByRole('textbox').getAttribute('style')).toContain('var(--radius)');
  });
});

// ── SolidCTA ──────────────────────────────────────────────────────────────────

describe('SolidCTA', () => {
  it('renders a button with children text', () => {
    render(<SolidCTA>Continue</SolidCTA>);
    expect(screen.getByRole('button', { name: 'Continue' })).toBeInTheDocument();
  });

  it('calls onClick when clicked', () => {
    const handler = vi.fn();
    render(<SolidCTA onClick={handler}>Click me</SolidCTA>);
    fireEvent.click(screen.getByRole('button'));
    expect(handler).toHaveBeenCalledOnce();
  });

  it('is disabled when disabled prop is true', () => {
    render(<SolidCTA disabled>Submit</SolidCTA>);
    expect(screen.getByRole('button')).toBeDisabled();
  });

  it('is disabled when loading is true', () => {
    render(<SolidCTA loading>Submit</SolidCTA>);
    expect(screen.getByRole('button')).toBeDisabled();
    expect(screen.getByRole('button')).toHaveAttribute('aria-busy', 'true');
  });

  it('applies solid black background token (no hex literal)', () => {
    render(<SolidCTA>CTA</SolidCTA>);
    expect(screen.getByRole('button').getAttribute('style')).toContain('var(--color-ink)');
  });

  it('applies zero border-radius', () => {
    render(<SolidCTA>CTA</SolidCTA>);
    expect(screen.getByRole('button').getAttribute('style')).toContain('var(--radius)');
  });

  it('uses uppercase tracking via letterSpacing token', () => {
    render(<SolidCTA>CTA</SolidCTA>);
    expect(screen.getByRole('button').getAttribute('style')).toContain('var(--tracking-label)');
  });
});

// ── HairlineTable ─────────────────────────────────────────────────────────────

describe('HairlineTable', () => {
  const columns = [
    { key: 'name', header: 'Name' },
    { key: 'role', header: 'Role' },
  ];
  const rows = [
    { name: 'Alice', role: 'Admin' },
    { name: 'Bob', role: 'User' },
  ];

  it('renders a table with columnHeaders', () => {
    render(<HairlineTable columns={columns} rows={rows} />);
    expect(screen.getByRole('table')).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /name/i })).toBeInTheDocument();
    expect(screen.getByRole('columnheader', { name: /role/i })).toBeInTheDocument();
  });

  it('renders row data', () => {
    render(<HairlineTable columns={columns} rows={rows} />);
    expect(screen.getByText('Alice')).toBeInTheDocument();
    expect(screen.getByText('Admin')).toBeInTheDocument();
  });

  it('renders caption element when caption prop provided', () => {
    const { container } = render(
      <HairlineTable columns={columns} rows={rows} caption="User list" />,
    );
    expect(container.querySelector('caption')).toHaveTextContent('User list');
  });
});

// ── MobileFrame ───────────────────────────────────────────────────────────────

describe('MobileFrame', () => {
  it('renders children inside a <main> landmark', () => {
    render(
      <MobileFrame>
        <p>Mobile content</p>
      </MobileFrame>,
    );
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByText('Mobile content')).toBeInTheDocument();
  });
});

// ── AdminShell ────────────────────────────────────────────────────────────────

describe('AdminShell', () => {
  it('renders sidebar content inside a <nav> landmark', () => {
    render(
      <AdminShell sidebar={<span>Nav</span>}>
        <p>Content</p>
      </AdminShell>,
    );
    expect(screen.getByRole('navigation', { name: /admin navigation/i })).toBeInTheDocument();
    expect(screen.getByText('Nav')).toBeInTheDocument();
  });

  it('renders main content inside a <main> landmark', () => {
    render(
      <AdminShell sidebar={<span>Nav</span>}>
        <p>Main content</p>
      </AdminShell>,
    );
    expect(screen.getByRole('main')).toBeInTheDocument();
    expect(screen.getByText('Main content')).toBeInTheDocument();
  });
});
