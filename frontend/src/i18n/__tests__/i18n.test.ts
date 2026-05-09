/**
 * i18n bundle structure tests for Hilo People.
 *
 * What: Verifies that all 24 locale bundles (3 locales × 8 namespaces) parse
 * correctly, contain the productive keys from instrucciones.md §6 verbatim,
 * maintain key-set parity across locales (drift detector), and that the
 * configured i18next instance resolves translations correctly including fallback.
 *
 * Phase/Slice: P00 / P00-S01-T005 — i18n resources ES/EN/FR
 *
 * Why real imports (not fs.readFileSync):
 *   Vite/Vitest handle JSON imports natively. Real static imports make the test
 *   sensitive to module resolution — if a bundle is missing or malformed, the
 *   import itself fails at parse time, not at test assertion time. This is the
 *   correct behavior for a gate that protects downstream P03 slices.
 *
 * Source-of-truth refs:
 *   - instrucciones.md §6: authoritative key inventory and productive copy
 *   - task pack P00-S01-T005.md §Decisions D5: drift detector design
 */

import { describe, it, expect } from 'vitest';

// ── Locale bundle imports (24 files) ─────────────────────────────────────────

import esCommon from '../../../public/locales/es/common.json';
import esAuth from '../../../public/locales/es/auth.json';
import esChat from '../../../public/locales/es/chat.json';
import esAccount from '../../../public/locales/es/account.json';
import esAdminAi from '../../../public/locales/es/admin-ai.json';
import esRag from '../../../public/locales/es/rag.json';
import esMcp from '../../../public/locales/es/mcp.json';
import esErrors from '../../../public/locales/es/errors.json';

import enCommon from '../../../public/locales/en/common.json';
import enAuth from '../../../public/locales/en/auth.json';
import enChat from '../../../public/locales/en/chat.json';
import enAccount from '../../../public/locales/en/account.json';
import enAdminAi from '../../../public/locales/en/admin-ai.json';
import enRag from '../../../public/locales/en/rag.json';
import enMcp from '../../../public/locales/en/mcp.json';
import enErrors from '../../../public/locales/en/errors.json';

import frCommon from '../../../public/locales/fr/common.json';
import frAuth from '../../../public/locales/fr/auth.json';
import frChat from '../../../public/locales/fr/chat.json';
import frAccount from '../../../public/locales/fr/account.json';
import frAdminAi from '../../../public/locales/fr/admin-ai.json';
import frRag from '../../../public/locales/fr/rag.json';
import frMcp from '../../../public/locales/fr/mcp.json';
import frErrors from '../../../public/locales/fr/errors.json';

import i18n from '../index';
import { NAMESPACES, SUPPORTED_LANGUAGES, isSupportedLanguage } from '../languages';

// ── Helper: recursive key flattener ─────────────────────────────────────────

/**
 * Recursively flattens a nested object to a list of dotted key paths.
 *
 * Used by the drift detector to compare key sets across locales.
 * Example: { a: { b: 1 } } → ['a.b']
 *
 * @param obj - Any JSON-compatible value.
 * @param prefix - Internal accumulator; callers pass '' or omit.
 * @returns Array of dotted key paths for every leaf value.
 */
function flatKeys(obj: unknown, prefix = ''): string[] {
  if (typeof obj !== 'object' || obj === null) {
    return prefix ? [prefix] : [];
  }
  return Object.entries(obj as Record<string, unknown>).flatMap(([k, v]) =>
    flatKeys(v, prefix ? `${prefix}.${k}` : k),
  );
}

// ── Test suite ────────────────────────────────────────────────────────────────

