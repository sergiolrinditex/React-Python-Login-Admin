"""
Async HTTP clients for AI provider model-list endpoints.

Slice: P00-S02-T006 — Dynamic LiteLLM model discovery endpoint
Phase: P00 — Scaffold + Design System

Implements one client class per supported provider_type:
  - GeminiDirectClient  — GET /v1beta/models?key={api_key}
  - OpenAIDirectClient  — GET /v1/models with Bearer token
  - LiteLLMProxyClient  — GET /v1/models with Bearer master_key

Each client returns a list of ProviderModel dataclasses with a normalised
`model_type` field ('chat' | 'embedding' | 'unknown') mapped from the
provider-specific response shape.

Dispatcher:
  `get_provider_client(provider_type, base_url, api_key)` — raises
  UnsupportedProviderError for unknown provider_type values.

HTTP contract (task-pack §B2):
  - httpx.AsyncClient with explicit Timeout(connect=5, read=15, write=5, pool=5)
  - AsyncHTTPTransport(retries=0) — no silent retries (avoids rate-limit multiplication)
  - verify=True (TLS certificate verification on)

Security:
  - api_key is NEVER logged (not in BEFORE/AFTER/ERROR log lines)
  - base_url is logged with query string stripped (avoids Gemini ?key= leak — R2)
  - Errors log only error_class + upstream_status (no response body)

Discrepancy doc-note resolved:
  LiteLLMProxyClient calls GET /v1/models which returns ONLY models configured
  in config.yaml (not upstream provider discovery). For dev environments with
  model_list: [] the result is total_seen=0 — this is correct, not a bug.
  See official-doc-notes/P00-S02-T006-litellm-models-discovery-2026-05-09.md.

Dependencies:
  - httpx 0.28.1
Source: task-pack P00-S02-T006 §7 steps 6 + §B1 + §B2 + §6.6 R1/R2
HILO_PEOPLE_TECHNICAL_GUIDE.md ADR-001 §15
"""
from __future__ import annotations

import dataclasses
from typing import Literal
from urllib.parse import urlparse

import httpx

from app.core.logging import get_logger

_logger = get_logger(__name__)

ModelType = Literal["chat", "embedding", "unknown"]

_HTTPX_TIMEOUT = httpx.Timeout(connect=5.0, read=15.0, write=5.0, pool=5.0)
_HTTPX_TRANSPORT = httpx.AsyncHTTPTransport(retries=0)


# ---------------------------------------------------------------------------
# Custom errors
# ---------------------------------------------------------------------------


class UnsupportedProviderError(Exception):
    """Raised by get_provider_client() for unknown provider_type strings.

    Purpose: typed error so routes.py can map to HTTP 422 without catching
    generic exceptions. Carries the offending provider_type string.
    """

    def __init__(self, provider_type: str) -> None:
        """Initialise with the unsupported provider_type value."""
        self.provider_type = provider_type
        super().__init__(f"Unsupported provider_type: {provider_type!r}")


class UpstreamProviderError(Exception):
    """Raised when an upstream provider call fails (timeout, 4xx, 5xx).

    Purpose: typed error for routes.py to map to HTTP 502. Contains a
    sanitised message (no key values, no raw provider body).

    Attributes:
      status_code — HTTP status from upstream (None for timeout/network errors).
      message     — sanitised summary for the 502 response body.
    """

    def __init__(self, message: str, status_code: int | None = None) -> None:
        """Initialise with sanitised message and optional upstream status code."""
        self.message = message
        self.status_code = status_code
        super().__init__(message)


