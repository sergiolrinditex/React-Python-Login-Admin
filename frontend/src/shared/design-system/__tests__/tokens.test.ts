/**
 * Unit tests for design tokens TS mirror.
 *
 * What: Asserts that the TS const mirror exports the correct CSS variable names
 * and that critical editorial invariants hold (radius=0 variable name, primary
 * color and tracking label are present). This prevents accidental token drift
 * between the CSS declarations and the TS constants.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Test type: unit (pure static assertion — no DOM, no imports from browser APIs).
 * No mocking required; the tokens object is a plain const.
 */

import { describe, it, expect } from 'vitest';
import { tokens } from '../../styles/index';

describe('tokens — TS mirror', () => {
  it('exports the --radius token name (value = 0 in CSS)', () => {
    expect(tokens.radius).toBe('--radius');
  });

  it('exports the primary colour tokens', () => {
    expect(tokens.colorBg).toBe('--color-bg');
    expect(tokens.colorInk).toBe('--color-ink');
    expect(tokens.colorPaper).toBe('--color-paper');
  });

  it('exports the editorial tracking-label token', () => {
    expect(tokens.trackingLabel).toBe('--tracking-label');
  });

  it('exports the font stacks', () => {
    expect(tokens.fontDisplay).toBe('--font-display');
    expect(tokens.fontSans).toBe('--font-sans');
  });

  it('exports the hairline token', () => {
    expect(tokens.hairline).toBe('--hairline');
  });

  it('exports type scale tokens', () => {
    expect(tokens.textBase).toBe('--text-base');
    expect(tokens.text2xl).toBe('--text-2xl');
    expect(tokens.text4xl).toBe('--text-4xl');
  });

  it('all token values start with --', () => {
    const values = Object.values(tokens);
    values.forEach((v) => {
      expect(v).toMatch(/^--/);
    });
  });
});
