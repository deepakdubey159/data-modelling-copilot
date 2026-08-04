"""Tests for migration.conceptual.html_renderer.

Rendering is a pure function of the model, so every test is an ordinary
assertion over the produced string. No browser, no network, no AI.
"""

from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree


from migration.conceptual.html_renderer import (
    ACCENTS,
    Card,
    CardGridSection,
    DiagramEdge,
    DiagramNode,
    MetaItem,
    NumberedSection,
    ProseSection,
    ReportDocument,
    build_conceptual_document,
    render_conceptual_html,
    render_diagram,
    render_report,
)
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

STAMP = datetime(2026, 8, 4, 22, 45)


def _package() -> ConceptualModelPackage:
    return ConceptualModelPackage(
        conceptual_model=parse_conceptual_model(valid_response_json()),
        generated_by="claude-opus-5",
    )


def _html() -> str:
    return render_conceptual_html(_package(), generated_at=STAMP)


# -- Self-containment ------------------------------------------------------


def test_page_is_valid_standalone_html():
    html = _html()

    assert html.startswith("<!DOCTYPE html>")
    assert html.rstrip().endswith("</html>")
    assert '<meta charset="utf-8" />' in html


SVG_NAMESPACE = 'xmlns="http://www.w3.org/2000/svg"'


def test_no_external_resources_of_any_kind():
    """A CDN reference would break the file the moment it is opened offline
    or emailed to someone behind a firewall.

    The SVG namespace declaration is excluded: it is an XML identifier, not
    a URL a browser ever requests.
    """
    html = _html().replace(SVG_NAMESPACE, "")

    for marker in (
        "http://",
        "https://",
        "//cdn",
        "<link",
        "src=",
        "@import",
        "cdnjs",
        "unpkg",
        "googleapis",
        "bootstrap",
        "mermaid",
        "react",
        "jquery",
        "url(http",
    ):
        assert marker not in html.lower(), f"found external reference: {marker}"


def test_the_only_url_in_the_page_is_the_svg_namespace():
    """Belt and braces on the check above: enumerate every URL-looking
    string and confirm the namespace is the only one."""
    urls = re.findall(r"https?://[^\s\"')]+", _html())

    assert set(urls) == {"http://www.w3.org/2000/svg"}


def test_css_and_js_are_inlined():
    html = _html()

    assert "<style>" in html and "</style>" in html
    assert "<script>" in html and "</script>" in html


def test_uses_only_system_fonts():
    assert "-apple-system" in _html()


# -- Required page structure ----------------------------------------------


def test_header_carries_platform_title_and_metadata():
    html = _html()

    assert "Enterprise AI Data Modernization Platform" in html
    assert "Conceptual Data Model" in html
    assert "testdb" in html
    assert "Source Database" in html
    assert "04 Aug 2026, 22:45" in html


def test_all_required_sections_are_present_in_order():
    html = _html()
    sections = [
        "Executive Summary",
        "Business Domains",
        "Business Entities",
        "Conceptual Diagram",
        "Business Rules",
        "Recommendations",
    ]
    positions = [html.index(name) for name in sections]

    assert positions == sorted(positions)


def test_assumptions_are_surfaced_in_the_report():
    """The report is what stakeholders actually read; hiding the AI's stated
    uncertainties there would be the wrong default."""
    assert "Assumptions" in _html()


def test_domain_cards_list_their_entities():
    html = _html()

    assert "Sales" in html
    assert "2 entities" in html


def test_entity_cards_carry_the_required_fields():
    html = _html()

    assert "Business key" in html
    assert "Customer Number" in html
    assert "Attributes" in html
    assert "Relationships" in html


def test_provenance_banner_names_the_model():
    html = _html()

    assert "claude-opus-5" in html
    assert "reviewed by someone who knows" in html


def test_business_rules_render_as_numbered_cards():
    html = _html()

    assert "numbered" in html
    assert "Every order must belong to exactly one customer." in html


# -- Determinism and escaping ---------------------------------------------


def test_rendering_is_deterministic_for_a_fixed_timestamp():
    assert render_conceptual_html(_package(), STAMP) == render_conceptual_html(
        _package(), STAMP
    )