# ---------------------------------------------------------------------------
# Provider model dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ProviderModel:
    """Normalised representation of a model returned by a provider endpoint.

    Attributes:
      model_id   — raw identifier from the provider (e.g. 'models/gemini-2.5-flash').
      model_type — normalised capability class: 'chat' | 'embedding' | 'unknown'.
    """

    model_id: str
    model_type: ModelType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _safe_base_url(base_url: str) -> str:
    """Return base_url with query string stripped (prevents api_key leak in logs).

    Security: R2 mitigation — Gemini embeds api_key in query string (?key=...).
    Logging the full URL would expose the key. Strip to scheme+host+path only.

    Params:
      base_url — raw base URL (may or may not have query string).
    Returns: scheme://host/path (no query, no fragment).
    """
    parsed = urlparse(base_url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"


def _map_gemini_model_type(supported_methods: list[str]) -> ModelType:
    """Map Gemini supportedGenerationMethods list to our model_type enum.

    Mapping per task-pack §6.6 R1:
      generateContent  → 'chat'
      embedContent     → 'embedding'
      (neither)        → 'unknown'

    Params:
      supported_methods — list of method strings from Gemini API response.
    Returns: 'chat' | 'embedding' | 'unknown'.
    """
    if "generateContent" in supported_methods:
        return "chat"
    if "embedContent" in supported_methods:
        return "embedding"
    return "unknown"


# ---------------------------------------------------------------------------
# Client classes
# ---------------------------------------------------------------------------


class GeminiDirectClient:
    """Async client for the Google Gemini API model list endpoint.

    Calls: GET {base_url}/v1beta/models?key={api_key}
    Response shape (per official docs confirmed 2026-05-09):
      { models: [ { name, displayName, supportedGenerationMethods, ... } ] }

    model_id is taken from the `name` field (e.g. 'models/gemini-2.5-flash').
    model_type is mapped from supportedGenerationMethods via _map_gemini_model_type.

    Security note: api_key is passed as a query param by the Gemini API. The
    request URL is NEVER logged — only scheme+host+path (no query string).
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        """Initialise with provider base_url and decrypted api_key.

        Params:
          base_url — Gemini API base (e.g. 'https://generativelanguage.googleapis.com').
          api_key  — decrypted plaintext API key. NEVER log this value.
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def list_models(self) -> list[ProviderModel]:
        """Fetch the model list from Google Gemini API.

        Returns: list of ProviderModel with normalised model_id + model_type.
        Raises: UpstreamProviderError on network failure or non-200 response.

        Logs: BEFORE with safe_url (no query string); AFTER with model_count.
        Security: api_key excluded from all log lines.
        """
        safe_url = _safe_base_url(self._base_url)
        endpoint = f"{self._base_url}/v1beta/models"
        _logger.info(
            "discover_models BEFORE",
            provider_type="gemini",
            endpoint_base=safe_url,
        )
        try:
            async with httpx.AsyncClient(
                timeout=_HTTPX_TIMEOUT,
                transport=_HTTPX_TRANSPORT,
                verify=True,
            ) as client:
                resp = await client.get(endpoint, params={"key": self._api_key})
                resp.raise_for_status()
        except httpx.TimeoutException as exc:
            _logger.warning(
                "ERROR discover_models gemini: timeout",
                provider_type="gemini",
                error_class="TimeoutException",
            )
            raise UpstreamProviderError(
                "Gemini API request timed out", status_code=None
            ) from exc
        except httpx.HTTPStatusError as exc:
            _logger.warning(
                "ERROR discover_models gemini: upstream HTTP error",
                provider_type="gemini",
                upstream_status=exc.response.status_code,
                error_class="HTTPStatusError",
            )
            raise UpstreamProviderError(
                f"Gemini API returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            _logger.warning(
                "ERROR discover_models gemini: network error",
                provider_type="gemini",
                error_class=type(exc).__name__,
            )
            raise UpstreamProviderError("Gemini API network error") from exc

        payload = resp.json()
        raw_models = payload.get("models", [])
        result: list[ProviderModel] = []
        for m in raw_models:
            name = m.get("name", "")
            if not name:
                continue
            methods = m.get("supportedGenerationMethods", [])
            result.append(
                ProviderModel(model_id=name, model_type=_map_gemini_model_type(methods))
            )

        _logger.info(
            "discover_models AFTER",
            provider_type="gemini",
            model_count=len(result),
        )
        return result


class OpenAIDirectClient:
    """Async client for the OpenAI API model list endpoint.

    Calls: GET {base_url}/v1/models with Authorization: Bearer {api_key}
    Response shape (OpenAI-compatible):
      { data: [ { id, object, created, owned_by } ] }

    model_id is taken from the `id` field.
    model_type is mapped: ids containing 'embed' → 'embedding', else 'chat'.
    """

    def __init__(self, base_url: str, api_key: str) -> None:
        """Initialise with provider base_url and decrypted api_key.

        Params:
          base_url — OpenAI-compatible API base (e.g. 'https://api.openai.com').
          api_key  — decrypted plaintext API key. NEVER log this value.
        """
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key

    async def list_models(self) -> list[ProviderModel]:
        """Fetch the model list from OpenAI-compatible API.

        Returns: list of ProviderModel with normalised model_id + model_type.
        Raises: UpstreamProviderError on failure.
        """
        safe_url = _safe_base_url(self._base_url)
        endpoint = f"{self._base_url}/v1/models"
        _logger.info(
            "discover_models BEFORE",
            provider_type="openai",
            endpoint_base=safe_url,
        )
        try:
            async with httpx.AsyncClient(
                timeout=_HTTPX_TIMEOUT,
                transport=_HTTPX_TRANSPORT,
                verify=True,
            ) as client:
                resp = await client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                resp.raise_for_status()
        except httpx.TimeoutException as exc:
            _logger.warning(
                "ERROR discover_models openai: timeout",
                provider_type="openai",
                error_class="TimeoutException",
            )
            raise UpstreamProviderError("OpenAI API timed out") from exc
        except httpx.HTTPStatusError as exc:
            _logger.warning(
                "ERROR discover_models openai: upstream HTTP error",
                provider_type="openai",
                upstream_status=exc.response.status_code,
                error_class="HTTPStatusError",
            )
            raise UpstreamProviderError(
                f"OpenAI API returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            _logger.warning(
                "ERROR discover_models openai: network error",
                provider_type="openai",
                error_class=type(exc).__name__,
            )
            raise UpstreamProviderError("OpenAI API network error") from exc

        payload = resp.json()
        raw_models = payload.get("data", [])
        result: list[ProviderModel] = []
        for m in raw_models:
            mid = m.get("id", "")
            if not mid:
                continue
            mtype: ModelType = "embedding" if "embed" in mid.lower() else "chat"
            result.append(ProviderModel(model_id=mid, model_type=mtype))

        _logger.info(
            "discover_models AFTER",
            provider_type="openai",
            model_count=len(result),
        )
        return result


class LiteLLMProxyClient:
    """Async client for the LiteLLM proxy model list endpoint.

    Calls: GET {base_url}/v1/models with Authorization: Bearer {master_key}
    Response shape (OpenAI-compatible):
      { data: [ { id, object, created, owned_by } ] }

    IMPORTANT — scope of results:
      /v1/models returns ONLY models explicitly configured in config.yaml under
      `model_list`. It does NOT enumerate upstream provider models unless wildcard
      entries + `check_provider_endpoint: true` are configured. For dev environments
      with `model_list: []`, the result will be total_seen=0. This is correct.
      See official-doc-notes/P00-S02-T006-litellm-models-discovery-2026-05-09.md.
      RESOLVED: this docstring documents the behaviour; no code change needed.
    """

    def __init__(self, base_url: str, master_key: str) -> None:
        """Initialise with proxy base_url and master_key.

        Params:
          base_url   — LiteLLM proxy base (e.g. 'http://localhost:4000').
          master_key — LiteLLM master key. NEVER log this value.
        """
        self._base_url = base_url.rstrip("/")
        self._master_key = master_key

    async def list_models(self) -> list[ProviderModel]:
        """Fetch the model list from the LiteLLM proxy.

        Returns: list of ProviderModel. Empty list when config.yaml has no model_list.
        Raises: UpstreamProviderError on failure.

        Note: total_seen=0 is valid for dev environments with model_list: [].
        """
        safe_url = _safe_base_url(self._base_url)
        endpoint = f"{self._base_url}/v1/models"
        _logger.info(
            "discover_models BEFORE",
            provider_type="litellm",
            endpoint_base=safe_url,
        )
        try:
            async with httpx.AsyncClient(
                timeout=_HTTPX_TIMEOUT,
                transport=_HTTPX_TRANSPORT,
                verify=True,
            ) as client:
                resp = await client.get(
                    endpoint,
                    headers={"Authorization": f"Bearer {self._master_key}"},
                )
                resp.raise_for_status()
        except httpx.TimeoutException as exc:
            _logger.warning(
                "ERROR discover_models litellm: timeout",
                provider_type="litellm",
                error_class="TimeoutException",
            )
            raise UpstreamProviderError("LiteLLM proxy timed out") from exc
        except httpx.HTTPStatusError as exc:
            _logger.warning(
                "ERROR discover_models litellm: upstream HTTP error",
                provider_type="litellm",
                upstream_status=exc.response.status_code,
                error_class="HTTPStatusError",
            )
            raise UpstreamProviderError(
                f"LiteLLM proxy returned HTTP {exc.response.status_code}",
                status_code=exc.response.status_code,
            ) from exc
        except httpx.HTTPError as exc:
            _logger.warning(
                "ERROR discover_models litellm: network error",
                provider_type="litellm",
                error_class=type(exc).__name__,
            )
            raise UpstreamProviderError("LiteLLM proxy network error") from exc

        payload = resp.json()
        raw_models = payload.get("data", [])
        result: list[ProviderModel] = []
        for m in raw_models:
            mid = m.get("id", "")
            if not mid:
                continue
            mtype: ModelType = "embedding" if "embed" in mid.lower() else "chat"
            result.append(ProviderModel(model_id=mid, model_type=mtype))

        _logger.info(
            "discover_models AFTER",
            provider_type="litellm",
            model_count=len(result),
        )
        return result


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------


def get_provider_client(
    provider_type: str,
    base_url: str,
    api_key: str,
) -> GeminiDirectClient | OpenAIDirectClient | LiteLLMProxyClient:
    """Return the correct provider client for the given provider_type.

    Purpose: single dispatch point; raises UnsupportedProviderError for unknown
    provider_type values so the route layer can return HTTP 422 cleanly.

    Params:
      provider_type — string from ai_providers.provider_type column.
      base_url      — from ai_providers.base_url column.
      api_key       — decrypted plaintext credential string.
    Returns: the appropriate client instance.
    Raises: UnsupportedProviderError — if provider_type is not 'gemini'|'openai'|'litellm'.

    Security: api_key is never logged here.
    """
    _logger.debug(
        "BEFORE get_provider_client: dispatching",
        provider_type=provider_type,
        base_url_safe=_safe_base_url(base_url) if base_url else None,
    )
    if provider_type == "gemini":
        return GeminiDirectClient(base_url=base_url, api_key=api_key)
    if provider_type == "openai":
        return OpenAIDirectClient(base_url=base_url, api_key=api_key)
    if provider_type == "litellm":
        return LiteLLMProxyClient(base_url=base_url, master_key=api_key)
    raise UnsupportedProviderError(provider_type)
