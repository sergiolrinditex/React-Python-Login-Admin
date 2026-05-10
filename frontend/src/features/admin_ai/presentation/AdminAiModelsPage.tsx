/**
 * AdminAiModelsPage — Shell page for /admin/ai/models (MVP).
 *
 * What: P00 MVP shell. Renders the AdminShell wrapper + a CTA that navigates
 *       to /admin/ai/models/new (ModelWizardPage). Does NOT fetch providers
 *       or models — that lands in P04-S01-T002 (canonical AdminAiModelsPage).
 *
 * UX states (UX_CONTRACT §3 row 1):
 *   - success  — always rendered (no fetch → always ready)
 *   - loading  — n/a (no fetch in MVP — covered by wizard). Documented here.
 *   - empty    — rendered as default state (no models table yet → CTA to discover)
 *   - error_network    — n/a (no fetch in MVP — covered by wizard)
 *   - permission_denied — n/a (no fetch in MVP — covered by wizard)
 *
 * Auth guard: NOT implemented (P01-S03-T001's job).
 *   TODO(P01-S03-T001): add auth guard — redirect to /sign-in if no session.
 *
 * Phase/Slice: P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Dependencies:
 *   - react-router-dom — Link (navigation)
 *   - react-i18next — useTranslation('admin-ai')
 *   - @/shared/design-system/AdminShell
 *   - @/shared/design-system/Wordmark
 *   - @/shared/design-system/TrackedLabel
 *   - @/shared/design-system/SolidCTA
 *
 * Source-of-truth refs:
 *   - TECHNICAL_GUIDE §6.1 (route /admin/ai/models, AdminAiModelsPage)
 *   - task-pack P00-S02-T007.md §5.1 (UX states for shell)
 *   - UX_CONTRACT.md §3 row 1
 *   - instrucciones.md §3.6 J103 (admin → /admin/ai/models → /admin/ai/models/new)
 *
 * Logging:
 *   No fetch actions — no BEFORE/AFTER logs needed at this stage.
 *   Per 01-non-negotiables.md §Logging: logs added when shell gains a fetch.
 *
 * Accessibility:
 *   - Main landmark from AdminShell.
 *   - CTA has accessible text via children content.
 *   - Keyboard tab order: CTA is the first and only interactive element.
 */

import type { CSSProperties } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { AdminShell } from '@/shared/design-system/AdminShell';
import { Wordmark } from '@/shared/design-system/Wordmark';
import { TrackedLabel } from '@/shared/design-system/TrackedLabel';
import { SolidCTA } from '@/shared/design-system/SolidCTA';

const contentStyle: CSSProperties = {
  display:       'flex',
  flexDirection: 'column',
  gap:           'var(--space-8)',
  maxWidth:      '640px',
};

const headerStyle: CSSProperties = {
  borderBottom: 'var(--hairline)',
  paddingBottom: 'var(--space-6)',
  marginBottom:  'var(--space-6)',
};

const deferred: CSSProperties = {
  marginTop:   'var(--space-4)',
  paddingTop:  'var(--space-4)',
  borderTop:   'var(--hairline)',
};

/**
 * Admin AI models page — MVP shell with CTA to discover new models.
 *
 * Renders the AdminShell layout with a single CTA pointing to
 * /admin/ai/models/new. Full hairline table with model list lands
 * in P04-S01-T002.
 */
export function AdminAiModelsPage() {
  const { t } = useTranslation('admin-ai');

  const sidebar = (
    <Wordmark />
  );

  return (
    <AdminShell sidebar={sidebar}>
      <div style={contentStyle}>
        <header style={headerStyle}>
          <TrackedLabel size="sm">/admin/ai/models</TrackedLabel>
          <h1
            style={{
              fontFamily:  'var(--font-display)',
              fontSize:    'var(--text-2xl)',
              fontWeight:  'var(--weight-bold)' as string,
              color:       'var(--color-text-primary)',
              margin:      'var(--space-4) 0 0',
              lineHeight:  'var(--leading-tight)',
            }}
          >
            {t('models.title')}
          </h1>
        </header>

        {/* Empty state — no models table yet in MVP */}
        <div>
          <p
            style={{
              fontFamily:   'var(--font-sans)',
              fontSize:     'var(--text-base)',
              color:        'var(--color-text-secondary)',
              margin:       '0 0 var(--space-6)',
              lineHeight:   'var(--leading-normal)',
            }}
          >
            {t('models.empty')}
          </p>

          {/* Primary CTA — links to wizard */}
          <Link to="/admin/ai/models/new" style={{ textDecoration: 'none' }}>
            <SolidCTA>{t('wizard.title')}</SolidCTA>
          </Link>
        </div>

        {/* Deferred scope notice — visible to verify-slice human */}
        <div style={deferred}>
          <TrackedLabel>
            {t('models.deferredScope')}
          </TrackedLabel>
        </div>
      </div>
    </AdminShell>
  );
}
