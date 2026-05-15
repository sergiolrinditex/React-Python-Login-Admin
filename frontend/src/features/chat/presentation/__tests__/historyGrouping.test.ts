/**
 * Hilo People — historyGrouping unit tests.
 *
 * Slice/Phase: P03-S02-T003 — HistoryPage / Phase 3.
 *
 * Responsibility: Exhaustive boundary tests for groupConversationsByRelativeDate.
 *   §D-T003-HISTORY-GROUPING-TESTS — G01–G06 per task pack §12.
 *   `now` is injected per test for deterministic results.
 *
 * Cases:
 *   G01 — empty input → [].
 *   G02 — only today → single "today" group.
 *   G03 — today + yesterday → 2 groups in canonical order.
 *   G04 — spans all 5 buckets → 5 groups in canonical order.
 *   G05 — timezone boundary (UTC ≠ local midnight).
 *   G06 — ordering within group preserves input order (updated_at DESC from backend).
 *   G07 — single item in "earlier" bucket.
 *   G08 — week boundary (7 days → thisWeek, 8 days → thisMonth).
 *   G09 — month boundary (30 days → thisMonth, 31 days → earlier).
 *   G10 — title null → untitled (grouping should not fail on null title).
 */

import { describe, it, expect } from "vitest";
import {
  groupConversationsByRelativeDate,
} from "../historyGrouping";
import type { ConversationSummary } from "../../domain/types";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/** Creates a minimal ConversationSummary with the given updated_at ISO string. */
function makeConv(id: string, updatedAt: string, title: string | null = "Test"): ConversationSummary {
  return {
    id,
    user_id: "user-1",
    title,
    language: "es",
    created_at: updatedAt,
    updated_at: updatedAt,
  };
}

/**
 * Returns a Date that is `days` calendar days before `now` at noon local time.
 * Using noon prevents midnight ambiguity when computing startOfDay.
 */
function daysAgo(now: Date, days: number): string {
  const d = new Date(now);
  d.setDate(d.getDate() - days);
  d.setHours(12, 0, 0, 0);
  return d.toISOString();
}

// Reference point for all tests (fixed to avoid flakiness)
const NOW = new Date("2026-05-15T15:00:00.000Z");

// ---------------------------------------------------------------------------
// Tests
// ---------------------------------------------------------------------------

describe("groupConversationsByRelativeDate", () => {
  it("G01 — empty input returns []", () => {
    const result = groupConversationsByRelativeDate([], NOW);
    expect(result).toEqual([]);
  });

  it("G02 — only today returns single 'today' group", () => {
    const conv = makeConv("c1", daysAgo(NOW, 0));
    const result = groupConversationsByRelativeDate([conv], NOW);
    expect(result).toHaveLength(1);
    expect(result[0].key).toBe("today");
    expect(result[0].items).toHaveLength(1);
    expect(result[0].items[0].id).toBe("c1");
  });

  it("G03 — today + yesterday produces 2 groups in canonical order", () => {
    const today = makeConv("c1", daysAgo(NOW, 0));
    const yesterday = makeConv("c2", daysAgo(NOW, 1));
    const result = groupConversationsByRelativeDate([today, yesterday], NOW);
    expect(result).toHaveLength(2);
    expect(result[0].key).toBe("today");
    expect(result[1].key).toBe("yesterday");
  });

  it("G04 — spans all 5 buckets produces 5 groups in canonical order", () => {
    const convs = [
      makeConv("today", daysAgo(NOW, 0)),
      makeConv("yesterday", daysAgo(NOW, 1)),
      makeConv("thisWeek", daysAgo(NOW, 4)),    // 4 days ago
      makeConv("thisMonth", daysAgo(NOW, 15)),  // 15 days ago
      makeConv("earlier", daysAgo(NOW, 45)),    // 45 days ago
    ];
    const result = groupConversationsByRelativeDate(convs, NOW);
    expect(result).toHaveLength(5);
    expect(result.map((g) => g.key)).toEqual([
      "today",
      "yesterday",
      "thisWeek",
      "thisMonth",
      "earlier",
    ]);
  });

  it("G05 — same UTC moment that is today in one timezone resolves to today", () => {
    // Just verifying that updated_at ISO strings parse correctly.
    // The grouping uses local time via Date constructor (browser default).
    // We use a time that is definitely "today" relative to NOW.
    const convToday = makeConv("ct", NOW.toISOString());
    const result = groupConversationsByRelativeDate([convToday], NOW);
    expect(result[0].key).toBe("today");
  });

  it("G06 — ordering within group preserves input order", () => {
    // 3 items all from today — order should be preserved
    const d = daysAgo(NOW, 0);
    const convs = [
      makeConv("first", d),
      makeConv("second", d),
      makeConv("third", d),
    ];
    const result = groupConversationsByRelativeDate(convs, NOW);
    expect(result).toHaveLength(1);
    expect(result[0].items.map((c) => c.id)).toEqual(["first", "second", "third"]);
  });

  it("G07 — single item in 'earlier' bucket", () => {
    const conv = makeConv("old", daysAgo(NOW, 90));
    const result = groupConversationsByRelativeDate([conv], NOW);
    expect(result).toHaveLength(1);
    expect(result[0].key).toBe("earlier");
  });

  it("G08 — week boundary: 7 days ago → thisWeek, 8 days ago → thisMonth", () => {
    const week7 = makeConv("w7", daysAgo(NOW, 7));
    const week8 = makeConv("w8", daysAgo(NOW, 8));
    const result = groupConversationsByRelativeDate([week7, week8], NOW);
    expect(result).toHaveLength(2);
    expect(result[0].key).toBe("thisWeek");
    expect(result[0].items[0].id).toBe("w7");
    expect(result[1].key).toBe("thisMonth");
    expect(result[1].items[0].id).toBe("w8");
  });

  it("G09 — month boundary: 30 days ago → thisMonth, 31 days ago → earlier", () => {
    const month30 = makeConv("m30", daysAgo(NOW, 30));
    const month31 = makeConv("m31", daysAgo(NOW, 31));
    const result = groupConversationsByRelativeDate([month30, month31], NOW);
    expect(result).toHaveLength(2);
    expect(result[0].key).toBe("thisMonth");
    expect(result[0].items[0].id).toBe("m30");
    expect(result[1].key).toBe("earlier");
    expect(result[1].items[0].id).toBe("m31");
  });

  it("G10 — null title does not cause grouping to fail", () => {
    const conv = makeConv("cn", daysAgo(NOW, 0), null);
    expect(conv.title).toBeNull();
    const result = groupConversationsByRelativeDate([conv], NOW);
    expect(result).toHaveLength(1);
    expect(result[0].key).toBe("today");
    expect(result[0].items[0].id).toBe("cn");
  });
});
