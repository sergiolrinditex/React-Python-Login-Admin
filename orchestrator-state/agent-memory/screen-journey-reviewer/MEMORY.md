# screen-journey-reviewer MEMORY

## Review history

### P01-S03-T001 — Auth state provider and protected route guards (2026-05-13)
- OUTCOME: approved
- Kind: setup (frontend guard mechanism, no new screen, Pantalla/Ruta blank)
- Route: n/a — redirect mechanism only; stubs /auth/sign-in, /admin, /chat are non-productive placeholders
- Key patterns learned:
  - Slices with Pantalla/Ruta blank in the registry are guard/infrastructure slices. VISUAL_CONTRACT_CHECK block is correctly absent; UX_CONTRACT §5 applies only to "pantalla productiva".
  - RequireAuth→RequireRole composition safety: RequireRole delegates to RequireAuth when status !== 'authenticated'; role check runs synchronously after authentication is confirmed. No transient leak window.
  - hydrating placeholder minimum: div with role="status", aria-live="polite", aria-label="Loading authentication state". No children, no redirect. Satisfies race-free render per UX_CONTRACT §3.
  - CORS blockage (F3-F5) was already a promoted FU (P01-S03-T002). Do not re-flag in Screen/Journey review — just note in coverage_notes.
  - When verify-slice shows CORS blocks positive auth flows but redirect flows (F1/F2) are verified and token-storage invariant (F6) + open-redirect (F7) pass, the redirect mechanism contract is satisfied for this scope. F3-F5 belong to CORS FU task.
  - page-level UI states (loading, empty, error_network, etc.) belong to page slices (P03). Guard slices own only hydrating state. UX_CONTRACT §3 screen inventory has no row for this slice's route.
  - not_applicable: no — this task has frontend/UX scope (route guards, hydration) and VISUAL_CONTRACT_CHECK was referenced in verify-slice context; reviewer was correctly invoked.

### P00-S01-T005 — i18n resources ES/EN/FR (2026-05-11)
- OUTCOME: approved
- Kind: setup/infrastructure (frontend, VISUAL_CONTRACT_CHECK present)
- Route: /showcase section 10 (I18nDemoSection)
- Key patterns learned:
  - Infrastructure slices (i18n, tokens, scaffold) correctly use `required_states_covered: n/a` in VISUAL_CONTRACT_CHECK — UX_CONTRACT §5 permits this.
  - `real_data_or_backend_used: n/a` is valid for static build-time slices with no backend/DB dependency.
  - WRITE_SET_DRIFT on /showcase additions (I18nDemoSection type) is an established precedent for P00 slices that need a visible verify_mode=human surface.
  - journey_refs on infrastructure slices mean "this slice is a prerequisite for those journeys" — it does NOT mean the slice closes the journey. Always verify with list_journey_closures.py confirmation.
  - Hilo visual contract: borderRadius=0, color-ink/paper tokens, hairline borders, tracked-label uppercase heading, solid-ink active CTA, no color badges. All confirmed in I18nDemoSection.tsx code and screenshots.
  - i18n literal keys to remember: ES auth.signIn.title="Entrar", EN="Sign in", FR="Connexion"; ES errors.AUTH_INVALID_CREDENTIALS="Email o contraseña incorrectos", EN="Incorrect email or password", FR="Email ou mot de passe incorrect"; common.productName="Hilo" (brand constant, all 3 langs).
  - errors namespace must have exactly 13 keys: 11 §6.4 codes + UNKNOWN + NETWORK.
