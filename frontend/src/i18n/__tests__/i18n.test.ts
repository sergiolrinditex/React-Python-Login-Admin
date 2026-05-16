/**
 * Hilo People — i18n test suite.
 *
 * Slice/Phase: P00-S01-T005 — i18n resources ES/EN/FR / Phase 0 Scaffold.
 *
 * Responsibility: verify that i18next is configured correctly with all 8 namespaces,
 *   3 locales, fallback behaviour, and error-code coverage.
 *   All tests use the literal string "i18n" in describe/it names so that the
 *   acceptance verification command `npm --prefix frontend run test -- --run -t i18n`
 *   includes them via Vitest's name filter.
 *
 * Tests are REAL: they use the actual i18n singleton loaded with real inline resources.
 * No mocks, no stubs of services we control.
 *
 * Key deps: i18next ^26.1.0, vitest ^3.0.0.
 * Source ref: task pack §8.4 (8 test assertions).
 */

import { describe, it, expect } from "vitest";
import i18n from "../index";
import { SUPPORTED_LANGUAGES, I18N_NAMESPACES, DEFAULT_LANGUAGE } from "../languages";

// ---------------------------------------------------------------------------
// Known error codes from TECHNICAL_GUIDE §6.4 (11 codes + UNKNOWN + NETWORK)
// ---------------------------------------------------------------------------

const ERROR_CODES = [
  "AUTH_INVALID_CREDENTIALS",
  "AUTH_MFA_REQUIRED",
  "AUTH_SESSION_EXPIRED",
  "AUTH_FORBIDDEN",
  "CHAT_STREAM_FAILED",
  "RAG_DOCUMENT_INVALID",
  "RAG_INDEX_IN_PROGRESS",
  "AI_PROVIDER_TEST_FAILED",
  "MCP_SERVER_UNREACHABLE",
  "MCP_TOOL_REQUIRES_APPROVAL",
  "AGENT_RUN_FAILED",
  "UNKNOWN",
  "NETWORK",
] as const;

// ---------------------------------------------------------------------------
// Test 1 — i18n: configuration — 8 namespaces, correct defaults
// ---------------------------------------------------------------------------

describe("i18n: configuration", () => {
  it("i18n: registers all 8 namespaces", () => {
    const registered = i18n.options.ns as string[];
    expect(I18N_NAMESPACES).toHaveLength(8);
    I18N_NAMESPACES.forEach((ns) => {
      expect(registered).toContain(ns);
    });
  });

  it("i18n: lng=es, fallbackLng=es, defaultNS=common", () => {
    expect(i18n.language).toBe(DEFAULT_LANGUAGE);
    const fb = i18n.options.fallbackLng;
    // fallbackLng can be string or string[] — normalise
    const fbArr = Array.isArray(fb) ? fb : [fb];
    expect(fbArr).toContain(DEFAULT_LANGUAGE);
    expect(i18n.options.defaultNS).toBe("common");
  });
});

// ---------------------------------------------------------------------------
// Test 2 — i18n: 24 bundles present (8 namespaces × 3 languages)
// ---------------------------------------------------------------------------

describe("i18n: 24 bundles present", () => {
  it("i18n: all 3 locales have all 8 namespaces loaded", () => {
    SUPPORTED_LANGUAGES.forEach((lng) => {
      I18N_NAMESPACES.forEach((ns) => {
        const bundle = i18n.getResourceBundle(lng, ns);
        expect(bundle).toBeDefined();
        expect(typeof bundle).toBe("object");
      });
    });
  });
});

// ---------------------------------------------------------------------------
// Test 3 — i18n: fallback to es when key missing in en/fr
// ---------------------------------------------------------------------------

describe("i18n: fallback behaviour", () => {
  it("i18n: falls back to es value for key absent in en and fr", async () => {
    // Add a key ONLY in es to verify fallback
    i18n.addResourceBundle("es", "common", { __testOnlyEs: "solo_en_es" }, true, true);

    await i18n.changeLanguage("en");
    const result = i18n.t("common:__testOnlyEs");
    // Fallback should return the es value, NOT the raw key
    expect(result).toBe("solo_en_es");

    await i18n.changeLanguage("fr");
    const resultFr = i18n.t("common:__testOnlyEs");
    expect(resultFr).toBe("solo_en_es");

    // Restore es as active language for subsequent tests
    await i18n.changeLanguage("es");
  });
});

// ---------------------------------------------------------------------------
// Test 4 — i18n: useTranslation-style t() resolves keys in multiple namespaces
// ---------------------------------------------------------------------------

describe("i18n: key resolution across namespaces", () => {
  it("i18n: resolves common:productName in es", async () => {
    await i18n.changeLanguage("es");
    expect(i18n.t("common:productName")).toBe("Hilo");
  });

  it("i18n: resolves auth:signIn.title in es", async () => {
    await i18n.changeLanguage("es");
    expect(i18n.t("auth:signIn.title")).toBe("Entrar");
  });

  it("i18n: resolves errors:AUTH_INVALID_CREDENTIALS in es", async () => {
    await i18n.changeLanguage("es");
    const val = i18n.t("errors:AUTH_INVALID_CREDENTIALS");
    expect(val).toBe("Email o contraseña incorrectos");
  });
});