describe('i18n bundle structure', () => {
  // ── Assertion 1: All 24 bundles parse and are non-empty objects ─────────────

  it('all 24 locale bundles import as non-empty objects', () => {
    const bundles = [
      esCommon, esAuth, esChat, esAccount, esAdminAi, esRag, esMcp, esErrors,
      enCommon, enAuth, enChat, enAccount, enAdminAi, enRag, enMcp, enErrors,
      frCommon, frAuth, frChat, frAccount, frAdminAi, frRag, frMcp, frErrors,
    ];
    for (const bundle of bundles) {
      expect(typeof bundle).toBe('object');
      expect(bundle).not.toBeNull();
      expect(Object.keys(bundle).length).toBeGreaterThan(0);
    }
  });

  // ── Assertion 2: Drift detector (flat key sets equal across all 3 locales) ──

  it('key sets are identical across es/en/fr for all 8 namespaces', () => {
    const pairs: [string, unknown, unknown, unknown][] = [
      ['common',   esCommon,   enCommon,   frCommon],
      ['auth',     esAuth,     enAuth,     frAuth],
      ['chat',     esChat,     enChat,     frChat],
      ['account',  esAccount,  enAccount,  frAccount],
      ['admin-ai', esAdminAi,  enAdminAi,  frAdminAi],
      ['rag',      esRag,      enRag,      frRag],
      ['mcp',      esMcp,      enMcp,      frMcp],
      ['errors',   esErrors,   enErrors,   frErrors],
    ];

    for (const [ns, es, en, fr] of pairs) {
      const esKeys = new Set(flatKeys(es));
      const enKeys = new Set(flatKeys(en));
      const frKeys = new Set(flatKeys(fr));

      expect(esKeys, `namespace '${ns}': es ≠ en key sets`).toEqual(enKeys);
      expect(esKeys, `namespace '${ns}': es ≠ fr key sets`).toEqual(frKeys);
    }
  });

  // ── Assertion 3: Productive copy present verbatim from instrucciones.md §6 ──

  it('contains productive keys from instrucciones.md §6 verbatim in all 3 locales', () => {
    // common
    expect(esCommon.productName).toBe('Hilo');
    expect(enCommon.productName).toBe('Hilo');
    expect(frCommon.productName).toBe('Hilo');

    // auth — sign in
    expect(esAuth.signIn.title).toBe('Entrar');
    expect(enAuth.signIn.title).toBe('Sign in');
    expect(frAuth.signIn.title).toBe('Connexion');

    expect(esAuth.signIn.email).toBe('Email corporativo');
    expect(enAuth.signIn.email).toBe('Corporate email');
    expect(frAuth.signIn.email).toBe('Email professionnel');

    expect(esAuth.signIn.password).toBe('Contraseña');
    expect(enAuth.signIn.password).toBe('Password');
    expect(frAuth.signIn.password).toBe('Mot de passe');

    // auth — forgot
    expect(esAuth.forgot.title).toBe('Recuperar acceso');
    expect(enAuth.forgot.title).toBe('Reset access');
    expect(frAuth.forgot.title).toBe("Réinitialiser l'accès");

    // auth — two-factor
    expect(esAuth.twoFactor.title).toBe('Verificación en dos pasos');
    expect(enAuth.twoFactor.title).toBe('Two-step verification');
    expect(frAuth.twoFactor.title).toBe('Vérification en deux étapes');

    // chat — empty state
    expect(esChat.empty.title).toBe('¿En qué puedo ayudarte?');
    expect(enChat.empty.title).toBe('How can I help?');
    expect(frChat.empty.title).toBe('Comment puis-je vous aider ?');

    expect(esChat.empty.promptVacation).toBe('¿Cuántos días de vacaciones me quedan?');
    expect(enChat.empty.promptVacation).toBe('How many vacation days do I have left?');
    expect(frChat.empty.promptVacation).toBe('Combien de jours de congé me reste-t-il ?');

    expect(esChat.empty.promptMobility).toBe('Política de movilidad interna');
    expect(enChat.empty.promptMobility).toBe('Internal mobility policy');
    expect(frChat.empty.promptMobility).toBe('Politique de mobilité interne');

    // chat — citation
    expect(esChat.citation.label).toBe('Fuente');
    expect(enChat.citation.label).toBe('Source');
    expect(frChat.citation.label).toBe('Source');

    // account
    expect(esAccount.language).toBe('Idioma');
    expect(enAccount.language).toBe('Language');
    expect(frAccount.language).toBe('Langue');

    // admin-ai
    expect(esAdminAi.models.title).toBe('Modelos LiteLLM');
    expect(enAdminAi.models.title).toBe('LiteLLM models');
    expect(frAdminAi.models.title).toBe('Modèles LiteLLM');

    expect(esAdminAi.mcp.title).toBe('Integraciones MCP');
    expect(enAdminAi.mcp.title).toBe('MCP integrations');
    expect(frAdminAi.mcp.title).toBe('Intégrations MCP');

    // rag
    expect(esRag.documents.title).toBe('Documentos de People');
    expect(enRag.documents.title).toBe('People documents');
    expect(frRag.documents.title).toBe('Documents People');

    // errors
    expect(esErrors.AUTH_INVALID_CREDENTIALS).toBe('Email o contraseña incorrectos');
    expect(enErrors.AUTH_INVALID_CREDENTIALS).toBe('Incorrect email or password');
    expect(frErrors.AUTH_INVALID_CREDENTIALS).toBe('Email ou mot de passe incorrect');

    // mcp — D1 minimal seed key (no §6 canonical, but bundle must not be empty)
    expect(esMcp.servers.title).toBe('Servidores MCP');
    expect(enMcp.servers.title).toBe('MCP servers');
    expect(frMcp.servers.title).toBe('Serveurs MCP');
  });

  // ── Assertion 4: i18next functional — t() resolves productive copy ───────────
  //
  // i18next namespace separator is ':'; dot '.' is a key nesting separator.
  // Correct form: t('common:productName') or t('productName') when defaultNS='common'.
  // Incorrect:    t('common.productName') — interprets 'common.productName' as a
  //               nested key { common: { productName: ... } } in the defaultNS.

  it('i18next resolves common:productName in all 3 locales', () => {
    expect(i18n.t('common:productName', { lng: 'es' })).toBe('Hilo');
    expect(i18n.t('common:productName', { lng: 'en' })).toBe('Hilo');
    expect(i18n.t('common:productName', { lng: 'fr' })).toBe('Hilo');
  });

  it('i18next resolves auth.signIn.title in all 3 locales', () => {
    expect(i18n.t('auth:signIn.title', { lng: 'es' })).toBe('Entrar');
    expect(i18n.t('auth:signIn.title', { lng: 'en' })).toBe('Sign in');
    expect(i18n.t('auth:signIn.title', { lng: 'fr' })).toBe('Connexion');
  });

  it('i18next falls back to es for unsupported locale', () => {
    // fallbackLng: 'es' means 'pt' resolves to the es bundle
    expect(i18n.t('common:productName', { lng: 'pt' })).toBe('Hilo');
  });

  // ── Assertion 5: all 8 namespaces registered on the i18next instance ────────

  it('i18next instance has all 8 namespaces registered with resource bundles', () => {
    for (const ns of NAMESPACES) {
      for (const lng of SUPPORTED_LANGUAGES) {
        expect(
          i18n.hasResourceBundle(lng, ns),
          `Missing resource bundle: locale='${lng}' namespace='${ns}'`,
        ).toBe(true);
      }
    }
  });

  // ── Assertion 6: languages.ts exports shape ───────────────────────────────

  it('SUPPORTED_LANGUAGES contains exactly es, en, fr', () => {
    expect(SUPPORTED_LANGUAGES).toEqual(['es', 'en', 'fr']);
  });

  it('NAMESPACES contains all 8 expected namespaces', () => {
    expect(NAMESPACES).toEqual([
      'common', 'auth', 'chat', 'account', 'admin-ai', 'rag', 'mcp', 'errors',
    ]);
  });

  it('isSupportedLanguage type-guard returns correct values', () => {
    expect(isSupportedLanguage('es')).toBe(true);
    expect(isSupportedLanguage('en')).toBe(true);
    expect(isSupportedLanguage('fr')).toBe(true);
    expect(isSupportedLanguage('pt')).toBe(false);
    expect(isSupportedLanguage('de')).toBe(false);
    expect(isSupportedLanguage('')).toBe(false);
  });
});
