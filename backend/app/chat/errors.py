"""
Hilo People — Chat domain errors.

Slice:  P02-S03-T001 — Chat conversation CRUD endpoints
Phase:  P02 Core Features (the motor)
Purpose: Typed domain errors for the chat bounded context. These errors are
         raised by services and repositories and caught by routers to emit
         the correct HTTP status and error code. Never expose raw exceptions
         to the HTTP layer.

Error hierarchy:
  ChatError (base)
    ConversationNotFoundError  → 404 CHAT_CONVERSATION_NOT_FOUND
    ConversationForbiddenError → 403 CHAT_CONVERSATION_FORBIDDEN
    CursorInvalidError         → 400 CHAT_CURSOR_INVALID

Source refs:
  - TECHNICAL_GUIDE §6.2 rows 264-266 (error codes per endpoint)
  - task pack P02-S03-T001 §F.5 (ownership semantics 404/403)
  - task pack P02-S03-T001 §G (pagination contract)
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
