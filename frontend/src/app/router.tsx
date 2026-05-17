/**
 * Hilo People — Application router.
 *
 * Slice/Phase: P01-S03-T001 — Auth state provider + route guards / Phase 1.
 *   Updated from P00-S01-T004 (original: /showcase only).
 *   Updated in P03-S01-T001 — replaced SignInStub with real SignInPage (§D-T001-ROUTER).
 *   WRITE_SET_DRIFT §D-T001-ROUTE (P03-S02-T001): wired /chat to ChatHomePage;
 *     updated / and * redirects so authenticated users land on /chat.
 *   Updated in P03-S01-T002 — added /auth/sign-up route wired to SignUpPage (§D-T002-ROUTER).
 *   Updated in P03-S02-T003 — added /history route wired to HistoryPage (§D-T003-ROUTER).
 *   Updated in P03-S01-T004 — added /auth/reset-sent route wired to ResetSentPage (§D-T004-ROUTER).
 *   Updated in P03-S01-T005 — added /auth/2fa route wired to TwoFactorPage (§D-T005-ROUTER).
 *   Updated in P04-S01-T001 (§D-T001-ROUTER): real AdminDashboardPage replaces AdminStub;
 *     added ROUTE_ADMIN_AI_MODELS, ROUTE_ADMIN_AI_MODELS_NEW, ROUTE_ADMIN_RAG_DOCUMENTS,
 *     ROUTE_ADMIN_RAG_COLLECTIONS, ROUTE_ADMIN_AI_MCP, ROUTE_ADMIN_AI_MCP_NEW,
 *     ROUTE_ADMIN_AI_AGENTS, ROUTE_ADMIN_AUDIT, ROUTE_ADMIN_USAGE constants for nav.
 *   Updated in P04-S02-T003 — added /admin/ai/mcp route wired to McpServersPage (§D-T003-ROUTER).
 *   Updated in P04-S02-T001 — added /admin/rag/documents route wired to RagDocumentsPage (§D-RAGDOC-ROUTER).
 *   Updated in P04-S01-T002 — added /admin/ai/models route wired to AdminAiModelsPage (§D-T002-ROUTER).
 *   Updated in P04-S02-T002 — added /admin/rag/collections route wired to RagCollectionsPage (§D-T002-ROUTER).
 *   Updated in P04-S01-T003 — wired /admin/ai/models/new to ModelWizardPage (§D-T003-ROUTER).
 *     WRITE_SET_DRIFT: router.tsx is not in the Coverage Registry write_set but is required
 *     to make the page reachable; justified by identical precedent in P04-S01-T002 (line 22
 *     of that handoff). Documented in handoff §D-T003-ROUTER.
 *   Updated in P04-S02-T004 — added /admin/ai/mcp/new route wired to McpWizardPage (§D-T004-ROUTER).
 *   Updated in P04-S01-T004 — added /admin/ai/models/:modelId/test wired to ModelTestDrawer (§D-T004-ROUTER).
 *     WRITE_SET_DRIFT §D-T004-ROUTER: authorized by task pack §6.2 file #11 (pre-approved wiring pattern).
 *
 * Responsibility: single mount point for the application's route tree.
 *   Exports <AppRouter> which is consumed by main.tsx inside <Providers>.
 *   <AuthProvider> is mounted INSIDE the router tree (not in providers.tsx — P-7).
 *
 * Route inventory:
 *   /showcase          → ShowcasePage (public — design-system demo, dev-only)
 *   /auth/sign-in      → SignInPage (real form, P03-S01-T001)
 *   /auth/sign-up      → SignUpPage (real form, P03-S01-T002)
 *   /auth/reset-sent   → ResetSentPage (P03-S01-T004)
 *   /auth/2fa          → TwoFactorPage (P03-S01-T005, public, J100 MFA step)
 *   /chat              → ChatHomePage (employee, RequireAuth) — P03-S02-T001
 *   /chat/:conversationId → placeholder (P03-S02-T002 adds real ConversationPage)
 *   /history              → HistoryPage (employee history, RequireAuth) — P03-S02-T003
 *   /admin             → AdminDashboardPage (people_admin|super_admin) — P04-S01-T001
 *   /admin/ai/mcp      → McpServersPage (admin, RequireRole) — P04-S02-T003 §D-T003-ROUTER
 *   /admin/ai/mcp/new  → McpWizardPage (admin, RequireRole) — P04-S02-T004 §D-T004-ROUTER
 *   /admin/rag/documents → RagDocumentsPage (admin, RequireRole) — P04-S02-T001 §D-RAGDOC-ROUTER
 *   /admin/rag/collections → RagCollectionsPage (admin, RequireRole) — P04-S02-T002 §D-T002-ROUTER
 *   /admin/ai/models   → placeholder (P04-S01-T002)
 *   (other admin routes → catch-all → /)
 *   /                  → RootRedirect: authenticated→/chat, unauthenticated→/auth/sign-in
 *   *                  → redirects to / (catch-all; uses RootRedirect logic)
 *
 * P03-S01-T001 adds: real SignInPage form replacing the /auth/sign-in stub.
 * P03-S01-T002 adds: real SignUpPage form at /auth/sign-up.
 * P03-S02-T001 adds: /chat real page; updates / and * redirects for authed users.
 * P03-S01-T005 adds: /auth/2fa — TwoFactorPage (public, MFA code verification step).
 * P04-S01-T001 adds: real AdminDashboardPage + ROUTE_ADMIN_* constants (§D-T001-ROUTER).
 * P04-S02-T003 adds: McpServersPage at /admin/ai/mcp (§D-T003-ROUTER).
 * P04-S02-T004 adds: McpWizardPage at /admin/ai/mcp/new (§D-T004-ROUTER).
 * P04-S02-T001 adds: RagDocumentsPage at /admin/rag/documents (§D-RAGDOC-ROUTER).
 *
 * AuthProvider composition (task pack §I):
 *   INSIDE router.tsx: <AuthProvider> wraps <Routes>.
 *   NOT inside providers.tsx — providers stay route-unaware (P-7 pattern).
 *
 * React Router: package name is "react-router" (v7 — canonical import).
 *   Version: ^7.15.0. Pattern used: <BrowserRouter> + <Routes> (legacy router).
 *   Component-wrapper guard pattern: <RequireAuth><Outlet/></RequireAuth> inside Route element.
 *
 * Journey refs: upstream foundation for J100/J101/J102/J103/J104/J105.
 */

