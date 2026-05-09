/**
 * ShowcasePage — Design system showcase route (/showcase).
 *
 * What: Developer-only page that renders every design system component shipped
 * in T004 plus visual samples of all token families (colour palette, type scale,
 * spacing rulers, motion durations). Used for visual verification in /verify-slice
 * and as a living reference during development.
 *
 * NOT a productive screen — it is intentionally absent from UX_CONTRACT Screen
 * inventory. No auth, no async data, no loading/empty/error/permission states
 * (all N/A — see task pack §11). Logging is not required on a static showcase.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Source: CHECKLIST P00-S01-T004 §Pantalla/Ruta = /showcase
 *         TECHNICAL_GUIDE §7 (all component names displayed here)
 *         instrucciones.md §7 (editorial identity)
 */

import { useState } from 'react';
import { Wordmark } from '@/shared/design-system/Wordmark';
import { TrackedLabel } from '@/shared/design-system/TrackedLabel';
import { StatusDot } from '@/shared/design-system/StatusDot';
import { EditorialInput } from '@/shared/design-system/EditorialInput';
import { SolidCTA } from '@/shared/design-system/SolidCTA';
import { HairlineTable } from '@/shared/design-system/HairlineTable';
import { MobileFrame } from '@/shared/design-system/MobileFrame';
import { AdminShell } from '@/shared/design-system/AdminShell';

// ── Section wrapper ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section
      aria-labelledby={`section-${title.toLowerCase().replace(/\s+/g, '-')}`}
      style={{ marginBottom: 'var(--space-16)' }}
    >
      <TrackedLabel
        size="sm"
        className=""
        style={{
          marginBottom: 'var(--space-6)',
          borderBottom: 'var(--hairline)',
          paddingBottom: 'var(--space-3)',
        } as React.CSSProperties}
      >
        {title}
      </TrackedLabel>
      {children}
    </section>
  );
}

// ── Colour swatch ─────────────────────────────────────────────────────────────

function Swatch({ token, label }: { token: string; label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', marginBottom: 'var(--space-3)' }}>
      <div
        aria-label={`Colour swatch for ${label}`}
        style={{
          width:        'var(--space-12)',
          height:       'var(--space-8)',
          background:   `var(${token})`,
          border:       'var(--hairline)',
          borderRadius: 'var(--radius)',
          flexShrink:   0,
        }}
      />
      <div>
        <TrackedLabel size="xs">{label}</TrackedLabel>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
          {token}
        </span>
      </div>
    </div>
  );
}

// ── Type specimen ─────────────────────────────────────────────────────────────

function TypeSpecimen({ token, sample }: { token: string; sample: string }) {
  return (
    <div style={{ marginBottom: 'var(--space-3)', borderBottom: 'var(--hairline)', paddingBottom: 'var(--space-2)' }}>
      <span style={{ fontSize: `var(${token})`, fontFamily: 'var(--font-sans)' }}>{sample}</span>
      <TrackedLabel size="xs" style={{ marginTop: 'var(--space-1)' } as React.CSSProperties}>
        {token}
      </TrackedLabel>
    </div>
  );
}

// ── Spacing ruler ─────────────────────────────────────────────────────────────

function SpacingRuler({ token }: { token: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--space-4)', marginBottom: 'var(--space-2)' }}>
      <div
        style={{
          height:      '12px',
          width:       `var(${token})`,
          background:  'var(--color-ink)',
          borderRadius: 'var(--radius)',
          flexShrink:  0,
          minWidth:    '2px',
        }}
        aria-label={`Spacing swatch for ${token}`}
      />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
        {token}
      </span>
    </div>
  );
}

// ── Main showcase page ────────────────────────────────────────────────────────

const tableColumns = [
  { key: 'component', header: 'Component' },
  { key: 'status', header: 'Status' },
  { key: 'slice', header: 'Slice' },
];

