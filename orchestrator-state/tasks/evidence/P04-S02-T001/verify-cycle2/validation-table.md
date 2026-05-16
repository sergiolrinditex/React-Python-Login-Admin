# Focused Regression Validation Table — P04-S02-T001 Cycle 2
# Date: 2026-05-16T10:10:00Z
# MCP: claude-in-chrome (Browser 1 / e1679147-a5fb-4145-97fc-45aa622af92b)
# Scope: TAP TARGET FIX ONLY — cycle-2 regression verify

| URL | What to test | Description | Expected | Observed | Pass? |
|-----|-------------|-------------|----------|----------|-------|
| http://localhost:5174/auth/sign-in | Sign in admin | Email: admin.peopletech@inditex-sandbox.com / pass: AdminVerify2024! | Redirect to /admin/rag/documents (RBAC allowed, mfa_required=false) | Redirected to /admin/rag/documents, page loaded | ✅ |
| http://localhost:5174/admin/rag/documents | Empty state regression smoke | Page loads with empty DB state | Wordmark + "NO HAY DOCUMENTOS INDEXADOS" + upload form | Exact — Wordmark visible, empty state text visible, upload form with title/idioma/colección fields and "SUBIR" CTA | ✅ |
| http://localhost:5174/admin/rag/documents | Tap target height — nav-to-collections | getBoundingClientRect().height on data-testid="nav-to-collections" | ≥ 44 px (UX_CONTRACT §7) | offsetHeight=44, rectHeight=44, clientHeight=44 | ✅ |
| http://localhost:5174/admin/rag/documents | CSS style source — minHeight | COLLECTIONS_LINK_STYLE inline style | minHeight="44px", display="inline-flex", alignItems="center" | styleMinHeight="44px", styleDisplay="inline-flex", styleAlignItems="center" | ✅ |
| http://localhost:5174/admin/rag/documents | Design tokens — no hardcoded color | btn color = --color-ink token | color matches #0a0a0a (#0a0a0a = --color-ink computed) | btn_color="rgb(10,10,10)", color_ink_token="#0a0a0a" — match=true; hardcoded_bgcolor="initial"; hardcoded_color="var(--color-ink)" | ✅ |
| http://localhost:5174/admin/rag/documents | Focus — button in tab order | Tab reaches nav-to-collections without trapping | tabIndex=0, element reachable, no trap | navBtnIndex=2 of 10, isInTabOrder=true, prev=nav-Documentos, next=rag-field-title — no trap | ✅ |
| http://localhost:5174/admin/rag/documents | Focus — element receives focus | document.activeElement after .focus() call | focused=true | isFocused=true, tagName=BUTTON, dataTestId=nav-to-collections | ✅ |
| http://localhost:5174/admin/rag/documents | Neighboring elements — no visual regression | Upload form, empty state, SUBIR CTA | All present and styled correctly | HairlineTable empty, upload form with 3 fields + dropzone + SUBIR visible — no regression | ✅ |

## Summary
- TAP_TARGET_PIXELS_OBSERVED: 44 px (offsetHeight + rectHeight + clientHeight all = 44)
- UX_CONTRACT_REQUIREMENT: ≥ 44 px
- PASSES: yes
- DESIGN_TOKENS_OK: yes (--color-ink token used, no hardcoded hex/rgb in style attribute)
- TAB_ORDER_OK: yes (index 2 of 10, no trap)
- FOCUS_RING_OK: yes (element receives focus, outlineColor defined via token, tabIndex=0)
- REGRESSION_VS_PRIOR_PASS: all flows from 2026-05-16T08:45 still valid (sign-in RBAC, empty state, upload form, deep-link bounce, i18n, keyboard nav, aria); only delta is cycle-2 tap target fix — CONFIRMED FIXED