def test_html_is_escaped_not_injected():
    model = ConceptualModel(
        database_name="db",
        summary="<script>alert('xss')</script> & \"quoted\"",
        entities=[ConceptualEntity(name="A & B <tag>", description="d")],
    )
    html = render_conceptual_html(
        ConceptualModelPackage(conceptual_model=model), STAMP
    )

    assert "<script>alert" not in html
    assert "&lt;script&gt;" in html
    assert "A &amp; B &lt;tag&gt;" in html


# -- Diagram ---------------------------------------------------------------


def _diagram(html: str) -> str:
    return html[html.index("<svg") : html.index("</svg>") + len("</svg>")]


def test_diagram_is_svg_not_mermaid():
    html = _html()

    assert "<svg" in html
    assert "mermaid" not in html.lower()
    assert "erDiagram" not in html


def test_diagram_is_well_formed_xml():
    """A malformed SVG renders as nothing at all in a browser."""
    svg = _diagram(_html())
    root = ElementTree.fromstring(svg)

    assert root.tag.endswith("svg")


def test_every_entity_appears_as_a_node():
    svg = _diagram(_html())

    for name in ("Customer", "Order", "Product"):
        assert f'data-id="{name}"' in svg


def test_edges_record_both_endpoints_for_hover_highlighting():
    svg = _diagram(_html())

    assert 'data-from="Customer"' in svg
    assert 'data-to="Order"' in svg


def test_edge_labels_use_the_business_verb_phrase():
    svg = _diagram(_html())

    assert "places" in svg
    assert "1:N" in svg  # ONE_TO_MANY badge


def test_reciprocal_relationships_are_drawn_once():
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
    svg = _diagram(
        render_conceptual_html(ConceptualModelPackage(conceptual_model=model), STAMP)
    )

    assert svg.count('class="edge"') == 1


def test_isolated_entity_still_appears_as_a_node():
    """An entity in no relationship must not vanish from the diagram."""
    model = ConceptualModel(
        database_name="db",
        summary="s",
        entities=[
            ConceptualEntity(name="Connected", description="d"),
            ConceptualEntity(name="Audit Entry", description="stands alone"),
        ],
    )
    svg = _diagram(
        render_conceptual_html(ConceptualModelPackage(conceptual_model=model), STAMP)
    )

    assert 'data-id="Audit Entry"' in svg


def test_self_reference_renders_without_error():
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
    svg = _diagram(
        render_conceptual_html(ConceptualModelPackage(conceptual_model=model), STAMP)
    )
    ElementTree.fromstring(svg)

    assert "reports to" in svg


def test_nodes_never_overlap():
    """Overlapping boxes are the classic auto-layout failure."""
    nodes = [DiagramNode(id=f"E{i}", label=f"Entity {i}") for i in range(12)]
    edges = [DiagramEdge(source="E0", target=f"E{i}", cardinality="ONE_TO_MANY") for i in range(1, 6)]
    svg = render_diagram(nodes, edges)

    boxes = [
        (float(x), float(y))
        for x, y in re.findall(r'class="node-box" x="([\d.]+)" y="([\d.]+)"', svg)
    ]
    assert len(boxes) == 12

    for i, a in enumerate(boxes):
        for b in boxes[i + 1 :]:
            separated = abs(a[0] - b[0]) >= 196 or abs(a[1] - b[1]) >= 64
            assert separated, f"boxes overlap at {a} and {b}"


def test_layout_places_parents_above_children():
    """The hierarchy should read top-down like an architecture diagram."""
    nodes = [DiagramNode(id=n, label=n) for n in ("Country", "State", "City")]
    edges = [
        DiagramEdge(source="Country", target="State", cardinality="ONE_TO_MANY"),
        DiagramEdge(source="State", target="City", cardinality="ONE_TO_MANY"),
    ]
    svg = render_diagram(nodes, edges)

    ys = {}
    for match in re.finditer(
        r'data-id="([^"]+)".*?class="node-box" x="[\d.]+" y="([\d.]+)"', svg
    ):
        ys[match.group(1)] = float(match.group(2))

    assert ys["Country"] < ys["State"] < ys["City"]


