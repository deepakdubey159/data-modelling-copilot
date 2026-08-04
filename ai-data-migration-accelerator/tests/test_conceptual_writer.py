"""Tests for migration.conceptual.writer.

Markdown and Mermaid are generated in code, never by the AI, so rendering is
a pure function and fully testable.
"""

from __future__ import annotations

import json
from pathlib import Path

from migration.conceptual.models import (
    ConceptualEntity,
    ConceptualModel,
    ConceptualModelPackage,
    ConceptualRelationship,
)
from migration.conceptual.parser import parse_conceptual_model
from migration.conceptual.writer import ConceptualModelWriter
from migration.relationship.models import Cardinality
from tests.conceptual_fixtures import valid_response_json

REQUIRED_SECTIONS = [
    "# Executive Summary",
    "# Business Overview",
    "# Business Domains",
    "# Business Entities",
    "# Entity Relationships",
    "# Mermaid Diagram",
    "# Business Rules",
    "# Assumptions",
    "# Recommendations",
]


def _package() -> ConceptualModelPackage:
    return ConceptualModelPackage(
        conceptual_model=parse_conceptual_model(valid_response_json()),
        generated_by="stub-model",
    )


def _render() -> str:
    return ConceptualModelWriter().render_markdown(_package())


# -- Markdown structure ----------------------------------------------------


def test_all_required_sections_are_present_in_order():
    markdown = _render()
    positions = [markdown.index(section) for section in REQUIRED_SECTIONS]

    assert positions == sorted(positions)


def test_summary_and_entities_are_rendered():
    markdown = _render()

    assert "A retail operation covering customers" in markdown
    assert "## Customer" in markdown
    assert "**Business key:** Customer Number" in markdown
    assert "Customer Name" in markdown


def test_source_tables_are_rendered_for_traceability():
    assert "`app.customer`" in _render()


def test_relationship_table_is_rendered():
    markdown = _render()

    assert "| Entity | Relationship | Related Entity | Cardinality | Participation |" in markdown
    assert "| Customer | places | Order | one-to-many | optional |" in markdown


def test_ai_provenance_is_stated():
    """A reader must be able to tell this artifact apart from the
    deterministic ones."""
    markdown = _render()

    assert "stub-model" in markdown
    assert "reviewed by someone who knows that business" in markdown


def test_rendering_is_deterministic():
    assert _render() == _render()


def test_empty_lists_render_a_placeholder_not_a_gap():
    model = parse_conceptual_model(valid_response_json())
    model.business_rules = []
    model.recommendations = []
    markdown = ConceptualModelWriter().render_markdown(
        ConceptualModelPackage(conceptual_model=model)
    )

    assert "_None identified._" in markdown
    assert "# Business Rules" in markdown


# -- Mermaid ---------------------------------------------------------------


def test_mermaid_block_is_generated():
    markdown = _render()

    assert "```mermaid" in markdown
    assert "erDiagram" in markdown


def test_mermaid_uses_correct_cardinality_symbols():
    markdown = _render()

    assert "||--o{" in markdown  # Customer one-to-many Order
    assert "}o--o{" in markdown  # Order many-to-many Product


def test_mermaid_entity_names_are_sanitized():
    model = ConceptualModel(
        database_name="db",
        summary="s",
        entities=[
            ConceptualEntity(
                name="Purchase Order (Header)",
                description="d",
                relationships=[
                    ConceptualRelationship(
                        related_entity="Line Item",
                        verb_phrase="contains",
                        cardinality=Cardinality.ONE_TO_MANY,
                    )
                ],
            ),
            ConceptualEntity(name="Line Item", description="d"),
        ],
    )
    markdown = ConceptualModelWriter().render_markdown(
        ConceptualModelPackage(conceptual_model=model)
    )

    assert "PURCHASE_ORDER_HEADER" in markdown
    assert "LINE_ITEM" in markdown
    assert "(" not in markdown.split("```mermaid")[1].split("```")[0]


def test_reciprocal_relationships_produce_one_edge():
    """Both sides declaring the relationship must not double the diagram."""
    model = ConceptualModel(
        database_name="db",
        summary="s",
        entities=[
            ConceptualEntity(
                name="Customer",
                description="d",
                relationships=[
                    ConceptualRelationship(
                        related_entity="Order",
                        verb_phrase="places",
                        cardinality=Cardinality.ONE_TO_MANY,
                    )
                ],
            ),
            ConceptualEntity(
                name="Order",
                description="d",
                relationships=[
                    ConceptualRelationship(
                        related_entity="Customer",
                        verb_phrase="is placed by",
                        cardinality=Cardinality.MANY_TO_ONE,
                    )
                ],
            ),
        ],
    )
    diagram = (
        ConceptualModelWriter()
        .render_markdown(ConceptualModelPackage(conceptual_model=model))
        .split("```mermaid")[1]
        .split("```")[0]
    )

    assert diagram.count("CUSTOMER") == 1
    assert diagram.count("ORDER") == 1


