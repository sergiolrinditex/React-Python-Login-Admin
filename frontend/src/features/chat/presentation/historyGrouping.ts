/**
 * Hilo People — History grouping pure function.
 *
 * Slice/Phase: P03-S02-T003 — HistoryPage / Phase 3.
 *
 * Responsibility: Groups ConversationSummary items into relative-date buckets
 *   (Today, Yesterday, This week, This month, Earlier) using the conversation's
 *   updated_at field relative to an injected `now` date.
 *
 * §D-T003-HISTORY-GROUPING — pure function, deterministic, testable in isolation.
 * Inject `now: Date` so tests can control the reference point without mocking globals.
 *
 * Bucket rules (calendar-day in user's local timezone):
 *   - today:     same calendar day as now
 *   - yesterday: calendar day - 1
 *   - thisWeek:  within last 7 calendar days (exclusive of today/yesterday)
 *   - thisMonth: within last 30 calendar days (exclusive of above)
 *   - earlier:   everything older
 *
 * Output order is canonical (today → yesterday → thisWeek → thisMonth → earlier).
 * Within each group items preserve the original order (backend returns updated_at DESC).
 *
 * Non-negotiables §logging: none here — pure function; caller logs.
 * Key deps: none (pure TypeScript, no framework imports).
 */

import type { ConversationSummary } from "../domain/types";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** A bucket label key — maps to i18n history.groups.* keys. */
export type GroupKey = "today" | "yesterday" | "thisWeek" | "thisMonth" | "earlier";

/** A group of conversations under a relative-date label. */
export interface ConversationGroup {
  key: GroupKey;
  items: ConversationSummary[];
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

/**
 * Returns a Date set to midnight local time for the given date.
 * Used to compare calendar days without time components.
 *
 * @param d - Input date.
 * @returns Date at start of its local calendar day.
 */
function startOfDay(d: Date): Date {
  return new Date(d.getFullYear(), d.getMonth(), d.getDate());
}

/**
 * Computes the bucket for a single conversation relative to `now`.
 *
 * @param conv - Conversation summary (uses updated_at for bucketing).
 * @param nowDay - startOfDay(now) — pre-computed to avoid recalculating per item.
 * @returns GroupKey bucket.
 */
function getBucket(conv: ConversationSummary, nowDay: Date): GroupKey {
  const updatedAt = new Date(conv.updated_at);
  const itemDay = startOfDay(updatedAt);

  const diffMs = nowDay.getTime() - itemDay.getTime();
  const diffDays = Math.round(diffMs / (1000 * 60 * 60 * 24));

  if (diffDays === 0) return "today";
  if (diffDays === 1) return "yesterday";
  if (diffDays <= 7) return "thisWeek";
  if (diffDays <= 30) return "thisMonth";
  return "earlier";
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

/**
 * Groups conversations into relative-date buckets.
 *
 * @param conversations - List of ConversationSummary items (typically sorted updated_at DESC by backend).
 * @param now - Reference date for relative-date computation (inject for deterministic tests).
 * @returns Array of ConversationGroup in canonical order, empty groups omitted.
 */
export function groupConversationsByRelativeDate(
  conversations: ConversationSummary[],
  now: Date,
): ConversationGroup[] {
  const nowDay = startOfDay(now);

  const buckets: Record<GroupKey, ConversationSummary[]> = {
    today: [],
    yesterday: [],
    thisWeek: [],
    thisMonth: [],
    earlier: [],
  };

  for (const conv of conversations) {
    buckets[getBucket(conv, nowDay)].push(conv);
  }

  // Canonical order — only include non-empty buckets
  const order: GroupKey[] = ["today", "yesterday", "thisWeek", "thisMonth", "earlier"];
  return order
    .filter((key) => buckets[key].length > 0)
    .map((key) => ({ key, items: buckets[key] }));
}
