"""
Tests for effort parameter handling across providers.

Verifies that the capability layer correctly prevents unsupported
parameters from being sent to models that don't support them.
"""

from __future__ import annotations

from unittest import mock

import pytest

from migration.llm.anthropic import AnthropicClient
from migration.llm.openai import OpenAIClient


class TestHaikuCapabilityHandling:
    """Verify Haiku 4.5 doesn't receive unsupported parameters."""

    def test_haiku_request_excludes_effort_parameter(self):
        """Haiku 4.5 should never receive effort in output_config."""
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
            output_config = call_kwargs["output_config"]

            # Effort should NOT be in the output_config for Haiku
            assert "effort" not in output_config, (
                "Haiku 4.5 should not receive effort parameter"
            )

    def test_haiku_request_excludes_adaptive_thinking(self):
        """Haiku 4.5 should never receive adaptive thinking."""
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

            # Thinking should NOT be in the request for Haiku
            assert "thinking" not in call_kwargs, (
                "Haiku 4.5 should not receive thinking parameter"
            )

    def test_haiku_request_excludes_both_effort_and_thinking(self):
        """Verify Haiku doesn't receive either unsupported parameter."""
        client = AnthropicClient(model="claude-haiku-4-5-20251001", effort="medium")

        with mock.patch("anthropic.Anthropic") as mock_anthropic:
            mock_stream = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.stop_reason = "end_turn"
            mock_response.content = [mock.MagicMock(type="text", text="test")]
            mock_response.usage = mock.MagicMock(input_tokens=10, output_tokens=5)

            mock_stream.__enter__.return_value = mock_stream
            mock_stream.get_final_message.return_value = mock_response
            mock_anthropic.return_value.messages.stream.return_value = mock_stream

            client.complete("system", "user", {"type": "object"})

            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]
            output_config = call_kwargs.get("output_config", {})

            # Verify both are absent
            assert "effort" not in output_config
            assert "thinking" not in call_kwargs
            # But JSON schema should still be present
            assert "format" in output_config


class TestOpusCapabilityHandling:
    """Verify Opus 5 receives all supported parameters."""

    def test_opus_includes_effort_and_thinking(self):
        """Opus 5 should receive both effort and adaptive thinking."""
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
            output_config = call_kwargs["output_config"]

            # Effort SHOULD be in output_config for Opus
            assert "effort" in output_config
            assert output_config["effort"] == "high"

            # Thinking SHOULD be in the request for Opus
            assert "thinking" in call_kwargs
            assert call_kwargs["thinking"] == {"type": "adaptive"}


class TestOpenAIEffortHandling:
    """Verify OpenAI maps effort to temperature instead of sending effort param."""

    def test_openai_maps_effort_to_temperature_not_effort_param(self):
        """OpenAI should map effort to temperature, never send effort param."""
        client = OpenAIClient(model="gpt-4o", effort="high")

        with mock.patch("openai.OpenAI") as mock_openai:
            mock_response = mock.MagicMock()
            mock_response.choices = [
                mock.MagicMock(message=mock.MagicMock(content="test"))
            ]
            mock_response.usage = mock.MagicMock(
                prompt_tokens=10, completion_tokens=5
            )

            mock_openai.return_value.chat.completions.create.return_value = (
                mock_response
            )

            client.complete("system", "user")

            call_kwargs = (
                mock_openai.return_value.chat.completions.create.call_args[1]
            )

            # OpenAI should get temperature, not effort
            assert "temperature" in call_kwargs
            assert call_kwargs["temperature"] == 0.2  # high effort → low temp
            assert "effort" not in call_kwargs
