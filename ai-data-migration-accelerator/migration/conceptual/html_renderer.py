"""
HTML Report Renderer

Renders a self-contained, professional HTML report from a Pydantic model.
Everything is embedded: no CDN, no external stylesheet, no external script,
no web font. The file opens correctly from disk with no network.

No LLM involvement. The AI returns `ConceptualModel` JSON and nothing else;
this module turns that model into a report deterministically, so the diagram
and the data can never disagree.

Structure
---------
The file is in three layers, which is what makes it reusable:

1. **Diagram** - `DiagramNode` / `DiagramEdge` -> layered SVG. Knows nothing
   about conceptual models.
2. **Report framework** - `ReportDocument` and the `Section` types -> full
   HTML page with CSS. Also model-agnostic.
3. **Conceptual mapping** - `build_conceptual_document` maps a
   `ConceptualModelPackage` onto layers 1 and 2.

A future `logical_model.html`, `physical_model.html`, `catalog.html`,
`business_glossary.html` or `migration_report.html` supplies its own layer-3
mapping function and reuses layers 1 and 2 unchanged.

Layout
------
Node placement reuses `migration.relationship.graph.build_dependency_order`,
which is domain-free by design. Entities are assigned to layers by
dependency depth, then ordered within each layer by the average position of
their parents (a barycentre pass) to reduce edge crossings. Deterministic:
the same model always produces the same coordinates.
"""

from __future__ import annotations

import html
from dataclasses import dataclass, field
from datetime import datetime

from migration.conceptual.models import ConceptualModel, ConceptualModelPackage
from migration.relationship.graph import build_dependency_order
from migration.relationship.models import Cardinality

# ---------------------------------------------------------
# Design tokens
# ---------------------------------------------------------

BRAND = "#1a56db"
BRAND_DARK = "#132a5e"
INK = "#0f172a"
MUTED = "#64748b"
BORDER = "#e2e8f0"
SURFACE = "#ffffff"
CANVAS = "#f8fafc"

FONT_STACK = (
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', "
    "Arial, 'Noto Sans', sans-serif"
)

ACCENTS: list[tuple[str, str]] = [
    ("#1a56db", "#eff4ff"),  # blue
    ("#047857", "#ecfdf5"),  # emerald
    ("#b45309", "#fffbeb"),  # amber
    ("#6d28d9", "#f5f3ff"),  # violet
    ("#be123c", "#fff1f2"),  # rose
    ("#0f766e", "#f0fdfa"),  # teal
    ("#4d7c0f", "#f7fee7"),  # lime
    ("#475569", "#f8fafc"),  # slate
]

# Diagram geometry
NODE_W = 196
NODE_H = 64
H_GAP = 44
V_GAP = 104
MARGIN = 32
LABEL_CHAR_PX = 7.4


def esc(value) -> str:
    """Escape text for both HTML and SVG bodies."""
    return html.escape(str(value if value is not None else ""), quote=True)


# =========================================================
# Layer 1 - Diagram
# =========================================================


@dataclass(frozen=True)
class DiagramNode:
    id: str
    label: str
    sublabel: str = ""
    group: str = ""
    """Grouping key (a domain, a subject area). Drives colour and legend."""


@dataclass(frozen=True)
class DiagramEdge:
    source: str
    target: str
    label: str = ""
    cardinality: str = ""
    """Rendered as a small badge on the connector, e.g. '1:N'."""


CARDINALITY_BADGE: dict[str, str] = {
    Cardinality.ONE_TO_ONE.value: "1:1",
    Cardinality.ONE_TO_MANY.value: "1:N",
    Cardinality.MANY_TO_ONE.value: "N:1",
    Cardinality.MANY_TO_MANY.value: "N:N",
    Cardinality.UNKNOWN.value: "",
}


def _layer_edges(nodes: list[DiagramNode], edges: list[DiagramEdge]) -> list[tuple[str, str]]:
    """Convert diagram edges to `(child, parent)` pairs for the layout pass.

    The "one" side of a relationship becomes the parent, so the hierarchy
    reads the way a data architect would draw it: reference data at the top,
    transactional detail below.
    """
    known = {node.id for node in nodes}
    pairs: list[tuple[str, str]] = []

    for edge in edges:
        if edge.source not in known or edge.target not in known:
            continue
        if edge.cardinality == Cardinality.MANY_TO_ONE.value:
            pairs.append((edge.source, edge.target))
        else:
            pairs.append((edge.target, edge.source))

    return pairs


