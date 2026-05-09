/**
 * Application entry point — Hilo People frontend.
 *
 * What: Mounts the React 19 root via createRoot, imports the global CSS
 * (design tokens + editorial reset), wraps the app in AppProviders, and
 * sets up a minimal createBrowserRouter with the /showcase route.
 *
 * Phase/Slice: P00 / P00-S01-T004 — Design tokens and editorial system
 *
 * Router note:
 *   Only the /showcase route exists at this stage — it is a development-only
 *   design-system surface (not in UX_CONTRACT Screen inventory). Productive
 *   routes (auth, chat, admin, etc.) are wired in P01-S03-T001 after the
 *   auth foundation is built. See TECHNICAL_GUIDE §5 for the full route tree.
 *
 * Dependencies:
 *   - react 19.2.6 / react-dom/client (createRoot)
 *   - react-router / react-router/dom (createBrowserRouter, RouterProvider)
 *     Per official-doc-notes/P00-S01-T004: v7 canonical import pattern.
 *   - AppProviders — from ./app/providers (T002)
 *   - ShowcasePage — from ./app/showcase/ShowcasePage (T004)
 *   - tokens.css / reset.css — from ./shared/styles (T004)
 */

import { createRoot } from 'react-dom/client';
import { createBrowserRouter, RouterProvider } from 'react-router-dom';

import { AppProviders } from './app/providers';
import { ShowcasePage } from './app/showcase/ShowcasePage';

import './shared/styles/tokens.css';
import './shared/styles/reset.css';

/**
 * Application router — minimal one-route setup for P00 scaffold.
 * Productive routes are wired in P01-S03-T001.
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
