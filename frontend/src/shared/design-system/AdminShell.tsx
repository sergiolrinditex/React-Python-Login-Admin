/**
 * Hilo People — AdminShell component.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Responsibility: desktop admin shell with left sidebar navigation and main
 *   content area (1440 px target per UX_CONTRACT §7). Hairline separates nav
 *   from content. No rounded corners anywhere. Used on: AdminDashboardPage,
 *   RagDocumentsPage, McpServersPage, AuditLogPage, UsagePage.
 *   Journey refs: J103 (admin management), J104 (MCP config).
 *
 * Token usage: --color-bg, --hairline, --font-sans, --color-ink.
 * Prohibitions: NO border-radius, NO box-shadow, NO colored nav backgrounds.
 *
 * Accessibility:
 *   - <nav> with aria-label for the left sidebar.
 *   - <main> for the content area.
 *   - skip-to-content link placeholder (screens add it).
 *
 * Key deps: React 19, Wordmark, CSS custom properties from tokens.css.
 */

import type { CSSProperties, ReactNode } from "react";
import Wordmark from "./Wordmark";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface AdminNavItem {
  /** Unique nav item key. */
  key: string;
  /** Display label. */
  label: string;
  /** Whether this item is the currently active route. */
  active?: boolean;
  /** Click handler. */
  onClick?: () => void;
}

export interface AdminShellProps {
  /** Left nav items. */
  navItems: AdminNavItem[];
  /** Page content. */
  children: ReactNode;
  /** Aria label for the left nav. */
  navAriaLabel?: string;
  className?: string;
  style?: CSSProperties;
}

// ---------------------------------------------------------------------------
// Styles
// ---------------------------------------------------------------------------

const SHELL_STYLE: CSSProperties = {
  display: "flex",
  minHeight: "100vh",
  backgroundColor: "var(--color-bg)",
  maxWidth: "1440px",
  margin: "0 auto",
  width: "100%",
};

const NAV_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  width: "220px",
  flexShrink: 0,
  borderRight: "var(--hairline)",
  padding: "1.5rem 1.25rem",
  gap: "0.25rem",
};

const WORDMARK_CONTAINER: CSSProperties = {
  marginBottom: "2rem",
  paddingBottom: "1rem",
  borderBottom: "var(--hairline)",
};

const NAV_ITEM_BASE: CSSProperties = {
  display: "block",
  width: "100%",
  textAlign: "left",
  padding: "0.5rem 0",
  fontFamily: "var(--font-sans)",
  fontSize: "0.8125rem",
  letterSpacing: "0.04em",
  color: "var(--color-ink)",
  background: "transparent",
  border: "none",
  borderRadius: 0,
  cursor: "pointer",
  opacity: 0.7,
  transition: "opacity 150ms",
};

const NAV_ITEM_ACTIVE_OVERRIDES: CSSProperties = {
  opacity: 1,
  fontWeight: 500,
};

const MAIN_STYLE: CSSProperties = {
  flex: 1,
  padding: "2rem 2.5rem",
  minWidth: 0,
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Admin shell: left nav + content area, hairline separator, 1440 px target.
 *
 * @param props - {@link AdminShellProps}
 * @returns The admin shell layout.
 */
export default function AdminShell({
  navItems,
  children,
  navAriaLabel = "Admin navigation",
  className,
  style,
}: AdminShellProps): ReactNode {
  /* BEFORE render log */
  if (import.meta.env.VITE_ENABLE_VERBOSE_LOGGING === "true") {
    console.info("AdminShell.render.start", {
      phase: "P00",
      slice: "P00-S01-T004",
      navItemCount: navItems.length,
    });
  }

  return (
    <div className={className} style={{ ...SHELL_STYLE, ...style }}>
      <nav aria-label={navAriaLabel} style={NAV_STYLE}>
        <div style={WORDMARK_CONTAINER}>
          <Wordmark size="1.25rem" />
        </div>

        {navItems.map((item) => (
          <button
            key={item.key}
            type="button"
            aria-current={item.active ? "page" : undefined}
            onClick={item.onClick}
            style={{
              ...NAV_ITEM_BASE,
              ...(item.active ? NAV_ITEM_ACTIVE_OVERRIDES : {}),
            }}
          >
            {item.label}
          </button>
        ))}
      </nav>

      <main style={MAIN_STYLE}>
        {children}
      </main>
    </div>
  );
}