def _assign_positions(
    nodes: list[DiagramNode], edges: list[DiagramEdge]
) -> tuple[dict[str, tuple[float, float]], int, int]:
    """Place every node. Returns (positions, canvas_width, canvas_height)."""
    ids = [node.id for node in nodes]
    pairs = _layer_edges(nodes, edges)

    _, depths, unresolved = build_dependency_order(ids, pairs)

    # Nodes caught in a cycle cannot be ordered; park them one level below
    # the deepest resolved node rather than dropping them from the diagram.
    if unresolved:
        deepest = max((depths[i] for i in ids if i not in set(unresolved)), default=0)
        for node_id in unresolved:
            depths[node_id] = deepest + 1

    layers: dict[int, list[str]] = {}
    for node_id in sorted(ids):
        layers.setdefault(depths.get(node_id, 0), []).append(node_id)

    # Barycentre pass: order each layer by the mean position of its parents
    # in the layer above. One pass is enough to remove most crossings and
    # keeps the result deterministic.
    parents: dict[str, list[str]] = {node_id: [] for node_id in ids}
    for child, parent in pairs:
        if child != parent:
            parents[child].append(parent)

    order_in_layer: dict[str, int] = {}
    for depth in sorted(layers):
        if depth == 0:
            layers[depth].sort()
        else:

            def barycentre(node_id: str) -> tuple[float, str]:
                positions = [
                    order_in_layer[p] for p in parents[node_id] if p in order_in_layer
                ]
                return (
                    sum(positions) / len(positions) if positions else float("inf"),
                    node_id,
                )

            layers[depth].sort(key=barycentre)

        for index, node_id in enumerate(layers[depth]):
            order_in_layer[node_id] = index

    widest = max((len(members) for members in layers.values()), default=1)
    canvas_width = MARGIN * 2 + widest * NODE_W + (widest - 1) * H_GAP
    canvas_height = MARGIN * 2 + len(layers) * NODE_H + max(len(layers) - 1, 0) * V_GAP

    positions: dict[str, tuple[float, float]] = {}
    for depth in sorted(layers):
        members = layers[depth]
        row_width = len(members) * NODE_W + (len(members) - 1) * H_GAP
        start_x = (canvas_width - row_width) / 2
        y = MARGIN + depth * (NODE_H + V_GAP)
        for index, node_id in enumerate(members):
            positions[node_id] = (start_x + index * (NODE_W + H_GAP), y)

    return positions, int(canvas_width), int(canvas_height)


def _truncate(text: str, available_px: float) -> str:
    limit = max(int(available_px / LABEL_CHAR_PX), 6)
    return text if len(text) <= limit else text[: limit - 1].rstrip() + "…"


def _edge_path(
    start: tuple[float, float], end: tuple[float, float]
) -> tuple[str, tuple[float, float]]:
    """Cubic bezier from a parent's bottom edge to a child's top edge.

    Returns the path and its midpoint, used to place the label.
    """
    x1, y1 = start
    x2, y2 = end
    dy = max((y2 - y1) * 0.45, 26)
    path = f"M {x1:.1f},{y1:.1f} C {x1:.1f},{y1 + dy:.1f} {x2:.1f},{y2 - dy:.1f} {x2:.1f},{y2:.1f}"
    midpoint = ((x1 + x2) / 2, (y1 + y2) / 2)
    return path, midpoint


