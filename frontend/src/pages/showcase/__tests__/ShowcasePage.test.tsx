/**
 * Hilo People — ShowcasePage smoke test.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Test strategy: real React render of the showcase page in jsdom + MemoryRouter.
 *   Verifies all 9 section headings are visible and the page renders without error.
 *   Does NOT check visual design — that is the human /verify-slice gate.
 *
 * Key deps: vitest ^3.0.0, @testing-library/react ^16.3.2, react-router ^7.15.0, jsdom.
 */

import { describe, it, expect, afterEach } from "vitest";
import { render, screen, cleanup } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import ShowcasePage from "../ShowcasePage";

afterEach(cleanup);

describe("ShowcasePage", () => {
  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={["/showcase"]}>
        <ShowcasePage />
      </MemoryRouter>
    );

  it("renders the page title", () => {
    renderPage();
    expect(screen.getByText("Design System")).toBeInTheDocument();
  });

  it("renders all 9 component sections", () => {
    renderPage();
    expect(screen.getByText(/1 · Wordmark/i)).toBeInTheDocument();
    expect(screen.getByText(/2 · TrackedLabel/i)).toBeInTheDocument();
    expect(screen.getByText(/3 · EditorialInput/i)).toBeInTheDocument();
    expect(screen.getByText(/4 · SolidCTA/i)).toBeInTheDocument();
    expect(screen.getByText(/5 · HairlineTable/i)).toBeInTheDocument();
    expect(screen.getByText(/6 · StatusDot/i)).toBeInTheDocument();
    expect(screen.getByText(/7 · MobileFrame/i)).toBeInTheDocument();
    expect(screen.getByText(/8 · AdminShell/i)).toBeInTheDocument();
    expect(screen.getByText(/9 · CitationInline/i)).toBeInTheDocument();
  });

  it("renders the Wordmark 'Hilo' brand text", () => {
    renderPage();
    const hiloElements = screen.getAllByText("Hilo");
    expect(hiloElements.length).toBeGreaterThan(0);
  });

  it("renders the design system footer", () => {
    renderPage();
    expect(screen.getByText(/Hilo People · Design System · P00-S01-T004/i)).toBeInTheDocument();
  });
});
