"""
OpenAI LLM provider implementation.

Translates common application settings to OpenAI API parameters.
Handles OpenAI-specific request format and capabilities.
"""

from __future__ import annotations

import json
import logging

from migration.llm.base import LLMClient, LLMError
from migration.llm.capabilities import get_capabilities

logger = logging.getLogger(__name__)


class OpenAIClient(LLMClient):
    """OpenAI SDK-based LLM client.

    Converts common application settings to OpenAI API parameters.
    Note: OpenAI does not support adaptive thinking or the 'effort' parameter,
    so 'effort' is mapped to a reasonable temperature value instead.
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
        """Send request to OpenAI API with structured output if requested."""
        try:
            from openai import OpenAI as OpenAISDK
        except ImportError as exc:
            raise LLMError(
                "The 'openai' package is required. "
                "Install it with: pip install openai"
            ) from exc

        client = (
            OpenAISDK(api_key=self._api_key) if self._api_key else OpenAISDK()
        )

        capabilities = get_capabilities(self.model)

        # OpenAI doesn't support 'effort', so map it to temperature
        # high effort → lower temp (more focused), low effort → higher temp (more creative)
        temp_map = {
            "low": 0.8,
            "medium": 0.5,
            "high": 0.2,
            "xhigh": 0.1,
            "max": 0.0,
        }
        temperature = temp_map.get(self.effort, 0.5)

        logger.info(
            "Calling %s (max_tokens=%s, temperature=%s)", self.model, self.max_tokens, temperature
        )

        request_kwargs = {
            "model": self.model,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }

        # Add structured output if requested and supported
        if json_schema is not None:
            if capabilities and not capabilities.supports_structured_output:
                raise LLMError(
                    f"Model '{self.model}' does not support structured output. "
                    "Cannot constrain response to JSON schema."
                )

            request_kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "structured_response",
                    "schema": json_schema,
                },
            }

        try:
            response = client.chat.completions.create(**request_kwargs)
        except Exception as exc:
            raise LLMError(f"OpenAI API request failed: {exc}") from exc

        usage = response.usage
        logger.info(
            "Response received (input=%s, output=%s tokens)",
            getattr(usage, "prompt_tokens", "?"),
            getattr(usage, "completion_tokens", "?"),
        )

        content = response.choices[0].message.content
        if not content:
            raise LLMError("OpenAI returned an empty response.")

        return content