def render_diagram(
    nodes: list[DiagramNode],
    edges: list[DiagramEdge],
    group_colours: dict[str, tuple[str, str]] | None = None,
) -> str:
    """Render nodes and edges as a self-contained, responsive SVG."""
    if not nodes:
        return '<p class="empty">No entities to diagram.</p>'

    group_colours = group_colours or {}
    positions, width, height = _assign_positions(nodes, edges)
    known = {node.id for node in nodes}

    parts: list[str] = [
        f'<svg class="diagram" viewBox="0 0 {width} {height}" '
        f'role="img" aria-label="Conceptual data model diagram" '
        f'xmlns="http://www.w3.org/2000/svg">',
        "<defs>",
        '<marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse">',
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{MUTED}" />',
        "</marker>",
        '<filter id="cardShadow" x="-20%" y="-20%" width="140%" height="160%">',
        '<feDropShadow dx="0" dy="2" stdDeviation="2.5" flood-color="#0f172a" '
        'flood-opacity="0.14" />',
        "</filter>",
        "</defs>",
        '<g class="edges">',
    ]

    # -- Edges first so nodes paint over them ---------------------------
    for index, edge in enumerate(edges):
        if edge.source not in known or edge.target not in known:
            continue

        sx, sy = positions[edge.source]
        tx, ty = positions[edge.target]

        if edge.source == edge.target:
            # Self-reference: a loop off the right-hand edge of the box.
            x = sx + NODE_W
            y = sy + NODE_H / 2
            path = (
                f"M {x:.1f},{y - 12:.1f} C {x + 54:.1f},{y - 40:.1f} "
                f"{x + 54:.1f},{y + 40:.1f} {x:.1f},{y + 12:.1f}"
            )
            midpoint = (x + 44, y)
        else:
            # Connect the facing edges of the two boxes.
            if ty >= sy:
                start = (sx + NODE_W / 2, sy + NODE_H)
                end = (tx + NODE_W / 2, ty)
            else:
                start = (sx + NODE_W / 2, sy)
                end = (tx + NODE_W / 2, ty + NODE_H)
            path, midpoint = _edge_path(start, end)

        badge = CARDINALITY_BADGE.get(edge.cardinality, "")
        caption = " ".join(part for part in (edge.label, badge) if part).strip()

        parts.append(
            f'<g class="edge" data-edge="{index}" '
            f'data-from="{esc(edge.source)}" data-to="{esc(edge.target)}">'
            f'<path class="edge-hit" d="{path}" />'
            f'<path class="edge-line" d="{path}" marker-end="url(#arrow)" />'
        )
        if caption:
            parts.append(
                f'<text class="edge-label" x="{midpoint[0]:.1f}" y="{midpoint[1]:.1f}" '
                f'text-anchor="middle" dominant-baseline="middle">{esc(caption)}</text>'
            )
        parts.append("</g>")

    parts.append("</g>")
    parts.append('<g class="nodes">')

    # -- Nodes ----------------------------------------------------------
    for node in nodes:
        x, y = positions[node.id]
        stroke, fill = group_colours.get(node.group, (BRAND, "#eff4ff"))
        label = _truncate(node.label, NODE_W - 26)
        sublabel = _truncate(node.sublabel, NODE_W - 26) if node.sublabel else ""

        label_y = y + (NODE_H / 2 - 5) if sublabel else y + NODE_H / 2
        parts.append(
            f'<g class="node" data-id="{esc(node.id)}">'
            f"<title>{esc(node.label)}"
            + (f" — {esc(node.group)}" if node.group else "")
            + "</title>"
            f'<rect class="node-box" x="{x:.1f}" y="{y:.1f}" width="{NODE_W}" '
            f'height="{NODE_H}" rx="12" ry="12" fill="{fill}" stroke="{stroke}" />'
            f'<rect class="node-tab" x="{x:.1f}" y="{y:.1f}" width="5" '
            f'height="{NODE_H}" rx="2.5" ry="2.5" fill="{stroke}" />'
            f'<text class="node-label" x="{x + NODE_W / 2:.1f}" y="{label_y:.1f}" '
            f'text-anchor="middle" dominant-baseline="middle">{esc(label)}</text>'
        )
        if sublabel:
            parts.append(
                f'<text class="node-sublabel" x="{x + NODE_W / 2:.1f}" '
                f'y="{y + NODE_H / 2 + 13:.1f}" text-anchor="middle" '
                f'dominant-baseline="middle">{esc(sublabel)}</text>'
            )
        parts.append("</g>")

    parts.append("</g>")
    parts.append("</svg>")
    return "".join(parts)


# =========================================================
# Layer 2 - Report framework
# =========================================================


@dataclass(frozen=True)
class MetaItem:
    label: str
    value: str


@dataclass(frozen=True)
class CardField:
    label: str
    value: str