import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router";
import type { ReactNode } from "react";
import ShowcasePage from "../pages/showcase/ShowcasePage";
import SignInPage from "../pages/auth/SignInPage";
import SignUpPage from "../pages/auth/SignUpPage";
import ResetSentPage from "../pages/auth/ResetSentPage";
import TwoFactorPage from "../pages/auth/TwoFactorPage";
import ChatHomePage from "../pages/chat/ChatHomePage";
import HistoryPage from "../pages/chat/HistoryPage";
import AdminDashboardPage from "../pages/admin/AdminDashboardPage";
import AdminAiModelsPage from "../pages/admin/ai/AdminAiModelsPage";
import ModelWizardPage from "../pages/admin/ai/ModelWizardPage";
import ModelTestDrawer from "../pages/admin/ai/ModelTestDrawer";
import McpServersPage from "../pages/admin/mcp/McpServersPage";
import McpWizardPage from "../pages/admin/mcp/McpWizardPage";
import RagDocumentsPage from "../pages/admin/rag/RagDocumentsPage";
import RagCollectionsPage from "../pages/admin/rag/RagCollectionsPage";
import { AuthProvider } from "../features/auth/presentation/AuthProvider";
import { useAuth } from "../features/auth/presentation/AuthProvider";
import { RequireAuth } from "../features/auth/presentation/RequireAuth";
import { RequireRole } from "../features/auth/presentation/RequireRole";

// ---------------------------------------------------------------------------
// Route constants — shared with downstream tasks to avoid magic strings
// ---------------------------------------------------------------------------

