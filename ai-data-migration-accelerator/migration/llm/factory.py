"""
LLM client factory.

Single responsibility: given a validated `LLMConfig`, return the right
client. Mirrors `migration/connectors/factory.py` — nothing outside this
module names a concrete client class, so adding a provider is a one-line
addition here rather than a change to the CLI or the engines.
"""

from __future__ import annotations

import logging

from migration.llm.client import AnthropicClient, resolve_api_key
from migration.models.config import LLMConfig, LLMProvider

logger = logging.getLogger(__name__)


class UnsupportedProviderError(Exception):
    """Raised when a config requests a provider with no client yet."""


class MissingAPIKeyError(Exception):
    """Raised when the configured provider has no API key available."""


def create_llm_client(llm: LLMConfig):
    """Build a client for the configured provider.

    Raises rather than returning None: the caller decides whether a missing
    key should abort the run or simply skip the AI artifacts, and that
    decision does not belong in a factory.
    """
    if llm.temperature is not None:
        logger.warning(
            "llm.temperature is set to %s in config.yaml but is not supported by "
            "current Claude models and will be ignored. Requests carrying a sampling "
            "parameter are rejected. Use llm.effort (currently '%s') instead.",
            llm.temperature,
            llm.effort.value,
        )

    if llm.provider == LLMProvider.ANTHROPIC:
        api_key = resolve_api_key(llm.api_key_env)
        if api_key is None:
            raise MissingAPIKeyError(
                f"No API key found. Set {llm.api_key_env} in your environment or .env "
                f"file, or set artifacts.conceptual_model to false to skip AI artifacts."
            )
        return AnthropicClient(
            model=llm.model,
            max_tokens=llm.max_tokens,
            effort=llm.effort.value,
            api_key=api_key,
        )

    raise UnsupportedProviderError(
        f"No LLM client implemented for provider '{llm.provider.value}'. "
        "Only 'anthropic' is supported; set llm.provider to anthropic in config.yaml."
    )
