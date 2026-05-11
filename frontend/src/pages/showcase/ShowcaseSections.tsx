/**
 * Hilo People — Design System Showcase Sections.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: renders all 9 base component sections with all required states
 *   per UX_CONTRACT §3 (component level) and task pack §E applicability matrix.
 *   Consumed exclusively by ShowcasePage.tsx.
 *
 * Data: declared inline demo fixtures only (flagged demo_fixture — not journey data).
 *   Source: task pack §E "Provided/fixture data" column.
 *
 * Key deps: React 19, all 9 design-system components, Section/Row helpers.
 */

import { useState, type ReactNode } from "react";
import Wordmark from "../../shared/design-system/Wordmark";
import TrackedLabel from "../../shared/design-system/TrackedLabel";
import EditorialInput from "../../shared/design-system/EditorialInput";
import SolidCTA from "../../shared/design-system/SolidCTA";
import HairlineTable from "../../shared/design-system/HairlineTable";
import StatusDot from "../../shared/design-system/StatusDot";
import AdminShell from "../../shared/design-system/AdminShell";
import CitationInline from "../../shared/design-system/CitationInline";

// ---------------------------------------------------------------------------
// Demo fixture data (§E — declared fixtures, flagged demo_fixture)
// ---------------------------------------------------------------------------

/** demo_fixture: static rows for HairlineTable populated state (§E) */
const TABLE_ROWS: { model: string; status: string; latency: string }[] = [
  { model: "gpt-4o-mini",    status: "Active",   latency: "320ms" },
  { model: "claude-3-haiku", status: "Inactive", latency: "—"     },
  { model: "llama-3-8b",     status: "Syncing",  latency: "510ms" },
];

const TABLE_COLUMNS = [
  { header: "Model",   accessor: "model"   as keyof (typeof TABLE_ROWS)[0] },
  { header: "Status",  accessor: "status"  as keyof (typeof TABLE_ROWS)[0] },
  { header: "Latency", accessor: "latency" as keyof (typeof TABLE_ROWS)[0] },
];

/** demo_fixture: nav items for AdminShell default state (§E) */
const ADMIN_NAV = [
  { key: "dashboard",  label: "Dashboard",   active: true,  onClick: () => {} },
  { key: "documents",  label: "Documents",   active: false, onClick: () => {} },
  { key: "mcp",        label: "MCP Servers", active: false, onClick: () => {} },
  { key: "audit",      label: "Audit Log",   active: false, onClick: () => {} },
  { key: "usage",      label: "Usage",       active: false, onClick: () => {} },
];

// ---------------------------------------------------------------------------
// Layout helpers (inlined — no external dep to avoid cross-file coupling)
// ---------------------------------------------------------------------------

function Section({ title, id, children }: { title: string; id: string; children: ReactNode }): ReactNode {
  return (
    <section aria-labelledby={id} style={{ marginBottom: "3rem" }}>
      <h2
        id={id}
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.6875rem",
          letterSpacing: "var(--tracking-label)",
          textTransform: "uppercase",
          color: "var(--color-ink)",
          opacity: 0.45,
          marginBottom: "1.5rem",
          borderBottom: "var(--hairline)",
          paddingBottom: "0.5rem",
        }}
      >
        {title}
      </h2>
      <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
        {children}
      </div>
    </section>
  );
}

function Row({ label, children }: { label: string; children: ReactNode }): ReactNode {
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "1.5rem", flexWrap: "wrap" }}>
      <span
        style={{
          fontFamily: "var(--font-sans)",
          fontSize: "0.6875rem",
          letterSpacing: "0.04em",
          color: "var(--color-ink)",
          opacity: 0.4,
          minWidth: "88px",
        }}
      >
        {label}
      </span>
      {children}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

/**
 * All 9 design-system sections with required states from §E.
 *
 * @returns All showcase sections.
 */
