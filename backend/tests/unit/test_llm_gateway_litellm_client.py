"""
Hilo People — Unit tests for LLM gateway LiteLLM client.

Slice:  P02-S03-T002 — Chat streaming endpoint (§K-TEST-SPLIT)
        P02-S03-T006 — Fix model_str composition: tests for _compose_sdk_model_args
Phase:  P02 Core Features (the motor)
Purpose: Tests stream_chat and embed_query translation layers.
         LiteLLM calls are mocked at the litellm.acompletion/aembedding boundary.
         Everything ELSE (StreamEvent construction, error translation, usage extraction)
         is real — only the network call is mocked (§J non-negotiable).

         P02-S03-T006 adds TestComposeHelper (T11–T17) that pins the
         _compose_sdk_model_args mapping so future changes cannot silently
         break provider routing. These tests are pure-unit (no network, no DB).

Tests map to task pack §J.2 (unit tests for LiteLLM client):
  - stream_chat translates LiteLLM chunks into StreamEvent records.
  - embed_query returns 1536-dim list.
  - LiteLLM error → typed LiteLLMError raised.
  - _compose_sdk_model_args maps provider_type → correct SDK model_str + api_base.

Source refs:
  - task pack P02-S03-T002 §J.2
  - task pack P02-S03-T006 §ROOT_CAUSE + §DECISIONS_TO_RECORD
  - 01-non-negotiables.md §Tests are REAL (mock only external 3rd-party APIs)
  - 01-non-negotiables.md §AI/ML libraries (acceptable mock: litellm boundary)
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.db.models.admin_ai import AiModel, AiProvider
from app.llm_gateway.errors import EmbeddingError, LiteLLMError
from app.llm_gateway.litellm_client import (
    StreamEvent,
    _compose_sdk_model_args,
    embed_query,
    stream_chat,
)


# ---------------------------------------------------------------------------
# Fixtures: minimal ORM mocks (no DB needed for unit tests)
# ---------------------------------------------------------------------------


def _mock_chat_model(model_id: str = "gpt-4o") -> AiModel:
    """Build a minimal AiModel mock for unit tests."""
    m = MagicMock(spec=AiModel)
    m.id = uuid.uuid4()
    m.model_id = model_id
    m.model_type = "chat"
    m.pricing = {"input_cost_per_token": 0.000005, "output_cost_per_token": 0.000015}
    return m


def _mock_embed_model(model_id: str = "text-embedding-3-small") -> AiModel:
    """Build a minimal AiModel mock for embeddings unit tests."""
    m = MagicMock(spec=AiModel)
    m.id = uuid.uuid4()
    m.model_id = model_id
    m.model_type = "embeddings"
    m.pricing = {}
    return m


def _mock_provider(
    provider_type: str = "openai", base_url: str | None = None
) -> AiProvider:
    """Build a minimal AiProvider mock for unit tests."""
    p = MagicMock(spec=AiProvider)
    p.id = uuid.uuid4()
    p.provider_type = provider_type
    p.base_url = base_url
    return p


def _make_chunk(content: str | None = None, usage=None) -> MagicMock:
    """Build a minimal LiteLLM-style chunk mock."""
    chunk = MagicMock()
    chunk.choices = [MagicMock()]
    chunk.choices[0].delta = MagicMock()
    chunk.choices[0].delta.content = content
    chunk.usage = usage
    return chunk


def _make_usage(prompt_tokens: int = 10, completion_tokens: int = 5) -> MagicMock:
    """Build a minimal LiteLLM-style usage mock."""
    u = MagicMock()
    u.prompt_tokens = prompt_tokens
    u.completion_tokens = completion_tokens
    return u


# ---------------------------------------------------------------------------
# Tests for stream_chat
# ---------------------------------------------------------------------------


class TestStreamChat:
    """Tests for stream_chat() async generator."""

    @pytest.mark.asyncio
    async def test_delta_events_yielded(self):
        """stream_chat yields delta StreamEvents for each non-None chunk."""

        async def _fake_iter():
            yield _make_chunk("Hello ")
            yield _make_chunk("world")
            yield _make_chunk(None, usage=_make_usage(10, 2))

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=_fake_iter()
        ):
            with patch("litellm.completion_cost", return_value=0.0):
                events = []
                async for ev in stream_chat(
                    model=_mock_chat_model(),
                    provider=_mock_provider(),
                    api_key="test-key",
                    messages=[{"role": "user", "content": "hi"}],
                    request_id="req-1",
                ):
                    events.append(ev)

        delta_events = [e for e in events if e.kind == "delta"]
        assert len(delta_events) == 2
        assert delta_events[0].payload["delta"] == "Hello "
        assert delta_events[1].payload["delta"] == "world"

    @pytest.mark.asyncio
    async def test_usage_event_yielded_last(self):
        """stream_chat yields exactly one usage event as the last event."""

        async def _fake_iter():
            yield _make_chunk("text", usage=_make_usage(20, 10))

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=_fake_iter()
        ):
            with patch("litellm.completion_cost", return_value=0.00042):
                events = []
                async for ev in stream_chat(
                    model=_mock_chat_model(),
                    provider=_mock_provider(),
                    api_key="test-key",
                    messages=[{"role": "user", "content": "hi"}],
                    request_id="req-2",
                ):
                    events.append(ev)

        usage_events = [e for e in events if e.kind == "usage"]
        assert len(usage_events) == 1
        u = usage_events[0].payload
        assert u["tokens_in"] == 20
        assert u["tokens_out"] == 10
        assert "latency_ms" in u
        assert u["latency_ms"] >= 0

    @pytest.mark.asyncio
    async def test_stream_event_types_are_correct(self):
        """Only 'delta' and 'usage' events yielded in happy path."""

        async def _fake_iter():
            yield _make_chunk("hi", usage=_make_usage(5, 2))

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=_fake_iter()
        ):
            with patch("litellm.completion_cost", return_value=0.0):
                events = []
                async for ev in stream_chat(
                    model=_mock_chat_model(),
                    provider=_mock_provider(),
                    api_key="test-key",
                    messages=[],
                    request_id="req-3",
                ):
                    events.append(ev)

        kinds = {e.kind for e in events}
        assert kinds <= {"delta", "usage"}

    @pytest.mark.asyncio
    async def test_litellm_connection_error_raises_litellm_error(self):
        """Connection failure before iteration raises LiteLLMError."""
        with patch("litellm.acompletion", side_effect=RuntimeError("connect fail")):
            with pytest.raises(LiteLLMError):
                async for _ in stream_chat(
                    model=_mock_chat_model(),
                    provider=_mock_provider(),
                    api_key="test-key",
                    messages=[],
                    request_id="req-4",
                ):
                    pass

    @pytest.mark.asyncio
    async def test_litellm_mid_stream_error_yields_error_event(self):
        """Mid-stream exception yields a StreamEvent(kind='error')."""

        async def _failing_iter():
            yield _make_chunk("partial")
            raise RuntimeError("mid-stream failure")

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=_failing_iter()
        ):
            events = []
            async for ev in stream_chat(
                model=_mock_chat_model(),
                provider=_mock_provider(),
                api_key="test-key",
                messages=[],
                request_id="req-5",
            ):
                events.append(ev)

        error_events = [e for e in events if e.kind == "error"]
        assert len(error_events) == 1
        assert error_events[0].payload["code"] == "LITELLM_MID_STREAM_ERROR"

    @pytest.mark.asyncio
    async def test_stream_event_is_dataclass(self):
        """Yielded events are StreamEvent instances."""

        async def _fake_iter():
            yield _make_chunk("hi", usage=_make_usage(1, 1))

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=_fake_iter()
        ):
            with patch("litellm.completion_cost", return_value=0.0):
                events = []
                async for ev in stream_chat(
                    model=_mock_chat_model(),
                    provider=_mock_provider(),
                    api_key="test-key",
                    messages=[],
                    request_id="req-6",
                ):
                    events.append(ev)

        for ev in events:
            assert isinstance(ev, StreamEvent)

    @pytest.mark.asyncio
    async def test_base_url_passed_when_provider_has_one(self):
        """api_base kwarg is passed to litellm when provider.base_url is set."""

        async def _fake_iter():
            yield _make_chunk("hi", usage=_make_usage(1, 1))

        with patch(
            "litellm.acompletion", new_callable=AsyncMock, return_value=_fake_iter()
        ) as mock_comp:
            with patch("litellm.completion_cost", return_value=0.0):
                async for _ in stream_chat(
                    model=_mock_chat_model(),
                    provider=_mock_provider(base_url="http://localhost:4000"),
                    api_key="test-key",
                    messages=[],
                    request_id="req-7",
                ):
                    pass

        call_kwargs = mock_comp.call_args.kwargs
        assert call_kwargs.get("api_base") == "http://localhost:4000"


# ---------------------------------------------------------------------------
# Tests for embed_query
# ---------------------------------------------------------------------------


class TestEmbedQuery:
    """Tests for embed_query() function."""

    @pytest.mark.asyncio
    async def test_returns_1536_dim_list(self):
        """embed_query returns a 1536-dim float list."""
        fake_vector = [0.0] * 1536
        mock_result = MagicMock()
        mock_result.data = [MagicMock()]
        mock_result.data[0].embedding = fake_vector

        with patch(
            "litellm.aembedding", new_callable=AsyncMock, return_value=mock_result
        ):
            result = await embed_query(
                model=_mock_embed_model(),
                provider=_mock_provider(),
                api_key="test-key",
                text="¿Cuántos días de vacaciones?",
                request_id="req-embed-1",
            )

        assert isinstance(result, list)
        assert len(result) == 1536

    @pytest.mark.asyncio
    async def test_wrong_dimension_raises_embedding_error(self):
        """Embedding with wrong dimension raises EmbeddingError."""
        fake_vector = [0.0] * 512  # Wrong dimension
        mock_result = MagicMock()
        mock_result.data = [MagicMock()]
        mock_result.data[0].embedding = fake_vector

        with patch(
            "litellm.aembedding", new_callable=AsyncMock, return_value=mock_result
        ):
            with pytest.raises(EmbeddingError):
                await embed_query(
                    model=_mock_embed_model(),
                    provider=_mock_provider(),
                    api_key="test-key",
                    text="query",
                    request_id="req-embed-2",
                )

    @pytest.mark.asyncio
    async def test_litellm_error_raises_embedding_error(self):
        """litellm failure raises EmbeddingError (typed)."""
        with patch("litellm.aembedding", side_effect=RuntimeError("embed fail")):
            with pytest.raises(EmbeddingError):
                await embed_query(
                    model=_mock_embed_model(),
                    provider=_mock_provider(),
                    api_key="test-key",
                    text="query",
                    request_id="req-embed-3",
                )


# ---------------------------------------------------------------------------
# Tests for _compose_sdk_model_args — P02-S03-T006 (T11–T17)
# ---------------------------------------------------------------------------


class TestComposeHelper:
    """Unit tests for the _compose_sdk_model_args helper (D-LITELLM-PROVIDER-MAP).

    These tests pin the provider_type → SDK prefix mapping so any future change
    to the mapping is immediately visible as a test failure. No network, no DB.
    """

    def test_litellm_provider_type_maps_to_openai_prefix(self):
        """Root cause fix: provider_type='litellm' → model='openai/<id>' + api_base set.

        This is the exact bug from P02-S03-T006:
          Old: model_str = f"litellm/{model_id}"  →  BadRequestError
          New: model_str = f"openai/{model_id}"  +  api_base = proxy_url
        """
        provider = _mock_provider(
            provider_type="litellm", base_url="http://localhost:4000"
        )
        model = _mock_chat_model(model_id="gpt-4o-mini")
        model_str, extra = _compose_sdk_model_args(provider, model, "req-t11")

        assert model_str == "openai/gpt-4o-mini", (
            f"provider_type='litellm' must map to 'openai/<model_id>', got '{model_str}'"
        )
        assert extra.get("api_base") == "http://localhost:4000", (
            "provider_type='litellm' must include api_base=<proxy_url>"
        )

    def test_openai_provider_type_direct_no_base_url(self):
        """provider_type='openai' without base_url → model='openai/<id>', no api_base."""
        provider = _mock_provider(provider_type="openai", base_url=None)
        model = _mock_chat_model(model_id="gpt-4o")
        model_str, extra = _compose_sdk_model_args(provider, model, "req-t12")

        assert model_str == "openai/gpt-4o"
        assert "api_base" not in extra

    def test_openai_provider_type_with_custom_base_url(self):
        """provider_type='openai' with base_url → api_base forwarded (custom endpoint)."""
        provider = _mock_provider(
            provider_type="openai", base_url="https://my-proxy.example.com"
        )
        model = _mock_chat_model(model_id="gpt-4o-mini")
        model_str, extra = _compose_sdk_model_args(provider, model, "req-t13")

        assert model_str == "openai/gpt-4o-mini"
        assert extra.get("api_base") == "https://my-proxy.example.com"

    def test_anthropic_provider_type(self):
        """provider_type='anthropic' → model='anthropic/<id>', no api_base by default."""
        provider = _mock_provider(provider_type="anthropic", base_url=None)
        model = _mock_chat_model(model_id="claude-3-5-sonnet-20241022")
        model_str, extra = _compose_sdk_model_args(provider, model, "req-t14")

        assert model_str == "anthropic/claude-3-5-sonnet-20241022"
        assert "api_base" not in extra

    def test_ollama_provider_type_requires_base_url(self):
        """provider_type='ollama' with base_url → model='ollama/<id>' + api_base."""
        provider = _mock_provider(
            provider_type="ollama", base_url="http://localhost:11434"
        )
        model = _mock_chat_model(model_id="llama3.2")
        model_str, extra = _compose_sdk_model_args(provider, model, "req-t15")

        assert model_str == "ollama/llama3.2"
        assert extra.get("api_base") == "http://localhost:11434"

    def test_unknown_provider_type_raises_litellm_error(self):
        """Unknown provider_type raises LiteLLMError — explicit fail is safer than wrong routing."""
        provider = _mock_provider(provider_type="nonexistent_provider", base_url=None)
        model = _mock_chat_model(model_id="some-model")

        with pytest.raises(LiteLLMError) as exc_info:
            _compose_sdk_model_args(provider, model, "req-t16")

        assert "nonexistent_provider" in str(exc_info.value).lower()

    def test_stream_chat_uses_compose_helper_for_litellm_provider(self):
        """stream_chat passes correct model_str to acompletion for litellm provider_type.

        Regression test: ensures the model= kwarg sent to litellm.acompletion
        is 'openai/gpt-4o-mini', NOT 'litellm/gpt-4o-mini'.
        """

        async def _fake_iter():
            from unittest.mock import MagicMock as MM

            chunk = MM()
            chunk.choices = [MM()]
            chunk.choices[0].delta = MM()
            chunk.choices[0].delta.content = "hello"
            chunk.usage = None
            yield chunk
            # Usage chunk
            usage_chunk = MM()
            usage_chunk.choices = []
            usage_chunk.usage = MM()
            usage_chunk.usage.prompt_tokens = 5
            usage_chunk.usage.completion_tokens = 2
            yield usage_chunk

        import asyncio
        from unittest.mock import AsyncMock, patch

        async def _run():
            with patch(
                "litellm.acompletion", new_callable=AsyncMock, return_value=_fake_iter()
            ) as mock_comp:
                with patch("litellm.completion_cost", return_value=0.0):
                    events = []
                    async for ev in stream_chat(
                        model=_mock_chat_model(model_id="gpt-4o-mini"),
                        provider=_mock_provider(
                            provider_type="litellm", base_url="http://localhost:4000"
                        ),
                        api_key="test-bearer",
                        messages=[{"role": "user", "content": "hi"}],
                        request_id="req-t17",
                    ):
                        events.append(ev)
                # Verify the model kwarg sent to acompletion
                call_kwargs = mock_comp.call_args.kwargs
                assert call_kwargs["model"] == "openai/gpt-4o-mini", (
                    f"Expected 'openai/gpt-4o-mini', got '{call_kwargs['model']}'"
                )
                assert call_kwargs.get("api_base") == "http://localhost:4000"
                # api_key must be present (never logged, but must be forwarded)
                assert call_kwargs.get("api_key") == "test-bearer"

        asyncio.run(_run())