def test_cyclic_relationships_do_not_lose_entities():
    """A cycle cannot be layered; those entities must still be drawn."""
    nodes = [DiagramNode(id=n, label=n) for n in ("A", "B")]
    edges = [
        DiagramEdge(source="A", target="B", cardinality="ONE_TO_MANY"),
        DiagramEdge(source="B", target="A", cardinality="ONE_TO_MANY"),
    ]
    svg = render_diagram(nodes, edges)

    assert 'data-id="A"' in svg
    assert 'data-id="B"' in svg


def test_empty_model_renders_a_placeholder_not_a_broken_svg():
    assert "No entities to diagram" in render_diagram([], [])


def test_long_entity_names_are_truncated_with_full_name_in_tooltip():
    nodes = [DiagramNode(id="X", label="An Extremely Long Business Entity Name Indeed")]
    svg = render_diagram(nodes, [])

    assert "…" in svg
    assert "<title>An Extremely Long Business Entity Name Indeed" in svg


# -- Styling requirements --------------------------------------------------


def test_report_is_print_friendly():
    assert "@media print" in _html()


def test_report_is_responsive():
    html = _html()

    assert "@media (max-width:640px)" in html
    assert "minmax(" in html


def test_uses_the_brand_blue_accent():
    assert "#1a56db" in _html()


# -- Reusability by future reports ----------------------------------------


def test_framework_renders_a_document_with_no_conceptual_model():
    """Layers 1 and 2 must be reusable by logical/physical/catalog reports;
    only the layer-3 mapping should change."""
    document = ReportDocument(
        platform="Enterprise AI Data Modernization Platform",
        title="Logical Data Model",
        meta=[MetaItem("Database", "warehouse")],
        sections=[
            ProseSection(title="Overview", paragraphs=["A logical model."]),
            CardGridSection(title="Tables", cards=[Card(title="DIM_CUSTOMER")]),
            NumberedSection(title="Rules", items=["Surrogate keys everywhere."]),
        ],
    )
    html = render_report(document)

    assert "Logical Data Model" in html
    assert "DIM_CUSTOMER" in html
    assert "Surrogate keys everywhere." in html
    assert "Conceptual" not in html


def test_sections_are_numbered_in_declaration_order():
    document = ReportDocument(
        platform="P",
        title="T",
        sections=[ProseSection(title="First"), ProseSection(title="Second")],
    )
    html = render_report(document)

    assert html.index('section-index">1<') < html.index('section-index">2<')


def test_empty_sections_render_a_placeholder():
    document = ReportDocument(platform="P", title="T", sections=[NumberedSection(title="Rules")])

    assert "Nothing recorded" in render_report(document)


def test_domain_colours_are_stable_and_distinct():
    document = build_conceptual_document(_package(), STAMP)
    diagram = next(s for s in document.sections if s.title == "Conceptual Diagram")

    colours = list(diagram.group_colours.values())
    assert colours[0] == ACCENTS[0]
    assert len(set(colours)) == len(colours)


# -- Writer integration ----------------------------------------------------


def test_writer_produces_all_three_artifacts(tmp_path: Path):
    json_path, markdown_path, html_path = ConceptualModelWriter().write(_package(), tmp_path)

    assert json_path.name == "conceptual_model.json"
    assert markdown_path.name == "conceptual_model.md"
    assert html_path.name == "conceptual_model.html"
    assert html_path.exists()


def test_written_html_is_utf8_and_complete(tmp_path: Path):
    html_path = ConceptualModelWriter().write_html(_package(), tmp_path)
    content = html_path.read_text(encoding="utf-8")

    assert content.startswith("<!DOCTYPE html>")
    assert content.rstrip().endswith("</html>")


def test_markdown_is_unchanged_by_the_html_addition(tmp_path: Path):
    """The Markdown artifact keeps its Mermaid block: it renders natively in
    GitHub and VS Code, where the HTML file cannot be previewed."""
    markdown = ConceptualModelWriter().write_markdown(_package(), tmp_path).read_text(
        encoding="utf-8"
    )

    assert "```mermaid" in markdown
    assert "erDiagram" in markdown