export function ShowcaseSections(): ReactNode {
  const [inputValue, setInputValue] = useState("");
  const [ctaLoading, setCtaLoading] = useState(false);

  const handleCtaClick = () => {
    setCtaLoading(true);
    setTimeout(() => setCtaLoading(false), 1500);
  };

  return (
    <>
      {/* 1. Wordmark — states: default */}
      <Section title="1 · Wordmark" id="sec-wordmark">
        <Row label="default"><Wordmark /></Row>
        <Row label="small"><Wordmark size="1rem" /></Row>
        <Row label="large"><Wordmark size="3rem" /></Row>
      </Section>

      {/* 2. TrackedLabel — states: default, active, muted */}
      <Section title="2 · TrackedLabel" id="sec-tracked-label">
        <Row label="default"><TrackedLabel>Section Header</TrackedLabel></Row>
        <Row label="active"><TrackedLabel variant="active">Active Label</TrackedLabel></Row>
        <Row label="muted"><TrackedLabel variant="muted">Muted Label</TrackedLabel></Row>
      </Section>

      {/* 3. EditorialInput — states: empty, filled, focused, error_validation, disabled */}
      <Section title="3 · EditorialInput" id="sec-editorial-input">
        <Row label="empty">
          <div style={{ width: "320px" }}>
            <EditorialInput label="Email" type="email" placeholder="user@company.com" />
          </div>
        </Row>
        <Row label="filled">
          <div style={{ width: "320px" }}>
            <EditorialInput label="Email" type="email" value="user@hilo.ai" onChange={() => {}} />
          </div>
        </Row>
        <Row label="error">
          <div style={{ width: "320px" }}>
            <EditorialInput
              label="Email"
              type="email"
              value="not-an-email"
              errorMessage="Enter a valid email address."
              onChange={() => {}}
            />
          </div>
        </Row>
        <Row label="disabled">
          <div style={{ width: "320px" }}>
            <EditorialInput label="Company" value="Hilo Inc." disabled onChange={() => {}} />
          </div>
        </Row>
        <Row label="controlled">
          <div style={{ width: "320px" }}>
            <EditorialInput
              label="Controlled Input"
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              placeholder="Type here…"
            />
          </div>
        </Row>
      </Section>

      {/* 4. SolidCTA — states: default, disabled, loading */}
      <Section title="4 · SolidCTA" id="sec-solid-cta">
        <Row label="default">
          <SolidCTA width="auto" style={{ padding: "0.75rem 2rem" }} onClick={handleCtaClick}>
            Sign In
          </SolidCTA>
        </Row>
        <Row label="disabled">
          <SolidCTA width="auto" style={{ padding: "0.75rem 2rem" }} disabled>
            Disabled
          </SolidCTA>
        </Row>
        <Row label="loading">
          <SolidCTA
            width="auto"
            style={{ padding: "0.75rem 2rem", minWidth: "140px" }}
            loading={ctaLoading}
            onClick={handleCtaClick}
            loadingLabel="Sending…"
          >
            {ctaLoading ? "Sending…" : "Click to Load"}
          </SolidCTA>
        </Row>
        <Row label="full width">
          <div style={{ width: "320px" }}>
            <SolidCTA>Full Width Button</SolidCTA>
          </div>
        </Row>
      </Section>

      {/* 5. HairlineTable — states: empty, populated, error_network, permission_denied */}
      <Section title="5 · HairlineTable" id="sec-hairline-table">
        <Row label="populated">
          <div style={{ width: "100%", minWidth: "400px" }}>
            <HairlineTable columns={TABLE_COLUMNS} rows={TABLE_ROWS} caption="AI model status" />
          </div>
        </Row>
        <Row label="empty">
          <div style={{ width: "100%", minWidth: "400px" }}>
            <HairlineTable columns={TABLE_COLUMNS} rows={[]} emptyMessage="No models configured." />
          </div>
        </Row>
        <Row label="error network">
          <div style={{ width: "100%", minWidth: "400px" }}>
            <HairlineTable
              columns={TABLE_COLUMNS}
              rows={[]}
              state="error_network"
              errorMessage="Could not load model data."
              onRetry={() => {}}
            />
          </div>
        </Row>
        <Row label="permission denied">
          <div style={{ width: "100%", minWidth: "400px" }}>
            <HairlineTable columns={TABLE_COLUMNS} rows={[]} state="permission_denied" />
          </div>
        </Row>
      </Section>

      {/* 6. StatusDot — states: active, inactive, syncing, error */}
      <Section title="6 · StatusDot" id="sec-status-dot">
        <Row label="active"><StatusDot state="active" /></Row>
        <Row label="inactive"><StatusDot state="inactive" /></Row>
        <Row label="syncing"><StatusDot state="syncing" /></Row>
        <Row label="error"><StatusDot state="error" /></Row>
        <Row label="custom label"><StatusDot state="active" label="Connected" /></Row>
      </Section>

      {/* 7. MobileFrame — states: default with placeholder copy */}
      <Section title="7 · MobileFrame" id="sec-mobile-frame">
        <Row label="default">
          <div style={{ backgroundColor: "var(--color-bg)", padding: "1rem", border: "var(--hairline)", maxWidth: "460px" }}>
            <div
              style={{
                backgroundColor: "var(--color-paper)",
                border: "var(--hairline)",
                borderRadius: 0,
                padding: "2rem",
                maxWidth: "402px",
                margin: "0 auto",
              }}
            >
              <Wordmark style={{ marginBottom: "1.5rem" }} />
              <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.875rem", color: "var(--color-ink)", opacity: 0.6 }}>
                402 px max, square corners, crude bg outer, paper inner.
              </p>
            </div>
          </div>
        </Row>
      </Section>

      {/* 8. AdminShell — states: default with placeholder left-nav */}
      <Section title="8 · AdminShell" id="sec-admin-shell">
        <Row label="default">
          <div style={{ width: "100%", border: "var(--hairline)", maxHeight: "280px", overflow: "hidden" }}>
            <AdminShell navItems={ADMIN_NAV}>
              <TrackedLabel variant="muted">Admin Content Area</TrackedLabel>
              <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.875rem", color: "var(--color-ink)", opacity: 0.55, marginTop: "0.75rem" }}>
                Left nav + hairline separator. Wordmark in sidebar. No rounded corners.
              </p>
            </AdminShell>
          </div>
        </Row>
      </Section>

      {/* 9. CitationInline — states: default, hover (CSS only) */}
      <Section title="9 · CitationInline" id="sec-citation-inline">
        <Row label="default">
          <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.875rem", color: "var(--color-ink)" }}>
            The assistant answered based on policy<CitationInline label="Fuente 1" href="#s1" />
            {" "}and documentation<CitationInline label="Fuente 2" href="#s2" />.
          </p>
        </Row>
        <Row label="button (no href)">
          <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.875rem", color: "var(--color-ink)" }}>
            Button citation (no href)<CitationInline label="Fuente 1" onClick={() => {}} />.
          </p>
        </Row>
        <Row label="external">
          <p style={{ fontFamily: "var(--font-sans)", fontSize: "0.875rem", color: "var(--color-ink)" }}>
            External link<CitationInline label="Fuente 3" href="https://example.com" external />.
          </p>
        </Row>
      </Section>
    </>
  );
}
