"""
LLM client factory.

Single responsibility: given a validated `LLMConfig`, instantiate the right
provider adapter. Nothing outside this module names concrete client classes.
"""

from __future__ import annotations

import logging

from migration.llm.anthropic import AnthropicClient
from migration.llm.base import LLMClient
from migration.llm.capabilities import get_capabilities
from migration.llm.client import resolve_api_key
from migration.llm.openai import OpenAIClient
from migration.models.config import LLMConfig, LLMProvider

logger = logging.getLogger(__name__)


class UnsupportedProviderError(Exception):
    """Raised when a config requests a provider with no client yet."""


class MissingAPIKeyError(Exception):
    """Raised when the configured provider has no API key available."""


class UnsupportedModelError(Exception):
    """Raised when a model doesn't support required capabilities."""


def create_llm_client(llm: LLMConfig) -> LLMClient:
    """Build a client for the configured provider.

    Validates that the model exists and supports required capabilities,
    then returns the appropriate provider adapter.

    Raises:
        MissingAPIKeyError: If no API key is found
        UnsupportedProviderError: If provider is not implemented
        UnsupportedModelError: If model doesn't support required features
    """
    if llm.temperature is not None:
        logger.warning(
            "llm.temperature is deprecated. Use llm.effort (currently '%s') instead.",
            llm.effort.value,
        )

    api_key = resolve_api_key(llm.api_key_env)
    if api_key is None:
        raise MissingAPIKeyError(
            f"No API key found. Set {llm.api_key_env} in your environment or .env "
            f"file, or set artifacts.conceptual_model to false to skip AI artifacts."
        )

    if llm.provider == LLMProvider.ANTHROPIC:
        return _create_anthropic_client(llm, api_key)
    elif llm.provider == LLMProvider.OPENAI:
        return _create_openai_client(llm, api_key)
    else:
        provider_str = llm.provider.value if hasattr(llm.provider, "value") else str(llm.provider)
        raise UnsupportedProviderError(
            f"No LLM client implemented for provider '{provider_str}'. "
            f"Supported providers: anthropic, openai"
        )


def _create_anthropic_client(llm: LLMConfig, api_key: str) -> AnthropicClient:
    """Create and validate an Anthropic client."""
    capabilities = get_capabilities(llm.model)

    if capabilities is None:
        logger.warning(
            "Model '%s' is not in the capability registry. "
            "It will be attempted without adaptive thinking.",
            llm.model,
        )
    else:
        logger.info(
            "Model '%s' supports: adaptive_thinking=%s, structured_output=%s",
            llm.model,
            capabilities.supports_adaptive_thinking,
            capabilities.supports_structured_output,
        )

    return AnthropicClient(
        model=llm.model,
        max_tokens=llm.max_tokens,
        effort=llm.effort.value,
        api_key=api_key,
    )


def _create_openai_client(llm: LLMConfig, api_key: str) -> OpenAIClient:
    """Create and validate an OpenAI client."""
    capabilities = get_capabilities(llm.model)

    if capabilities is None:
        logger.warning(
            "Model '%s' is not in the capability registry. "
            "Proceeding with defaults.",
            llm.model,
        )
    else:
        logger.info(
            "Model '%s' supports: structured_output=%s",
            llm.model,
            capabilities.supports_structured_output,
        )

    return OpenAIClient(
        model=llm.model,
        max_tokens=llm.max_tokens,
        effort=llm.effort.value,
        api_key=api_key,
    )
