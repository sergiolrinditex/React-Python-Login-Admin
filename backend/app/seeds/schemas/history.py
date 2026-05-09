"""
Pydantic models for the 'history' namespace.

Slice: P00-S02-T003 — Seed data and reset verification bundle
Phase: P00 — Scaffold + Design System

Covers data/verification/history/conversations.json.
At least 2 conversations for the employee_primary user (J102 requirement).

Dependencies:
  - pydantic 2.12.5
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ConversationMessageSeed(BaseModel):
    """A single message within a seed conversation.

    Params:
      role    — 'user' or 'assistant'.
      content — message body text.
    """

    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"] = Field(...)
    content: str = Field(..., min_length=1, max_length=4000)


class ConversationSeed(BaseModel):
    """Seed record for a conversation history entry.

    Purpose: pre-populate conversation history for J102 (history + language).
    Params:
      user_email      — references the UserSeed.email of the owner.
      title           — conversation title shown in history sidebar.
      language        — UI language in which the conversation was started.
      messages        — list of message turns (at least 1).
      collection_name — optional collection context.
    Errors: ValidationError if messages is empty.
    """

    model_config = ConfigDict(extra="forbid")

    user_email: str = Field(..., description="Owner user email.")
    title: str = Field(..., min_length=1, max_length=300)
    language: Literal["es", "en", "fr"] = Field("es")
    messages: list[ConversationMessageSeed] = Field(..., min_length=1)
    collection_name: str | None = Field(None, description="Optional RAG collection context.")


class ConversationListSeed(BaseModel):
    """Wrapper for a list of conversation seeds.

    At least 2 conversations required (J102 journey contract).
    """

    model_config = ConfigDict(extra="forbid")

    conversations: list[ConversationSeed] = Field(..., min_length=2)
