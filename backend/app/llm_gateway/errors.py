"""
Hilo People — LLM gateway typed errors.

Slice:  P02-S03-T002 — Chat streaming endpoint (new module §K-LLM-GATEWAY)
Phase:  P02 Core Features (the motor)
Purpose: Typed domain errors for the LLM gateway layer. These wrap raw
         litellm exceptions so callers depend only on typed errors from
         this module and not on litellm internals.

Error hierarchy:
  LlmGatewayError (base)
    LiteLLMError          — any litellm invocation error
    LiteLLMTimeoutError   — connect / inference timeout
    EmbeddingError        — failure in embed_query()

Source refs:
  - task pack P02-S03-T002 §E.3 (gateway API contract)
  - task pack P02-S03-T002 §F.2 §K-LLM-GATEWAY
  - 01-non-negotiables.md §Error handling (typed domain errors)
"""

from __future__ import annotations


class LlmGatewayError(Exception):
    """Base class for all LLM gateway errors."""

    code: str = "LLM_GATEWAY_ERROR"
    message: str = "LLM gateway error"


class LiteLLMError(LlmGatewayError):
    """Raised when a litellm.acompletion or related call fails.

    Wraps any litellm / provider exception so callers see only typed errors.

    Attributes:
        code: Machine-readable error code.
        message: Description with context (no API key, no prompt content).
        cause: The original exception (for logging / re-raise chaining).
    """

    code = "LITELLM_ERROR"

    def __init__(self, message: str = "LiteLLM invocation failed.", cause: Exception | None = None) -> None:
        """Initialize with a message and optional underlying cause.

        Args:
            message: Human-readable error description.
            cause: Original exception that triggered this error.
        """
        self.message = message
        self.cause = cause
        super().__init__(message)


class LiteLLMTimeoutError(LiteLLMError):
    """Raised when litellm times out (connect or per-chunk inactivity).

    Subclasses LiteLLMError so callers can catch either.

    Attributes:
        code: Machine-readable error code.
    """

    code = "LITELLM_TIMEOUT"

    def __init__(self, message: str = "LiteLLM request timed out.", cause: Exception | None = None) -> None:
        """Initialize with a message and optional underlying cause.

        Args:
            message: Human-readable timeout description.
            cause: Original exception.
        """
        super().__init__(message=message, cause=cause)


class EmbeddingError(LlmGatewayError):
    """Raised when embed_query() fails to produce a valid embedding vector.

    Attributes:
        code: Machine-readable error code.
        message: Description (no API key, no input text content).
        cause: Original exception.
    """

    code = "EMBEDDING_ERROR"

    def __init__(self, message: str = "Embedding generation failed.", cause: Exception | None = None) -> None:
        """Initialize with a message and optional underlying cause.

        Args:
            message: Human-readable error description.
            cause: Original exception.
        """
        self.message = message
        self.cause = cause
        super().__init__(message)


# WRITE_SET_DRIFT §D-LLMG-ERRORS (P02-S05-T002): ModelTestFailedError for the
# non-streaming admin model-test endpoint. Maps to HTTP 502 AI_PROVIDER_TEST_FAILED.
class ModelTestFailedError(LlmGatewayError):
    """Raised when a non-streaming model test invocation fails at the LiteLLM boundary.

    Used by complete_chat.py to wrap any litellm exception (except timeout) so
    the admin/model_test router can map it to HTTP 502 AI_PROVIDER_TEST_FAILED
    without leaking litellm internals or provider error messages.

    Attributes:
        code: Machine-readable error code.
        message: Description (no API key, no prompt content).
        cause: Original exception.
        status: ai_model_tests status value — 'failure' or 'timeout'.
    """

    code = "AI_PROVIDER_TEST_FAILED"
    status: str = "failure"

    def __init__(
        self,
        message: str = "Model test invocation failed.",
        cause: Exception | None = None,
        status: str = "failure",
    ) -> None:
        """Initialize with a message, optional cause and status.

        Args:
            message: Human-readable error description (no secrets).
            cause:   Original exception.
            status:  'failure' | 'timeout' for ai_model_tests.status column.
        """
        self.message = message
        self.cause = cause
        self.status = status
        super().__init__(message)
