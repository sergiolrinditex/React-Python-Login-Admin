# Acceptance Checklist — P03-S02-T003

## Pack acceptance bullets vs evidence

1. **/history route reachable only inside RequireAuth; deep link bounces to /auth/sign-in?next=/history**
   - Evidence: router.tsx audited — ROUTE_HISTORY wired inside RequireAuth block. HistoryPage.test.tsx P01–P09 use MemoryRouter with auth context. Pass.

2. **listConversations calls GET /api/v1/chat/conversations via authFetch (ADR-002 compliant), returns Result<...>, never throws**
   - Evidence: chatRepository.ts lines 161-245 audited. authFetch called with same-origin relative URL. Returns Result<ListConversationsResponse, ChatError>. Test R01–R05 pass (193/193). curl-list-conversations.txt → 200 + envelope shape confirmed.

3. **All 5 UX states render correctly**
   - loading (aria-busy): HistoryPage.test.tsx P01 — aria-busy="true" skeleton rendered. PASS.
   - empty (Wordmark + CTA to /chat): P02 — empty state with CTA to /chat. PASS.
   - error_network (retry CTA + refetch): P03 — retry triggers refetch. PASS.
   - permission_denied (ForbiddenView for 403): P04 — ForbiddenView rendered. PASS.
   - success (grouped list with hairline separators): P05 — grouped rows rendered. PASS.
   - Evidence: vitest-verbose-true.log (193/193 pass, 16 test files).

4. **Relative-date grouping: pure function, deterministic, 5 buckets**
   - Evidence: historyGrouping.test.ts G01–G10 (10 tests), all pass. `now` injected for determinism. Today/Yesterday/ThisWeek/ThisMonth/Earlier buckets covered.

5. **Tokens only: no hardcoded literals outside tokens.css**
   - Evidence: design-tokens.log → "OK Design tokens". DT_EXIT:0.

6. **i18n: ES/EN/FR history namespace fully populated**
   - Evidence: public/locales/es/history.json, en/history.json, fr/history.json created. i18n.test.ts updated to 9 namespaces (16 tests pass). P08 smoke test passes.

7. **Accessibility: list aria-label, row aria-label, keyboard nav Enter, tap target ≥ 44×44px**
   - Evidence: HistoryPage.test.tsx P07 (Enter-key activation). Aria-labels audited in HistoryPage.tsx. PASS.

8. **Logging: BEFORE+AFTER in repo+hook+page, PII-clean (count+has_more only, no IDs/titles)**
   - Evidence: PII audit confirms no titles, UUIDs, emails in log payloads. Verbose=false shows only warn/error (0 verbose lines in vitest-verbose-false.log). Verbose=true shows full flow. PASS.

9. **Test suite green: tsc clean, vitest 193/193, design-tokens OK, build green**
   - tsc.log: exit 0
   - vitest-verbose-true.log: 193/193 PASS (16 test files)
   - vitest-verbose-false.log: 193/193 PASS (16 test files)
   - build.log: 219 modules, exit 0
   - design-tokens.log: OK, exit 0

10. **VISUAL_CONTRACT_CHECK block present in handoff**
    - Evidence: handoff contains VISUAL_CONTRACT_CHECK section with route, tokens_used, base_components_used, required_states_covered, real_data_or_backend_used, i18n_checked, evidence_path, deviations=none. PASS.

## Backend probe shape check
- Endpoint: GET /api/v1/chat/conversations?limit=10
- Status: 200
- Envelope: {data:[...], meta:{request_id, pagination:{next_cursor, has_more}}, errors:[]}
- data: 3 ConversationDTO items (id, user_id, title, language, created_at, updated_at) — ≥2 required
- meta.pagination.next_cursor: null, has_more: false
- errors: []
- Evidence: curl-list-conversations.txt

## Verification Data Contract used
- Row: J102 history-language — empleado con conversación previa
- User: employee.verification@inditex-sandbox.com (employee_primary.json)
- Data observed: 3 conversations already persisted (≥ 2 required by contract)
- Auth: MFA TOTP from data/verification/auth/mfa_primary.json (JBSWY3DPEHPK3PXP)
