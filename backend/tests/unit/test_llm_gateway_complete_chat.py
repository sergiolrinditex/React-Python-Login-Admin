"""
Hilo People — Unit tests for LLM gateway complete_chat helper.

Slice:  P02-S03-T008 — Bug fix: complete_chat.py uses non-existent SDK provider
                       'litellm/<model>' (identical root cause to P02-S03-T006)
Phase:  P02 Core Features (the motor)
Purpose: Pin the fix: complete_chat must call _compose_sdk_model_args (not inline
         f-string) so provider_type='litellm' produces 'openai/<model_id>' +
         api_base=<proxy_url>, matching the P02-S03-T006 fix for stream_chat.

         All LiteLLM SDK calls (litellm.acompletion, litellm.completion_cost) are
         mocked at the network boundary only — every other layer (result extraction,
         error translation, cost computation, CompletionResult construction) is real.

         Test classes:
           - TestCompleteChatUsesComposeHelper  (acceptance #2 — MANDATORY)
           - TestCompleteChatHappyPath          (recommended — result correctness)
           - TestCompleteChatErrorTranslation   (recommended — error wrapping)
           - TestCompleteChatUnsupportedProviderRaises  (explicit fail path)

Source refs:
  - task pack P02-S03-T008 §Test plan
  - 01-non-negotiables.md §Tests are REAL (mock only external 3rd-party APIs)
  - 01-non-negotiables.md §AI/ML libraries (acceptable mock: litellm boundary)
  - test_llm_gateway_litellm_client.py T17 (mirror pattern)
"""

from __future__ import annotations

import asyncio
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.admin_ai import AiModel, AiProvider
from app.llm_gateway.complete_chat import CompletionResult, complete_chat
from app.llm_gateway.errors import (
    LiteLLMError,
    LiteLLMTimeoutError,
    ModelTestFailedError,
)


# ---------------------------------------------------------------------------
# Fixtures: minimal ORM mocks (no DB needed for unit tests)
# Copied from test_llm_gateway_litellm_client.py — tests remain self-contained.
# ---------------------------------------------------------------------------


def _mock_chat_model(model_id: str = "gpt-4o-mini") -> AiModel:
    """Build a minimal AiModel mock for unit tests."""
    m = MagicMock(spec=AiModel)
    m.id = uuid.uuid4()
    m.model_id = model_id
    m.model_type = "chat"
    m.pricing = {"input_cost_per_token": 0.000005, "output_cost_per_token": 0.000015}
    return m


def _mock_provider(
    provider_type: str = "litellm", base_url: str | None = "http://localhost:4000"
) -> AiProvider:
    """Build a minimal AiProvider mock for unit tests."""
    p = MagicMock(spec=AiProvider)
    p.id = uuid.uuid4()
    p.provider_type = provider_type
    p.base_url = base_url
    return p


def _make_mock_response(
    content: str = "Hello from LLM",
    model: str = "gpt-4o-mini",
    prompt_tokens: int = 10,
    completion_tokens: int = 5,
    finish_reason: str = "stop",
) -> MagicMock:
    """Build a minimal LiteLLM ModelResponse-style mock for acompletion."""
    resp = MagicMock()
    # choices[0].message.content
    resp.choices = [MagicMock()]
    resp.choices[0].message = MagicMock()
    resp.choices[0].message.content = content
    resp.choices[0].finish_reason = finish_reason
    # usage
    resp.usage = MagicMock()
    resp.usage.prompt_tokens = prompt_tokens
    resp.usage.completion_tokens = completion_tokens
    resp.usage.total_tokens = prompt_tokens + completion_tokens
    # model
    resp.model = model
    return resp


# ---------------------------------------------------------------------------
# T01–T02: TestCompleteChatUsesComposeHelper (MANDATORY — acceptance #2)
# ---------------------------------------------------------------------------


