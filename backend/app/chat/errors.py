"""
Hilo People — Chat domain errors.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints (initial)
        P02-S03-T002 — Chat streaming endpoint (extended: stream + upstream + model errors)
Phase:  P02 Core Features (the motor)
Purpose: Typed domain errors for the chat bounded context. These errors are
         raised by services and repositories and caught by routers to emit
         the correct HTTP status and error code. Never expose raw exceptions
         to the HTTP layer.

Error hierarchy:
  ChatError (base)
    ConversationNotFoundError    → 404 CHAT_CONVERSATION_NOT_FOUND
    ConversationForbiddenError   → 403 CHAT_CONVERSATION_FORBIDDEN
    CursorInvalidError           → 400 CHAT_CURSOR_INVALID
    ChatStreamBadRequestError    → 400 CHAT_STREAM_BAD_REQUEST   (P02-S03-T002)
    ChatStreamUpstreamError      → 502 CHAT_STREAM_UPSTREAM_FAILED (P02-S03-T002)
    NoActiveChatModelError       → 502 AI_PROVIDER_NOT_CONFIGURED  (P02-S03-T002)

Source refs:
  - TECHNICAL_GUIDE §6.2 rows 264-266 (error codes per endpoint)
  - task pack P02-S03-T001 §F.5 (ownership semantics 404/403)
  - task pack P02-S03-T001 §G (pagination contract)
  - task pack P02-S03-T002 §C (stream error codes table)
"""

from __future__ import annotations


class ChatError(Exception):
    """Base class for all chat domain errors.

    All chat errors carry a machine-readable code for the HTTP envelope.
    """

    code: str = "CHAT_ERROR"
    message: str = "Chat error"


class ConversationNotFoundError(ChatError):
    """Raised when a conversation_id does not exist in the DB.

    Maps to HTTP 404 CHAT_CONVERSATION_NOT_FOUND.

    Attributes:
        code: Machine-readable error code.
        message: Debug message (not displayed to users).
    """

    code = "CHAT_CONVERSATION_NOT_FOUND"
    message = "Conversation not found."


class ConversationForbiddenError(ChatError):
    """Raised when a conversation exists but the requesting user is not the owner.

    Maps to HTTP 403 CHAT_CONVERSATION_FORBIDDEN.

    Attributes:
        code: Machine-readable error code.
        message: Debug message (not displayed to users).
    """

    code = "CHAT_CONVERSATION_FORBIDDEN"
    message = "Access to this conversation is not allowed."


class CursorInvalidError(ChatError):
    """Raised when the pagination cursor cannot be decoded or parsed.

    Maps to HTTP 400 CHAT_CURSOR_INVALID.

    Attributes:
        code: Machine-readable error code.
        message: Debug message with the reason.
    """

    code = "CHAT_CURSOR_INVALID"

    def __init__(self, reason: str = "Invalid or malformed pagination cursor.") -> None:
        """Initialize with an optional reason string.

        Args:
            reason: Human-readable reason for the parse failure.
        """
        self.message = reason
        super().__init__(reason)


class ChatStreamBadRequestError(ChatError):
    """Raised when the stream request body is invalid (empty/missing message, >8000 chars).

    Maps to HTTP 400 CHAT_STREAM_BAD_REQUEST.
    Raised BEFORE streaming headers are sent (error can be a standard JSON envelope).

    Attributes:
        code: Machine-readable error code.
        message: Debug message with reason.
    """

    code = "CHAT_STREAM_BAD_REQUEST"

    def __init__(self, reason: str = "Invalid stream request body.") -> None:
        """Initialize with an optional reason string.

        Args:
            reason: Human-readable reason (e.g. 'message field empty').
        """
        self.message = reason
        super().__init__(reason)


class ChatStreamUpstreamError(ChatError):
    """Raised when the LLM provider fails BEFORE streaming starts (fatal 502).

    Maps to HTTP 502 CHAT_STREAM_UPSTREAM_FAILED.
    Raised BEFORE streaming headers are sent (error can be a standard JSON envelope).

    Attributes:
        code: Machine-readable error code.
        message: Debug message with upstream error context.
    """

    code = "CHAT_STREAM_UPSTREAM_FAILED"

    def __init__(self, reason: str = "LLM upstream provider failed.") -> None:
        """Initialize with an optional reason string.

        Args:
            reason: Human-readable reason (logged internally, not returned to user).
        """
        self.message = reason
        super().__init__(reason)


class NoActiveChatModelError(ChatError):
    """Raised when no active chat model (is_default=True, enabled=True, model_type='chat') exists.

    Maps to HTTP 502 AI_PROVIDER_NOT_CONFIGURED.
    This is a configuration/admin issue, not a user error.

    Attributes:
        code: Machine-readable error code.
        message: Debug message.
    """

    code = "AI_PROVIDER_NOT_CONFIGURED"
    message = "No active chat model configured. Contact your administrator."