/** Route path for the design-system showcase (dev-only, pre-journey). */
export const ROUTE_SHOWCASE = "/showcase";

/** Route path for sign-in page. Form implemented in P03-S01-T001. */
export const ROUTE_AUTH_SIGN_IN = "/auth/sign-in";

/** Route path for sign-up page. Form implemented in P03-S01-T002. */
export const ROUTE_AUTH_SIGN_UP = "/auth/sign-up";

/** Route path for admin area. Dashboard implemented in P04-S01-T001. */
export const ROUTE_ADMIN = "/admin";

/**
 * Route path for password-reset confirmation page. Implemented in P03-S01-T004.
 * §D-T004-ROUTER: public route, outside RequireAuth, mirrors /auth/sign-in pattern.
 * Source: TECHNICAL_GUIDE §6.4 Navigation Contract — explicit public route.
 */
export const ROUTE_AUTH_RESET_SENT = "/auth/reset-sent";

/**
 * Route path for 2FA verification page. Implemented in P03-S01-T005. §D-T005-ROUTER.
 * Public route — no RequireAuth (§6.4 Navigation Contract).
 * Reads mfa_challenge_token from router state (set by SignInPage on MFA branch).
 * §D-T005-DEEP-LINK-GUARD: without router state, bounces to /auth/sign-in.
 * Source: TECHNICAL_GUIDE §6.4 Navigation Contract — explicit public route.
 */
export const ROUTE_AUTH_2FA = "/auth/2fa";

/** Route path for employee chat home. Implemented in P03-S02-T001. */
export const ROUTE_CHAT = "/chat";

/** Route path for employee conversation history. Implemented in P03-S02-T003. §D-T003-ROUTER */
export const ROUTE_HISTORY = "/history";

// ---------------------------------------------------------------------------
// Admin route constants — §D-T001-ROUTER (P04-S01-T001)
// Added for AdminShell nav and downstream P04-S01-T002..T004 slices.
// ---------------------------------------------------------------------------

/** Admin AI models list. Implemented in P04-S01-T002. */
export const ROUTE_ADMIN_AI_MODELS = "/admin/ai/models";

/** Admin AI new model wizard. Implemented in P04-S01-T003. */
export const ROUTE_ADMIN_AI_MODELS_NEW = "/admin/ai/models/new";

/**
 * Admin AI model test playground. Implemented in P04-S01-T004.
 * §D-T004-ROUTER: template string (contains :modelId param — do not use directly).
 * Use routeAdminAiModelsTestFor(modelId) to build actual URL.
 * Route: /admin/ai/models/:modelId/test (RequireRole['people_admin','super_admin']).
 * Deep-links work; auth guard redirects to /auth/sign-in?next=... on unauthenticated access.
 */
export const ROUTE_ADMIN_AI_MODELS_TEST = "/admin/ai/models/:modelId/test";

/**
 * Builds the concrete URL for a specific model's test page.
 * Usage: navigate(routeAdminAiModelsTestFor(model.id))
 *
 * @param modelId - UUID of the model to test.
 * @returns Concrete URL string e.g. "/admin/ai/models/abc-123/test".
 */
export function routeAdminAiModelsTestFor(modelId: string): string {
  return `/admin/ai/models/${modelId}/test`;
}

/** Admin RAG documents. Implemented in P04-S02-T001. */
export const ROUTE_ADMIN_RAG_DOCUMENTS = "/admin/rag/documents";

/** Admin RAG collections. Implemented in P04-S02-T002. */
export const ROUTE_ADMIN_RAG_COLLECTIONS = "/admin/rag/collections";

/**
 * Admin MCP servers page. Implemented in P04-S02-T003.
 * §D-T003-ROUTER: admin-only route inside RequireRole(['people_admin','super_admin']).
 * Source: TECHNICAL_GUIDE §6.1 row + §6.4 Navigation Contract.
 */
export const ROUTE_ADMIN_AI_MCP = "/admin/ai/mcp";

/** Admin new MCP server wizard. Implemented in downstream slice (P04-S02-T004). */
export const ROUTE_ADMIN_AI_MCP_NEW = "/admin/ai/mcp/new";

