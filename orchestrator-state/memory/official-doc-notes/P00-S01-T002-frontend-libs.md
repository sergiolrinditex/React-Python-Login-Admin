# Official Doc Note — T002 Frontend Library Versions

**Date**: 2026-05-11
**Task**: P00-S01-T002
**Written by**: developer (reconciliation during npm install)

## Discrepancy: react-i18next + i18next + TypeScript 6 peer deps

The task pack § 6 stated react-i18next@^15.5.2 and i18next@^25.2.1. npm install
fails with ERESOLVE because react-i18next@15.7.4 declares:
  peerOptional typescript@"^5"
— which conflicts with our typescript@6.0.3 in npm 11 strict mode.

### npm registry reality (2026-05-11)

| Package | Task pack said | npm latest |
|---|---|---|
| react-i18next | ^15.5.2 | 17.0.7 (major jump) |
| i18next | ^25.2.1 | 26.0.10 (major jump) |
| i18next-browser-languagedetector | ^8.1.0 | 8.2.1 |

react-i18next v17.0.7 peer deps:
  - i18next: >= 26.0.10
  - react: >= 16.8.0
  - typescript: ^5 || ^6 (optional)

react-i18next v15.x (15.7.4):
  - peerOptional typescript: ^5 — conflicts with TS 6 in npm 11 strict mode

### Resolution

Use react-i18next@^17.0.7 + i18next@^26.0.10 which:
  1. Supports TypeScript ^5 || ^6 natively
  2. Peer-compatible with React 19
  3. Eliminates the ERESOLVE

This is a legitimate API-compatible upgrade for the providers shell (empty
resources, no namespace code changes). T005 i18n resources slice is unaffected
since it works with any i18next >= 23.x API.

RESOLVED: 2026-05-11 — developer updated frontend/package.json to
react-i18next@^17.0.7 and i18next@^26.0.10 to resolve TypeScript 6 peer dep
conflict. i18next-browser-languagedetector updated to ^8.2.1 to peer-match.
<!-- RESOLVED: 2026-05-11 — versions updated to react-i18next@^17.0.7, i18next@^26.0.10, languagedetector@^8.2.1 -->
