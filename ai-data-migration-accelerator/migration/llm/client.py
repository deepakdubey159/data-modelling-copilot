"""
LLM Client — backward compatibility module.

Re-exports the provider-agnostic interface and helpers.
New code should import directly from base, anthropic, openai, or factory.
"""

from __future__ import annotations

import os

# Re-export for backward compatibility
from migration.llm.base import LLMClient, LLMError
from migration.llm.anthropic import AnthropicClient

__all__ = ["LLMClient", "LLMError", "AnthropicClient", "resolve_api_key"]


def resolve_api_key(env_var: str) -> str | None:
    """Read the API key from the environment.

    Returns None rather than raising, so a run without a key can still
    produce every deterministic artifact.
    """
    key = os.environ.get(env_var, "").strip()
    return key or None