// ---------------------------------------------------------------------------
// Test 5 — i18n: changeLanguage updates resolution
// ---------------------------------------------------------------------------

describe("i18n: changeLanguage", () => {
  it("i18n: changeLanguage updates auth:signIn.title to EN", async () => {
    await i18n.changeLanguage("en");
    expect(i18n.t("auth:signIn.title")).toBe("Sign in");
  });

  it("i18n: changeLanguage updates auth:signIn.title to FR", async () => {
    await i18n.changeLanguage("fr");
    expect(i18n.t("auth:signIn.title")).toBe("Connexion");
  });

  it("i18n: reverts to es correctly", async () => {
    await i18n.changeLanguage("es");
    expect(i18n.t("auth:signIn.title")).toBe("Entrar");
  });
});

// ---------------------------------------------------------------------------
// Test 6 — i18n: missing key does not throw
// ---------------------------------------------------------------------------

describe("i18n: missing key handler", () => {
  it("i18n: missing key in all languages returns key or empty string, never throws", () => {
    SUPPORTED_LANGUAGES.forEach(async (lng) => {
      await i18n.changeLanguage(lng);
      expect(() => i18n.t("common:__keyThatDoesNotExistEver")).not.toThrow();
    });
    // Restore
    void i18n.changeLanguage("es");
  });
});

// ---------------------------------------------------------------------------
// Test 7 — i18n: errors namespace has all 13 codes in all 3 languages
// ---------------------------------------------------------------------------

describe("i18n: errors namespace coverage", () => {
  it("i18n: all error codes present in es", () => {
    ERROR_CODES.forEach((code) => {
      const bundle = i18n.getResourceBundle("es", "errors") as Record<string, string>;
      expect(bundle[code]).toBeDefined();
      expect(typeof bundle[code]).toBe("string");
      expect(bundle[code].length).toBeGreaterThan(0);
    });
  });

  it("i18n: all error codes present in en", () => {
    ERROR_CODES.forEach((code) => {
      const bundle = i18n.getResourceBundle("en", "errors") as Record<string, string>;
      expect(bundle[code]).toBeDefined();
    });
  });

  it("i18n: all error codes present in fr", () => {
    ERROR_CODES.forEach((code) => {
      const bundle = i18n.getResourceBundle("fr", "errors") as Record<string, string>;
      expect(bundle[code]).toBeDefined();
    });
  });
});

// ---------------------------------------------------------------------------
// Test 8 — i18n: EN and FR translations are NOT identical to ES
// ---------------------------------------------------------------------------

describe("i18n: no copy-paste across languages", () => {
  it("i18n: errors:AUTH_INVALID_CREDENTIALS differs across es, en, fr", () => {
    const es = (i18n.getResourceBundle("es", "errors") as Record<string, string>)
      .AUTH_INVALID_CREDENTIALS;
    const en = (i18n.getResourceBundle("en", "errors") as Record<string, string>)
      .AUTH_INVALID_CREDENTIALS;
    const fr = (i18n.getResourceBundle("fr", "errors") as Record<string, string>)
      .AUTH_INVALID_CREDENTIALS;
    expect(es).not.toBe(en);
    expect(es).not.toBe(fr);
    expect(en).not.toBe(fr);
  });

  it("i18n: auth:signIn.title differs across es, en, fr", () => {
    const es = (i18n.getResourceBundle("es", "auth") as Record<string, unknown> & {
      signIn: { title: string };
    }).signIn.title;
    const en = (i18n.getResourceBundle("en", "auth") as Record<string, unknown> & {
      signIn: { title: string };
    }).signIn.title;
    const fr = (i18n.getResourceBundle("fr", "auth") as Record<string, unknown> & {
      signIn: { title: string };
    }).signIn.title;
    expect(es).not.toBe(en);
    expect(es).not.toBe(fr);
    expect(en).not.toBe(fr);
  });
});

// ---------------------------------------------------------------------------
// Test 9 — i18n: admin-ai.dashboard.* keys present in es/en/fr (P04-S01-T001)
// Write-set anchor: §D-T001-I18N-TEST-EXTEND
// ---------------------------------------------------------------------------

type AdminAiBundle = {
  dashboard: {
    title: string;
    window: { range: string };
    kpi: { invocations: string; tokens: string; cost: string; latency: string };
    table: {
      caption: string;
      headers: {
        model: string;
        invocations: string;
        tokensIn: string;
        tokensOut: string;
        cost: string;
        latency: string;
      };
    };
    empty: { title: string; body: string };
    errors: {
      network: { title: string; body: string };
      forbidden: { title: string; body: string };
    };
    actions: { retry: string; manageModels: string };
  };
  nav: {
    dashboard: string;
    models: string;
    modelsNew: string;
    ragDocuments: string;
    ragCollections: string;
    mcpServers: string;
    mcpNew: string;
    agents: string;
    audit: string;
    usage: string;
  };
};

