"""
Unit tests for seed Pydantic schemas (P00-S02-T005).

Slice: P00-S02-T005 — Replace synthetic verification bundle with People Tech delivery
Phase: P00 — Scaffold + Design System

Tests covered (18 cases):
  MfaPrimarySeed (5):
    1.  synthetic bundle with synthetic_totp=True  → valid
    2.  synthetic bundle with synthetic_totp=False → ValueError
    3.  productive bundle with synthetic_totp=False and 10 hashes → valid
    4.  productive bundle with synthetic_totp=True  → ValueError
    5.  bundle_type=None                           → ValueError (R7 guard)

  AiProviderSeed (4):
    6.  synthetic: api_key 'synthetic-xxx' → valid
    7.  synthetic: api_key without prefix  → ValueError
    8.  synthetic: api_key matches sk-... real pattern → ValueError
    9.  productive: api_key_env reference  → valid (no plaintext key)
    10. productive: api_key with AIza real pattern → ValueError

  AiModelSeed (3):
    11. valid chat model with required fields
    12. capability='reranker' is accepted
    13. missing model_id                   → ValidationError

  McpServerSeed (3):
    14. synthetic: access_token 'synthetic-xxx' → valid
    15. synthetic: missing access_token         → ValueError
    16. productive: public server (no token, no env) → valid

  AgentSeed (3):
    17. supervisor invariant: parent=None, topics=None → valid
    18. subagent invariant: parent required → ValueError when parent=None
    19. subagent with parent set + topics list → valid

  resolve_env_var (2):
    20. required=True, env var set → returns value
    21. required=True, env var missing → BundleLoadError

Rules:
  - No mocking. No DB. Pure Pydantic / stdlib unit tests.
  - Each test is a standalone function. No shared state.

Dependencies:
  - pytest 9.0.3
  - pydantic 2.12.5
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.seeds.loader._common import resolve_env_var
from app.seeds.schemas.admin_ai import AiModelSeed, AiProviderSeed
from app.seeds.schemas.auth import MfaPrimarySeed
from app.seeds.schemas.mcp_agents import AgentSeed, McpServerSeed

# ---------------------------------------------------------------------------
# MfaPrimarySeed
# ---------------------------------------------------------------------------

_TOTP_BASE = {
    "totp_secret": "AAAAAAAAAAAAAAAA",
    "algorithm": "SHA1",
    "digits": 6,
    "period": 30,
}


def test_mfa_synthetic_valid() -> None:
    """synthetic bundle with synthetic_totp=True passes validation."""
    data = {**_TOTP_BASE, "synthetic_totp": True}
    result = MfaPrimarySeed.validate_with_bundle_type(data, "synthetic")
    assert result.synthetic_totp is True
    assert result.backup_codes_argon2 is None


def test_mfa_synthetic_real_totp_rejected() -> None:
    """synthetic bundle with synthetic_totp=False is rejected (guard against real secrets)."""
    data = {**_TOTP_BASE, "synthetic_totp": False}
    with pytest.raises(ValueError, match="synthetic bundle"):
        MfaPrimarySeed.validate_with_bundle_type(data, "synthetic")


def test_mfa_productive_valid() -> None:
    """productive bundle with synthetic_totp=False and 10 argon2 hashes passes validation."""
    fake_hashes = [f"$argon2id$v=19$hash{i}" for i in range(10)]
    data = {
        **_TOTP_BASE,
        "synthetic_totp": False,
        "backup_codes_argon2": fake_hashes,
    }
    result = MfaPrimarySeed.validate_with_bundle_type(data, "productive")
    assert result.synthetic_totp is False
    assert result.backup_codes_argon2 is not None
    assert len(result.backup_codes_argon2) == 10


def test_mfa_productive_synthetic_flag_rejected() -> None:
    """productive bundle with synthetic_totp=True is rejected (must be real TOTP)."""
    data = {**_TOTP_BASE, "synthetic_totp": True}
    with pytest.raises(ValueError, match="productive bundle"):
        MfaPrimarySeed.validate_with_bundle_type(data, "productive")


def test_mfa_none_bundle_type_rejected() -> None:
    """bundle_type=None raises ValueError (R7 guard — context propagation required)."""
    data = {**_TOTP_BASE, "synthetic_totp": True}
    with pytest.raises(ValueError, match="bundle_type must not be None"):
        MfaPrimarySeed.validate_with_bundle_type(data, None)


# ---------------------------------------------------------------------------
# AiProviderSeed
# ---------------------------------------------------------------------------

_PROVIDER_BASE = {
    "name": "test-provider",
    "provider_type": "litellm",
    "base_url": "http://localhost:4000",
    "is_active": True,
}


def test_provider_synthetic_valid() -> None:
    """synthetic: api_key with 'synthetic-' prefix is accepted."""
    data = {**_PROVIDER_BASE, "api_key": "synthetic-test-key-123"}
    result = AiProviderSeed.validate_with_bundle_type(data, "synthetic")
    assert result.api_key == "synthetic-test-key-123"


def test_provider_synthetic_missing_prefix_rejected() -> None:
    """synthetic: api_key without 'synthetic-' prefix is rejected."""
    data = {**_PROVIDER_BASE, "api_key": "real-looking-key"}
    with pytest.raises(ValueError, match="synthetic-"):
        AiProviderSeed.validate_with_bundle_type(data, "synthetic")


def test_provider_synthetic_real_sk_pattern_rejected() -> None:
    """synthetic: api_key matching sk-... real-key pattern is rejected."""
    data = {**_PROVIDER_BASE, "api_key": "sk-abcdefghijklmnopqrstuvwxyz123456"}
    with pytest.raises(ValueError):
        AiProviderSeed.validate_with_bundle_type(data, "synthetic")


def test_provider_productive_env_ref_valid() -> None:
    """productive: api_key_env reference is accepted (no plaintext key required)."""
    data = {**_PROVIDER_BASE, "api_key_env": "VERIFICATION_GEMINI_API_KEY"}
    result = AiProviderSeed.validate_with_bundle_type(data, "productive")
    assert result.api_key_env == "VERIFICATION_GEMINI_API_KEY"
    assert result.api_key is None


def test_provider_productive_aiza_pattern_rejected() -> None:
    """productive: api_key matching AIza real-key pattern is rejected."""
    data = {**_PROVIDER_BASE, "api_key": "AIzaSyAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"}
    with pytest.raises(ValueError, match="plaintext real key"):
        AiProviderSeed.validate_with_bundle_type(data, "productive")


# ---------------------------------------------------------------------------
# AiModelSeed
# ---------------------------------------------------------------------------


def test_model_valid_chat() -> None:
    """Valid chat model with all required fields is accepted."""
    data = {
        "name": "gemini-2.5-flash",
        "model_id": "gemini/gemini-2.5-flash",
        "provider_name": "gemini-direct",
        "capability": "chat",
        "is_active": True,
        "auto_discovered": False,
    }
    result = AiModelSeed.model_validate(data)
    assert result.capability == "chat"
    assert result.auto_discovered is False
    assert result.display_name is None  # optional


def test_model_reranker_capability_accepted() -> None:
    """capability='reranker' is a valid literal value."""
    data = {
        "name": "my-reranker",
        "model_id": "some/reranker-model",
        "provider_name": "gemini-direct",
        "capability": "reranker",
        "is_active": False,
        "auto_discovered": False,
    }
    result = AiModelSeed.model_validate(data)
    assert result.capability == "reranker"


def test_model_missing_model_id_raises() -> None:
    """Missing model_id raises ValidationError."""
    data = {
        "name": "incomplete-model",
        "provider_name": "some-provider",
        "capability": "chat",
        "is_active": True,
        "auto_discovered": False,
    }
    with pytest.raises(ValidationError, match="model_id"):
        AiModelSeed.model_validate(data)


# ---------------------------------------------------------------------------
# McpServerSeed
# ---------------------------------------------------------------------------

_SERVER_BASE = {
    "name": "test-server",
    "endpoint_url": "http://localhost:9000/mcp",
    "transport": "http",
    "is_active": True,
}


def test_server_synthetic_valid() -> None:
    """synthetic: access_token with 'synthetic-' prefix is accepted."""
    data = {**_SERVER_BASE, "access_token": "synthetic-token-abc"}
    result = McpServerSeed.validate_with_bundle_type(data, "synthetic")
    assert result.access_token == "synthetic-token-abc"


def test_server_synthetic_missing_token_rejected() -> None:
    """synthetic: missing access_token is rejected (required in synthetic bundle)."""
    data = {**_SERVER_BASE}  # no access_token
    with pytest.raises(ValueError, match="access_token is required"):
        McpServerSeed.validate_with_bundle_type(data, "synthetic")


def test_server_productive_public_server_valid() -> None:
    """productive: public server with neither token nor env is valid (no auth required)."""
    data = {**_SERVER_BASE, "is_active": True}  # no access_token, no access_token_env
    result = McpServerSeed.validate_with_bundle_type(data, "productive")
    assert result.access_token is None
    assert result.access_token_env is None


# ---------------------------------------------------------------------------
# AgentSeed
# ---------------------------------------------------------------------------

_AGENT_BASE = {
    "name": "test-agent",
    "description": "A test agent for unit testing.",
    "system_prompt": "You are a test agent.",
    "model_id": "gemini/gemini-2.5-flash",
    "is_active": True,
}


def test_agent_supervisor_valid() -> None:
    """supervisor with parent=None and topics=None passes cross-field validator."""
    data = {
        **_AGENT_BASE,
        "agent_type": "supervisor",
        "parent_agent_name": None,
        "subagent_topics": None,
    }
    result = AgentSeed.model_validate(data)
    assert result.agent_type == "supervisor"
    assert result.parent_agent_name is None


def test_agent_subagent_missing_parent_rejected() -> None:
    """subagent with parent_agent_name=None raises ValidationError."""
    data = {
        **_AGENT_BASE,
        "agent_type": "subagent",
        "parent_agent_name": None,
    }
    with pytest.raises(ValidationError, match="parent_agent_name"):
        AgentSeed.model_validate(data)


def test_agent_subagent_with_parent_and_topics_valid() -> None:
    """subagent with parent_agent_name set and subagent_topics list passes validation."""
    data = {
        **_AGENT_BASE,
        "agent_type": "subagent",
        "parent_agent_name": "people-supervisor",
        "subagent_topics": ["vacaciones", "bajas"],
        "framework": "deepagents",
    }
    result = AgentSeed.model_validate(data)
    assert result.parent_agent_name == "people-supervisor"
    assert result.subagent_topics == ["vacaciones", "bajas"]


# ---------------------------------------------------------------------------
# resolve_env_var
# ---------------------------------------------------------------------------


def test_resolve_env_var_set_returns_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """resolve_env_var returns the env var value when it is set."""
    monkeypatch.setenv("TEST_RESOLVE_KEY_T005", "test-value-xyz")
    value = resolve_env_var("TEST_RESOLVE_KEY_T005", required=True)
    assert value == "test-value-xyz"


def test_resolve_env_var_missing_required_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """resolve_env_var raises BundleLoadError when required=True and var is missing."""
    monkeypatch.delenv("TEST_MISSING_KEY_T005", raising=False)
    from app.seeds.io import BundleLoadError
    with pytest.raises(BundleLoadError, match="TEST_MISSING_KEY_T005"):
        resolve_env_var("TEST_MISSING_KEY_T005", required=True)
