/**
 * StepIndicator — Minimal 3-step progress indicator for the ModelWizardPage.
 *
 * What: Renders a horizontal row of numbered steps with labels. Active step
 *       is visually emphasised via color-ink. Completed steps are marked.
 *       Zero rounded corners; all colors via CSS custom property tokens.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   - react-i18next — useTranslation('admin-ai') for the aria-label only.
 *     Step labels remain caller-provided (already localized by ModelWizardPage).
 *
 * Source-of-truth refs:
 *   - task-pack P00-S02-T007.md §5.2 (3 logical steps)
 *   - instrucciones.md §7 (editorial identity: hairlines, tracking)
 *   - UX_CONTRACT.md §6 (a11y: accessible label on nav)
 *
 * Logging:
 *   No runtime actions. No logs needed per 01-non-negotiables.md §Logging
 *   (pure presentational, no action handler).
 *
 * Accessibility:
 *   - Rendered as <ol> with localized aria-label (admin-ai:wizard.progressLabel).
 *   - Current step marked with aria-current="step".
 *   - Step number + label provide full context without color-only cues.
 */

import type { CSSProperties } from 'react';
import { useTranslation } from 'react-i18next';

interface Step {
  /** Step number (1-based). */
  number: number;
  /** Short label shown below the step circle. */
  label: string;
}

interface StepIndicatorProps {
  /** Ordered list of steps. */
  steps: Step[];
  /** 1-based index of the currently active step. */
  current: number;
}

const olStyle: CSSProperties = {
  display:       'flex',
  alignItems:    'center',
  gap:           'var(--space-6)',
  listStyle:     'none',
  margin:        0,
  padding:       0,
};

const liStyle: CSSProperties = {
  display:       'flex',
  flexDirection: 'column',
  alignItems:    'center',
  gap:           'var(--space-2)',
  position:      'relative',
};

function stepCircleStyle(isActive: boolean, isDone: boolean): CSSProperties {
  return {
    width:           '28px',
    height:          '28px',
    display:         'flex',
    alignItems:      'center',
    justifyContent:  'center',
    border:          'var(--hairline)',
    borderRadius:    'var(--radius)',   /* = 0 */
    fontFamily:      'var(--font-sans)',
    fontSize:        'var(--text-xs)',
    fontWeight:      'var(--weight-semibold)' as string,
    letterSpacing:   'var(--tracking-label)',
    color:           isActive || isDone ? 'var(--color-paper)' : 'var(--color-text-secondary)',
    backgroundColor: isActive || isDone ? 'var(--color-ink)' : 'transparent',
    transition:      `background-color var(--duration-fast) var(--ease-standard)`,
  };
}

function stepLabelStyle(isActive: boolean): CSSProperties {
  return {
    fontFamily:    'var(--font-sans)',
    fontSize:      'var(--text-xs)',
    fontWeight:    isActive ? ('var(--weight-semibold)' as string) : ('var(--weight-normal)' as string),
    letterSpacing: 'var(--tracking-label)',
    textTransform: 'uppercase',
    color:         isActive ? 'var(--color-text-primary)' : 'var(--color-text-secondary)',
    whiteSpace:    'nowrap',
  };
}

/**
 * Horizontal step progress indicator.
 *
 * @param steps - Array of step definitions ({ number, label }).
 * @param current - 1-based index of the active step.
 */
export function StepIndicator({ steps, current }: StepIndicatorProps) {
  const { t } = useTranslation('admin-ai');
  return (
    <ol aria-label={t('wizard.progressLabel')} style={olStyle}>
      {steps.map((step) => {
        const isActive = step.number === current;
        const isDone = step.number < current;
        return (
          <li
            key={step.number}
            aria-current={isActive ? 'step' : undefined}
            style={liStyle}
          >
            <span style={stepCircleStyle(isActive, isDone)} aria-hidden="true">
              {isDone ? '✓' : step.number}
            </span>
            <span style={stepLabelStyle(isActive)}>{step.label}</span>
          </li>
        );
      })}
    </ol>
  );
}
