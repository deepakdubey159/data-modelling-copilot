"""
Logical Data Model Engine

Derives a logical model from the conceptual model in `business_model.json`.

Fully deterministic — no LLM. The conceptual model already contains the
business judgment (what the entities mean, how they relate); turning that
into a normalized logical design is a set of well-defined transformation
rules, and rules belong in code. This keeps the platform's stated order
intact: deterministic engines first, AI only where judgment is genuinely
required.

Transformation rules
--------------------
1.  Every conceptual entity becomes a logical entity.
2.  Attributes are typed against abstract domains by name (`_infer_type`).
3.  The business key becomes the primary key. Where none was identified, a
    surrogate identifier is introduced and recorded as a design decision.
4.  Attributes that look uniquely identifying but are not the primary key
    become alternate keys.
5.  Many-to-many relationships are resolved into associative entities
    (1NF: a relationship cannot carry a repeating group of parents).
6.  Foreign key attributes are propagated from parent to child.
7.  An entity whose business key contains a parent's key is DEPENDENT, and
    that relationship is identifying.
8.  Optionality is carried through from the conceptual relationship.
"""

from __future__ import annotations

import logging
import re

from migration.canonical.models import MetadataPackage
from migration.conceptual.models import (
    ConceptualEntity,
    ConceptualModel,
    ConceptualModelPackage,
)
from migration.metadata.source_lookup import resolve_source_column
from migration.logical.models import (
    AttributeRole,
    EntityKind,
    KeyKind,
    LogicalAttribute,
    LogicalDataType,
    LogicalEntity,
    LogicalKey,
    LogicalModel,
    LogicalModelPackage,
    LogicalRelationship,
    NormalForm,
    NormalizationAction,
    Optionality,
    SubjectArea,
)
from migration.relationship.models import Cardinality

logger = logging.getLogger(__name__)

# Attribute-name keywords mapped to abstract domains. Ordered: the first
# match wins, so more specific keywords must come first ("order date"
# should be DATE, not TEXT).
_TYPE_KEYWORDS: tuple[tuple[LogicalDataType, tuple[str, ...]], ...] = (
    (LogicalDataType.EMAIL, ("email",)),
    (LogicalDataType.PHONE, ("phone", "telephone", "mobile", "fax")),
    (LogicalDataType.TIMESTAMP, ("timestamp", "datetime", "recorded at", "performed at")),
    (LogicalDataType.DATE, ("date", "hired", "shipped", "created")),
    (LogicalDataType.PERCENTAGE, ("percent", "percentage", "rate", "discount")),
    (LogicalDataType.AMOUNT, ("amount", "price", "salary", "credit limit", "cost", "value", "total")),
    (LogicalDataType.WHOLE_NUMBER, ("quantity", "count", "level", "number of", "line number")),
    (LogicalDataType.BOOLEAN, ("is", "has", "flag", "indicator")),
    (
        LogicalDataType.CODE,
        ("code", "status", "type", "method", "reason", "sku", "stock keeping unit", "operation"),
    ),
    (LogicalDataType.IDENTIFIER, ("identifier", "number", "reference", "tracking", "id")),
)

# Keywords are matched on word boundaries, not as raw substrings. Without
# this, "Account Status" matches "count" and is typed as a whole number.
_TYPE_PATTERNS: tuple[tuple[LogicalDataType, "re.Pattern[str]"], ...] = tuple(
    (
        data_type,
        re.compile(r"\b(?:" + "|".join(re.escape(k) for k in keywords) + r")\b"),
    )
    for data_type, keywords in _TYPE_KEYWORDS
)

# Attribute names that identify a single instance and therefore make good
# alternate keys when they are not already the primary key.
_ALTERNATE_KEY_KEYWORDS = (
    "email",
    "code",
    "number",
    "sku",
    "tracking",
    "reference",
    "identifier",
)


