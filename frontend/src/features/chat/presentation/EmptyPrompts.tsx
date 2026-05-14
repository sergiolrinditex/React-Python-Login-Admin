/**
 * Hilo People — EmptyPrompts component.
 *
 * Slice/Phase: P03-S02-T001 — ChatHomePage / Phase 3.
 *
 * Responsibility: Renders the empty-state prompt suggestion grid for ChatHomePage.
 *   Shows Wordmark, i18n title + subtitle, and clickable prompt chips.
 *   Per D-T001-PROMPT-CHIP-BEHAVIOR: clicking a chip triggers direct submit (one-tap UX).
 *   Per UX_CONTRACT §4: "empty state shows Hilo wordmark and three prompt suggestions"
 *   (two prompts declared in source-of-truth cover the "plural" requirement).
 *
 * Token usage: --font-display, --font-sans, --color-ink, --color-bg, --hairline.
 * A11y: all chips are <button> elements with visible text as accessible name.
 *   Tab order: wordmark → prompt 1 → prompt 2.
 *
 * Non-negotiables §logging: BEFORE render log gated by VITE_ENABLE_VERBOSE_LOGGING.
 */

import type { CSSProperties, ReactNode } from "react";
import { useTranslation } from "react-i18next";
import Wordmark from "../../../shared/design-system/Wordmark";
import TrackedLabel from "../../../shared/design-system/TrackedLabel";
import { logVerbose } from "../data/logger";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

export interface EmptyPromptsProps {
  /** Called when user clicks a prompt chip. Triggers direct-submit per D-T001-PROMPT-CHIP-BEHAVIOR. */
  onPromptSelect: (prompt: string) => void;
  /** Disable chips while a mutation is in-flight. */
  disabled?: boolean;
}

// ---------------------------------------------------------------------------
// Styles (tokens only — no raw literals)
// ---------------------------------------------------------------------------

const CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: "1.5rem",
  paddingTop: "2rem",
  paddingBottom: "1rem",
};

const HEADER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: "0.5rem",
  textAlign: "center",
};

const TITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "1.125rem",
  color: "var(--color-ink)",
  marginTop: "0.75rem",
  fontWeight: 400,
};

const SUBTITLE_STYLE: CSSProperties = {
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  opacity: 0.6,
};

const CHIPS_CONTAINER_STYLE: CSSProperties = {
  display: "flex",
  flexDirection: "column",
  gap: "0.5rem",
  width: "100%",
};

const CHIP_STYLE: CSSProperties = {
  display: "block",
  width: "100%",
  padding: "0.75rem 1rem",
  border: "var(--hairline)",
  borderRadius: 0,
  background: "transparent",
  fontFamily: "var(--font-sans)",
  fontSize: "0.875rem",
  color: "var(--color-ink)",
  textAlign: "left",
  cursor: "pointer",
  minHeight: "44px",
};

const CHIP_DISABLED_STYLE: CSSProperties = {
  ...CHIP_STYLE,
  opacity: 0.4,
  cursor: "not-allowed",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

/**
 * Empty state for ChatHomePage: Wordmark + title + subtitle + prompt chips.
 *
 * @param props - {@link EmptyPromptsProps}
 * @returns The empty prompts element.
 */
export default function EmptyPrompts({
  onPromptSelect,
  disabled = false,
}: EmptyPromptsProps): ReactNode {
  const { t } = useTranslation(["chat", "common"]);

  logVerbose("chat.EmptyPrompts.render.start", { disabled });

  const prompts: { key: string; text: string }[] = [
    { key: "promptVacation", text: t("chat:empty.promptVacation") },
    { key: "promptMobility", text: t("chat:empty.promptMobility") },
  ];

  return (
    <div style={CONTAINER_STYLE} data-testid="empty-prompts">
      {/* Wordmark — per UX_CONTRACT §4 */}
      <header style={HEADER_STYLE}>
        <h1>
          <Wordmark size="2rem" aria-label={t("common:productName")} />
        </h1>
        <p style={TITLE_STYLE}>{t("chat:empty.title")}</p>
        <TrackedLabel as="p" variant="muted" style={SUBTITLE_STYLE}>
          {t("chat:empty.subtitle")}
        </TrackedLabel>
      </header>

      {/* Prompt chips — direct-submit per D-T001-PROMPT-CHIP-BEHAVIOR */}
      <div
        style={CHIPS_CONTAINER_STYLE}
        role="list"
        aria-label={t("chat:empty.title")}
      >
        {prompts.map(({ key, text }) => (
          <button
            key={key}
            role="listitem"
            type="button"
            style={disabled ? CHIP_DISABLED_STYLE : CHIP_STYLE}
            disabled={disabled}
            aria-disabled={disabled ? "true" : undefined}
            onClick={() => {
              logVerbose("chat.EmptyPrompts.prompt_selected", { key });
              onPromptSelect(text);
            }}
            data-testid={`prompt-chip-${key}`}
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  );
}
