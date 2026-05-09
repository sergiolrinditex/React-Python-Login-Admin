"""
Pure keyword-overlap routing algorithm for the deepagents Supervisor.

Slice: P00-S02-T008 — deepagents Supervisor + topic-routing runtime
Phase: P00 — Scaffold + Design System

Responsibility:
  Implements `select_subagent()`, a deterministic pure function that selects
  the most relevant subagent based on keyword overlap between the user's message
  and each subagent's `subagent_topics` list.  No LLM, no I/O, no side effects.

Algorithm (per TECHNICAL_GUIDE §15 ADR-002):
  1. Tokenise the message using Unicode-aware `\\w+` regex → token set.
  2. For each subagent compute score = |message_tokens ∩ topic_set|.
  3. Select the subagent with the highest score > 0.
  4. Tie-break: prefer larger `len(subagent_topics)` (broader coverage); then
     alphabetical `name` ascending for determinism.
  5. If no score > 0 → return fallback RoutingDecision (selected_subagent=None).

Edge cases (all tested):
  - Empty message → fallback.
  - Empty subagent list → fallback.
  - Supervisor with no subagents in list → fallback (not ValueError here;
    ValueError is raised by the caller if it requires ≥1 subagent).
  - Tie between two subagents → tie-break rules applied deterministically.

Accent normalisation:
  Topics from the fixture do NOT use accented forms (e.g. "vacaciones", not
  "vacación").  Tokenisation is lowercased ASCII, so "vacación" (accented) in
  a message will NOT match "vacaciones".  Full Unicode normalisation (NFKD +
  strip combining chars) is deferred to a follow-up if the need arises (YAGNI).

Dependencies:
  - Python stdlib only (re, dataclasses).
  - `AgentSpec` from `app.agents.specs` (same package, no external deps).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from app.agents.specs import AgentSpec
from app.core.logging import get_logger

_logger = get_logger("app.agents.routing")

# ---------------------------------------------------------------------------
# Domain dataclass
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class RoutingDecision:
    """Result of a routing selection.

    Attributes:
      selected_subagent: name of the chosen subagent, or None on fallback.
      score: number of matched keyword tokens (0 on fallback).
      matched_topics: sorted list of tokens that contributed to the score.
      fallback_used: True when no subagent exceeded score=0.
    """

    selected_subagent: str | None
    score: int
    matched_topics: list[str] = field(default_factory=list)
    fallback_used: bool = False

    @classmethod
    def fallback(cls) -> RoutingDecision:
        """Return the canonical fallback decision (no subagent matched)."""
        return cls(
            selected_subagent=None,
            score=0,
            matched_topics=[],
            fallback_used=True,
        )


# ---------------------------------------------------------------------------
# Pure routing function
# ---------------------------------------------------------------------------


def _tokenise(text: str) -> set[str]:
    """Extract lowercase word tokens from text using Unicode-aware regex.

    Params:
      text — arbitrary user message string.
    Returns: set of lowercase token strings (empty set for empty text).
    """
    return set(re.findall(r"\w+", text.lower(), flags=re.UNICODE))


def select_subagent(
    message: str,
    subagents: list[AgentSpec],
) -> RoutingDecision:
    """Select the best subagent for the given message via keyword overlap.

    Algorithm: for each subagent in `subagents` compute the intersection
    cardinality between the message token set and the subagent's
    normalised `subagent_topics` set.  The subagent with the highest score
    is selected.  Tie-break: prefer larger topic list, then name ascending.

    Business rule (ADR-002): "El supervisor enruta mensajes del usuario al
    subagente cuyo `subagent_topics` tenga mayor solapamiento de palabras clave."

    NOTE: `message` is NOT logged in full (may contain PII in production).
    Only `message_token_count` is emitted.

    Params:
      message   — user message to route (any string, including empty).
      subagents — list of AgentSpec with `subagent_topics` populated.

    Returns: RoutingDecision with the winning subagent name, score and
             matched topics (or fallback if no overlap or empty inputs).

    Errors: does not raise — always returns a RoutingDecision.
    """
    _logger.debug(
        "agents.routing.select.before",
        message_token_count=len(_tokenise(message)) if message else 0,
        subagent_count=len(subagents),
    )

    if not message or not subagents:
        decision = RoutingDecision.fallback()
        _logger.debug(
            "agents.routing.select.after",
            selected_subagent=None,
            score=0,
            matched_topics_count=0,
            fallback_used=True,
        )
        return decision

    message_tokens: set[str] = _tokenise(message)
    best: RoutingDecision = RoutingDecision.fallback()
    best_agent: AgentSpec | None = None

    for spec in subagents:
        if not spec.subagent_topics:
            continue
        topic_set = {t.lower() for t in spec.subagent_topics}
        matched = sorted(message_tokens & topic_set)
        score = len(matched)

        if score > best.score:
            best = RoutingDecision(
                selected_subagent=spec.name,
                score=score,
                matched_topics=matched,
                fallback_used=False,
            )
            best_agent = spec
        elif score == best.score and score > 0:
            # Tie-break: prefer the subagent with more topics (broader coverage).
            # Secondary: alphabetical name ascending for determinism.
            # `spec.subagent_topics` is not None here (checked by `if not spec.subagent_topics`
            # above and score > 0 ensures a non-empty intersection was found).
            current_topics = len(spec.subagent_topics)
            # `best_agent` was set in a prior iteration (score == best.score > 0 guarantees it).
            _best_topics = best_agent.subagent_topics if best_agent else None
            best_topics = len(_best_topics) if _best_topics else 0
            if current_topics > best_topics or (
                current_topics == best_topics and spec.name < (best.selected_subagent or "")
            ):
                best = RoutingDecision(
                    selected_subagent=spec.name,
                    score=score,
                    matched_topics=matched,
                    fallback_used=False,
                )
                best_agent = spec

    _logger.debug(
        "agents.routing.select.after",
        selected_subagent=best.selected_subagent,
        score=best.score,
        matched_topics_count=len(best.matched_topics),
        fallback_used=best.fallback_used,
    )
    return best
