"""Reconcile ConceptualModel with authoritative source relationships.

After LLM-generated conceptual model parsing, this module ensures all source
FK relationships are present, even if the LLM omitted them. Technical fields
(entity names, cardinality, optionality) are restored from RelationshipPackage.
Business semantics (verb_phrase, description) come from the LLM when
available, else a sensible default.

This preserves the contract: RelationshipEngine discovers FK relationships,
ConceptualModelEngine receives them, and LogicalModelEngine receives the
complete relationship set. The LLM assists with business context but is
never the authority on whether a source FK relationship exists.

Direction and field semantics (matches migration/relationship/models.py and
how migration/logical/engine.py consumes ConceptualRelationship):

- A `Relationship` in RelationshipGraph points from the table holding the FK
  (`source`, the child/"many" side) to the table it references (`target`,
  the parent/"one" side). Its `cardinality` is expressed source-to-target
  (naturally MANY_TO_ONE), and `is_optional` reflects whether the source's
  FK column is nullable.
- A `ConceptualRelationship` may be declared on EITHER entity, with
  `cardinality` expressed from the declaring entity toward `related_entity`.
  LogicalModelEngine derives parent/child from that cardinality alone (see
  `LogicalModelEngine._orient`), then applies `is_optional` directly to the
  child's foreign-key attribute. That means `is_optional` always means "is
  the FK-holder's column nullable" and must equal `fk.is_optional` verbatim
  regardless of which entity declares the relationship - only `cardinality`
  needs to flip when the relationship is declared from the target's side.
"""

from __future__ import annotations

import logging

from migration.conceptual.models import ConceptualModel, ConceptualRelationship
from migration.relationship.models import Cardinality, Relationship, RelationshipGraph
from migration.relationship.rules import name_variants, normalize_identifier

logger = logging.getLogger(__name__)


def reconcile_with_source_relationships(
    model: ConceptualModel,
    source_relationships: RelationshipGraph,
    entity_lookup: dict[str, str] | None = None,
    known_tables: list[tuple[str, str]] | None = None,
) -> ConceptualModel:
    """Reconcile ConceptualModel with authoritative source FK relationships.

    Ensures every discovered FK is present in the conceptual model with
    technical fields (cardinality, optionality) matching the source exactly.
    If the LLM omitted a relationship, it is added. If the LLM already
    declared it (from either entity), its technical fields are corrected in
    place and its business semantics (verb_phrase, description) are kept.

    Args:
        model: Parsed ConceptualModel (may have omitted or misstated relationships)
        source_relationships: Authoritative FK relationships from metadata
        entity_lookup: Optional pre-built "schema.table" -> entity name mapping.
                      If None, built from model.entities[].source_tables (with a
                      bare-table-name fallback for unqualified names).
        known_tables: Optional (schema, table) pairs from the source metadata.
                      Used only to fill gaps left by `entity_lookup` - when an
                      entity's declared `source_tables` doesn't resolve a table
                      (the LLM left it empty or mismatched), a table is mapped
                      to an entity by normalized name instead, but only when
                      exactly one entity's name matches it unambiguously. This
                      never invents a relationship - it only helps attribute an
                      already-discovered FK to the right entity.

    Returns:
        The same ConceptualModel, modified in place, with all source
        relationships present and technically correct.
    """
    if not source_relationships.relationships:
        return model

    if entity_lookup is None:
        entity_lookup = _build_entity_lookup(model)

    if known_tables:
        for key, entity_name in _build_fallback_entity_lookup(model, known_tables).items():
            entity_lookup.setdefault(key, entity_name)

    existing_by_pair = _index_existing_relationships(model)

    restored = 0
    corrected = 0

    for fk in source_relationships.relationships:
        source_entity_name = entity_lookup.get(_table_key(fk.source_schema, fk.source_table))
        target_entity_name = entity_lookup.get(_table_key(fk.target_schema, fk.target_table))

        if not source_entity_name or not target_entity_name:
            logger.debug(
                "Skipping FK %s.%s -> %s.%s: table not mapped to any entity in the "
                "conceptual model",
                fk.source_schema,
                fk.source_table,
                fk.target_schema,
                fk.target_table,
            )
            continue

        pair_key = frozenset((source_entity_name, target_entity_name))
        matches = existing_by_pair.get(pair_key)

        if matches:
            for holder_name, relationship in matches:
                if _correct_relationship_technical_fields(
                    holder_name, source_entity_name, relationship, fk
                ):
                    corrected += 1
            continue

        relationship = _add_relationship_to_entity(
            model, target_entity_name, source_entity_name, fk
        )
        existing_by_pair.setdefault(pair_key, []).append((target_entity_name, relationship))
        restored += 1

    if restored or corrected:
        logger.info(
            "Reconciliation complete: %s relationship(s) restored, %s corrected",
            restored,
            corrected,
        )

    return model


