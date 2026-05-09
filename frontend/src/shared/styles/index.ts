/**
 * TypeScript const mirror for Hilo People design tokens.
 *
 * What: Exposes the CSS custom-property names as typed string constants so
 * component code can reference tokens via `tokens.colorBg` instead of
 * bare string `'--color-bg'`, reducing typo risk and enabling IDE completions.
 *
 * IMPORTANT: This module exports NAMES only (the CSS variable key strings).
 * It does NOT duplicate the VALUES. The values live exclusively in tokens.css.
 * If a test needs to compare a computed value, it should rely on jsdom
 * getComputedStyle() against the real CSS, not on a constant from this file.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Dependencies:
 *   - tokens.css (must be imported before components for var() to resolve)
 */

/** CSS variable names for design tokens — type-safe string constants. */
export const tokens = {
  // ── Colour palette ──────────────────────────────────────────────────
  colorBg:            '--color-bg',
  colorInk:           '--color-ink',
  colorPaper:         '--color-paper',
  colorTextPrimary:   '--color-text-primary',
  colorTextSecondary: '--color-text-secondary',
  colorTextDisabled:  '--color-text-disabled',
  colorBorder:        '--color-border',
  colorBgHover:       '--color-bg-hover',
  colorFocusRing:     '--color-focus-ring',

  // ── Typography ────────────────────────────────────────────────────
  fontDisplay: '--font-display',
  fontSans:    '--font-sans',
  fontMono:    '--font-mono',

  // ── Type scale ────────────────────────────────────────────────────
  textXs:   '--text-xs',
  textSm:   '--text-sm',
  textBase: '--text-base',
  textLg:   '--text-lg',
  textXl:   '--text-xl',
  text2xl:  '--text-2xl',
  text3xl:  '--text-3xl',
  text4xl:  '--text-4xl',

  // ── Tracking (letter-spacing) ─────────────────────────────────────
  trackingTight:  '--tracking-tight',
  trackingNormal: '--tracking-normal',
  trackingLabel:  '--tracking-label',
  trackingWide:   '--tracking-wide',

  // ── Spacing ───────────────────────────────────────────────────────
  space0:  '--space-0',
  space1:  '--space-1',
  space2:  '--space-2',
  space3:  '--space-3',
  space4:  '--space-4',
  space5:  '--space-5',
  space6:  '--space-6',
  space8:  '--space-8',
  space10: '--space-10',
  space12: '--space-12',
  space16: '--space-16',
  space20: '--space-20',
  space24: '--space-24',

  // ── Borders and hairlines ─────────────────────────────────────────
  hairline: '--hairline',

  // ── Border radius — ALWAYS ZERO per editorial code ───────────────
  radius: '--radius',

  // ── Z-index layers ────────────────────────────────────────────────
  zBelow:    '--z-below',
  zBase:     '--z-base',
  zRaised:   '--z-raised',
  zDropdown: '--z-dropdown',
  zSticky:   '--z-sticky',
  zOverlay:  '--z-overlay',
  zModal:    '--z-modal',
  zToast:    '--z-toast',

  // ── Motion / transitions ──────────────────────────────────────────
  durationFast:   '--duration-fast',
  durationNormal: '--duration-normal',
  durationSlow:   '--duration-slow',
  easeStandard:   '--ease-standard',
  easeEnter:      '--ease-enter',
  easeExit:       '--ease-exit',

  // ── Shadows ───────────────────────────────────────────────────────
  shadowNone: '--shadow-none',
} as const;

/** Type for valid token CSS variable name keys. */
export type TokenKey = keyof typeof tokens;

/** Type for valid token CSS variable name values (e.g. '--color-bg'). */
export type TokenValue = (typeof tokens)[TokenKey];
