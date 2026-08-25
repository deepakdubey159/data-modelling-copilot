"""
Anthropic LLM provider implementation.

Translates common application settings (effort, max_tokens) to Anthropic
API parameters. Handles model-specific capabilities like adaptive thinking.
"""

from __future__ import annotations

import logging

from migration.llm.base import LLMClient, LLMError
from migration.llm.capabilities import get_capabilities

logger = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    """Anthropic SDK-based LLM client.

    Converts common application settings to Anthropic API parameters,
    respecting model-specific capabilities (e.g., not sending adaptive
    thinking to models that don't support it).
    """

    def __init__(
        self,
        model: str,
        max_tokens: int = 32000,
        effort: str = "high",
        api_key: str | None = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self._api_key = api_key

    def complete(
        self, system_prompt: str, user_prompt: str, json_schema: dict | None = None
    ) -> str:
        """Send request to Claude API with adaptive thinking if supported."""
        try:
            import anthropic
        except ImportError as exc:
            raise LLMError(
                "The 'anthropic' package is required. "
                "Install it with: pip install anthropic"
            ) from exc

        client = (
            anthropic.Anthropic(api_key=self._api_key)
            if self._api_key
            else anthropic.Anthropic()
        )

        capabilities = get_capabilities(self.model)

        output_config: dict = {}
        # Only include effort if the model supports it
        if capabilities and capabilities.supports_effort:
            output_config["effort"] = self.effort
        elif not capabilities:
            # Unknown model: try sending effort, log warning
            output_config["effort"] = self.effort
            logger.warning(
                "Model '%s' not in capability registry; attempting with effort='%s'",
                self.model,
                self.effort,
            )

        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}

        logger.info(
            "Calling %s (max_tokens=%s, effort=%s, output_config=%s)",
            self.model,
            self.max_tokens,
            self.effort,
            list(output_config.keys()),
        )

        stream_kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "system": system_prompt,
            "output_config": output_config,
            "messages": [{"role": "user", "content": user_prompt}],
        }

        # Only send adaptive thinking if the model supports it
        if capabilities and capabilities.supports_adaptive_thinking:
            stream_kwargs["thinking"] = {"type": "adaptive"}

        try:
            with client.messages.stream(**stream_kwargs) as stream:
                response = stream.get_final_message()
        except anthropic.APIStatusError as exc:
            raise LLMError(
                f"{self.model} rejected the request ({exc.status_code}): {exc.message}"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"Could not reach the Anthropic API: {exc}") from exc

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            raise LLMError(f"The model declined this request (category: {category}).")

        if response.stop_reason == "max_tokens":
            logger.warning(
                "Response hit the max_tokens ceiling (%s) and may be truncated. "
                "Raise llm.max_tokens in config.yaml if parsing fails.",
                self.max_tokens,
            )

        usage = response.usage
        logger.info(
            "Response received (input=%s, output=%s tokens)",
            getattr(usage, "input_tokens", "?"),
            getattr(usage, "output_tokens", "?"),
        )

        return "".join(block.text for block in response.content if block.type == "text")
