# Debugger fix — cycle 2 of max 3

**TASK_ID**: P03-S02-T003
**TIMESTAMP**: 2026-05-15T08:38:00Z
**LEAD**: screen-journey-reviewer (Screen/Journey review section in handoff, OUTCOME=changes_requested)

## Defect (in-scope)

`EmptyState` in `frontend/src/pages/chat/_HistoryPage.error-views.tsx` rendered only the `TrackedLabel`
title and the `SolidCTA`, but the task pack §4 declares:

> Wordmark + tracked label headline (i18n key `history.empty.title`) + body explaining
> "starting a new chat" (i18n key `history.empty.body`) + `SolidCTA` linking to `/chat`
> (i18n key `history.empty.cta`).

UX_CONTRACT.md §4: "Empty state invites starting a new chat."

The i18n key `history.empty.body` was already populated in:
- `frontend/src/i18n/index.ts` (inline ES/EN/FR resources)
- `frontend/public/locales/{es,en,fr}/history.json`

…but never consumed in render — pure code omission, not an i18n gap.

## Fix

Smallest safe diff inside the pre-authorized §D-T003-PAGE-SPLIT-ERRORVIEWS write set.

1. Added `EMPTY_BODY_STYLE: CSSProperties` constant next to existing `ERROR_TEXT_STYLE` —
   tokens only (`var(--font-sans)`, `var(--color-ink)`), `0.875rem`, `opacity 0.85`,
   `textAlign: center` (the empty container already centers its children),
   `margin: 0` (paragraph reset since the container uses `gap: 1.5rem`).

2. Added a single `<p style={EMPTY_BODY_STYLE} data-testid="history-empty-body">{t("history:empty.body")}</p>`
   between the `TrackedLabel` (title) and the `SolidCTA` (CTA).

3. Extended the existing P02 unit test in
   `frontend/src/pages/chat/__tests__/HistoryPage.test.tsx` to assert
   `getByTestId("history-empty-body")` is present and renders the ES productive copy
   ("Empieza una nueva conversación para ver el historial aquí.").

No new components. No new i18n keys. No scope expansion. No write set drift —
file is in pre-authorized anchor §D-T003-PAGE-SPLIT-ERRORVIEWS (per pack §5 and validator review).

## Quality gates re-run

| Gate | Command | Result |
|---|---|---|
| TS check | `node_modules/.bin/tsc --noEmit` | exit 0 |
| Vitest verbose=true | `ENABLE_VERBOSE_LOGGING=true npx vitest run` | 193/193 pass (16 files), 2.94s |
| Vitest verbose=false | `ENABLE_VERBOSE_LOGGING=false npx vitest run` | 193/193 pass (16 files), 2.64s |
| Build | `npm run build` | 219 modules, exit 0 |
| Design tokens | `bash .claude/enforcers/design_tokens_v1.sh` | OK |

Test count delta: 193 → 193 (extended P02 in place, did not add a new case).

## Files changed

- `frontend/src/pages/chat/_HistoryPage.error-views.tsx`
  - +9 lines (EMPTY_BODY_STYLE constant + body paragraph element)
  - file size: 195 lines (was 186) — well under 300-line cap
- `frontend/src/pages/chat/__tests__/HistoryPage.test.tsx`
  - +6 lines (extended existing P02 case)

## SCREEN_REVIEW_LEAD_CONFIRMED

Yes — root cause matches verbatim the screen-journey-reviewer FINDINGS:
"`EmptyState` in `frontend/src/pages/chat/_HistoryPage.error-views.tsx` omits rendering
the body paragraph". Fix exactly the recommended one-line addition (with corresponding
test extension and token-only style constant).
