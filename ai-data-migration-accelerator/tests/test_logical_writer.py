"""Tests for migration.logical.writer and migration.logical.html_renderer.

Rendering is a pure function of the model, so these are ordinary assertions
over the produced strings. No browser, no AI, no database.
"""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree

from migration.conceptual.models import ConceptualDomain
from migration.logical.engine import LogicalModelEngine
from migration.logical.html_renderer import build_logical_document, render_logical_html
from migration.logical.models import LogicalModelPackage
from migration.logical.writer import LogicalModelWriter
from tests.test_logical_engine import build, entity, relationship
from migration.relationship.models import Cardinality

STAMP = datetime(2026, 8, 7, 9, 30)


def _package() -> LogicalModelPackage:
    conceptual = build(
        [
            entity(
                "Customer",
                business_key=["Customer Number"],
                attributes=["Email Address", "Credit Limit"],
                relationships=[
                    relationship(
                        "Sales Order", Cardinality.ONE_TO_MANY, verb="places", optional=True
                    )
                ],
                source_tables=["bronze.customer"],
            ),
            entity(
                "Sales Order",
                business_key=["Order Number"],
                attributes=["Order Date"],
                relationships=[
                    relationship("Order Line", Cardinality.ONE_TO_MANY, verb="consists of")
                ],
            ),
            entity(
                "Order Line",
                business_key=["Order Number", "Line Number"],
                attributes=["Quantity Ordered"],
            ),
        ],
        domains=[
            ConceptualDomain(
                name="Sales",
                description="Demand and fulfilment.",
                entities=["Customer", "Sales Order", "Order Line"],
            )
        ],
    )
    return LogicalModelEngine(conceptual).generate()


def _markdown() -> str:
    return LogicalModelWriter().render_markdown(_package())


def _html() -> str:
    return render_logical_html(_package(), generated_at=STAMP)


# -- Markdown --------------------------------------------------------------


REQUIRED_SECTIONS = [
    "# Executive Summary",
    "# Logical Model Overview",
    "# Subject Areas",
    "# Logical Entities",
    "# Entity Relationships",
    "# Normalization",
    "# Assumptions",
]


def test_markdown_sections_appear_in_order():
    markdown = _markdown()
    positions = [markdown.index(section) for section in REQUIRED_SECTIONS]

    assert positions == sorted(positions)


def test_markdown_contains_no_mermaid():
    markdown = _markdown()

    assert "mermaid" not in markdown.lower()
    assert "erDiagram" not in markdown


def test_markdown_renders_an_attribute_table_per_entity():
    markdown = _markdown()

    assert "| Attribute | Domain | Key | Optionality | References |" in markdown
    assert "| Customer Number | Identifier | PK | Mandatory |  |" in markdown


def test_markdown_marks_foreign_keys_and_their_target():
    markdown = _markdown()

    assert re.search(r"\| Customer Number \|.*\| FK \|.*\| Customer \|", markdown)


def test_markdown_relationship_table_reports_identifying():
    markdown = _markdown()

    assert "| Parent | Child | Cardinality | Optionality | Identifying | Foreign key |" in markdown
    assert "| Sales Order | Order Line |" in markdown


def test_markdown_states_the_derivation_is_deterministic():
    markdown = _markdown()

    assert "business_model.json" in markdown
    assert "No AI was involved" in markdown


def test_markdown_normalization_section_lists_actions():
    markdown = _markdown()

    assert "### 2NF — Order Line" in markdown


def test_markdown_rendering_is_deterministic():
    assert _markdown() == _markdown()


# -- HTML: self-containment ------------------------------------------------


SVG_NAMESPACE = 'xmlns="http://www.w3.org/2000/svg"'


def test_html_is_valid_standalone_page():
    html = _html()

    assert html.startswith("<!DOCTYPE html>")
    assert html.rstrip().endswith("</html>")


def test_html_has_no_external_resources():
    html = _html().replace(SVG_NAMESPACE, "")

    for marker in ("http://", "https://", "<link", "src=", "@import", "cdn", "mermaid"):
        assert marker not in html.lower(), f"found external reference: {marker}"