/** Admin AI agents. Implemented in downstream slice (P04-S02-T005). */
export const ROUTE_ADMIN_AI_AGENTS = "/admin/ai/agents";

/** Admin audit log. Implemented in downstream slice. */
export const ROUTE_ADMIN_AUDIT = "/admin/audit";

/** Admin usage / cost & latency. Implemented in downstream slice. */
export const ROUTE_ADMIN_USAGE = "/admin/usage";

/**
 * Alias for ROUTE_ADMIN_AI_MCP kept for backward compat with P04-S02-T003 tests
 * that reference ROUTE_ADMIN_MCP. Both point to "/admin/ai/mcp".
 * §D-T003-ROUTER.
 */
export const ROUTE_ADMIN_MCP = ROUTE_ADMIN_AI_MCP;

// ---------------------------------------------------------------------------
// RootRedirect — auth-aware redirect for "/" and "*" catch-all
// D-T001-ROUTE: authenticated → /chat; unauthenticated → /auth/sign-in;
//   hydrating → null (RequireAuth handles the loading state for guarded routes).
// D-T001-DEEPLINK-AUTHED-DEFAULT: direct navigation to "/" always lands on /chat.
// ---------------------------------------------------------------------------

/**
 * Root redirect component. Checks auth status and redirects accordingly.
 * status='hydrating' → renders nothing (avoids flash to sign-in).
 * status='authenticated' → /chat (employee home per D-T001-ROUTE).
 * status='unauthenticated' → /auth/sign-in.
 */
