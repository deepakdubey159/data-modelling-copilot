"""
Logical Model HTML Renderer

Renders `logical_model.html` from the logical model.

This is the payoff for the way `migration/conceptual/html_renderer.py` was
built. That module is in three layers, and only the third knows about
conceptual models:

    1. Diagram        DiagramNode / DiagramEdge -> layered SVG
    2. Report shell   ReportDocument + Section types -> full HTML page
    3. Mapping        conceptual model -> layers 1 and 2

Layers 1 and 2 are imported here unchanged. This file is layer 3 for the
logical model — the mapping, and nothing else. No new CSS, no new page
shell, no second diagram engine. A future physical model, catalog or
glossary report is another file of this shape.

Nothing in Module 4 is modified; this only imports from it.
"""

from __future__ import annotations

from datetime import datetime

from migration.conceptual.html_renderer import (
    ACCENTS,
    BulletSection,
    Card,
    CardField,
    CardGridSection,
    DiagramEdge,
    DiagramNode,
    DiagramSection,
    MetaItem,
    NumberedSection,
    ProseSection,
    ReportDocument,
    render_report,
)
from migration.logical.models import (
    AttributeRole,
    EntityKind,
    LogicalEntity,
    LogicalModel,
    LogicalModelPackage,
)

_KIND_LABEL = {
    EntityKind.FUNDAMENTAL: "Fundamental",
    EntityKind.DEPENDENT: "Dependent",
    EntityKind.ASSOCIATIVE: "Associative",
}


def _subject_area_colours(model: LogicalModel) -> dict[str, tuple[str, str]]:
    """One stable colour per subject area, in declaration order."""
    return {
        area.name: ACCENTS[index % len(ACCENTS)]
        for index, area in enumerate(model.subject_areas)
    }


def _attribute_summary(entity: LogicalEntity) -> str:
    """A compact 'Name (Domain)' list for the entity card."""
    descriptive = [
        f"{a.name} ({a.data_type.value.replace('_', ' ').lower()})"
        for a in entity.attributes
        if a.role == AttributeRole.DESCRIPTIVE
    ]
    return ", ".join(descriptive) if descriptive else "None"


