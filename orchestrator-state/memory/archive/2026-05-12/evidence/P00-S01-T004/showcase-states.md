# ShowcasePage — Component × State Matrix

Route: /showcase
Slice: P00-S01-T004
Source: task pack §E applicability matrix

| Component     | State             | Status       | Notes |
|---------------|-------------------|--------------|-------|
| Wordmark      | default           | ✓ rendered   |       |
| TrackedLabel  | default           | ✓ rendered   |       |
| TrackedLabel  | active            | ✓ rendered   |       |
| TrackedLabel  | muted             | ✓ rendered   |       |
| EditorialInput | empty            | ✓ rendered   |       |
| EditorialInput | filled           | ✓ rendered   |       |
| EditorialInput | error_validation | ✓ rendered   | aria-invalid=true, role=alert on msg |
| EditorialInput | disabled         | ✓ rendered   | opacity 0.4, cursor not-allowed |
| EditorialInput | controlled       | ✓ rendered   | live onChange demo |
| SolidCTA      | default           | ✓ rendered   |       |
| SolidCTA      | disabled          | ✓ rendered   | aria-disabled=true |
| SolidCTA      | loading           | ✓ rendered   | aria-busy=true, click to trigger 1.5s |
| SolidCTA      | full width        | ✓ rendered   |       |
| HairlineTable | populated         | ✓ rendered   | 3 demo_fixture rows |
| HairlineTable | empty             | ✓ rendered   | "No models configured." |
| HairlineTable | error_network     | ✓ rendered   | role=alert, Retry CTA |
| HairlineTable | permission_denied | ✓ rendered   | role=alert |
| StatusDot     | active            | ✓ rendered   |       |
| StatusDot     | inactive          | ✓ rendered   |       |
| StatusDot     | syncing           | ✓ rendered   |       |
| StatusDot     | error             | ✓ rendered   |       |
| MobileFrame   | default           | ✓ rendered   | 402px max, inline demo |
| AdminShell    | default           | ✓ rendered   | 5 nav items, hairline separator |
| CitationInline | default          | ✓ rendered   | anchor with href |
| CitationInline | button (no href) | ✓ rendered   | button element |
| CitationInline | external         | ✓ rendered   | rel="noopener noreferrer" |

Page-level states:
- loading: N/A — showcase loads synchronously from static fixtures
- success: N/A — no submission outcome
- permission_denied: N/A — dev-only, not auth-guarded

Screenshots: placeholder paths for /verify-slice human gate
- showcase-mobile.png: orchestrator-state/tasks/evidence/P00-S01-T004/showcase-mobile.png
- showcase-admin.png: orchestrator-state/tasks/evidence/P00-S01-T004/showcase-admin.png
