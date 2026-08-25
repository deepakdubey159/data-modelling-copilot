"""
Model capability registry.

Defines which models support which features (thinking, structured output, etc.)
and provides helper functions to detect capabilities at runtime.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ModelCapabilities:
    """Describes what a model supports."""

    model_id: str
    provider: str
    supports_adaptive_thinking: bool = False
    supports_effort: bool = True
    supports_structured_output: bool = True
    supports_streaming: bool = True
    max_tokens_default: int = 32000
    max_tokens_max: int = 200000


# Capability registry — single source of truth for what each model supports
CAPABILITY_REGISTRY: dict[str, ModelCapabilities] = {
    # Anthropic models
    "claude-opus-5": ModelCapabilities(
        model_id="claude-opus-5",
        provider="anthropic",
        supports_adaptive_thinking=True,
        supports_structured_output=True,
        supports_streaming=True,
        max_tokens_max=200000,
    ),
    "claude-opus-4-8": ModelCapabilities(
        model_id="claude-opus-4-8",
        provider="anthropic",
        supports_adaptive_thinking=True,
        supports_structured_output=True,
        supports_streaming=True,
        max_tokens_max=200000,
    ),
    "claude-opus-4-6": ModelCapabilities(
        model_id="claude-opus-4-6",
        provider="anthropic",
        supports_adaptive_thinking=True,
        supports_structured_output=True,
        supports_streaming=True,
        max_tokens_max=200000,
    ),
    "claude-sonnet-5": ModelCapabilities(
        model_id="claude-sonnet-5",
        provider="anthropic",
        supports_adaptive_thinking=True,
        supports_structured_output=True,
        supports_streaming=True,
        max_tokens_max=200000,
    ),
    "claude-sonnet-4-6": ModelCapabilities(
        model_id="claude-sonnet-4-6",
        provider="anthropic",
        supports_adaptive_thinking=True,
        supports_structured_output=True,
        supports_streaming=True,
    ),
    "claude-sonnet-4-8": ModelCapabilities(
        model_id="claude-sonnet-4-8",
        provider="anthropic",
        supports_adaptive_thinking=True,
        supports_structured_output=True,
        supports_streaming=True,
    ),
    "claude-haiku-4-5-20251001": ModelCapabilities(
        model_id="claude-haiku-4-5-20251001",
        provider="anthropic",
        supports_adaptive_thinking=False,
        supports_effort=False,
        supports_structured_output=True,
        supports_streaming=True,
        max_tokens_default=10000,
        max_tokens_max=100000,
    ),
    # OpenAI models
    "gpt-4o": ModelCapabilities(
        model_id="gpt-4o",
        provider="openai",
        supports_adaptive_thinking=False,
        supports_effort=False,
        supports_structured_output=True,
        supports_streaming=True,
    ),
    "gpt-4-turbo": ModelCapabilities(
        model_id="gpt-4-turbo",
        provider="openai",
        supports_adaptive_thinking=False,
        supports_effort=False,
        supports_structured_output=True,
        supports_streaming=True,
    ),
    "gpt-4": ModelCapabilities(
        model_id="gpt-4",
        provider="openai",
        supports_adaptive_thinking=False,
        supports_effort=False,
        supports_structured_output=False,
        supports_streaming=True,
    ),
}


def get_capabilities(model_id: str) -> ModelCapabilities | None:
    """Look up capabilities for a model ID.

    Returns None if the model is unknown (unregistered). Unknown models
    should trigger a configuration warning but may still be attempted.
    """
    return CAPABILITY_REGISTRY.get(model_id)


def resolve_model_id_prefix(partial_id: str, provider: str) -> str | None:
    """Resolve a partial model ID (e.g., 'claude-opus-5') to a full model ID.

    For Anthropic, this handles version suffixes. For other providers,
    returns the input as-is.

    Returns None if ambiguous or not found.
    """
    if provider == "anthropic":
        # Exact match first
        if partial_id in CAPABILITY_REGISTRY:
            return partial_id

        # Prefix match for models like 'claude-haiku-4-5' → 'claude-haiku-4-5-20251001'
        matches = [m for m in CAPABILITY_REGISTRY if m.startswith(partial_id)]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            return None  # Ambiguous
    else:
        if partial_id in CAPABILITY_REGISTRY:
            return partial_id

    return None
