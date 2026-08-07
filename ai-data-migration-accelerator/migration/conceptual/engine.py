"""
Conceptual Model Engine

Coordinates the first AI-assisted module.

    MetadataPackage + ProfilePackage + RelationshipPackage
        -> ContextBuilder    (deterministic)
        -> PromptBuilder     (deterministic)
        -> LLM               (the only non-deterministic step)
        -> Parser            (deterministic, validating)
        -> ConceptualModel

The engine never reads a JSON file. It takes the three Pydantic packages and
returns a Pydantic package. File I/O is the writer's job, and the
orchestrator's.

The AI boundary is a single method, `LLMClient.complete`. The engine has no
knowledge of any provider, and tests substitute a two-line stub. That is
what keeps this module testable without an API key and without a network.
"""

from __future__ import annotations

import logging
from typing import Protocol

from migration.canonical.models import MetadataPackage
from migration.conceptual.context_builder import ContextBuilder
from migration.conceptual.models import (
    BusinessContext,
    ConceptualModel,
    ConceptualModelPackage,
)
from migration.conceptual.parser import parse_conceptual_model
from migration.conceptual.prompt_builder import PromptBuilder
from migration.profiler.models import ProfilePackage
from migration.relationship.models import RelationshipPackage

logger = logging.getLogger(__name__)


class LLMClient(Protocol):
    """The entire AI surface this platform depends on.

    One method. Prompt in, text out. Any provider, any transport, and a stub
    in tests. Keeping it this narrow is what stops provider details leaking
    into the engines.
    """

    def complete(self, system_prompt: str, user_prompt: str, json_schema: dict | None = None) -> str:
        """Return the model's response as raw text."""
        ...


class ConceptualModelEngine:
    """Generates a conceptual model from the deterministic artifacts."""

    def __init__(
        self,
        client: LLMClient,
        context_builder: ContextBuilder | None = None,
        prompt_builder: PromptBuilder | None = None,
        model_name: str | None = None,
    ):
        self.client = client
        self.context_builder = context_builder or ContextBuilder()
        self.prompt_builder = prompt_builder or PromptBuilder()
        self.model_name = model_name

    # -- Public API --------------------------------------------------------

    def generate(
        self,
        metadata: MetadataPackage,
        profile: ProfilePackage | None = None,
        relationships: RelationshipPackage | None = None,
    ) -> ConceptualModelPackage:
        """Run the full flow and return a validated package."""
        context = self.build_context(metadata, profile, relationships)

        system_prompt = self.prompt_builder.build_system_prompt()
        user_prompt = self.prompt_builder.build_user_prompt(context)
        schema = self.prompt_builder.response_json_schema(ConceptualModel)

        logger.info(
            "Requesting conceptual model for '%s' (%s tables described, %s relationships)",
            context.database_name,
            len(context.tables),
            context.total_relationships,
        )

        raw = self.client.complete(system_prompt, user_prompt, schema)
        model = parse_conceptual_model(raw)

        logger.info(
            "Conceptual model parsed: %s domains, %s entities, %s business rules",
            len(model.domains),
            len(model.entities),
            len(model.business_rules),
        )

        return ConceptualModelPackage(
            conceptual_model=model,
            generated_by=self.model_name or getattr(self.client, "model", None),
        )

    def build_context(
        self,
        metadata: MetadataPackage,
        profile: ProfilePackage | None = None,
        relationships: RelationshipPackage | None = None,
    ) -> BusinessContext:
        """Build the business context without calling the AI.

        Exposed separately so the context can be inspected, tested, and
        token-counted before anyone spends money on a completion.
        """
        return self.context_builder.build(
            metadata=metadata.metadata,
            profile=profile.profile if profile is not None else None,
            relationships=relationships.relationships if relationships is not None else None,
        )