class TestCompleteChatUsesComposeHelper:
    """Pin that complete_chat uses _compose_sdk_model_args (D-T008-COMPOSE-HELPER).

    These tests verify the exact kwarg sent to litellm.acompletion, ensuring
    provider_type='litellm' → model='openai/<model_id>' + api_base=<proxy_url>,
    NOT the old (buggy) 'litellm/<model_id>'.
    Mirror of T17 in test_llm_gateway_litellm_client.py for the non-streaming path.
    """

    def test_complete_chat_uses_compose_helper_for_litellm_provider(self):
        """provider_type='litellm' → acompletion called with model='openai/gpt-4o-mini' + api_base.

        Root cause fix verification (acceptance criterion #2):
          Old (BUGGY): model='litellm/gpt-4o-mini' → SDK BadRequestError
          New (FIXED): model='openai/gpt-4o-mini'  + api_base='http://localhost:4000'
        """
        mock_resp = _make_mock_response(content="hi", model="gpt-4o-mini")

        async def _run():
            with patch(
                "litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp
            ) as mock_comp:
                with patch("litellm.completion_cost", return_value=0.000123):
                    result = await complete_chat(
                        model=_mock_chat_model(model_id="gpt-4o-mini"),
                        provider=_mock_provider(
                            provider_type="litellm", base_url="http://localhost:4000"
                        ),
                        api_key="test-bearer",
                        prompt="hello from T008 test",
                        request_id="req-t008-t01",
                    )
            # Verify the model kwarg sent to acompletion (the critical assertion)
            call_kwargs = mock_comp.call_args.kwargs
            assert call_kwargs["model"] == "openai/gpt-4o-mini", (
                f"Expected 'openai/gpt-4o-mini', got '{call_kwargs['model']}'. "
                "This pins fix D-T008-COMPOSE-HELPER: complete_chat must NOT compose "
                "model_str inline — it must use _compose_sdk_model_args."
            )
            assert call_kwargs.get("api_base") == "http://localhost:4000", (
                "provider_type='litellm' must forward api_base to the proxy URL"
            )
            assert call_kwargs.get("api_key") == "test-bearer"
            assert isinstance(result, CompletionResult)

        asyncio.run(_run())

    def test_complete_chat_openai_provider_no_base_url(self):
        """provider_type='openai' without base_url → model='openai/<id>', no api_base kwarg.

        Sanity check: standard OpenAI provider must NOT send api_base (would break routing).
        """
        mock_resp = _make_mock_response(content="direct openai response")

        async def _run():
            with patch(
                "litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp
            ) as mock_comp:
                with patch("litellm.completion_cost", return_value=0.0):
                    await complete_chat(
                        model=_mock_chat_model(model_id="gpt-4o"),
                        provider=_mock_provider(provider_type="openai", base_url=None),
                        api_key="sk-openai-test",
                        prompt="test prompt",
                        request_id="req-t008-t02",
                    )
            call_kwargs = mock_comp.call_args.kwargs
            assert call_kwargs["model"] == "openai/gpt-4o"
            assert "api_base" not in call_kwargs, (
                "Direct OpenAI provider with no base_url must NOT include api_base"
            )

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# T03: TestCompleteChatHappyPath (recommended — result correctness)
# ---------------------------------------------------------------------------


