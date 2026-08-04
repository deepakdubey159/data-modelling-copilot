"""
LLM Client

The platform's entire AI surface is one method: prompt in, text out. Engines
depend on that shape and nothing else, which is what keeps provider details
out of the business logic and lets every engine be tested with a stub.

`AnthropicClient` satisfies it structurally — engines type against a
`Protocol`, so no inheritance is needed and no engine imports this module.
"""

from __future__ import annotations

import logging
import os

logger = logging.getLogger(__name__)

DEFAULT_MODEL = "claude-opus-5"
DEFAULT_MAX_TOKENS = 32000
DEFAULT_EFFORT = "high"


class LLMError(Exception):
    """Raised for any failure talking to the model provider."""


class AnthropicClient:
    """`LLMClient` backed by the Anthropic SDK.

    Three deliberate choices, all from the current API contract:

    - **`temperature` is never sent.** Sampling parameters were removed from
      current models and a request carrying one is rejected with a 400. The
      platform's `LLMConfig.temperature` therefore does not reach the API;
      reasoning depth is controlled with `effort` instead.
    - **Structured outputs constrain the response** to the caller's JSON
      schema, so malformed JSON is prevented rather than merely detected.
      The parser still validates independently — a provider without schema
      support must not be able to write an invalid artifact.
    - **The request is streamed.** `max_tokens` sits well above the point
      where a non-streaming request risks an HTTP timeout.

    The SDK is imported lazily inside `complete`, so importing this module
    costs nothing and the package is only needed when a run actually calls
    the API.
    """

    def __init__(
        self,
        model: str = DEFAULT_MODEL,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        effort: str = DEFAULT_EFFORT,
        api_key: str | None = None,
    ):
        self.model = model
        self.max_tokens = max_tokens
        self.effort = effort
        self._api_key = api_key

    def complete(
        self, system_prompt: str, user_prompt: str, json_schema: dict | None = None
    ) -> str:
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - depends on env
            raise LLMError(
                "The 'anthropic' package is required to generate AI artifacts. "
                "Install it with: pip install anthropic"
            ) from exc

        client = (
            anthropic.Anthropic(api_key=self._api_key)
            if self._api_key
            else anthropic.Anthropic()
        )

        output_config: dict = {"effort": self.effort}
        if json_schema is not None:
            output_config["format"] = {"type": "json_schema", "schema": json_schema}

        logger.info(
            "Calling %s (max_tokens=%s, effort=%s)", self.model, self.max_tokens, self.effort
        )

        try:
            with client.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system_prompt,
                thinking={"type": "adaptive"},
                output_config=output_config,
                messages=[{"role": "user", "content": user_prompt}],
            ) as stream:
                response = stream.get_final_message()
        except anthropic.APIStatusError as exc:
            raise LLMError(
                f"{self.model} rejected the request ({exc.status_code}): {exc.message}"
            ) from exc
        except anthropic.APIConnectionError as exc:
            raise LLMError(f"Could not reach the Anthropic API: {exc}") from exc

        # A refusal is a successful HTTP response with empty or partial
        # content, so it must be checked before reading content blocks.
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


def resolve_api_key(env_var: str) -> str | None:
    """Read the API key from the environment.

    Returns None rather than raising, so a run without a key can still
    produce every deterministic artifact.
    """
    key = os.environ.get(env_var, "").strip()
    return key or None