# -- Internal ----------------------------------------------------------------


def _build_entity_lookup(model: ConceptualModel) -> dict[str, str]:
    """Build "schema.table" -> entity_name mapping from source_tables.

    Also indexes bare table names (no schema) as a fallback for when the
    LLM returns an unqualified or mis-schemaed source_tables entry - but
    only when that bare name is unambiguous across the whole model, so a
    same-named table in two schemas never resolves to the wrong entity.
    """
    lookup: dict[str, str] = {}
    bare_owners: dict[str, set[str]] = {}

    for entity in model.entities:
        for source_table in entity.source_tables:
            qualified = source_table.strip().lower()
            if not qualified:
                continue
            lookup[qualified] = entity.name
            bare = qualified.rsplit(".", 1)[-1]
            bare_owners.setdefault(bare, set()).add(entity.name)

    for bare, owners in bare_owners.items():
        if len(owners) == 1 and bare not in lookup:
            lookup[bare] = next(iter(owners))

    return lookup


def _build_fallback_entity_lookup(
    model: ConceptualModel, known_tables: list[tuple[str, str]]
) -> dict[str, str]:
    """Map "schema.table" -> entity name by normalized name, for tables an
    entity's declared `source_tables` failed to cover.

    Entity names are business names invented by the LLM (e.g. "Customer" for
    a `customer` table), so this only helps when an entity's name is a close
    variant of its table's name - which is the common case, and exactly the
    case the reconciler most needs to cover when the LLM leaves
    `source_tables` empty. A table is mapped only when exactly one entity's
    normalized name matches it, so an ambiguous or coincidental match is
    left unresolved rather than guessed.
    """
    entity_names_by_normalized: dict[str, list[str]] = {}
    for entity in model.entities:
        entity_names_by_normalized.setdefault(normalize_identifier(entity.name), []).append(
            entity.name
        )

    lookup: dict[str, str] = {}
    for schema_name, table_name in known_tables:
        candidates: set[str] = set()
        for variant in name_variants(normalize_identifier(table_name)):
            candidates.update(entity_names_by_normalized.get(variant, []))

        if len(candidates) == 1:
            lookup[_table_key(schema_name, table_name)] = next(iter(candidates))

    return lookup


def _table_key(schema: str, table: str) -> str:
    """Create consistent key for (schema, table) pair."""
    return f"{schema}.{table}".lower()


def _index_existing_relationships(
    model: ConceptualModel,
) -> dict[frozenset[str], list[tuple[str, ConceptualRelationship]]]:
    """Index existing relationships by unordered entity pair.

    A relationship between two entities may have been declared by either
    side; grouping by the unordered pair lets reconciliation recognise it
    regardless of direction, and avoids adding a duplicate.
    """
    index: dict[frozenset[str], list[tuple[str, ConceptualRelationship]]] = {}
    for entity in model.entities:
        for relationship in entity.relationships:
            key = frozenset((entity.name, relationship.related_entity))
            index.setdefault(key, []).append((entity.name, relationship))
    return index


