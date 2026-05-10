/**
 * Application entry point — Hilo People frontend.
 *
 * What: Mounts the React 19 root via createRoot, imports the global CSS
 * (design tokens + editorial reset), wraps the app in AppProviders, and
 * sets up a minimal createBrowserRouter with the /showcase route.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 * Updated:     P00 / P00-S02-T007 — AdminAiModelsPage discover wizard UI
 *
 * Router note:
 *   /showcase and / were wired in P00-S01-T004.
 *   /admin/ai/models and /admin/ai/models/new are added in P00-S02-T007 (MVP).
 *   Full productive route tree (auth, chat, admin canonical) is wired in
 *   P01-S03-T001 after the auth foundation is built.
 *   See TECHNICAL_GUIDE §5 and §6.1 for the full route tree.
 *
 * Dependencies:
 *   - react 19.2.6 / react-dom/client (createRoot)
 *   - react-router / react-router/dom (createBrowserRouter, RouterProvider)
 *     Per official-doc-notes/P00-S01-T004: v7 canonical import pattern.
 *   - AppProviders — from ./app/providers (T002)
 *   - ShowcasePage — from ./app/showcase/ShowcasePage (T004)
 *   - AdminAiModelsPage — from ./features/admin_ai/presentation/AdminAiModelsPage (T007)
 *   - ModelWizardPage — from ./features/admin_ai/presentation/ModelWizardPage (T007)
 *   - tokens.css / reset.css — from ./shared/styles (T004)
 */

import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

import { AppProviders } from './app/providers';
import { ShowcasePage } from './app/showcase/ShowcasePage';
import { AdminAiModelsPage } from './features/admin_ai/presentation/AdminAiModelsPage';
import { ModelWizardPage } from './features/admin_ai/presentation/ModelWizardPage';

import './shared/styles/tokens.css';
import './shared/styles/reset.css';

/**
 * Application router — P00 scaffold + admin AI MVP routes.
 *
 * Routes added in P00-S02-T007:
 *   /admin/ai/models     — AdminAiModelsPage (shell, no auth guard — P01-S03-T001)
 *   /admin/ai/models/new — ModelWizardPage  (discover wizard MVP)
 *
 * Remaining productive routes are wired in P01-S03-T001.
 */
const router = createBrowserRouter([
  {
    path: '/showcase',
    element: <ShowcasePage />,
  },
  {
    // Redirect root to showcase during scaffold phase only.
    // Replaced by auth-gated root in P01-S03-T001.
    path: '/',
    element: <ShowcasePage />,
  },
  {
    // MVP shell — J103 admin AI models list (full table in P04-S01-T002)
    // TODO(P01-S03-T001): add auth guard — redirect to /sign-in if no session.
    path: '/admin/ai/models',
    element: <AdminAiModelsPage />,
  },
  {
    // MVP discover-models wizard — J103 (FU-X1 endpoint, T006)
    // TODO(P01-S03-T001): add auth guard — redirect to /sign-in if no session.
    path: '/admin/ai/models/new',
    element: <ModelWizardPage />,
  },
]);

const container = document.getElementById('root');

if (container === null) {
  throw new Error(
    'Mount target #root not found. Verify that index.html contains <div id="root">.',
  );
}

createRoot(container).render(
  <AppProviders>
    <RouterProvider router={router} />
  </AppProviders>,
);