class TestCompleteChatHappyPath:
    """Verify CompletionResult fields are populated correctly from the mock response."""

    def test_complete_chat_returns_completion_result_with_tokens_and_cost(self):
        """All CompletionResult fields populated from mock response + cost mock."""
        mock_resp = _make_mock_response(
            content="Test answer from the LLM",
            model="gpt-4o-mini",
            prompt_tokens=20,
            completion_tokens=8,
            finish_reason="stop",
        )

        async def _run():
            with patch(
                "litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp
            ):
                with patch("litellm.completion_cost", return_value=0.000123):
                    result = await complete_chat(
                        model=_mock_chat_model(model_id="gpt-4o-mini"),
                        provider=_mock_provider(
                            provider_type="litellm", base_url="http://localhost:4000"
                        ),
                        api_key="test-bearer",
                        prompt="What is the capital of France?",
                        max_tokens=128,
                        request_id="req-t008-t03",
                    )
            assert result.text == "Test answer from the LLM"
            assert result.prompt_tokens == 20
            assert result.completion_tokens == 8
            assert result.total_tokens == 28
            assert result.cost_usd == pytest.approx(0.000123)
            assert result.latency_ms >= 0
            assert result.finish_reason == "stop"
            # model_used comes from response.model (mock returns "gpt-4o-mini")
            assert result.model_used == "gpt-4o-mini"

        asyncio.run(_run())

    def test_complete_chat_cost_falls_back_to_pricing_jsonb(self):
        """When litellm.completion_cost returns 0.0, fallback to pricing JSONB estimate."""
        mock_resp = _make_mock_response(
            content="fallback cost path",
            prompt_tokens=100,
            completion_tokens=50,
        )

        async def _run():
            with patch(
                "litellm.acompletion", new_callable=AsyncMock, return_value=mock_resp
            ):
                # completion_cost returns 0.0 → triggers JSONB fallback
                with patch("litellm.completion_cost", return_value=0.0):
                    result = await complete_chat(
                        model=_mock_chat_model(model_id="gpt-4o-mini"),
                        provider=_mock_provider(
                            provider_type="litellm", base_url="http://localhost:4000"
                        ),
                        api_key="test-bearer",
                        prompt="test fallback",
                        request_id="req-t008-t04",
                    )
            # pricing: 100 * 0.000005 + 50 * 0.000015 = 0.0005 + 0.00075 = 0.00125
            assert result.cost_usd is not None
            assert result.cost_usd > 0.0

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# T04–T05: TestCompleteChatErrorTranslation (recommended — error wrapping)
# ---------------------------------------------------------------------------


class TestCompleteChatErrorTranslation:
    """Verify litellm exceptions are wrapped into typed domain errors."""

    def test_litellm_timeout_raises_litellm_timeout_error(self):
        """litellm.Timeout → LiteLLMTimeoutError raised (status='timeout').

        litellm.Timeout requires (message, model, llm_provider) positional args
        per litellm v1.83.14 constructor signature.
        """
        import litellm as _litellm

        async def _run():
            with patch(
                "litellm.acompletion",
                new_callable=AsyncMock,
                side_effect=_litellm.Timeout(  # type: ignore[attr-defined]
                    "request timed out", "gpt-4o-mini", "openai"
                ),
            ):
                with pytest.raises(LiteLLMTimeoutError):
                    await complete_chat(
                        model=_mock_chat_model(),
                        provider=_mock_provider(),
                        api_key="test-bearer",
                        prompt="timeout test",
                        request_id="req-t008-t05",
                    )

        asyncio.run(_run())

    def test_generic_exception_raises_model_test_failed_error(self):
        """Any non-timeout exception → ModelTestFailedError with status='failure'."""

        async def _run():
            with patch(
                "litellm.acompletion",
                new_callable=AsyncMock,
                side_effect=RuntimeError("unexpected SDK failure"),
            ):
                with pytest.raises(ModelTestFailedError) as exc_info:
                    await complete_chat(
                        model=_mock_chat_model(),
                        provider=_mock_provider(),
                        api_key="test-bearer",
                        prompt="error test",
                        request_id="req-t008-t06",
                    )
            assert exc_info.value.status == "failure"

        asyncio.run(_run())


# ---------------------------------------------------------------------------
# T06: TestCompleteChatUnsupportedProviderRaises
# ---------------------------------------------------------------------------


class TestCompleteChatUnsupportedProviderRaises:
    """Unknown provider_type raises LiteLLMError BEFORE the SDK is called."""

    def test_unsupported_provider_type_raises_litellm_error_via_helper(self):
        """provider_type='nonexistent' → LiteLLMError before acompletion is invoked.

        The helper _compose_sdk_model_args raises LiteLLMError on unknown types.
        This test verifies complete_chat propagates it and does NOT call the SDK.
        """

        async def _run():
            with patch("litellm.acompletion", new_callable=AsyncMock) as mock_comp:
                with pytest.raises(LiteLLMError) as exc_info:
                    await complete_chat(
                        model=_mock_chat_model(model_id="some-model"),
                        provider=_mock_provider(
                            provider_type="nonexistent_provider", base_url=None
                        ),
                        api_key="test-bearer",
                        prompt="should not reach SDK",
                        request_id="req-t008-t07",
                    )
            # SDK must NOT be called (helper raises before kwargs are assembled)
            mock_comp.assert_not_called()
            assert "nonexistent_provider" in str(exc_info.value).lower()

        asyncio.run(_run())