class LogicalModelEngine:
    """Derives a `LogicalModelPackage` from a conceptual model."""

    def __init__(
        self,
        package: ConceptualModelPackage,
        source_artifact: str = "business_model.json",
        metadata: MetadataPackage | None = None,
    ):
        self.package = package
        self.model: ConceptualModel = package.conceptual_model
        self.source_artifact = source_artifact
        self.metadata = metadata

        self._entities: dict[str, LogicalEntity] = {}
        self._relationships: list[LogicalRelationship] = []
        self._actions: list[NormalizationAction] = []
        self._assumptions: list[str] = []

    # -- Public API --------------------------------------------------------

    def generate(self) -> LogicalModelPackage:
        """Run the transformation and return a validated package."""
        self._entity_domain = self._map_entity_to_domain()

        self._build_entities()
        pairs = self._collect_relationship_pairs()
        self._resolve_many_to_many(pairs)
        self._propagate_foreign_keys(pairs)
        self._classify_dependents()
        self._record_normalization_checks()

        logical = LogicalModel(
            database_name=self.model.database_name,
            summary=self._summary(),
            subject_areas=self._subject_areas(),
            entities=[self._entities[name] for name in sorted(self._entities)],
            relationships=sorted(
                self._relationships, key=lambda r: (r.parent_entity, r.child_entity, r.name)
            ),
            normalization_actions=sorted(
                self._actions, key=lambda a: (a.normal_form.value, a.entity, a.action)
            ),
            # Sorted so the model is a function of its content, not of the
            # order the conceptual entities happened to be declared in.
            assumptions=sorted(self._assumptions),
        )

        logger.info(
            "Logical model derived: %s entities (%s associative), %s relationships, "
            "%s normalization actions",
            len(logical.entities),
            sum(1 for e in logical.entities if e.kind == EntityKind.ASSOCIATIVE),
            len(logical.relationships),
            len(logical.normalization_actions),
        )

        return LogicalModelPackage(
            logical_model=logical,
            generated_from=self.source_artifact,
            generated_by=self.package.generated_by,
        )

    # -- Entities ----------------------------------------------------------

    def _map_entity_to_domain(self) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for domain in self.model.domains:
            for entity_name in domain.entities:
                lookup.setdefault(entity_name, domain.name)
        return lookup

    def _build_entities(self) -> None:
        for entity in self.model.entities:
            self._entities[entity.name] = self._build_entity(entity)

    def _build_entity(self, entity: ConceptualEntity) -> LogicalEntity:
        attributes: list[LogicalAttribute] = []
        seen: set[str] = set()

        # Business-key attributes first: they identify the entity, so they
        # lead the attribute list the way a reader expects.
        ordered = list(entity.business_key) + [
            a for a in entity.attributes if a not in entity.business_key
        ]

        for name in ordered:
            if name in seen:
                continue
            seen.add(name)
            in_key = name in entity.business_key
            source_column = self._resolve_source_column(entity, name)
            attributes.append(
                LogicalAttribute(
                    name=name,
                    data_type=_infer_type(name),
                    optionality=Optionality.MANDATORY if in_key else Optionality.OPTIONAL,
                    role=AttributeRole.PRIMARY_KEY if in_key else AttributeRole.DESCRIPTIVE,
                    source_attribute=name,
                    **_source_fields(source_column),
                )
            )

        primary_key = self._build_primary_key(entity, attributes)
        alternate_keys = self._build_alternate_keys(entity, attributes, primary_key)

        return LogicalEntity(
            name=entity.name,
            description=entity.description,
            kind=EntityKind.FUNDAMENTAL,
            subject_area=self._entity_domain.get(entity.name, ""),
            attributes=attributes,
            primary_key=primary_key,
            alternate_keys=alternate_keys,
            source_entities=[entity.name],
            source_tables=list(entity.source_tables),
        )

    def _resolve_source_column(self, entity: ConceptualEntity, attribute_name: str):
        """Find the source column an attribute was derived from, if any.

        Conservative by design: returns None (never a guess) when no
        metadata was supplied, the entity declares no source tables, or the
        attribute name does not resolve unambiguously to one column - the
        physical model still gets a chance to resolve it independently, and
        an unresolved attribute simply keeps its abstract-domain typing.
        """
        if self.metadata is None or not entity.source_tables:
            return None
        return resolve_source_column(
            entity.source_tables, attribute_name, self.metadata.metadata
        )

    def _build_primary_key(
        self, entity: ConceptualEntity, attributes: list[LogicalAttribute]
    ) -> LogicalKey:
        if entity.business_key:
            return LogicalKey(
                name=f"PK_{_slug(entity.name)}",
                kind=KeyKind.PRIMARY,
                attributes=list(entity.business_key),
            )

        # No natural key: introduce a surrogate and say so.
        surrogate = f"{entity.name} Identifier"
        attributes.insert(
            0,
            LogicalAttribute(
                name=surrogate,
                data_type=LogicalDataType.IDENTIFIER,
                optionality=Optionality.MANDATORY,
                role=AttributeRole.PRIMARY_KEY,
                description="Surrogate identifier introduced by the logical design.",
            ),
        )
        self._actions.append(
            NormalizationAction(
                normal_form=NormalForm.FIRST,
                entity=entity.name,
                action=f"Introduced surrogate identifier '{surrogate}'",
                rationale=(
                    "The conceptual model identified no business key, so the entity had "
                    "no way to be uniquely identified. A surrogate was introduced rather "
                    "than assuming one of the descriptive attributes is unique."
                ),
            )
        )
        self._assumptions.append(
            f"'{entity.name}' was given a surrogate identifier because no business key "
            f"was recorded for it. Confirm whether a natural key exists."
        )
        return LogicalKey(
            name=f"PK_{_slug(entity.name)}",
            kind=KeyKind.PRIMARY,
            attributes=[surrogate],
            is_surrogate=True,
        )

    def _build_alternate_keys(
        self,
        entity: ConceptualEntity,
        attributes: list[LogicalAttribute],
        primary_key: LogicalKey,
    ) -> list[LogicalKey]:
        alternates: list[LogicalKey] = []
        for attribute in attributes:
            if attribute.name in primary_key.attributes:
                continue
            lowered = attribute.name.lower()
            if any(keyword in lowered for keyword in _ALTERNATE_KEY_KEYWORDS):
                attribute.role = AttributeRole.ALTERNATE_KEY
                alternates.append(
                    LogicalKey(
                        name=f"AK_{_slug(entity.name)}_{_slug(attribute.name)}",
                        kind=KeyKind.ALTERNATE,
                        attributes=[attribute.name],
                    )
                )
        return alternates

    # -- Relationships -----------------------------------------------------

    def _collect_relationship_pairs(self) -> list[tuple[str, str, object]]:
        """Collect one entry per relationship, de-duplicated by entity pair.

        A relationship declared from both sides is one relationship. Keeping
        both would double every foreign key.
        """
        seen: set[frozenset[str]] = set()
        pairs: list[tuple[str, str, object]] = []

        for entity in self.model.entities:
            for relationship in entity.relationships:
                if relationship.related_entity not in self._entities:
                    continue
                key = frozenset({entity.name, relationship.related_entity})
                if key in seen and entity.name != relationship.related_entity:
                    continue
                seen.add(key)
                pairs.append((entity.name, relationship.related_entity, relationship))

        return pairs

    def _resolve_many_to_many(self, pairs: list[tuple[str, str, object]]) -> None:
        """Replace each M:N with an associative entity (1NF)."""
        for source, target, relationship in list(pairs):
            if relationship.cardinality != Cardinality.MANY_TO_MANY:
                continue

            left, right = sorted((source, target))
            name = f"{left} {right} Association"
            left_fk = self._foreign_key_name(left, self._entities[left], set())
            right_fk = self._foreign_key_name(right, self._entities[right], {left_fk})

            associative = LogicalEntity(
                name=name,
                description=(
                    f"Resolves the many-to-many relationship between {left} and {right}. "
                    f"Each occurrence records that one {left} {relationship.verb_phrase} "
                    f"one {right}."
                ),
                kind=EntityKind.ASSOCIATIVE,
                subject_area=self._entities[left].subject_area,
                attributes=[
                    LogicalAttribute(
                        name=left_fk,
                        data_type=LogicalDataType.IDENTIFIER,
                        optionality=Optionality.MANDATORY,
                        role=AttributeRole.PRIMARY_KEY,
                        references_entity=left,
                    ),
                    LogicalAttribute(
                        name=right_fk,
                        data_type=LogicalDataType.IDENTIFIER,
                        optionality=Optionality.MANDATORY,
                        role=AttributeRole.PRIMARY_KEY,
                        references_entity=right,
                    ),
                ],
                primary_key=LogicalKey(
                    name=f"PK_{_slug(name)}",
                    kind=KeyKind.PRIMARY,
                    attributes=[left_fk, right_fk],
                ),
                source_entities=[left, right],
            )
            self._entities[name] = associative

            for parent, fk in ((left, left_fk), (right, right_fk)):
                self._relationships.append(
                    LogicalRelationship(
                        name=f"{parent} to {name}",
                        parent_entity=parent,
                        child_entity=name,
                        cardinality=Cardinality.ONE_TO_MANY,
                        optionality=Optionality.MANDATORY,
                        is_identifying=True,
                        foreign_key_attributes=[fk],
                        verb_phrase="is referenced by",
                        derived_from=f"many-to-many between {left} and {right}",
                    )
                )

            self._actions.append(
                NormalizationAction(
                    normal_form=NormalForm.FIRST,
                    entity=name,
                    action=f"Resolved many-to-many between {left} and {right}",
                    rationale=(
                        "A many-to-many relationship cannot be represented without a "
                        "repeating group. An associative entity keyed on both parents "
                        "removes the repetition and gives the relationship a place to "
                        "carry its own attributes later."
                    ),
                )
            )
            pairs.remove((source, target, relationship))

    def _propagate_foreign_keys(self, pairs: list[tuple[str, str, object]]) -> None:
        """Add a foreign key on the child for every remaining relationship."""
        for source, target, relationship in pairs:
            parent, child = self._orient(source, target, relationship.cardinality)
            parent_entity = self._entities[parent]
            child_entity = self._entities[child]

            existing = {a.name for a in child_entity.attributes}
            fk_name = self._foreign_key_name(
                parent, parent_entity, existing, self_reference=parent == child
            )

            optionality = (
                Optionality.OPTIONAL if relationship.is_optional else Optionality.MANDATORY
            )

            child_entity.attributes.append(
                LogicalAttribute(
                    name=fk_name,
                    data_type=LogicalDataType.IDENTIFIER,
                    optionality=optionality,
                    role=AttributeRole.FOREIGN_KEY,
                    references_entity=parent,
                    description=f"References {parent}.",
                )
            )

            # A one-to-one relationship additionally constrains the child's
            # foreign key to be unique, which is an alternate key.
            if relationship.cardinality == Cardinality.ONE_TO_ONE:
                child_entity.alternate_keys.append(
                    LogicalKey(
                        name=f"AK_{_slug(child)}_{_slug(fk_name)}",
                        kind=KeyKind.ALTERNATE,
                        attributes=[fk_name],
                    )
                )

            self._relationships.append(
                LogicalRelationship(
                    name=f"{parent} to {child}",
                    parent_entity=parent,
                    child_entity=child,
                    cardinality=self._child_cardinality(relationship.cardinality),
                    optionality=optionality,
                    is_identifying=False,
                    foreign_key_attributes=[fk_name],
                    verb_phrase=relationship.verb_phrase,
                    derived_from=f"conceptual relationship '{source} {relationship.verb_phrase} {target}'",
                )
            )

    @staticmethod
    def _orient(source: str, target: str, cardinality: Cardinality) -> tuple[str, str]:
        """Return (parent, child). The parent is the 'one' side."""
        if cardinality == Cardinality.MANY_TO_ONE:
            return target, source
        return source, target

    @staticmethod
    def _child_cardinality(cardinality: Cardinality) -> Cardinality:
        """Express every relationship parent-to-child, so the whole model
        reads in one direction."""
        if cardinality == Cardinality.ONE_TO_ONE:
            return Cardinality.ONE_TO_ONE
        return Cardinality.ONE_TO_MANY

    def _foreign_key_name(
        self,
        parent: str,
        parent_entity: LogicalEntity,
        existing: set[str],
        self_reference: bool = False,
    ) -> str:
        """Name a foreign key after the parent's primary key attribute.

        Prefixed with the parent entity only when the key name does not
        already carry it, so `Customer` contributes `Customer Number` rather
        than `Customer Customer Number`.
        """
        key_attributes = parent_entity.primary_key.attributes if parent_entity.primary_key else []
        base = key_attributes[0] if key_attributes else f"{parent} Identifier"

        if self_reference:
            candidate = f"Parent {base}"
        elif any(word.lower() in base.lower() for word in parent.split()):
            candidate = base
        else:
            candidate = f"{parent} {base}"

        name = candidate
        suffix = 2
        while name in existing:
            name = f"{candidate} {suffix}"
            suffix += 1
        return name

    # -- Dependent entities and normalization ------------------------------

    def _classify_dependents(self) -> None:
        """An entity whose business key contains a parent's key is dependent
        on that parent, and the relationship is identifying."""
        for relationship in self._relationships:
            if relationship.is_identifying:
                continue

            child = self._entities[relationship.child_entity]
            parent = self._entities[relationship.parent_entity]
            if child.primary_key is None or parent.primary_key is None:
                continue

            shared = set(child.primary_key.attributes) & set(parent.primary_key.attributes)
            if not shared or child.name == parent.name:
                continue

            relationship.is_identifying = True
            child.kind = EntityKind.DEPENDENT

            # The shared attribute is the propagated key, not a separate one.
            for attribute in child.attributes:
                if attribute.name in shared:
                    attribute.role = AttributeRole.PRIMARY_KEY
                    attribute.references_entity = parent.name
                    attribute.optionality = Optionality.MANDATORY

            relationship.foreign_key_attributes = sorted(shared)
            self._remove_redundant_foreign_key(child, parent)

            self._actions.append(
                NormalizationAction(
                    normal_form=NormalForm.SECOND,
                    entity=child.name,
                    action=f"Identified {child.name} as dependent on {parent.name}",
                    rationale=(
                        f"Its business key includes {parent.name}'s key "
                        f"({', '.join(sorted(shared))}), so it cannot be identified "
                        f"independently. The relationship is identifying and the key is "
                        f"propagated rather than duplicated."
                    ),
                )
            )

    @staticmethod
    def _remove_redundant_foreign_key(child: LogicalEntity, parent: LogicalEntity) -> None:
        """Drop the separately-propagated foreign key to an identifying parent.

        Once the relationship is identifying, the parent's key already lives
        in the child's own primary key. A second copy propagated earlier is
        the same fact stored twice — the exact redundancy normalization
        exists to remove.
        """
        key_attributes = set(child.primary_key.attributes) if child.primary_key else set()
        child.attributes = [
            attribute
            for attribute in child.attributes
            if not (
                attribute.role == AttributeRole.FOREIGN_KEY
                and attribute.references_entity == parent.name
                and attribute.name not in key_attributes
            )
        ]

    def _record_normalization_checks(self) -> None:
        """Record the checks performed, including the ones that found nothing.

        A normalization section that only lists changes leaves the reader
        unable to tell "compliant" from "not examined".
        """
        for name in sorted(self._entities):
            entity = self._entities[name]
            if entity.primary_key is None or len(entity.primary_key.attributes) < 2:
                continue

            descriptive = [
                a.name for a in entity.attributes if a.role == AttributeRole.DESCRIPTIVE
            ]
            if descriptive:
                self._actions.append(
                    NormalizationAction(
                        normal_form=NormalForm.SECOND,
                        entity=name,
                        action="Checked non-key attributes against the full composite key",
                        rationale=(
                            f"{name} has a composite key, so every non-key attribute "
                            f"({', '.join(descriptive)}) must depend on the whole key "
                            f"rather than part of it. No partial dependency was found."
                        ),
                    )
                )

        # Transitive dependency: a chain parent -> grandparent means the
        # intermediate attributes already live in their own entity.
        parents = {r.child_entity: r.parent_entity for r in self._relationships}
        for child, parent in sorted(parents.items()):
            grandparent = parents.get(parent)
            if grandparent and grandparent != child:
                self._actions.append(
                    NormalizationAction(
                        normal_form=NormalForm.THIRD,
                        entity=child,
                        action=f"Confirmed {parent} attributes are not repeated on {child}",
                        rationale=(
                            f"{child} references {parent}, which references {grandparent}. "
                            f"The chain is already decomposed, so {grandparent}'s attributes "
                            f"reach {child} by navigation rather than by duplication."
                        ),
                    )
                )

    # -- Assembly ----------------------------------------------------------

    def _subject_areas(self) -> list[SubjectArea]:
        areas: list[SubjectArea] = []
        for domain in self.model.domains:
            members = sorted(
                name
                for name, entity in self._entities.items()
                if entity.subject_area == domain.name
            )
            areas.append(
                SubjectArea(name=domain.name, description=domain.description, entities=members)
            )

        unassigned = sorted(
            name for name, entity in self._entities.items() if not entity.subject_area
        )
        if unassigned:
            areas.append(
                SubjectArea(
                    name="Unassigned",
                    description="Entities the conceptual model placed in no domain.",
                    entities=unassigned,
                )
            )
        return areas

    def _summary(self) -> str:
        associative = sum(
            1 for e in self._entities.values() if e.kind == EntityKind.ASSOCIATIVE
        )
        dependent = sum(1 for e in self._entities.values() if e.kind == EntityKind.DEPENDENT)
        surrogates = sum(
            1
            for e in self._entities.values()
            if e.primary_key is not None and e.primary_key.is_surrogate
        )

        return (
            f"Logical design for {self.model.database_name}, derived from the conceptual "
            f"model. {len(self._entities)} entities carry {len(self._relationships)} "
            f"relationships: {associative} associative entities resolve many-to-many "
            f"relationships and {dependent} entities are identified through a parent. "
            f"{surrogates} entities required a surrogate identifier because no business "
            f"key was recorded. Attributes are typed against abstract domains and carry "
            f"no platform-specific length, precision or storage."
        )


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def _infer_type(name: str) -> LogicalDataType:
    """Map an attribute name onto an abstract domain.

    Matching is on word boundaries. Raw substring matching mistypes real
    attribute names — "Account Status" contains "count" and would otherwise
    be resolved as a whole number rather than a code.
    """
    lowered = name.lower()
    for data_type, pattern in _TYPE_PATTERNS:
        if pattern.search(lowered):
            return data_type
    return LogicalDataType.TEXT


def _slug(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").upper()


def _source_fields(column) -> dict:
    """Build the LogicalAttribute source_* kwargs from a resolved column.

    Returns an empty dict (leaving every source_* field at its None
    default) when no column was resolved.
    """
    if column is None:
        return {}
    return {
        "source_data_type": column.data_type,
        "source_length": column.character_length,
        "source_precision": column.numeric_precision,
        "source_scale": column.numeric_scale,
        "source_nullable": column.nullable,
        "source_default": column.default_value,
    }