def test_self_reference_renders_as_a_loop():
    model = ConceptualModel(
        database_name="db",
        summary="s",
        entities=[
            ConceptualEntity(
                name="Employee",
                description="d",
                relationships=[
                    ConceptualRelationship(
                        related_entity="Employee",
                        verb_phrase="reports to",
                        cardinality=Cardinality.MANY_TO_ONE,
                    )
                ],
            )
        ],
    )
    markdown = ConceptualModelWriter().render_markdown(
        ConceptualModelPackage(conceptual_model=model)
    )

    assert "EMPLOYEE }o--|| EMPLOYEE" in markdown


def test_edge_direction_matches_the_verb_phrase():
    """The label is written for the declared direction, so reordering the
    pair would leave it reading backwards."""
    model = ConceptualModel(
        database_name="db",
        summary="s",
        entities=[
            # 'Zebra' sorts after 'Apple'; a naive alphabetical reorder would
            # flip this edge and make the label nonsense.
            ConceptualEntity(
                name="Zebra",
                description="d",
                relationships=[
                    ConceptualRelationship(
                        related_entity="Apple",
                        verb_phrase="is located in",
                        cardinality=Cardinality.MANY_TO_ONE,
                    )
                ],
            ),
            ConceptualEntity(name="Apple", description="d"),
        ],
    )
    markdown = ConceptualModelWriter().render_markdown(
        ConceptualModelPackage(conceptual_model=model)
    )

    assert 'ZEBRA }o--|| APPLE : "is located in"' in markdown


def test_isolated_entity_still_appears_in_the_diagram():
    """An entity with no relationships takes part in no edge and would
    otherwise vanish from a diagram that has other edges."""
    model = ConceptualModel(
        database_name="db",
        summary="s",
        entities=[
            ConceptualEntity(
                name="Customer",
                description="d",
                relationships=[
                    ConceptualRelationship(
                        related_entity="Order",
                        verb_phrase="places",
                        cardinality=Cardinality.ONE_TO_MANY,
                    )
                ],
            ),
            ConceptualEntity(name="Order", description="d"),
            ConceptualEntity(name="Audit Entry", description="stands alone"),
        ],
    )
    diagram = (
        ConceptualModelWriter()
        .render_markdown(ConceptualModelPackage(conceptual_model=model))
        .split("```mermaid")[1]
        .split("```")[0]
    )

    assert "CUSTOMER ||--o{ ORDER" in diagram
    assert "AUDIT_ENTRY { }" in diagram


def test_model_with_no_relationships_still_declares_its_nodes():
    model = ConceptualModel(
        database_name="db",
        summary="s",
        entities=[ConceptualEntity(name="Lonely", description="d")],
    )
    markdown = ConceptualModelWriter().render_markdown(
        ConceptualModelPackage(conceptual_model=model)
    )

    assert "LONELY { }" in markdown


def test_quotes_in_verb_phrase_do_not_break_the_diagram():
    model = ConceptualModel(
        database_name="db",
        summary="s",
        entities=[
            ConceptualEntity(
                name="A",
                description="d",
                relationships=[
                    ConceptualRelationship(
                        related_entity="B",
                        verb_phrase='is "linked" to',
                        cardinality=Cardinality.ONE_TO_ONE,
                    )
                ],
            ),
            ConceptualEntity(name="B", description="d"),
        ],
    )
    diagram = (
        ConceptualModelWriter()
        .render_markdown(ConceptualModelPackage(conceptual_model=model))
        .split("```mermaid")[1]
        .split("```")[0]
    )

    assert diagram.count('"') == 2  # exactly the label's own delimiters


# -- File output -----------------------------------------------------------


def test_writes_all_artifacts(tmp_path: Path):
    json_path, markdown_path, html_path = ConceptualModelWriter().write(
        _package(), tmp_path
    )

    assert json_path.name == "conceptual_model.json"
    assert markdown_path.name == "conceptual_model.md"
    assert html_path.name == "conceptual_model.html"
    assert json_path.exists() and markdown_path.exists() and html_path.exists()


def test_written_json_round_trips(tmp_path: Path):
    json_path = ConceptualModelWriter().write_json(_package(), tmp_path)
    payload = json.load(open(json_path, encoding="utf-8"))

    assert list(payload.keys()) == ["conceptual_model", "generated_by"]
    restored = ConceptualModelPackage.model_validate(payload)
    assert restored.conceptual_model.database_name == "testdb"
    assert restored.generated_by == "stub-model"