def build_logical_document(
    package: LogicalModelPackage, generated_at: datetime | None = None
) -> ReportDocument:
    """Map a logical model onto the shared report framework."""
    model = package.logical_model
    stamp = generated_at or datetime.now()
    colours = _subject_area_colours(model)
    area_index = {name: index for index, name in enumerate(colours)}

    kinds = {kind: 0 for kind in EntityKind}
    for entity in model.entities:
        kinds[entity.kind] += 1
    attribute_count = sum(len(entity.attributes) for entity in model.entities)

    # -- Section 1: Executive Summary -----------------------------------
    summary = ProseSection(title="Executive Summary", paragraphs=[model.summary])

    # -- Section 2: Subject Areas ---------------------------------------
    subject_areas = CardGridSection(
        title="Subject Areas",
        description="Groupings carried through from the conceptual model.",
        cards=[
            Card(
                title=area.name,
                body=area.description,
                badge=f"{len(area.entities)} entities",
                tags=list(area.entities),
                accent=index,
            )
            for index, area in enumerate(model.subject_areas)
        ],
    )

    # -- Section 3: Logical Entities ------------------------------------
    entity_cards = []
    for entity in model.entities:
        fields = []
        if entity.primary_key:
            suffix = " (surrogate)" if entity.primary_key.is_surrogate else ""
            fields.append(
                CardField("Primary key", ", ".join(entity.primary_key.attributes) + suffix)
            )
        if entity.alternate_keys:
            fields.append(
                CardField(
                    "Alternate keys",
                    "; ".join(", ".join(k.attributes) for k in entity.alternate_keys),
                )
            )

        foreign = [
            f"{a.name} → {a.references_entity}"
            for a in entity.attributes
            if a.role == AttributeRole.FOREIGN_KEY
        ]
        if foreign:
            fields.append(CardField("Foreign keys", "; ".join(foreign)))

        fields.append(CardField("Attributes", _attribute_summary(entity)))
        fields.append(CardField("Total", f"{len(entity.attributes)} attributes"))
        if entity.source_tables:
            fields.append(CardField("Derived from", ", ".join(entity.source_tables)))

        entity_cards.append(
            Card(
                title=entity.name,
                subtitle=entity.subject_area or "Unassigned",
                badge=_KIND_LABEL[entity.kind],
                body=entity.description,
                fields=fields,
                accent=area_index.get(entity.subject_area, 0),
            )
        )

    entities = CardGridSection(
        title="Logical Entities",
        description=(
            f"{len(model.entities)} entities and {attribute_count} attributes. "
            f"Domains are abstract: no lengths, precision or vendor types appear "
            f"until the physical model."
        ),
        cards=entity_cards,
    )

    # -- Section 4: Logical Diagram --------------------------------------
    nodes = [
        DiagramNode(
            id=entity.name,
            label=entity.name,
            sublabel=(
                ", ".join(entity.primary_key.attributes) if entity.primary_key else ""
            ),
            group=entity.subject_area,
        )
        for entity in model.entities
    ]
    edges = [
        DiagramEdge(
            source=relationship.parent_entity,
            target=relationship.child_entity,
            label=relationship.verb_phrase,
            cardinality=relationship.cardinality.value,
        )
        for relationship in model.relationships
    ]

    diagram = DiagramSection(
        title="Logical Diagram",
        description=(
            "Entities coloured by subject area, keyed by their primary key. "
            "Arrows run from parent to child in the direction of the foreign key."
        ),
        nodes=nodes,
        edges=edges,
        group_colours=colours,
    )

    # -- Section 5: Relationships ----------------------------------------
    relationship_cards = [
        Card(
            title=f"{relationship.parent_entity} → {relationship.child_entity}",
            subtitle=relationship.verb_phrase,
            badge="Identifying" if relationship.is_identifying else "Non-identifying",
            fields=[
                CardField(
                    "Cardinality",
                    relationship.cardinality.value.replace("_", "-").lower(),
                ),
                CardField("Optionality", relationship.optionality.value.title()),
                CardField("Foreign key", ", ".join(relationship.foreign_key_attributes)),
            ],
            accent=area_index.get(
                next(
                    (
                        e.subject_area
                        for e in model.entities
                        if e.name == relationship.parent_entity
                    ),
                    "",
                ),
                0,
            ),
        )
        for relationship in model.relationships
    ]
    relationships = CardGridSection(
        title="Entity Relationships",
        description=(
            "An identifying relationship means the child cannot be identified "
            "without its parent."
        ),
        cards=relationship_cards,
        compact=True,
    )

    # -- Section 6: Normalization ----------------------------------------
    normalization = NumberedSection(
        title="Normalization",
        description=(
            "Actions taken and checks performed. Checks that found nothing are "
            "listed too, so a compliant design is distinguishable from one that "
            "was never examined."
        ),
        items=[
            f"{action.normal_form.value} — {action.entity}: {action.action}. "
            f"{action.rationale}"
            for action in model.normalization_actions
        ],
    )

    # -- Section 7: Assumptions ------------------------------------------
    assumptions = BulletSection(
        title="Assumptions",
        description="Design decisions worth confirming with the business.",
        items=list(model.assumptions),
    )

    return ReportDocument(
        platform="Enterprise AI Data Modernization Platform",
        title="Logical Data Model",
        meta=[
            MetaItem("Database", model.database_name),
            MetaItem("Generated", stamp.strftime("%d %b %Y, %H:%M")),
            MetaItem("Subject areas", str(len(model.subject_areas))),
            MetaItem("Entities", str(len(model.entities))),
            MetaItem("Attributes", str(attribute_count)),
            MetaItem("Relationships", str(len(model.relationships))),
        ],
        sections=[
            summary,
            subject_areas,
            entities,
            diagram,
            relationships,
            normalization,
            assumptions,
        ],
        provenance=(
            f"Derived deterministically from {package.generated_from or 'the conceptual model'}. "
            "No AI was involved in this step: the conceptual model already carries the "
            "business judgement, and turning it into a normalized logical design is a set "
            "of transformation rules. Every design decision the derivation made appears "
            "under Normalization or Assumptions."
        ),
        footer=(
            "Generated by the Enterprise AI Data Modernization Platform. "
            "Logical design, diagram and layout rendered deterministically; "
            "attribute domains are abstract and independent of any target database."
        ),
    )


def render_logical_html(
    package: LogicalModelPackage, generated_at: datetime | None = None
) -> str:
    """Render `logical_model.html` from a validated package."""
    return render_report(build_logical_document(package, generated_at))