@dataclass(frozen=True)
class Card:
    title: str
    subtitle: str = ""
    body: str = ""
    fields: list[CardField] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    accent: int = 0
    badge: str = ""


@dataclass(frozen=True)
class Section:
    """Base section. Subclasses implement `body_html`."""

    title: str
    description: str = ""

    def body_html(self) -> str:  # pragma: no cover - overridden
        return ""

    def render(self, index: int) -> str:
        description = (
            f'<p class="section-note">{esc(self.description)}</p>' if self.description else ""
        )
        return (
            f'<section class="section">'
            f'<h2><span class="section-index">{index}</span>{esc(self.title)}</h2>'
            f"{description}{self.body_html()}"
            f"</section>"
        )


@dataclass(frozen=True)
class ProseSection(Section):
    paragraphs: list[str] = field(default_factory=list)

    def body_html(self) -> str:
        if not self.paragraphs:
            return '<p class="empty">Nothing recorded.</p>'
        body = "".join(f"<p>{esc(p)}</p>" for p in self.paragraphs)
        return f'<div class="prose">{body}</div>'


@dataclass(frozen=True)
class CardGridSection(Section):
    cards: list[Card] = field(default_factory=list)
    compact: bool = False

    def body_html(self) -> str:
        if not self.cards:
            return '<p class="empty">Nothing recorded.</p>'

        rendered = []
        for card in self.cards:
            stroke, tint = ACCENTS[card.accent % len(ACCENTS)]
            badge = (
                f'<span class="card-badge" style="background:{tint};color:{stroke}">'
                f"{esc(card.badge)}</span>"
                if card.badge
                else ""
            )
            subtitle = (
                f'<p class="card-subtitle">{esc(card.subtitle)}</p>' if card.subtitle else ""
            )
            body = f'<p class="card-body">{esc(card.body)}</p>' if card.body else ""

            fields = ""
            if card.fields:
                rows = "".join(
                    f'<div class="field"><dt>{esc(f.label)}</dt><dd>{esc(f.value)}</dd></div>'
                    for f in card.fields
                )
                fields = f'<dl class="card-fields">{rows}</dl>'

            tags = ""
            if card.tags:
                chips = "".join(f'<span class="tag">{esc(t)}</span>' for t in card.tags)
                tags = f'<div class="tags">{chips}</div>'

            rendered.append(
                f'<article class="card" style="--accent:{stroke};--accent-tint:{tint}">'
                f'<div class="card-head"><h3>{esc(card.title)}</h3>{badge}</div>'
                f"{subtitle}{body}{fields}{tags}</article>"
            )

        css_class = "grid grid-compact" if self.compact else "grid"
        return f'<div class="{css_class}">{"".join(rendered)}</div>'


@dataclass(frozen=True)
class NumberedSection(Section):
    items: list[str] = field(default_factory=list)

    def body_html(self) -> str:
        if not self.items:
            return '<p class="empty">Nothing recorded.</p>'
        rendered = "".join(
            f'<li class="numbered-card"><span class="numeral">{index}</span>'
            f"<p>{esc(item)}</p></li>"
            for index, item in enumerate(self.items, start=1)
        )
        return f'<ol class="numbered">{rendered}</ol>'


@dataclass(frozen=True)
class BulletSection(Section):
    items: list[str] = field(default_factory=list)

    def body_html(self) -> str:
        if not self.items:
            return '<p class="empty">Nothing recorded.</p>'
        rendered = "".join(
            f'<li class="bullet-card"><span class="dot"></span><p>{esc(item)}</p></li>'
            for item in self.items
        )
        return f'<ul class="bullets">{rendered}</ul>'


@dataclass(frozen=True)
class DiagramSection(Section):
    nodes: list[DiagramNode] = field(default_factory=list)
    edges: list[DiagramEdge] = field(default_factory=list)
    group_colours: dict[str, tuple[str, str]] = field(default_factory=dict)

    def body_html(self) -> str:
        legend = ""
        if self.group_colours:
            chips = "".join(
                f'<span class="legend-item"><span class="swatch" '
                f'style="background:{tint};border-color:{stroke}"></span>{esc(group)}</span>'
                for group, (stroke, tint) in self.group_colours.items()
            )
            legend = f'<div class="legend">{chips}</div>'

        hint = (
            '<p class="diagram-hint">Hover an entity to isolate its relationships. '
            "Use your browser zoom to enlarge.</p>"
        )
        diagram = render_diagram(self.nodes, self.edges, self.group_colours)
        return f'{legend}<div class="diagram-frame">{diagram}</div>{hint}'