def test_html_inlines_css_and_js():
    html = _html()

    assert "<style>" in html and "<script>" in html


# -- HTML: structure -------------------------------------------------------


def test_html_header_identifies_the_logical_model():
    html = _html()

    assert "Logical Data Model" in html
    assert "Enterprise AI Data Modernization Platform" in html
    assert "07 Aug 2026, 09:30" in html


def test_html_sections_appear_in_order():
    """Anchored on the heading markup, not the bare text: several section
    names also appear in the provenance banner, which precedes them."""
    html = _html()
    sections = [
        "Executive Summary",
        "Subject Areas",
        "Logical Entities",
        "Logical Diagram",
        "Entity Relationships",
        "Normalization",
        "Assumptions",
    ]
    positions = [html.index(f"</span>{name}</h2>") for name in sections]

    assert positions == sorted(positions)


def test_html_entity_cards_show_keys_and_domains():
    html = _html()

    assert "Primary key" in html
    assert "Customer Number" in html
    assert "Foreign keys" in html
    assert "identifier" in html.lower()


def test_html_labels_entity_kinds():
    html = _html()

    assert "Fundamental" in html
    assert "Dependent" in html


def test_html_provenance_names_the_source_artifact():
    html = _html()

    assert "business_model.json" in html
    assert "No AI was involved" in html


def test_html_rendering_is_deterministic():
    assert render_logical_html(_package(), STAMP) == render_logical_html(_package(), STAMP)


# -- HTML: diagram ---------------------------------------------------------


def _diagram(html: str) -> str:
    return html[html.index("<svg") : html.index("</svg>") + len("</svg>")]


def test_diagram_is_svg_and_well_formed():
    svg = _diagram(_html())
    root = ElementTree.fromstring(svg)

    assert root.tag.endswith("svg")


def test_every_entity_appears_in_the_diagram():
    svg = _diagram(_html())

    for name in ("Customer", "Sales Order", "Order Line"):
        assert f'data-id="{name}"' in svg


def test_diagram_nodes_carry_the_primary_key_as_a_sublabel():
    svg = _diagram(_html())

    assert "Customer Number" in svg


def test_diagram_edges_are_wired_for_hover_highlighting():
    svg = _diagram(_html())

    assert 'data-from="Customer"' in svg
    assert 'data-to="Sales Order"' in svg


def test_diagram_shows_cardinality_badges():
    assert "1:N" in _diagram(_html())


# -- Reuse -----------------------------------------------------------------


def test_html_reuses_the_conceptual_report_framework():
    """Module 5 must not carry a second page shell or diagram engine."""
    import migration.logical.html_renderer as renderer

    source = Path(renderer.__file__).read_text(encoding="utf-8")

    assert "from migration.conceptual.html_renderer import" in source
    assert "<style>" not in source  # no second stylesheet
    assert "<svg" not in source  # no second diagram engine


def test_document_is_a_report_document_like_the_conceptual_one():
    from migration.conceptual.html_renderer import ReportDocument

    assert isinstance(build_logical_document(_package(), STAMP), ReportDocument)


# -- File output -----------------------------------------------------------


def test_writer_produces_all_three_artifacts(tmp_path: Path):
    json_path, markdown_path, html_path = LogicalModelWriter().write(_package(), tmp_path)

    assert json_path.name == "logical_model.json"
    assert markdown_path.name == "logical_model.md"
    assert html_path.name == "logical_model.html"
    assert all(p.exists() for p in (json_path, markdown_path, html_path))


def test_written_json_round_trips(tmp_path: Path):
    json_path = LogicalModelWriter().write_json(_package(), tmp_path)
    restored = LogicalModelPackage.model_validate(json.load(open(json_path, encoding="utf-8")))

    assert restored.logical_model.database_name == "testdb"
    assert restored.generated_from == "business_model.json"


def test_written_html_is_utf8_and_complete(tmp_path: Path):
    html_path = LogicalModelWriter().write_html(_package(), tmp_path)
    content = html_path.read_text(encoding="utf-8")

    assert content.startswith("<!DOCTYPE html>")
    assert content.rstrip().endswith("</html>")
