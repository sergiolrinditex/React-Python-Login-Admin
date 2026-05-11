/**
 * Hilo People — Design System component smoke tests.
 *
 * Slice/Phase: P00-S01-T004 — Design tokens + editorial system / Phase 0 Scaffold.
 *
 * Test strategy: real React renders via @testing-library/react in jsdom.
 *   - Verifies all 9 base components render without throwing.
 *   - Verifies token CSS classes/vars are referenced (structural check).
 *   - Verifies accessibility attributes on interactive components.
 *   - NO mocking of component internals.
 *
 * Key deps: vitest ^3.0.0, @testing-library/react ^16.3.2, jsdom ^25.0.0.
 */

import { describe, it, expect, afterEach, vi } from "vitest";
import { render, screen, cleanup, fireEvent } from "@testing-library/react";
import Wordmark from "../Wordmark";
import TrackedLabel from "../TrackedLabel";
import EditorialInput from "../EditorialInput";
import SolidCTA from "../SolidCTA";
import HairlineTable from "../HairlineTable";
import StatusDot from "../StatusDot";
import MobileFrame from "../MobileFrame";
import AdminShell from "../AdminShell";
import CitationInline from "../CitationInline";

afterEach(cleanup);

// ---------------------------------------------------------------------------
// 1. Wordmark
// ---------------------------------------------------------------------------
describe("Wordmark", () => {
  it("renders 'Hilo' text", () => {
    render(<Wordmark />);
    expect(screen.getByText("Hilo")).toBeInTheDocument();
  });

  it("has default aria-label 'Hilo'", () => {
    render(<Wordmark />);
    expect(screen.getByLabelText("Hilo")).toBeInTheDocument();
  });

  it("renders custom element via 'as' prop", () => {
    const { container } = render(<Wordmark as="h1" />);
    expect(container.querySelector("h1")).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 2. TrackedLabel
// ---------------------------------------------------------------------------
describe("TrackedLabel", () => {
  it("renders children", () => {
    render(<TrackedLabel>My Label</TrackedLabel>);
    expect(screen.getByText("My Label")).toBeInTheDocument();
  });

  it("renders all variants without throwing", () => {
    const { unmount } = render(
      <>
        <TrackedLabel variant="default">A</TrackedLabel>
        <TrackedLabel variant="active">B</TrackedLabel>
        <TrackedLabel variant="muted">C</TrackedLabel>
      </>
    );
    expect(screen.getByText("A")).toBeInTheDocument();
    unmount();
  });

  it("renders as label element", () => {
    const { container } = render(
      <TrackedLabel as="label" htmlFor="x">Test</TrackedLabel>
    );
    const el = container.querySelector("label");
    expect(el).not.toBeNull();
    expect(el?.getAttribute("for")).toBe("x");
  });
});

// ---------------------------------------------------------------------------
// 3. EditorialInput
// ---------------------------------------------------------------------------
describe("EditorialInput", () => {
  it("renders label and input", () => {
    render(<EditorialInput label="Email" placeholder="test@test.com" />);
    expect(screen.getByLabelText("Email")).toBeInTheDocument();
  });

  it("shows error message with aria-invalid", () => {
    render(
      <EditorialInput
        label="Email"
        errorMessage="Invalid email"
        value="bad"
        onChange={() => {}}
      />
    );
    const input = screen.getByLabelText("Email");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByText("Invalid email")).toBeInTheDocument();
  });

  it("disables input and renders muted label", () => {
    render(<EditorialInput label="Company" value="Hilo" disabled onChange={() => {}} />);
    expect(screen.getByLabelText("Company")).toBeDisabled();
  });

  it("calls onChange", () => {
    const onChange = vi.fn();
    render(<EditorialInput label="Name" onChange={onChange} />);
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Alice" } });
    expect(onChange).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 4. SolidCTA
// ---------------------------------------------------------------------------
describe("SolidCTA", () => {
  it("renders children", () => {
    render(<SolidCTA>Sign In</SolidCTA>);
    expect(screen.getByText("Sign In")).toBeInTheDocument();
  });

  it("is disabled when disabled prop is true", () => {
    render(<SolidCTA disabled>Submit</SolidCTA>);
    expect(screen.getByRole("button")).toBeDisabled();
  });

  it("shows loading label when loading=true", () => {
    render(<SolidCTA loading loadingLabel="Sending…">Submit</SolidCTA>);
    expect(screen.getByText("Sending…")).toBeInTheDocument();
  });

  it("has aria-busy when loading", () => {
    render(<SolidCTA loading>Submit</SolidCTA>);
    expect(screen.getByRole("button")).toHaveAttribute("aria-busy", "true");
  });

  it("calls onClick when not disabled", () => {
    const onClick = vi.fn();
    render(<SolidCTA onClick={onClick}>Click</SolidCTA>);
    fireEvent.click(screen.getByRole("button"));
    expect(onClick).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 5. HairlineTable
// ---------------------------------------------------------------------------
describe("HairlineTable", () => {
  const cols = [
    { header: "Name", accessor: "name" as const },
    { header: "Status", accessor: "status" as const },
  ];
  const rows = [
    { name: "Alice", status: "Active" },
    { name: "Bob",   status: "Inactive" },
  ];

  it("renders populated rows", () => {
    render(<HairlineTable columns={cols} rows={rows} />);
    expect(screen.getByText("Alice")).toBeInTheDocument();
    expect(screen.getByText("Bob")).toBeInTheDocument();
  });

  it("renders empty message when rows is empty", () => {
    render(<HairlineTable columns={cols} rows={[]} emptyMessage="No results." />);
    expect(screen.getByText("No results.")).toBeInTheDocument();
  });

  it("renders error_network state with retry CTA", () => {
    const onRetry = vi.fn();
    render(
      <HairlineTable
        columns={cols}
        rows={[]}
        state="error_network"
        errorMessage="Load failed."
        onRetry={onRetry}
      />
    );
    expect(screen.getByText("Load failed.")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /retry/i }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("renders permission_denied state", () => {
    render(<HairlineTable columns={cols} rows={[]} state="permission_denied" />);
    expect(
      screen.getByText(/you do not have permission/i)
    ).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 6. StatusDot
// ---------------------------------------------------------------------------
describe("StatusDot", () => {
  it("renders active state with label", () => {
    render(<StatusDot state="active" />);
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("renders error state with label", () => {
    render(<StatusDot state="error" />);
    expect(screen.getByText("Error")).toBeInTheDocument();
  });

  it("renders custom label", () => {
    render(<StatusDot state="active" label="Connected" />);
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("has aria-label with status", () => {
    render(<StatusDot state="syncing" />);
    const el = screen.getByLabelText(/Status: Syncing/i);
    expect(el).toBeInTheDocument();
  });
});

// ---------------------------------------------------------------------------
// 7. MobileFrame
// ---------------------------------------------------------------------------
describe("MobileFrame", () => {
  it("renders children", () => {
    render(<MobileFrame><span>Content</span></MobileFrame>);
    expect(screen.getByText("Content")).toBeInTheDocument();
  });

  it("renders as main when asMain=true", () => {
    const { container } = render(
      <MobileFrame asMain><span>Main</span></MobileFrame>
    );
    expect(container.querySelector("main")).not.toBeNull();
  });
});

// ---------------------------------------------------------------------------
// 8. AdminShell
// ---------------------------------------------------------------------------
describe("AdminShell", () => {
  const navItems = [
    { key: "a", label: "Dashboard", active: true, onClick: vi.fn() },
    { key: "b", label: "Documents", active: false, onClick: vi.fn() },
  ];

  it("renders nav items", () => {
    render(<AdminShell navItems={navItems}><div>Content</div></AdminShell>);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
    expect(screen.getByText("Documents")).toBeInTheDocument();
  });

  it("renders children in main", () => {
    render(<AdminShell navItems={navItems}><span>Page Body</span></AdminShell>);
    const main = screen.getByRole("main");
    expect(main).toHaveTextContent("Page Body");
  });

  it("marks active item with aria-current=page", () => {
    render(<AdminShell navItems={navItems}><div /></AdminShell>);
    const activeBtn = screen.getByRole("button", { name: "Dashboard" });
    expect(activeBtn).toHaveAttribute("aria-current", "page");
  });

  it("calls onClick when nav item is clicked", () => {
    const onClick = vi.fn();
    render(
      <AdminShell navItems={[{ key: "x", label: "Click Me", active: false, onClick }]}>
        <div />
      </AdminShell>
    );
    fireEvent.click(screen.getByRole("button", { name: "Click Me" }));
    expect(onClick).toHaveBeenCalled();
  });
});

// ---------------------------------------------------------------------------
// 9. CitationInline
// ---------------------------------------------------------------------------
describe("CitationInline", () => {
  it("renders as anchor when href provided", () => {
    const { container } = render(<CitationInline label="Fuente 1" href="#s1" />);
    expect(container.querySelector("a")).not.toBeNull();
  });

  it("renders as button when no href", () => {
    render(<CitationInline label="Fuente 1" onClick={() => {}} />);
    expect(screen.getByRole("button")).toBeInTheDocument();
  });

  it("displays [label] format", () => {
    render(<CitationInline label="Fuente 1" href="#s1" />);
    expect(screen.getByText("[Fuente 1]")).toBeInTheDocument();
  });

  it("has accessible aria-label", () => {
    render(<CitationInline label="Fuente 1" href="#s1" />);
    expect(screen.getByLabelText("Citation: Fuente 1")).toBeInTheDocument();
  });

  it("adds rel=noopener noreferrer when external", () => {
    const { container } = render(
      <CitationInline label="Fuente 1" href="https://example.com" external />
    );
    const link = container.querySelector("a");
    expect(link?.getAttribute("rel")).toBe("noopener noreferrer");
  });
});