@dataclass(frozen=True)
class ReportDocument:
    """A complete report, independent of which model produced it."""

    platform: str
    title: str
    meta: list[MetaItem] = field(default_factory=list)
    sections: list[Section] = field(default_factory=list)
    provenance: str = ""
    footer: str = ""


def _stylesheet() -> str:
    return f"""
*,*::before,*::after{{box-sizing:border-box}}
html{{-webkit-text-size-adjust:100%}}
body{{margin:0;background:{CANVAS};color:{INK};font-family:{FONT_STACK};
 font-size:15px;line-height:1.6;-webkit-font-smoothing:antialiased}}
.page{{max-width:1180px;margin:0 auto;padding:0 24px 72px}}

header.masthead{{background:linear-gradient(135deg,{BRAND_DARK} 0%,{BRAND} 100%);
 color:#fff;padding:38px 0 32px;margin-bottom:32px}}
header.masthead .inner{{max-width:1180px;margin:0 auto;padding:0 24px}}
.platform{{font-size:12px;letter-spacing:.14em;text-transform:uppercase;
 opacity:.82;margin:0 0 6px;font-weight:600}}
header.masthead h1{{margin:0;font-size:31px;line-height:1.2;font-weight:700;
 letter-spacing:-.02em}}
.meta{{display:flex;flex-wrap:wrap;gap:10px 32px;margin-top:22px}}
.meta div{{min-width:120px}}
.meta dt{{font-size:11px;letter-spacing:.09em;text-transform:uppercase;
 opacity:.78;margin:0 0 2px}}
.meta dd{{margin:0;font-size:14.5px;font-weight:600}}

.provenance{{background:#fffbeb;border:1px solid #fcd9a4;border-left:4px solid #b45309;
 border-radius:10px;padding:14px 18px;margin:0 0 30px;color:#713f12;font-size:13.5px}}

.section{{margin:0 0 42px}}
.section h2{{display:flex;align-items:center;gap:12px;font-size:20px;font-weight:700;
 letter-spacing:-.01em;margin:0 0 6px;padding-bottom:12px;border-bottom:1px solid {BORDER}}}
.section-index{{display:inline-flex;align-items:center;justify-content:center;
 width:26px;height:26px;border-radius:8px;background:{BRAND};color:#fff;
 font-size:13px;font-weight:700;flex:none}}
.section-note{{color:{MUTED};font-size:13.5px;margin:0 0 18px}}
.prose p{{margin:0 0 12px;font-size:15.5px;max-width:80ch}}
.empty{{color:{MUTED};font-style:italic}}

.grid{{display:grid;gap:16px;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));
 margin-top:18px}}
.grid-compact{{grid-template-columns:repeat(auto-fill,minmax(228px,1fr))}}
.card{{background:{SURFACE};border:1px solid {BORDER};border-top:3px solid var(--accent);
 border-radius:12px;padding:18px 18px 16px;box-shadow:0 1px 2px rgba(15,23,42,.05);
 transition:box-shadow .15s ease,transform .15s ease}}
.card:hover{{box-shadow:0 6px 18px rgba(15,23,42,.09);transform:translateY(-1px)}}
.card-head{{display:flex;align-items:flex-start;justify-content:space-between;gap:10px}}
.card h3{{margin:0;font-size:16px;font-weight:700;letter-spacing:-.01em}}
.card-badge{{flex:none;font-size:11px;font-weight:700;padding:3px 9px;border-radius:20px;
 white-space:nowrap}}
.card-subtitle{{margin:3px 0 0;font-size:12px;font-weight:600;color:var(--accent);
 letter-spacing:.03em;text-transform:uppercase}}
.card-body{{margin:10px 0 0;font-size:14px;color:#334155}}
.card-fields{{margin:14px 0 0;display:grid;gap:8px}}
.field{{display:grid;grid-template-columns:96px 1fr;gap:10px;align-items:start}}
.field dt{{font-size:11px;letter-spacing:.06em;text-transform:uppercase;color:{MUTED};
 font-weight:600;padding-top:1px}}
.field dd{{margin:0;font-size:13.5px}}
.tags{{display:flex;flex-wrap:wrap;gap:6px;margin-top:13px}}
.tag{{background:var(--accent-tint);color:var(--accent);border:1px solid var(--accent);
 border-radius:6px;padding:2px 8px;font-size:11.5px;font-weight:600}}

.numbered{{list-style:none;margin:18px 0 0;padding:0;display:grid;gap:10px}}
.numbered-card{{display:flex;gap:14px;background:{SURFACE};border:1px solid {BORDER};
 border-radius:10px;padding:14px 16px}}
.numeral{{flex:none;width:26px;height:26px;border-radius:8px;background:{BRAND};color:#fff;
 display:inline-flex;align-items:center;justify-content:center;font-size:13px;font-weight:700}}
.numbered-card p{{margin:2px 0 0;font-size:14.5px}}

.bullets{{list-style:none;margin:18px 0 0;padding:0;display:grid;gap:10px;
 grid-template-columns:repeat(auto-fill,minmax(340px,1fr))}}
.bullet-card{{display:flex;gap:12px;background:{SURFACE};border:1px solid {BORDER};
 border-left:3px solid {BRAND};border-radius:10px;padding:14px 16px}}
.dot{{flex:none;width:7px;height:7px;border-radius:50%;background:{BRAND};margin-top:8px}}
.bullet-card p{{margin:0;font-size:14.5px}}

.legend{{display:flex;flex-wrap:wrap;gap:8px 18px;margin:0 0 14px}}
.legend-item{{display:inline-flex;align-items:center;gap:7px;font-size:12.5px;
 font-weight:600;color:#334155}}
.swatch{{width:13px;height:13px;border-radius:4px;border:1.5px solid}}
.diagram-frame{{background:{SURFACE};border:1px solid {BORDER};border-radius:12px;
 padding:20px;overflow-x:auto;text-align:center;box-shadow:0 1px 2px rgba(15,23,42,.05)}}
.diagram{{width:100%;height:auto;max-width:100%;display:block;margin:0 auto}}
.diagram-hint{{color:{MUTED};font-size:12.5px;margin:10px 0 0;text-align:center}}

.node-box{{stroke-width:1.5;filter:url(#cardShadow)}}
.node-label{{font-family:{FONT_STACK};font-size:13px;font-weight:700;fill:{INK}}}
.node-sublabel{{font-family:{FONT_STACK};font-size:10.5px;fill:{MUTED}}}
.node{{cursor:default}}
.edge-line{{fill:none;stroke:#94a3b8;stroke-width:1.5}}
.edge-hit{{fill:none;stroke:transparent;stroke-width:14}}
.edge-label{{font-family:{FONT_STACK};font-size:10.5px;font-weight:600;fill:#475569;
 paint-order:stroke;stroke:{SURFACE};stroke-width:4px;stroke-linejoin:round}}

.diagram.focus .node,.diagram.focus .edge{{opacity:.16;transition:opacity .12s ease}}
.diagram.focus .node.active,.diagram.focus .edge.active{{opacity:1}}
.diagram.focus .edge.active .edge-line{{stroke:{BRAND};stroke-width:2.4}}
.diagram.focus .edge.active .edge-label{{fill:{BRAND_DARK}}}

footer.report-footer{{border-top:1px solid {BORDER};margin-top:12px;padding-top:20px;
 color:{MUTED};font-size:12.5px}}

@media (max-width:640px){{
 header.masthead h1{{font-size:24px}}
 .grid,.bullets{{grid-template-columns:1fr}}
 .field{{grid-template-columns:1fr;gap:2px}}
}}

@media print{{
 body{{background:#fff;font-size:11.5pt}}
 header.masthead{{background:{BRAND_DARK} !important;-webkit-print-color-adjust:exact;
  print-color-adjust:exact}}
 .card,.numbered-card,.bullet-card,.diagram-frame{{box-shadow:none;
  break-inside:avoid;page-break-inside:avoid}}
 .card:hover{{transform:none}}
 .section{{break-inside:avoid-page}}
 .diagram-hint{{display:none}}
 .diagram-frame{{overflow:visible}}
}}
""".strip()