def _correct_relationship_technical_fields(
    holder_name: str,
    fk_source_entity_name: str,
    relationship: ConceptualRelationship,
    fk: Relationship,
) -> bool:
    """Correct an LLM-declared relationship's technical fields in place.

    Business semantics (verb_phrase, description) are left untouched - only
    cardinality and optionality, which must match the authoritative source
    regardless of what the LLM produced.

    Returns:
        True if any field was changed.
    """
    if holder_name == fk_source_entity_name:
        # Declared from the FK holder's side: cardinality matches the FK verbatim.
        correct_cardinality = fk.cardinality
    else:
        # Declared from the referenced side: cardinality is the FK's inverse.
        correct_cardinality = _invert_cardinality(fk.cardinality)

    # is_optional always describes the FK holder's column nullability,
    # regardless of which entity declared the relationship.
    correct_is_optional = fk.is_optional

    changed = False
    if relationship.cardinality != correct_cardinality:
        logger.info(
            "Correcting cardinality for %s -> %s: %s -> %s (source of truth: RelationshipPackage)",
            holder_name,
            relationship.related_entity,
            relationship.cardinality.value,
            correct_cardinality.value,
        )
        relationship.cardinality = correct_cardinality
        changed = True

    if relationship.is_optional != correct_is_optional:
        logger.info(
            "Correcting optionality for %s -> %s: %s -> %s (source of truth: RelationshipPackage)",
            holder_name,
            relationship.related_entity,
            relationship.is_optional,
            correct_is_optional,
        )
        relationship.is_optional = correct_is_optional
        changed = True

    return changed


def _add_relationship_to_entity(
    model: ConceptualModel,
    entity_name: str,
    related_entity_name: str,
    fk: Relationship,
) -> ConceptualRelationship:
    """Add an FK-derived relationship to `entity_name` (the FK's target/parent).

    Args:
        model: ConceptualModel to modify in-place
        entity_name: Entity to add the relationship to (target of FK)
        related_entity_name: Entity this relationship points to (source of FK)
        fk: Authoritative relationship from RelationshipPackage

    Returns:
        The newly created ConceptualRelationship.
    """
    entity = next((e for e in model.entities if e.name == entity_name), None)
    if not entity:
        raise ValueError(f"Entity {entity_name} not found in model")

    # Cardinality is expressed from entity_name toward related_entity_name,
    # which is the FK's target-to-source direction: the inverse of the FK.
    inverted_cardinality = _invert_cardinality(fk.cardinality)
    verb_phrase = _infer_verb_phrase(entity_name, related_entity_name)

    relationship = ConceptualRelationship(
        related_entity=related_entity_name,
        verb_phrase=verb_phrase,
        cardinality=inverted_cardinality,
        # is_optional always reflects the FK holder's column nullability,
        # not the declaring entity's side - no inversion here.
        is_optional=fk.is_optional,
        description=(
            f"Restored from source metadata: {related_entity_name} references "
            f"{entity_name}."
        ),
    )

    entity.relationships.append(relationship)

    logger.info(
        "Restored missing FK relationship: %s -> %s (%s%s)",
        entity_name,
        related_entity_name,
        inverted_cardinality.value,
        " (optional)" if fk.is_optional else "",
    )

    return relationship


def _invert_cardinality(cardinality: Cardinality) -> Cardinality:
    """Invert cardinality when flipping which entity declares the relationship.

    MANY_TO_ONE inverts to ONE_TO_MANY, ONE_TO_MANY inverts to MANY_TO_ONE.
    ONE_TO_ONE, MANY_TO_MANY and UNKNOWN are symmetric and stay unchanged.
    """
    if cardinality == Cardinality.MANY_TO_ONE:
        return Cardinality.ONE_TO_MANY
    if cardinality == Cardinality.ONE_TO_MANY:
        return Cardinality.MANY_TO_ONE
    return cardinality


def _infer_verb_phrase(entity_name: str, related_entity_name: str) -> str:
    """Generate a sensible default verb phrase for a restored FK relationship.

    Used only when the LLM omitted the relationship entirely, so there is no
    business phrasing to preserve.
    """
    related_lower = related_entity_name.lower()
    entity_lower = entity_name.lower()

    if entity_lower + "s" == related_lower or entity_lower == related_lower.rstrip("s"):
        return "contains"

    return "references"
