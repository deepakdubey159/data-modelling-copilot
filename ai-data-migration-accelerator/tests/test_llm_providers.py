"""
Tests for LLM provider architecture.

Verifies:
- Anthropic and OpenAI adapters work correctly
- Model capabilities are respected
- Common settings translate correctly to provider-specific params
- Unsupported capabilities are rejected
- Factory routes to correct provider
"""

from __future__ import annotations

from unittest import mock

import pytest

from migration.llm.anthropic import AnthropicClient
from migration.llm.base import LLMClient, LLMError
from migration.llm.capabilities import get_capabilities
from migration.llm.factory import (
    UnsupportedProviderError,
    MissingAPIKeyError,
    create_llm_client,
)
from migration.llm.openai import OpenAIClient
from migration.models.config import LLMConfig, LLMProvider, LLMEffort


class TestCapabilityRegistry:
    """Verify model capability detection."""

    def test_opus_5_supports_adaptive_thinking(self):
        caps = get_capabilities("claude-opus-5")
        assert caps is not None
        assert caps.supports_adaptive_thinking is True

    def test_haiku_4_5_does_not_support_adaptive_thinking(self):
        caps = get_capabilities("claude-haiku-4-5-20251001")
        assert caps is not None
        assert caps.supports_adaptive_thinking is False

    def test_gpt_4o_does_not_support_adaptive_thinking(self):
        caps = get_capabilities("gpt-4o")
        assert caps is not None
        assert caps.supports_adaptive_thinking is False

    def test_unknown_model_returns_none(self):
        caps = get_capabilities("some-future-model-xyz")
        assert caps is None


class TestAnthropicProvider:
    """Verify Anthropic provider adapter."""

    def test_client_inherits_from_base(self):
        client = AnthropicClient(model="claude-opus-5")
        assert isinstance(client, LLMClient)

    def test_opus_5_request_includes_adaptive_thinking(self):
        """Opus 5 should always receive adaptive thinking parameter."""
        client = AnthropicClient(model="claude-opus-5", effort="high")

        with mock.patch("anthropic.Anthropic") as mock_anthropic:
            mock_stream = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.stop_reason = "end_turn"
            mock_response.content = [mock.MagicMock(type="text", text="test")]
            mock_response.usage = mock.MagicMock(input_tokens=10, output_tokens=5)

            mock_stream.__enter__.return_value = mock_stream
            mock_stream.get_final_message.return_value = mock_response
            mock_anthropic.return_value.messages.stream.return_value = mock_stream

            client.complete("system", "user")

            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]
            assert "thinking" in call_kwargs
            assert call_kwargs["thinking"] == {"type": "adaptive"}

    def test_haiku_request_excludes_adaptive_thinking(self):
        """Haiku 4.5 should never receive adaptive thinking parameter."""
        client = AnthropicClient(model="claude-haiku-4-5-20251001", effort="low")

        with mock.patch("anthropic.Anthropic") as mock_anthropic:
            mock_stream = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.stop_reason = "end_turn"
            mock_response.content = [mock.MagicMock(type="text", text="test")]
            mock_response.usage = mock.MagicMock(input_tokens=10, output_tokens=5)

            mock_stream.__enter__.return_value = mock_stream
            mock_stream.get_final_message.return_value = mock_response
            mock_anthropic.return_value.messages.stream.return_value = mock_stream

            client.complete("system", "user")

            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]
            assert "thinking" not in call_kwargs

    def test_effort_maps_to_output_config(self):
        """Effort level should map to output_config."""
        client = AnthropicClient(model="claude-opus-5", effort="medium")

        with mock.patch("anthropic.Anthropic") as mock_anthropic:
            mock_stream = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.stop_reason = "end_turn"
            mock_response.content = [mock.MagicMock(type="text", text="test")]
            mock_response.usage = mock.MagicMock(input_tokens=10, output_tokens=5)

            mock_stream.__enter__.return_value = mock_stream
            mock_stream.get_final_message.return_value = mock_response
            mock_anthropic.return_value.messages.stream.return_value = mock_stream

            client.complete("system", "user")

            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]
            assert call_kwargs["output_config"]["effort"] == "medium"

    def test_json_schema_adds_output_format(self):
        """JSON schema should add format constraint to output_config, matching
        the installed anthropic SDK's OutputConfigParam.format (JSONOutputFormatParam)."""
        client = AnthropicClient(model="claude-opus-5")
        schema = {"type": "object", "properties": {"test": {"type": "string"}}}

        with mock.patch("anthropic.Anthropic") as mock_anthropic:
            mock_stream = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.stop_reason = "end_turn"
            mock_response.content = [mock.MagicMock(type="text", text="test")]
            mock_response.usage = mock.MagicMock(input_tokens=10, output_tokens=5)

            mock_stream.__enter__.return_value = mock_stream
            mock_stream.get_final_message.return_value = mock_response
            mock_anthropic.return_value.messages.stream.return_value = mock_stream

            client.complete("system", "user", schema)

            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]
            assert "output" not in call_kwargs  # not a valid SDK 0.120.2 kwarg
            assert "format" in call_kwargs["output_config"]
            assert call_kwargs["output_config"]["format"]["type"] == "json_schema"
            assert call_kwargs["output_config"]["format"]["schema"] == schema

    def test_json_schema_kwargs_match_installed_sdk_signature(self):
        """Guards against passing kwargs the installed anthropic SDK doesn't
        accept - the exact regression this test suite is protecting against
        (a prior fix invented a nonexistent 'output' kwarg)."""
        import inspect

        import anthropic

        valid_params = set(
            inspect.signature(anthropic.resources.messages.Messages.stream).parameters
        )

        client = AnthropicClient(model="claude-opus-5")
        schema = {"type": "object", "properties": {"test": {"type": "string"}}}

        with mock.patch("anthropic.Anthropic") as mock_anthropic:
            mock_stream = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.stop_reason = "end_turn"
            mock_response.content = [mock.MagicMock(type="text", text="test")]
            mock_response.usage = mock.MagicMock(input_tokens=10, output_tokens=5)

            mock_stream.__enter__.return_value = mock_stream
            mock_stream.get_final_message.return_value = mock_response
            mock_anthropic.return_value.messages.stream.return_value = mock_stream

            client.complete("system", "user", schema)

            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]
            assert set(call_kwargs).issubset(valid_params), (
                f"Sent kwargs not accepted by installed SDK: "
                f"{set(call_kwargs) - valid_params}"
            )


