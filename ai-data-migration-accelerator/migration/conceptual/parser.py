"""
Conceptual Model Parser

Turns a raw LLM response into a validated `ConceptualModel`, or rejects it.

This is the trust boundary. Everything upstream is a language model's
judgment; everything downstream is a typed Pydantic object. Nothing
unvalidated is allowed past this module — a malformed response must fail
loudly here rather than produce a half-populated artifact that looks fine
until a downstream generator trips over it.

Two levels of checking:

1. Structural — is it JSON, and does it satisfy the model's schema?
2. Referential — do the cross-references inside it actually resolve? A
   domain listing an entity that does not exist, or a relationship pointing
   at an unknown entity, is well-formed JSON and still wrong. It would also
   produce a broken diagram, so it is caught here.

Reusable by any future AI-assisted engine: `parse_model(raw, SomeModel)` is
generic, and only the referential-integrity pass is conceptual-specific.
"""

from __future__ import annotations

import json
import logging
import re
from typing import TypeVar

from pydantic import BaseModel, ValidationError

from migration.conceptual.models import ConceptualModel

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_CODE_FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class ConceptualModelParseError(Exception):
    """Raised when a response cannot be turned into a valid model."""

    @property
    def duplicate_entity_names(self) -> list[str] | None:
        """Extract duplicate names from the error message if this is a duplicate-names error.

        Returns the names if the error is about duplicates, None otherwise."""
        error_msg = str(self)
        if "Response defined duplicate entity names:" in error_msg:
            # Extract names from message like "Response defined duplicate entity names: Customer, Product"
            prefix = "Response defined duplicate entity names: "
            start = error_msg.find(prefix)
            if start != -1:
                names_str = error_msg[start + len(prefix) :]
                return [name.strip() for name in names_str.split(",")]
        return None


def strip_code_fences(raw: str) -> str:
    """Remove a surrounding markdown code fence if present.

    The prompt asks for bare JSON, but models wrap output in fences often
    enough that failing the whole run over three backticks would be a poor
    trade. This is tolerance for a harmless formatting habit, not tolerance
    for malformed content.
    """
    match = _CODE_FENCE.match(raw)
    return match.group(1) if match else raw.strip()


def parse_model(raw: str, model_class: type[T]) -> T:
    """Parse and validate a raw LLM response into `model_class`.

    Generic on purpose — future engines parse their own response models
    through this same function.
    """
    if raw is None or not raw.strip():
        raise ConceptualModelParseError("Model returned an empty response.")

    text = strip_code_fences(raw)

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        preview = text[:200].replace("\n", " ")
        raise ConceptualModelParseError(
            f"Response was not valid JSON: {exc}. Response began: {preview!r}"
        ) from exc

    if not isinstance(payload, dict):
        raise ConceptualModelParseError(
            f"Expected a JSON object at the top level, got {type(payload).__name__}."
        )

    try:
        return model_class.model_validate(payload)
    except ValidationError as exc:
        raise ConceptualModelParseError(
            f"Response did not match the required {model_class.__name__} schema:\n{exc}"
        ) from exc


def parse_conceptual_model(
    raw: str,
    expected_relationship_count: int = 0,
    source_relationships=None,
    known_tables: list[tuple[str, str]] | None = None,
) -> ConceptualModel:
    """Parse a conceptual model and verify its internal references.

    Reconciles with source relationships to ensure no FK data loss.

    Args:
        raw: The LLM response JSON string
        expected_relationship_count: Number of relationships discovered in source metadata.
                                   If > 0, response must include relationships or an error is raised.
        source_relationships: Optional RelationshipGraph to reconcile against.
                             If provided, missing FKs are restored from source.
        known_tables: Optional (schema, table) pairs from source metadata, used as a
                     fallback to attribute a relationship to the right entity when an
                     entity's declared `source_tables` doesn't cover it.
    """
    model = parse_model(raw, ConceptualModel)
    _resolve_references(model)

    # Reconcile with source relationships BEFORE validation
    # This ensures LLM omissions are restored from the authoritative source
    if source_relationships is not None and source_relationships.relationships:
        from migration.conceptual.reconciler import reconcile_with_source_relationships

        model = reconcile_with_source_relationships(
            model, source_relationships, known_tables=known_tables
        )

    _require_content(model)
    _require_relationships(model, expected_relationship_count)
    return model


# -- Internal --------------------------------------------------------------


def _require_content(model: ConceptualModel) -> None:
    """An empty model is structurally valid and useless. Reject it."""
    if not model.entities:
        raise ConceptualModelParseError(
            "Response contained no entities - a conceptual model with no entities "
            "is not a usable result."
        )
    if not model.summary.strip():
        raise ConceptualModelParseError("Response contained an empty summary.")


def _require_relationships(model: ConceptualModel, expected_count: int) -> None:
    """Validate that source relationships were mapped to entity.relationships.

    When source FKs exist, the LLM response MUST include them in entity.relationships.
    This prevents silent data loss when the model omits relationships.
    """
    if expected_count == 0:
        # No source relationships to preserve
        return

    # Count relationships in the response
    actual_count = sum(len(entity.relationships) for entity in model.entities)

    if actual_count == 0:
        raise ConceptualModelParseError(
            f"Response omitted all source relationships. "
            f"Expected at least {expected_count} relationship(s) from source metadata, "
            f"but entity.relationships arrays were all empty. "
            f"The LLM must map declared database foreign keys to entity.relationships."
        )


def _resolve_references(model: ConceptualModel) -> None:
    """Resolve domain and relationship references to canonical entity names.

    Matching is case- and whitespace-insensitive before a reference is
    declared broken. A model that returns 'customer' where it defined
    'Customer' has made a cosmetic slip, not a semantic error, and failing
    the whole run over letter case would be brittle. A genuinely
    unresolvable name is still an error — it would silently vanish from the
    diagram otherwise.
    """
    canonical = {_normalize(entity.name): entity.name for entity in model.entities}

    duplicates = len(canonical) != len(model.entities)
    if duplicates:
        seen: set[str] = set()
        repeated = sorted(
            {
                entity.name
                for entity in model.entities
                if _normalize(entity.name) in seen or seen.add(_normalize(entity.name))
            }
        )
        raise ConceptualModelParseError(
            f"Response defined duplicate entity names: {', '.join(repeated)}"
        )

    for domain in model.domains:
        resolved = []
        for name in domain.entities:
            match = canonical.get(_normalize(name))
            if match is None:
                raise ConceptualModelParseError(
                    f"Domain '{domain.name}' lists entity '{name}', which is not "
                    f"defined in the model."
                )
            resolved.append(match)
        domain.entities = resolved

    for entity in model.entities:
        for relationship in entity.relationships:
            match = canonical.get(_normalize(relationship.related_entity))
            if match is None:
                raise ConceptualModelParseError(
                    f"Entity '{entity.name}' declares a relationship to "
                    f"'{relationship.related_entity}', which is not defined in the model."
                )
            relationship.related_entity = match


def _normalize(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (name or "").lower())