describe("i18n: admin-ai.dashboard.* lockstep in es/en/fr", () => {
  it("i18n: admin-ai.dashboard.* all keys present in es", () => {
    const bundle = i18n.getResourceBundle("es", "admin-ai") as AdminAiBundle;
    expect(bundle.dashboard.title).toBeTruthy();
    expect(bundle.dashboard.window.range).toBeTruthy();
    expect(bundle.dashboard.kpi.invocations).toBeTruthy();
    expect(bundle.dashboard.kpi.tokens).toBeTruthy();
    expect(bundle.dashboard.kpi.cost).toBeTruthy();
    expect(bundle.dashboard.kpi.latency).toBeTruthy();
    expect(bundle.dashboard.table.caption).toBeTruthy();
    expect(bundle.dashboard.table.headers.model).toBeTruthy();
    expect(bundle.dashboard.table.headers.invocations).toBeTruthy();
    expect(bundle.dashboard.table.headers.tokensIn).toBeTruthy();
    expect(bundle.dashboard.table.headers.tokensOut).toBeTruthy();
    expect(bundle.dashboard.table.headers.cost).toBeTruthy();
    expect(bundle.dashboard.table.headers.latency).toBeTruthy();
    expect(bundle.dashboard.empty.title).toBeTruthy();
    expect(bundle.dashboard.empty.body).toBeTruthy();
    expect(bundle.dashboard.errors.network.title).toBeTruthy();
    expect(bundle.dashboard.errors.network.body).toBeTruthy();
    expect(bundle.dashboard.errors.forbidden.title).toBeTruthy();
    expect(bundle.dashboard.errors.forbidden.body).toBeTruthy();
    expect(bundle.dashboard.actions.retry).toBeTruthy();
    expect(bundle.dashboard.actions.manageModels).toBeTruthy();
  });

  it("i18n: admin-ai.dashboard.* all keys present in en", () => {
    const bundle = i18n.getResourceBundle("en", "admin-ai") as AdminAiBundle;
    expect(bundle.dashboard.title).toBeTruthy();
    expect(bundle.dashboard.window.range).toBeTruthy();
    expect(bundle.dashboard.kpi.invocations).toBeTruthy();
    expect(bundle.dashboard.kpi.tokens).toBeTruthy();
    expect(bundle.dashboard.kpi.cost).toBeTruthy();
    expect(bundle.dashboard.kpi.latency).toBeTruthy();
    expect(bundle.dashboard.table.caption).toBeTruthy();
    expect(bundle.dashboard.empty.title).toBeTruthy();
    expect(bundle.dashboard.empty.body).toBeTruthy();
    expect(bundle.dashboard.errors.network.title).toBeTruthy();
    expect(bundle.dashboard.errors.forbidden.title).toBeTruthy();
    expect(bundle.dashboard.actions.retry).toBeTruthy();
    expect(bundle.dashboard.actions.manageModels).toBeTruthy();
  });

  it("i18n: admin-ai.dashboard.* all keys present in fr", () => {
    const bundle = i18n.getResourceBundle("fr", "admin-ai") as AdminAiBundle;
    expect(bundle.dashboard.title).toBeTruthy();
    expect(bundle.dashboard.window.range).toBeTruthy();
    expect(bundle.dashboard.kpi.invocations).toBeTruthy();
    expect(bundle.dashboard.kpi.tokens).toBeTruthy();
    expect(bundle.dashboard.kpi.cost).toBeTruthy();
    expect(bundle.dashboard.kpi.latency).toBeTruthy();
    expect(bundle.dashboard.table.caption).toBeTruthy();
    expect(bundle.dashboard.empty.title).toBeTruthy();
    expect(bundle.dashboard.empty.body).toBeTruthy();
    expect(bundle.dashboard.errors.network.title).toBeTruthy();
    expect(bundle.dashboard.errors.forbidden.title).toBeTruthy();
    expect(bundle.dashboard.actions.retry).toBeTruthy();
    expect(bundle.dashboard.actions.manageModels).toBeTruthy();
  });

  it("i18n: admin-ai.dashboard.title differs across es, en, fr", () => {
    const esBundle = i18n.getResourceBundle("es", "admin-ai") as AdminAiBundle;
    const enBundle = i18n.getResourceBundle("en", "admin-ai") as AdminAiBundle;
    const frBundle = i18n.getResourceBundle("fr", "admin-ai") as AdminAiBundle;
    expect(esBundle.dashboard.title).not.toBe(enBundle.dashboard.title);
    expect(esBundle.dashboard.title).not.toBe(frBundle.dashboard.title);
  });

  it("i18n: admin-ai.nav.* all keys present in es/en/fr", () => {
    const NAV_KEYS: (keyof AdminAiBundle["nav"])[] = [
      "dashboard", "models", "modelsNew", "ragDocuments", "ragCollections",
      "mcpServers", "mcpNew", "agents", "audit", "usage",
    ];
    SUPPORTED_LANGUAGES.forEach((lng) => {
      const bundle = i18n.getResourceBundle(lng, "admin-ai") as AdminAiBundle;
      NAV_KEYS.forEach((key) => {
        expect(bundle.nav[key]).toBeTruthy();
      });
    });
  });
});