def _script() -> str:
    """Hover highlighting. Inline, dependency-free, ~25 lines."""
    return """
(function () {
  var svg = document.querySelector('.diagram');
  if (!svg) return;
  var nodes = Array.prototype.slice.call(svg.querySelectorAll('.node'));
  var edges = Array.prototype.slice.call(svg.querySelectorAll('.edge'));

  function clear() {
    svg.classList.remove('focus');
    nodes.concat(edges).forEach(function (el) { el.classList.remove('active'); });
  }

  function focus(id) {
    var related = {};
    related[id] = true;
    edges.forEach(function (edge) {
      var from = edge.getAttribute('data-from');
      var to = edge.getAttribute('data-to');
      if (from === id || to === id) {
        edge.classList.add('active');
        related[from] = true;
        related[to] = true;
      }
    });
    nodes.forEach(function (node) {
      if (related[node.getAttribute('data-id')]) node.classList.add('active');
    });
    svg.classList.add('focus');
  }

  nodes.forEach(function (node) {
    node.addEventListener('mouseenter', function () {
      clear();
      focus(node.getAttribute('data-id'));
    });
    node.addEventListener('mouseleave', clear);
  });
})();
""".strip()


def render_report(document: ReportDocument) -> str:
    """Render a `ReportDocument` as one self-contained HTML file."""
    meta = "".join(
        f"<div><dt>{esc(item.label)}</dt><dd>{esc(item.value)}</dd></div>"
        for item in document.meta
    )
    sections = "".join(
        section.render(index) for index, section in enumerate(document.sections, start=1)
    )
    provenance = (
        f'<div class="provenance">{esc(document.provenance)}</div>'
        if document.provenance
        else ""
    )
    footer = (
        f'<footer class="report-footer">{esc(document.footer)}</footer>'
        if document.footer
        else ""
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n<head>\n'
        '<meta charset="utf-8" />\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1" />\n'
        f"<title>{esc(document.title)} — {esc(document.platform)}</title>\n"
        f"<style>\n{_stylesheet()}\n</style>\n"
        "</head>\n<body>\n"
        '<header class="masthead"><div class="inner">'
        f'<p class="platform">{esc(document.platform)}</p>'
        f"<h1>{esc(document.title)}</h1>"
        f'<dl class="meta">{meta}</dl>'
        "</div></header>\n"
        f'<main class="page">{provenance}{sections}{footer}</main>\n'
        f"<script>\n{_script()}\n</script>\n"
        "</body>\n</html>\n"
    )


