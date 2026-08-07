"""Tests for migration.llm.factory and the LLM configuration.

No API key and no network. The factory is exercised for what it builds and
what it refuses; `AnthropicClient.complete` is never called.
"""

from __future__ import annotations

import logging

import pytest

from migration.llm.client import AnthropicClient, resolve_api_key
from migration.llm.factory import (
    MissingAPIKeyError,
    UnsupportedProviderError,
    create_llm_client,
)
from migration.models.config import LLMConfig, LLMEffort, LLMProvider


def _config(**overrides) -> LLMConfig:
    values = {"provider": LLMProvider.ANTHROPIC, "model": "claude-opus-5"}
    values.update(overrides)
    return LLMConfig(**values)


# -- Configuration ---------------------------------------------------------


def test_defaults_are_sensible():
    config = _config()

    assert config.effort == LLMEffort.HIGH
    assert config.max_tokens == 32000
    assert config.api_key_env == "ANTHROPIC_API_KEY"
    assert config.temperature is None


def test_temperature_is_still_accepted_for_backward_compatibility():
    """Existing config files set it; they must keep loading."""
    assert _config(temperature=0).temperature == 0
    assert _config(temperature=0.7).temperature == 0.7


def test_effort_accepts_every_supported_level():
    for level in ("low", "medium", "high", "xhigh", "max"):
        assert _config(effort=level).effort.value == level


def test_invalid_effort_is_rejected():
    with pytest.raises(ValueError):
        _config(effort="scorching")


def test_zero_max_tokens_is_rejected():
    with pytest.raises(ValueError):
        _config(max_tokens=0)


# -- Factory ---------------------------------------------------------------


def test_builds_an_anthropic_client(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    client = create_llm_client(_config(effort="medium", max_tokens=8000))

    assert isinstance(client, AnthropicClient)
    assert client.model == "claude-opus-5"
    assert client.effort == "medium"
    assert client.max_tokens == 8000


def test_uses_the_configured_environment_variable(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setenv("MY_TEAM_KEY", "sk-team-key")

    client = create_llm_client(_config(api_key_env="MY_TEAM_KEY"))

    assert isinstance(client, AnthropicClient)


def test_missing_api_key_raises_an_actionable_error(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    with pytest.raises(MissingAPIKeyError, match="ANTHROPIC_API_KEY"):
        create_llm_client(_config())


def test_blank_api_key_counts_as_missing(monkeypatch):
    """An exported-but-empty variable is a common .env mistake."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "   ")

    with pytest.raises(MissingAPIKeyError):
        create_llm_client(_config())


def test_openai_provider_is_refused_with_a_clear_message(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    with pytest.raises(UnsupportedProviderError, match="anthropic"):
        create_llm_client(_config(provider=LLMProvider.OPENAI))


def test_temperature_in_config_logs_a_warning(monkeypatch, caplog):
    """The field is inert, and a silent no-op would mislead the operator."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    with caplog.at_level(logging.WARNING):
        create_llm_client(_config(temperature=0.7))

    assert "temperature" in caplog.text
    assert "effort" in caplog.text


def test_no_warning_when_temperature_is_unset(monkeypatch, caplog):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-key")

    with caplog.at_level(logging.WARNING):
        create_llm_client(_config())

    assert "temperature" not in caplog.text


# -- Key resolution --------------------------------------------------------


def test_resolve_api_key_returns_none_when_unset(monkeypatch):
    monkeypatch.delenv("SOME_KEY", raising=False)

    assert resolve_api_key("SOME_KEY") is None


def test_resolve_api_key_strips_surrounding_whitespace(monkeypatch):
    monkeypatch.setenv("SOME_KEY", "  sk-abc  ")

    assert resolve_api_key("SOME_KEY") == "sk-abc"


# -- Client construction ---------------------------------------------------


def test_client_does_not_import_anthropic_at_construction():
    """Constructing must be free; the SDK is only needed on a real call."""
    client = AnthropicClient(model="claude-opus-5")

    assert client.model == "claude-opus-5"
    assert client.effort == "high"


def test_client_never_stores_a_temperature():
    """The one field that would cause a 400 must not be plumbed through."""
    client = AnthropicClient()

    assert not hasattr(client, "temperature")
