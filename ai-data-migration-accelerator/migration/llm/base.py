"""
Base LLM client interface.

All providers must implement this interface. The platform depends only on this
interface, never on specific provider implementations.
"""

from __future__ import annotations

from abc import ABC, abstractmethod


class LLMClient(ABC):
    """Provider-agnostic LLM client interface.

    One method. Prompt in, text out. Any provider, any transport.
    Engines and orchestrators depend only on this interface.
    """

    @abstractmethod
    def complete(
        self, system_prompt: str, user_prompt: str, json_schema: dict | None = None
    ) -> str:
        """Return the model's response as raw text.

        Args:
            system_prompt: System prompt that defines behavior/role
            user_prompt: User message/query
            json_schema: Optional JSON schema to constrain response format

        Returns:
            Model response as plain text

        Raises:
            LLMError: If the request fails or provider rejects it
        """
        ...


class LLMError(Exception):
    """Raised for any failure talking to an LLM provider."""