function RootRedirect(): ReactNode {
  const { status } = useAuth();

  if (status === "hydrating") {
    return null;
  }

  if (status === "authenticated") {
    return <Navigate to={ROUTE_CHAT} replace />;
  }

  return <Navigate to={ROUTE_AUTH_SIGN_IN} replace />;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Application router — mounts BrowserRouter, AuthProvider, and the route tree.
 *
 * AuthProvider is mounted HERE (inside BrowserRouter, above Routes) so that
 * useNavigate() is available inside the provider when needed by logout handlers.
 *
 * @returns The router-wrapped application shell.
 */
export function AppRouter(): ReactNode {
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    // §D-T004-ROUTER (P04-S01-T004): ROUTE_ADMIN_AI_MODELS_TEST added to verbose-log routes array
    console.info("AppRouter.render.start", {
      phase: "P04",
      slice: "P04-S01-T004",
      routes: [ROUTE_SHOWCASE, ROUTE_AUTH_SIGN_IN, ROUTE_AUTH_SIGN_UP, ROUTE_AUTH_RESET_SENT, ROUTE_AUTH_2FA, ROUTE_CHAT, ROUTE_HISTORY, ROUTE_ADMIN, ROUTE_ADMIN_AI_MCP, ROUTE_ADMIN_RAG_DOCUMENTS, ROUTE_ADMIN_AI_MODELS, ROUTE_ADMIN_AI_MODELS_NEW, ROUTE_ADMIN_AI_MODELS_TEST],
    });
  }

  return (
    <BrowserRouter>
      <AuthProvider>
        <Routes>
          {/* Public routes — no auth required */}
          <Route path={ROUTE_SHOWCASE} element={<ShowcasePage />} />
          {/* P03-S01-T001: real SignInPage replaces stub (§D-T001-ROUTER) */}
          <Route path={ROUTE_AUTH_SIGN_IN} element={<SignInPage />} />
          {/* P03-S01-T002: real SignUpPage (§D-T002-ROUTER) */}
          <Route path={ROUTE_AUTH_SIGN_UP} element={<SignUpPage />} />
          {/* P03-S01-T004: ResetSentPage — public route (§D-T004-ROUTER, §D-T004-PUBLIC-ROUTE) */}
          <Route path={ROUTE_AUTH_RESET_SENT} element={<ResetSentPage />} />
          {/* P03-S01-T005: TwoFactorPage — public route (§D-T005-ROUTER, §D-T005-DEEP-LINK-GUARD) */}
          <Route path={ROUTE_AUTH_2FA} element={<TwoFactorPage />} />

          {/* Protected employee routes */}
          <Route element={<RequireAuth><Outlet /></RequireAuth>}>
            {/* /chat — real ChatHomePage (P03-S02-T001) */}
            <Route path={ROUTE_CHAT} element={<ChatHomePage />} />
            {/* /history — real HistoryPage (P03-S02-T003 §D-T003-ROUTER) */}
            <Route path={ROUTE_HISTORY} element={<HistoryPage />} />
            {/*
             * /chat/:conversationId — placeholder for P03-S02-T002 (ConversationPage).
             * D-T001-OUTAGE-OF-CHAT-T002: navigate succeeds; unknown path bounces to /chat.
             * This route must exist to prevent the catch-all intercepting /chat/:id navigations.
             */}
            <Route
              path={`${ROUTE_CHAT}/:conversationId`}
              element={<Navigate to={ROUTE_CHAT} replace />}
            />
          </Route>

          {/* Admin routes — people_admin or super_admin only */}
          <Route
            element={
              <RequireRole roles={["people_admin", "super_admin"]}>
                <Outlet />
              </RequireRole>
            }
          >
            {/* /admin — real AdminDashboardPage (P04-S01-T001 §D-T001-ROUTER) */}
            <Route path={ROUTE_ADMIN} element={<AdminDashboardPage />} />
            {/* P04-S02-T003: McpServersPage — §D-T003-ROUTER, TECHNICAL_GUIDE §6.1 */}
            <Route path={ROUTE_ADMIN_AI_MCP} element={<McpServersPage />} />
            {/* P04-S02-T004: McpWizardPage — §D-T004-ROUTER, TECHNICAL_GUIDE §6.1 */}
            <Route path={ROUTE_ADMIN_AI_MCP_NEW} element={<McpWizardPage />} />
            {/* P04-S02-T001: RagDocumentsPage — §D-RAGDOC-ROUTER, TECHNICAL_GUIDE §6.1 */}
            <Route path={ROUTE_ADMIN_RAG_DOCUMENTS} element={<RagDocumentsPage />} />
            {/* P04-S01-T002: AdminAiModelsPage — §D-T002-ROUTER, TECHNICAL_GUIDE §6.1 */}
            <Route path={ROUTE_ADMIN_AI_MODELS} element={<AdminAiModelsPage />} />
            {/* P04-S01-T003: ModelWizardPage — §D-T003-ROUTER, TECHNICAL_GUIDE §6.1
                Must be placed BEFORE any catch-all/wildcard admin route.
                WRITE_SET_DRIFT: justified by identical T002 pattern; documented in handoff. */}
            <Route path={ROUTE_ADMIN_AI_MODELS_NEW} element={<ModelWizardPage />} />
            {/* P04-S01-T004: ModelTestDrawer — §D-T004-ROUTER, TECHNICAL_GUIDE §6.1, §6.4.
                Route /admin/ai/models/:modelId/test (RequireRole guard already applied above).
                Deep-links respect auth guard via RequireRole wrapper (redirects to sign-in?next=…).
                WRITE_SET_DRIFT §D-T004-ROUTER: authorized by task pack §6.2 file #11. */}
            <Route path={ROUTE_ADMIN_AI_MODELS_TEST} element={<ModelTestDrawer />} />
            {/* P04-S02-T002: RagCollectionsPage — §D-T002-ROUTER, TECHNICAL_GUIDE §6.1 */}
            <Route path={ROUTE_ADMIN_RAG_COLLECTIONS} element={<RagCollectionsPage />} />
          </Route>

          {/*
           * Root redirect — D-T001-ROUTE + D-T001-DEEPLINK-AUTHED-DEFAULT.
           * authenticated → /chat; unauthenticated → /auth/sign-in; hydrating → null.
           */}
          <Route path="/" element={<RootRedirect />} />

          {/* Catch-all — redirect to root which applies RootRedirect logic. */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AuthProvider>
    </BrowserRouter>
  );
}