const tableRows = [
  { component: 'Wordmark',       status: 'Shipped',   slice: 'P00-S01-T004' },
  { component: 'TrackedLabel',   status: 'Shipped',   slice: 'P00-S01-T004' },
  { component: 'StatusDot',      status: 'Shipped',   slice: 'P00-S01-T004' },
  { component: 'EditorialInput', status: 'Shipped',   slice: 'P00-S01-T004' },
  { component: 'SolidCTA',       status: 'Shipped',   slice: 'P00-S01-T004' },
  { component: 'HairlineTable',  status: 'Shipped',   slice: 'P00-S01-T004' },
  { component: 'MobileFrame',    status: 'Shipped',   slice: 'P00-S01-T004' },
  { component: 'AdminShell',     status: 'Shipped',   slice: 'P00-S01-T004' },
  { component: 'CitationInline', status: 'Deferred',  slice: 'P03-S02' },
];

/**
 * Design system showcase page.
 *
 * Displays all T004 token families and components for visual verification.
 * This route (/showcase) is a development surface only.
 */
export function ShowcasePage() {
  const [inputValue, setInputValue] = useState('');
  const [inputError, setInputError] = useState('');

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setInputValue(e.target.value);
    setInputError('');
  };

  const handleCTAClick = () => {
    if (!inputValue.trim()) {
      setInputError('Este campo es requerido');
    }
  };

  return (
    <div
      data-testid="showcase-page"
      style={{
        padding:         'var(--space-8)',
        maxWidth:        '960px',
        margin:          '0 auto',
        backgroundColor: 'var(--color-bg)',
      }}
    >
      {/* Header */}
      <header style={{ marginBottom: 'var(--space-16)', borderBottom: 'var(--hairline)', paddingBottom: 'var(--space-8)' }}>
        <Wordmark size="4xl" />
        <p style={{ marginTop: 'var(--space-4)', fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
          Design System Showcase — P00-S01-T004
        </p>
      </header>

      {/* Colour tokens */}
      <Section title="Colour Tokens">
        <Swatch token="--color-bg"    label="Background (crudo linen)" />
        <Swatch token="--color-ink"   label="Ink (near-black)" />
        <Swatch token="--color-paper" label="Paper (pure white)" />
        <Swatch token="--color-text-secondary" label="Text Secondary (56 % ink)" />
        <Swatch token="--color-text-disabled"  label="Text Disabled (34 % ink)" />
        <Swatch token="--color-bg-hover"       label="Hover surface (4 % ink)" />
      </Section>

      {/* Type scale */}
      <Section title="Type Scale">
        <TypeSpecimen token="--text-xs"   sample="Micro label — 12 px" />
        <TypeSpecimen token="--text-sm"   sample="Caption / metadata — 14 px" />
        <TypeSpecimen token="--text-base" sample="Body copy — 16 px" />
        <TypeSpecimen token="--text-lg"   sample="Large body / subheading — 18 px" />
        <TypeSpecimen token="--text-xl"   sample="Section heading — 20 px" />
        <TypeSpecimen token="--text-2xl"  sample="Page title — 24 px" />
        <TypeSpecimen token="--text-3xl"  sample="Hero / display — 30 px" />
        <TypeSpecimen token="--text-4xl"  sample="Editorial hero — 36 px" />
      </Section>

      {/* Spacing */}
      <Section title="Spacing Scale">
        {(['--space-1','--space-2','--space-3','--space-4','--space-6','--space-8','--space-12','--space-16'] as const).map(t => (
          <SpacingRuler key={t} token={t} />
        ))}
      </Section>

      {/* Motion */}
      <Section title="Motion Durations">
        <div style={{ display: 'flex', gap: 'var(--space-8)', flexWrap: 'wrap' }}>
          {[
            { token: '--duration-fast',   label: 'Fast — 100ms' },
            { token: '--duration-normal', label: 'Normal — 200ms' },
            { token: '--duration-slow',   label: 'Slow — 350ms' },
          ].map(({ token, label }) => (
            <div key={token} style={{ textAlign: 'center' }}>
              <TrackedLabel size="xs">{label}</TrackedLabel>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 'var(--text-xs)', color: 'var(--color-text-secondary)' }}>
                {token}
              </span>
            </div>
          ))}
        </div>
      </Section>

      {/* Wordmark variants */}
      <Section title="Wordmark">
        <div style={{ display: 'flex', gap: 'var(--space-8)', alignItems: 'baseline', flexWrap: 'wrap' }}>
          <Wordmark size="lg" />
          <Wordmark size="2xl" />
          <Wordmark size="3xl" />
          <Wordmark size="4xl" />
        </div>
      </Section>

      {/* TrackedLabel */}
      <Section title="TrackedLabel">
        <TrackedLabel size="xs">Extra small label</TrackedLabel>
        <TrackedLabel size="sm">Small label</TrackedLabel>
        <TrackedLabel htmlFor="demo-input" size="xs" style={{ marginTop: 'var(--space-4)' } as React.CSSProperties}>
          Form field label (htmlFor)
        </TrackedLabel>
      </Section>

      {/* StatusDot */}
      <Section title="StatusDot">
        <div style={{ display: 'flex', gap: 'var(--space-6)', flexWrap: 'wrap' }}>
          <StatusDot status="active"   label="Active" />
          <StatusDot status="inactive" label="Inactive" />
          <StatusDot status="pending"  label="Pending" />
        </div>
      </Section>

      {/* EditorialInput */}
      <Section title="EditorialInput">
        <div style={{ maxWidth: '400px', display: 'flex', flexDirection: 'column', gap: 'var(--space-6)' }}>
          <EditorialInput
            id="demo-input"
            label="Email"
            placeholder="user@example.com"
            type="email"
            value={inputValue}
            onChange={handleInputChange}
          />
          <EditorialInput
            id="demo-input-error"
            label="Required field (static error demo)"
            placeholder="Leave empty and click CTA"
            type="text"
            errorMessage={inputError}
            value={inputValue}
            onChange={handleInputChange}
          />
        </div>
      </Section>

      {/* SolidCTA */}
      <Section title="SolidCTA">
        <div style={{ display: 'flex', gap: 'var(--space-4)', flexWrap: 'wrap', alignItems: 'center' }}>
          <SolidCTA size="sm" onClick={handleCTAClick}>Small CTA</SolidCTA>
          <SolidCTA size="md" onClick={handleCTAClick}>Medium CTA</SolidCTA>
          <SolidCTA size="lg" onClick={handleCTAClick}>Large CTA</SolidCTA>
          <SolidCTA size="md" disabled>Disabled</SolidCTA>
          <SolidCTA size="md" loading>Loading</SolidCTA>
        </div>
      </Section>

      {/* HairlineTable */}
      <Section title="HairlineTable">
        <HairlineTable
          caption="Design system component registry"
          columns={tableColumns}
          rows={tableRows}
        />
      </Section>

      {/* MobileFrame preview */}
      <Section title="MobileFrame (preview)">
        <div style={{ maxWidth: '402px', border: 'var(--hairline)' }}>
          <MobileFrame>
            <div style={{ padding: 'var(--space-8)' }}>
              <Wordmark size="2xl" />
              <p style={{ marginTop: 'var(--space-4)', fontFamily: 'var(--font-sans)', fontSize: 'var(--text-sm)', color: 'var(--color-text-secondary)' }}>
                Mobile shell preview content
              </p>
            </div>
          </MobileFrame>
        </div>
      </Section>

      {/* AdminShell preview */}
      <Section title="AdminShell (preview)">
        <div style={{ border: 'var(--hairline)', height: '200px', overflow: 'hidden' }}>
          <AdminShell
            sidebar={
              <div>
                <Wordmark size="lg" />
                <TrackedLabel size="xs" style={{ marginTop: 'var(--space-4)' } as React.CSSProperties}>
                  Navigation
                </TrackedLabel>
              </div>
            }
          >
            <TrackedLabel size="sm">Admin content area</TrackedLabel>
          </AdminShell>
        </div>
      </Section>
    </div>
  );
}
