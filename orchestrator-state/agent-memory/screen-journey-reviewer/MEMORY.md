# screen-journey-reviewer MEMORY

## Review history

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