class TestOpenAIProvider:
    """Verify OpenAI provider adapter."""

    def test_client_inherits_from_base(self):
        client = OpenAIClient(model="gpt-4o")
        assert isinstance(client, LLMClient)

    def test_effort_maps_to_temperature(self):
        """Effort level should map to temperature (OpenAI doesn't support 'effort')."""
        test_cases = [
            ("low", 0.8),
            ("medium", 0.5),
            ("high", 0.2),
            ("xhigh", 0.1),
            ("max", 0.0),
        ]

        for effort, expected_temp in test_cases:
            client = OpenAIClient(model="gpt-4o", effort=effort)

            with mock.patch("openai.OpenAI") as mock_openai:
                mock_response = mock.MagicMock()
                mock_response.choices = [
                    mock.MagicMock(message=mock.MagicMock(content="test"))
                ]
                mock_response.usage = mock.MagicMock(
                    prompt_tokens=10, completion_tokens=5
                )

                mock_openai.return_value.chat.completions.create.return_value = mock_response

                client.complete("system", "user")

                call_kwargs = (
                    mock_openai.return_value.chat.completions.create.call_args[1]
                )
                assert call_kwargs["temperature"] == expected_temp

    def test_system_prompt_in_messages(self):
        """System prompt should be included as a message."""
        client = OpenAIClient(model="gpt-4o")

        with mock.patch("openai.OpenAI") as mock_openai:
            mock_response = mock.MagicMock()
            mock_response.choices = [
                mock.MagicMock(message=mock.MagicMock(content="test"))
            ]
            mock_response.usage = mock.MagicMock(
                prompt_tokens=10, completion_tokens=5
            )

            mock_openai.return_value.chat.completions.create.return_value = mock_response

            client.complete("system prompt", "user prompt")

            call_kwargs = (
                mock_openai.return_value.chat.completions.create.call_args[1]
            )
            messages = call_kwargs["messages"]
            assert len(messages) == 2
            assert messages[0]["role"] == "system"
            assert messages[0]["content"] == "system prompt"
            assert messages[1]["role"] == "user"
            assert messages[1]["content"] == "user prompt"

    def test_unsupported_structured_output_raises_error(self):
        """If model doesn't support structured output, should raise error."""
        client = OpenAIClient(model="gpt-4")  # gpt-4 doesn't support structured output
        schema = {"type": "object"}

        with mock.patch("openai.OpenAI"):
            with pytest.raises(
                LLMError, match="does not support structured output"
            ):
                client.complete("system", "user", schema)


class TestFactory:
    """Verify LLM client factory."""

    def test_anthropic_provider_creates_anthropic_client(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-opus-5",
        )

        client = create_llm_client(config)
        assert isinstance(client, AnthropicClient)
        assert client.model == "claude-opus-5"

    def test_openai_provider_creates_openai_client(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")

        config = LLMConfig(
            provider=LLMProvider.OPENAI,
            model="gpt-4o",
            api_key_env="OPENAI_API_KEY",
        )

        client = create_llm_client(config)
        assert isinstance(client, OpenAIClient)
        assert client.model == "gpt-4o"

    def test_missing_api_key_raises_error(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-opus-5",
        )

        with pytest.raises(MissingAPIKeyError):
            create_llm_client(config)

    def test_unsupported_provider_raises_error(self, monkeypatch):
        """Test error handling for a provider string that isn't in the enum."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        # Create a config with a provider that would fail the enum check
        # We simulate this by using a string directly instead of enum
        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-opus-5",
        )
        # Monkey-patch to bypass enum validation
        monkeypatch.setattr(config, "provider", "bedrock", raising=False)

        with pytest.raises(UnsupportedProviderError, match="bedrock"):
            create_llm_client(config)

    def test_effort_setting_preserved(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-opus-5",
            effort=LLMEffort.LOW,
        )

        client = create_llm_client(config)
        assert client.effort == "low"

    def test_max_tokens_setting_preserved(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-opus-5",
            max_tokens=8000,
        )

        client = create_llm_client(config)
        assert client.max_tokens == 8000

    def test_temperature_deprecation_warning(self, monkeypatch, caplog):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="claude-opus-5",
            temperature=0.7,
        )

        import logging

        with caplog.at_level(logging.WARNING):
            create_llm_client(config)

        assert "temperature" in caplog.text.lower()
        assert "effort" in caplog.text.lower()

    def test_unknown_model_logged_but_allowed(self, monkeypatch, caplog):
        """Unknown models should be logged but still instantiated."""
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")

        config = LLMConfig(
            provider=LLMProvider.ANTHROPIC,
            model="future-claude-model-xyz",
        )

        import logging

        with caplog.at_level(logging.WARNING):
            client = create_llm_client(config)

        assert client is not None
        assert "future-claude-model-xyz" in caplog.text.lower()
