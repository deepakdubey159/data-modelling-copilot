"""Tests for adaptive thinking support in AnthropicClient.

Verifies that adaptive thinking is only sent for models that support it,
and is never sent for Haiku 4.5 and other unsupported models.

Note: This test is now superseded by tests/test_llm_providers.py which
tests the full provider architecture. Kept for backward compatibility.
"""

from __future__ import annotations

from unittest import mock

import pytest

from migration.llm.anthropic import AnthropicClient
from migration.llm.capabilities import get_capabilities


class TestAdaptiveThinkingSupport:
    """Verify adaptive thinking detection across model versions."""

    def test_opus_5_supports_adaptive_thinking(self):
        caps = get_capabilities("claude-opus-5")
        assert caps is not None
        assert caps.supports_adaptive_thinking

    def test_sonnet_5_supports_adaptive_thinking(self):
        caps = get_capabilities("claude-sonnet-5")
        assert caps is not None
        assert caps.supports_adaptive_thinking

    def test_opus_4_8_supports_adaptive_thinking(self):
        caps = get_capabilities("claude-opus-4-8")
        assert caps is not None
        assert caps.supports_adaptive_thinking

    def test_sonnet_4_6_supports_adaptive_thinking(self):
        caps = get_capabilities("claude-sonnet-4-6")
        assert caps is not None
        assert caps.supports_adaptive_thinking

    def test_haiku_4_5_does_not_support_adaptive_thinking(self):
        caps = get_capabilities("claude-haiku-4-5-20251001")
        assert caps is not None
        assert not caps.supports_adaptive_thinking

    def test_unknown_model_returns_none(self):
        caps = get_capabilities("some-custom-model")
        assert caps is None

    def test_empty_string_returns_none(self):
        caps = get_capabilities("")
        assert caps is None


class TestAnthropicClientThinkingRequest:
    """Verify that Anthropic requests include/exclude thinking correctly."""

    def test_haiku_request_does_not_include_adaptive_thinking(self):
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

            client.complete("system prompt", "user prompt")

            # Verify the stream was called
            mock_anthropic.return_value.messages.stream.assert_called_once()

            # Get the call arguments
            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]

            # Verify thinking parameter is NOT in the request
            assert "thinking" not in call_kwargs, (
                "Haiku 4.5 should not receive adaptive thinking parameter"
            )

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

            client.complete("system prompt", "user prompt")

            # Get the call arguments
            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]

            # Verify thinking parameter IS in the request for Opus 5
            assert "thinking" in call_kwargs, (
                "Opus 5 should receive adaptive thinking parameter"
            )
            assert call_kwargs["thinking"] == {"type": "adaptive"}

    def test_sonnet_5_request_includes_adaptive_thinking(self):
        """Sonnet 5 should always receive adaptive thinking parameter."""
        client = AnthropicClient(model="claude-sonnet-5", effort="medium")

        with mock.patch("anthropic.Anthropic") as mock_anthropic:
            mock_stream = mock.MagicMock()
            mock_response = mock.MagicMock()
            mock_response.stop_reason = "end_turn"
            mock_response.content = [mock.MagicMock(type="text", text="test")]
            mock_response.usage = mock.MagicMock(input_tokens=10, output_tokens=5)

            mock_stream.__enter__.return_value = mock_stream
            mock_stream.get_final_message.return_value = mock_response
            mock_anthropic.return_value.messages.stream.return_value = mock_stream

            client.complete("system prompt", "user prompt")

            # Get the call arguments
            call_kwargs = mock_anthropic.return_value.messages.stream.call_args[1]

            # Verify thinking parameter IS in the request for Sonnet 5
            assert "thinking" in call_kwargs
            assert call_kwargs["thinking"] == {"type": "adaptive"}
