/**
 * eslint.config.js — Hilo People frontend ESLint flat configuration.
 *
 * Slice: P04-S01-T008 (dev-tooling: install ESLint flat-config stack and reach zero
 * warnings on the existing 155-file TypeScript/React codebase without touching src/**).
 *
 * Stack: ESLint 10.4.0 + typescript-eslint 8.59.3 + @eslint/js 10.0.1
 *        + eslint-plugin-react-hooks 7.1.1 + eslint-plugin-react-refresh 0.5.2
 *        + globals 17.6.0
 *
 * Design decisions (anchors §D-T008-*):
 * - §D-T008-TOOL-ESLINT        : ESLint (per TECHNICAL_GUIDE §2.1), not oxlint/Biome.
 * - §D-T008-FLAT-CONFIG-JS     : One flat-config file (ESM, package.json "type":"module").
 * - §D-T008-ESLINT-VERSION     : eslint@10.4.0 (latest stable as of 2026-05-17).
 * - §D-T008-MAX-WARNINGS-FLAG  : scripts.lint = "eslint src --max-warnings 0".
 * - §D-T008-NO-TYPE-AWARE-V1   : Uses only syntactic `recommended` preset (no projectService).
 * - §D-T008-IGNORES            : dist/, node_modules/, coverage/ explicitly ignored.
 * - §D-T008-EXISTING-DISABLES-PRESERVED: 5+ pre-existing eslint-disable-next-line comments
 *                                kept alive by including eslint-plugin-react-hooks.
 *
 * Rule overrides (conservative v1 — zero warnings on existing codebase):
 * - @typescript-eslint/no-explicit-any  → off  (43 `any` occurrences in src)
 * - @typescript-eslint/no-unused-vars   → off  (numerous pattern; clean-up is separate slice)
 * - no-console                          → off  (26 console.* uses; logger.ts legitimately uses them)
 * - react-refresh/only-export-components → off (barrel files re-export hooks + components)
 */

import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';

export default tseslint.config(
  // Global ignores — §D-T008-IGNORES
  {
    ignores: ['dist/**', 'node_modules/**', 'coverage/**'],
  },

  // Suppress "unused disable directive" warnings — some pre-existing eslint-disable-next-line
  // comments target exhaustive-deps on lines where the rule does not fire under the current
  // syntactic (non-type-aware) preset. Removing the comments would require touching src/**;
  // turning off the report is the config-conservative alternative. (§D-T008-NO-PRODUCT-MUTATION)
  {
    linterOptions: {
      reportUnusedDisableDirectives: 'off',
    },
  },

  // Base JS recommended rules for all JS/TS/TSX files
  js.configs.recommended,

  // TypeScript syntactic recommended rules — §D-T008-NO-TYPE-AWARE-V1 (no parserOptions.project)
  ...tseslint.configs.recommended,

  // Language options: browser globals for src/, ES2022, ESM
  {
    files: ['**/*.ts', '**/*.tsx'],
    languageOptions: {
      globals: {
        ...globals.browser,
      },
      ecmaVersion: 2022,
      sourceType: 'module',
    },
  },

  // React Hooks plugin — flat config entry (§D-T008-EXISTING-DISABLES-PRESERVED)
  reactHooks.configs.flat['recommended-latest'],

  // React Refresh plugin — rule disabled for barrel-file codebase
  {
    plugins: {
      'react-refresh': reactRefresh,
    },
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },

  // Conservative rule overrides to reach zero warnings on existing codebase
  {
    files: ['**/*.ts', '**/*.tsx'],
    rules: {
      // 43 `any` occurrences in src; enable in a future clean-up slice
      '@typescript-eslint/no-explicit-any': 'off',
      // Unused vars widespread; dedicated clean-up is out of scope for this slice
      '@typescript-eslint/no-unused-vars': 'off',
      // 26 console.* calls; data/logger.ts uses them legitimately under verbose flag
      'no-console': 'off',
      // Redundant boolean cast: pre-existing pattern in ModelWizardPage; clean-up out of scope
      'no-extra-boolean-cast': 'off',
      // React Compiler rules (react-hooks v7 "recommended-latest") — fire on valid existing patterns:
      // - react-hooks/purity: Date.now() inside useRef() initializer (useDashboardUsage.ts)
      // - react-hooks/refs: .current read inside useMemo (useDashboardUsage.ts)
      // - react-hooks/set-state-in-effect: guarded setState in useEffect body (TwoFactorPage.tsx)
      // - react-hooks/incompatible-library: react-hook-form watch() not memoizable (McpWizardPage.tsx)
      // These rules target React Compiler optimizations; defer enabling until Compiler is adopted.
      'react-hooks/purity': 'off',
      'react-hooks/refs': 'off',
      'react-hooks/set-state-in-effect': 'off',
      'react-hooks/incompatible-library': 'off',
    },
  },
);
