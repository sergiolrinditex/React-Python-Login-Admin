# verify-flows.md — Flow narrative for P03-S01-T003 ForgotPasswordPage
# Verification run: 2026-05-15T10:00Z
# MCP: claude-in-chrome (Browser 1, deviceId: e1679147-a5fb-4145-97fc-45aa622af92b)
# Environment: backend :8000 health 200, frontend :5173 200

## Flow 1: Cold load /auth/forgot-password — editorial mobile layout

**URL**: http://localhost:5173/auth/forgot-password
**Result**: PASS

DOM snapshot via read_page:
- heading "Hilo" (Wordmark)
- generic "Área de empleados" (TrackedLabel subtitle)
- generic "Recuperar acceso" (page heading)
- form[aria-label="Recuperar acceso"] with noValidate
- label "Email corporativo" → input type="email" id="_r_0_" (labelFor matches)
- button[type="submit"] "Enviar enlace" (SolidCTA)
- nav[aria-label="Auth navigation"] > link "Volver a iniciar sesión" href="/auth/sign-in"

A11y baseline (pre-touch):
- aria-invalid: null (not set before interaction — correct)
- labelFor "_r_0_" matches inputId "_r_0_" (association confirmed)
- formAriaLabel: "Recuperar acceso"
- button: not disabled, aria-busy: null

Note: Screenshots timed out (CDP Page.captureScreenshot timeout) but page content
fully readable via read_page. DOM structure confirmed complete and correct.

## Flow 2: Invalid email submit — inline zod error, aria-invalid after touch

**Result**: PASS

Empty submit (button click):
- Alert shows: "El email es obligatorio." (role="alert")
- aria-invalid="true" set on input after touch
- aria-describedby="_r_0_-error" (error element linked)

Invalid format "not-an-email":
- Alert shows: "Introduce un email válido." (role="alert")

No fetch called for either case (client-side validation intercepts).

## Flow 3: Known email → loading state → success → navigation

**URL**: http://localhost:5173/auth/forgot-password
**Email**: employee.verification@inditex-sandbox.com
**Result**: PASS

- Form filled and submitted
- Network: POST http://localhost:5173/api/v1/auth/forgot-password → HTTP 200
  - Relative URL confirmed (ADR-002)
  - NOT absolute http://localhost:8000
- Navigation: → /auth/sign-in (R1 expected: T004 ResetSentPage not yet shipped)
  - Page navigated = success flow triggered correctly
- DB: new row in password_reset_tokens
  - id: 9588efe5-fad1-4094-bcb8-0a667d482c9f (first browser submit)
  - id: eaf12f04-037e-41a0-8d59-984563e81db2 (final browser submit)
  - expires_at: ~1hr from submit
  - used_at: NULL
  - token_hash: 64-char SHA-256 hex
- Audit: auth.password_reset.requested | user_found: true | email_domain: "inditex-sandbox.com"

Note: Loading state (aria-busy) on button was not captured — button state captured
immediately after click returns non-loading state since fetch is near-instantaneous
on localhost. aria-busy is tested at unit level (T04 in ForgotPasswordPage.test.tsx).

## Flow 4: Unknown email → IDENTICAL success outcome (anti-enumeration)

**Email**: nobody.verify.T003@inditex-sandbox.com (valid syntax, not in DB)
**Result**: PASS

- POST http://localhost:5173/api/v1/auth/forgot-password → HTTP 200
- Navigation: → /auth/sign-in (IDENTICAL to known email — anti-enum confirmed)
- DB: 0 rows in password_reset_tokens for this email (anti-enum at DB level)
- Audit: user_found: false | entity_type: empty | no token_id in metadata

Note: Initial test used nobody+verify-T003@example.invalid which got 400 (Pydantic
EmailStr rejects .invalid TLD). Switched to nobody.verify.T003@inditex-sandbox.com
for valid syntax anti-enum test.

## Flow 5: Rate limit (429) → error_validation UI state

**Result**: PASS

- 3 curl calls + 1 browser submit exceeded AUTH_FORGOT_RATE_PER_MINUTE=3
- 429 response received
- Browser UI shows form-level alert: "Demasiados intentos. Espera 12 segundos e inténtalo de nuevo."
- data-error-state="error_validation" confirmed
- button.disabled=true (submit disabled while rate-limited)
- NO permission_denied UI state (anti-enum maintained for 429)
- Console: auth.forgot.submit.rate_limited logged

## Flow 6: Network error simulation → error_network UI state

**Result**: PASS

- fetch overridden with TypeError rejection targeting forgot-password URL
- Browser UI shows form-level alert: "Sin conexión. Comprueba tu red e inténtalo de nuevo."
- data-error-state="error_network" confirmed
- Console: [ERROR] auth.forgot.submit.network logged (ERROR level, not WARNING)

## Flow 7: i18n ES/EN/FR — key verification

**Result**: PASS (with scope note)

Note: Language detector is OFF (i18next-browser-languagedetector deferred to
AccountPage P03-S02-T004 per handoff §D-T003-I18N). The app always renders in ES.
Language switching UI does not exist in this slice. i18n is verified as follows:

EN locale file keys confirmed (15 forgot.* keys):
  ['cta', 'title', 'email', 'emailPlaceholder', 'submit', 'titleHint', 'status',
   'successFlash', 'actions', 'errors']
  errors: ['emailRequired', 'emailFormat', 'rateLimited', 'network', 'serverInternal', 'validation']

FR locale file keys confirmed (15 forgot.* keys):
  Same key set as EN (lockstep confirmed)

No missing-key console warnings observed during any verification session.
Unit test T10 in ForgotPasswordPage.test.tsx verifies i18n.changeLanguage('en').

## Flow 8: Back navigation from /auth/sign-in → /auth/forgot-password

**Result**: PASS

- Navigated to /auth/sign-in
- Clicked "¿Olvidaste tu contraseña?" link → href="/auth/forgot-password"
- /auth/forgot-password renders clean: no leftover error state from previous submissions
- Form is clean with empty email input
- label, input, button all present and correct

## Flow 9: Anonymous deep link to /auth/forgot-password (public route)

**Result**: PASS

- Direct navigation to http://localhost:5173/auth/forgot-password (no auth cookie)
- Page renders immediately (no redirect, no spinner, no permission_denied)
- publicRouteWorks: true
- isLoggedIn: false (anonymous user confirmed)
- Form available without authentication