# =========================================================
# Layer 3 - Conceptual model mapping
# =========================================================


def _domain_colours(model: ConceptualModel) -> dict[str, tuple[str, str]]:
    """Assign a stable colour per domain, in declaration order."""
    return {
        domain.name: ACCENTS[index % len(ACCENTS)]
        for index, domain in enumerate(model.domains)
    }


def _entity_domain(model: ConceptualModel) -> dict[str, str]:
    """Map each entity to its domain. Entities in no domain map to ''."""
    lookup: dict[str, str] = {}
    for domain in model.domains:
        for entity_name in domain.entities:
            lookup.setdefault(entity_name, domain.name)
    return lookup


def build_conceptual_document(
    package: ConceptualModelPackage,
    generated_at: datetime | None = None,
) -> ReportDocument:
    """Map a conceptual model onto the generic report framework.

    A future logical/physical/catalog report supplies its own equivalent of
    this function and reuses everything above it unchanged.
    """
    model = package.conceptual_model
    stamp = generated_at or datetime.now()
    colours = _domain_colours(model)
    entity_domain = _entity_domain(model)
    domain_index = {name: index for index, name in enumerate(colours)}

    relationship_total = sum(len(entity.relationships) for entity in model.entities)

    # -- Section 1: Executive Summary -----------------------------------
    summary = ProseSection(title="Executive Summary", paragraphs=[model.summary])

    # -- Section 2: Business Domains ------------------------------------
    domain_cards = [
        Card(
            title=domain.name,
            body=domain.description,
            badge=f"{len(domain.entities)} entities",
            tags=list(domain.entities),
            accent=index,
        )
        for index, domain in enumerate(model.domains)
    ]
    domains = CardGridSection(
        title="Business Domains",
        description="Subject areas a single team could own.",
        cards=domain_cards,
    )

    # -- Section 3: Business Entities -----------------------------------
    entity_cards = []
    for entity in model.entities:
        domain_name = entity_domain.get(entity.name, "")
        fields = [
            CardField(
                "Business key",
                ", ".join(entity.business_key) if entity.business_key else "Not identified",
            ),
            CardField(
                "Attributes",
                ", ".join(entity.attributes) if entity.attributes else "None recorded",
            ),
            CardField("Relationships", str(len(entity.relationships))),
        ]
        if entity.source_tables:
            fields.append(CardField("Derived from", ", ".join(entity.source_tables)))

        entity_cards.append(
            Card(
                title=entity.name,
                subtitle=domain_name,
                body=entity.description,
                fields=fields,
                accent=domain_index.get(domain_name, 0),
            )
        )

    entities = CardGridSection(
        title="Business Entities",
        description=(
            f"{len(model.entities)} entities carrying {relationship_total} "
            f"relationships between them."
        ),
        cards=entity_cards,
    )

    # -- Section 4: Conceptual Diagram ----------------------------------
    nodes = [
        DiagramNode(
            id=entity.name,
            label=entity.name,
            sublabel=entity.business_key[0] if entity.business_key else "",
            group=entity_domain.get(entity.name, ""),
        )
        for entity in model.entities
    ]

    # One edge per declared relationship, de-duplicated by entity pair so a
    # reciprocally declared relationship is drawn once rather than twice.
    seen: set[frozenset[str]] = set()
    edges: list[DiagramEdge] = []
    for entity in model.entities:
        for relationship in entity.relationships:
            pair = frozenset({entity.name, relationship.related_entity})
            if pair in seen:
                continue
            seen.add(pair)
            edges.append(
                DiagramEdge(
                    source=entity.name,
                    target=relationship.related_entity,
                    label=relationship.verb_phrase,
                    cardinality=relationship.cardinality.value,
                )
            )

    diagram = DiagramSection(
        title="Conceptual Diagram",
        description="Entities coloured by business domain; arrows read in the direction of the label.",
        nodes=nodes,
        edges=edges,
        group_colours=colours,
    )

    # -- Sections 5-7 ----------------------------------------------------
    rules = NumberedSection(
        title="Business Rules",
        description="Rules the structure and value distributions imply.",
        items=list(model.business_rules),
    )
    assumptions = NumberedSection(
        title="Assumptions",
        description=(
            "Where interpretation happened. Each of these is a judgement, not a "
            "fact read from the database, and should be confirmed."
        ),
        items=list(model.assumptions),
    )
    recommendations = BulletSection(
        title="Recommendations",
        description="Gaps and questions worth raising with the business.",
        items=list(model.recommendations),
    )

    return ReportDocument(
        platform="Enterprise AI Data Modernization Platform",
        title="Conceptual Data Model",
        meta=[
            MetaItem("Database", model.database_name),
            MetaItem("Source Database", model.database_name),
            MetaItem("Generated", stamp.strftime("%d %b %Y, %H:%M")),
            MetaItem("Domains", str(len(model.domains))),
            MetaItem("Entities", str(len(model.entities))),
            MetaItem("Relationships", str(relationship_total)),
        ],
        sections=[
            summary,
            domains,
            entities,
            diagram,
            rules,
            assumptions,
            recommendations,
        ],
        provenance=(
            f"This conceptual model was generated by "
            f"{package.generated_by or 'an AI model'} from the deterministic metadata, "
            "profile and relationship artifacts. It is an interpretation of the business "
            "the database appears to support and should be reviewed by someone who knows "
            "that business. The Assumptions section lists where interpretation happened."
        ),
        footer=(
            "Generated by the Enterprise AI Data Modernization Platform. "
            "Diagram and layout rendered deterministically from the conceptual model; "
            "no part of this page was written by the AI."
        ),
    )


def render_conceptual_html(
    package: ConceptualModelPackage, generated_at: datetime | None = None
) -> str:
    """Render `conceptual_model.html` from a validated package."""
    return render_report(build_conceptual_document(package, generated_at))
