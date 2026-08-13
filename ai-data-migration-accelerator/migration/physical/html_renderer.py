"""
Physical Model HTML Renderer

Renders `physical_model.html`, including a true entity-relationship diagram.

Reuse
-----
The page shell, stylesheet, card/section types and hover script all come from
`migration/conceptual/html_renderer.py` unchanged. This module supplies two
things that module cannot:

1.  A **column-level ERD**. The shared `render_diagram` draws a labelled box
    per entity, which is right for a conceptual model. A physical model has
    to show the columns, their types and their key markers — that is what a
    reviewer checks and what a client demo needs to see.
2.  The physical-model mapping onto the shared report framework.

The ERD deliberately emits the same `.node` / `.edge` / `data-from` /
`data-to` structure the shared stylesheet and hover script already target,
so highlighting works without a line of new CSS or JavaScript.

Nothing in Modules 1-5 is modified; this only imports from them.
"""

from __future__ import annotations

from datetime import datetime

from migration.conceptual.html_renderer import (
    ACCENTS,
    BORDER,
    BulletSection,
    Card,
    CardField,
    CardGridSection,
    FONT_STACK,
    INK,
    MUTED,
    MetaItem,
    ProseSection,
    ReportDocument,
    Section,
    SURFACE,
    esc,
    render_report,
)
from migration.physical.models import (
    ConstraintType,
    PhysicalModel,
    PhysicalModelPackage,
    PhysicalTable,
    TableClassification,
)
from migration.relationship.graph import build_dependency_order

# -- ERD geometry ----------------------------------------------------------

BOX_W = 258
HEADER_H = 32
ROW_H = 19
BOX_PAD = 8
H_GAP = 46
V_GAP = 78
MARGIN = 30
MAX_ROWS = 9
"""Columns shown per table before collapsing into a '+N more' row. Keeps a
19-table diagram legible on one screen; the full list is in the tables
below it."""

CLASSIFICATION_ACCENT: dict[TableClassification, int] = {
    TableClassification.LOOKUP: 5,  # teal
    TableClassification.MASTER: 0,  # blue
    TableClassification.TRANSACTION: 2,  # amber
}


# =========================================================
# Entity-relationship diagram
# =========================================================


def _box_height(table: PhysicalTable) -> int:
    rows = min(len(table.columns), MAX_ROWS)
    if len(table.columns) > MAX_ROWS:
        rows += 1
    return HEADER_H + rows * ROW_H + BOX_PAD


def _layout(
    tables: list[PhysicalTable], edges: list[tuple[str, str]]
) -> tuple[dict[str, tuple[float, float]], int, int]:
    """Place variable-height boxes in dependency layers.

    Reuses `build_dependency_order` from the relationship engine — it is
    domain-free by design, and using it keeps every diagram in the platform
    laid out on the same principle.
    """
    names = [table.name for table in tables]
    heights = {table.name: _box_height(table) for table in tables}

    _, depths, unresolved = build_dependency_order(names, edges)
    if unresolved:
        deepest = max((depths[n] for n in names if n not in set(unresolved)), default=0)
        for name in unresolved:
            depths[name] = deepest + 1

    layers: dict[int, list[str]] = {}
    for name in sorted(names):
        layers.setdefault(depths.get(name, 0), []).append(name)

    widest = max((len(members) for members in layers.values()), default=1)
    width = MARGIN * 2 + widest * BOX_W + (widest - 1) * H_GAP

    positions: dict[str, tuple[float, float]] = {}
    y = MARGIN
    for depth in sorted(layers):
        members = layers[depth]
        row_width = len(members) * BOX_W + (len(members) - 1) * H_GAP
        x = (width - row_width) / 2
        for name in members:
            positions[name] = (x, y)
            x += BOX_W + H_GAP
        y += max(heights[name] for name in members) + V_GAP

    return positions, int(width), int(y - V_GAP + MARGIN)


def render_erd(model: PhysicalModel) -> str:
    """Render the physical model as a column-level ERD."""
    tables = model.tables
    if not tables:
        return '<p class="empty">No tables to diagram.</p>'

    by_name = {table.name: table for table in tables}
    edges: list[tuple[str, str]] = []
    for table in tables:
        for constraint in table.constraints:
            if (
                constraint.constraint_type == ConstraintType.FOREIGN_KEY
                and constraint.referenced_table in by_name
            ):
                edges.append((table.name, constraint.referenced_table))

    positions, width, height = _layout(tables, edges)
    heights = {table.name: _box_height(table) for table in tables}

    parts: list[str] = [
        f'<svg class="diagram" viewBox="0 0 {width} {height}" role="img" '
        f'aria-label="Physical entity-relationship diagram" '
        f'xmlns="http://www.w3.org/2000/svg">',
        "<defs>",
        '<marker id="erdArrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" '
        'markerHeight="7" orient="auto-start-reverse">',
        f'<path d="M 0 0 L 10 5 L 0 10 z" fill="{MUTED}" /></marker>',
        '<filter id="cardShadow" x="-20%" y="-20%" width="140%" height="160%">',
        '<feDropShadow dx="0" dy="2" stdDeviation="2.5" flood-color="#0f172a" '
        'flood-opacity="0.13" /></filter>',
        "</defs>",
        '<g class="edges">',
    ]

    # -- Relationships --------------------------------------------------
    for index, (child, parent) in enumerate(sorted(set(edges))):
        cx, cy = positions[child]
        px, py = positions[parent]

        if cy >= py:
            start = (px + BOX_W / 2, py + heights[parent])
            end = (cx + BOX_W / 2, cy)
        else:
            start = (px + BOX_W / 2, py)
            end = (cx + BOX_W / 2, cy + heights[child])

        dy = max(abs(end[1] - start[1]) * 0.45, 24)
        path = (
            f"M {start[0]:.1f},{start[1]:.1f} "
            f"C {start[0]:.1f},{start[1] + dy:.1f} "
            f"{end[0]:.1f},{end[1] - dy:.1f} {end[0]:.1f},{end[1]:.1f}"
        )
        midpoint = ((start[0] + end[0]) / 2, (start[1] + end[1]) / 2)

        parts.append(
            f'<g class="edge" data-edge="{index}" data-from="{esc(child)}" '
            f'data-to="{esc(parent)}">'
            f'<path class="edge-hit" d="{path}" />'
            f'<path class="edge-line" d="{path}" marker-end="url(#erdArrow)" />'
            f'<text class="edge-label" x="{midpoint[0]:.1f}" y="{midpoint[1]:.1f}" '
            f'text-anchor="middle" dominant-baseline="middle">N:1</text>'
            f"</g>"
        )

    parts.append("</g>")
    parts.append('<g class="nodes">')

    # -- Tables ------------------------------------------------------------
    for table in tables:
        x, y = positions[table.name]
        stroke, tint = ACCENTS[CLASSIFICATION_ACCENT[table.classification] % len(ACCENTS)]
        box_h = heights[table.name]

        parts.append(
            f'<g class="node" data-id="{esc(table.name)}">'
            f"<title>{esc(table.name)} — {esc(table.classification.value.title())} "
            f"({len(table.columns)} columns)</title>"
            f'<rect class="node-box" x="{x:.1f}" y="{y:.1f}" width="{BOX_W}" '
            f'height="{box_h}" rx="9" ry="9" fill="{SURFACE}" stroke="{stroke}" />'
            f'<path d="M {x:.1f},{y + HEADER_H:.1f} h {BOX_W}" stroke="{BORDER}" '
            f'stroke-width="1" fill="none" />'
            f'<path d="M {x + 9:.1f},{y:.1f} h {BOX_W - 18} a 9 9 0 0 1 9 9 '
            f"v {HEADER_H - 9} h -{BOX_W} v -{HEADER_H - 9} a 9 9 0 0 1 9 -9 z\" "
            f'fill="{tint}" />'
            f'<text x="{x + 12:.1f}" y="{y + HEADER_H / 2 + 1:.1f}" '
            f'font-family="{FONT_STACK}" font-size="12.5" font-weight="700" '
            f'fill="{stroke}" dominant-baseline="middle">{esc(table.name)}</text>'
            f'<text x="{x + BOX_W - 12:.1f}" y="{y + HEADER_H / 2 + 1:.1f}" '
            f'font-family="{FONT_STACK}" font-size="9" font-weight="600" '
            f'fill="{stroke}" text-anchor="end" opacity="0.75" '
            f"dominant-baseline=\"middle\">{esc(table.classification.value[:4])}</text>"
        )

        shown = table.columns[:MAX_ROWS]
        row_y = y + HEADER_H + ROW_H / 2 + 2

        for column in shown:
            marker = (
                "PK" if column.is_primary_key else "FK" if column.is_foreign_key else ""
            )
            if not marker and column.is_unique:
                marker = "AK"

            parts.append(
                f'<text x="{x + 12:.1f}" y="{row_y:.1f}" font-family="{FONT_STACK}" '
                f'font-size="8.5" font-weight="700" fill="{stroke}" '
                f'dominant-baseline="middle">{esc(marker)}</text>'
                f'<text x="{x + 34:.1f}" y="{row_y:.1f}" font-family="{FONT_STACK}" '
                f'font-size="10.5" fill="{INK}" '
                f'font-weight="{"600" if marker == "PK" else "400"}" '
                f'dominant-baseline="middle">{esc(_shorten(column.name, 22))}</text>'
                f'<text x="{x + BOX_W - 12:.1f}" y="{row_y:.1f}" '
                f'font-family="{FONT_STACK}" font-size="9" fill="{MUTED}" '
                f'text-anchor="end" dominant-baseline="middle">'
                f"{esc(_shorten(column.type_signature(), 16))}</text>"
            )
            row_y += ROW_H

        if len(table.columns) > MAX_ROWS:
            parts.append(
                f'<text x="{x + 34:.1f}" y="{row_y:.1f}" font-family="{FONT_STACK}" '
                f'font-size="9.5" fill="{MUTED}" font-style="italic" '
                f'dominant-baseline="middle">'
                f"+{len(table.columns) - MAX_ROWS} more columns</text>"
            )

        parts.append("</g>")

    parts.append("</g></svg>")
    return "".join(parts)


def _shorten(text: str, limit: int) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


class ErdSection(Section):
    """A diagram section carrying the physical ERD.

    Subclasses the shared `Section` so it renders inside the same page shell
    with the same heading treatment as every other section.
    """

    def __init__(self, title: str, description: str, model: PhysicalModel):
        object.__setattr__(self, "title", title)
        object.__setattr__(self, "description", description)
        object.__setattr__(self, "model", model)

    def body_html(self) -> str:
        legend = "".join(
            f'<span class="legend-item"><span class="swatch" '
            f'style="background:{ACCENTS[CLASSIFICATION_ACCENT[c]][1]};'
            f'border-color:{ACCENTS[CLASSIFICATION_ACCENT[c]][0]}"></span>'
            f"{esc(c.value.title())}</span>"
            for c in TableClassification
        )
        hint = (
            '<p class="diagram-hint">Hover a table to isolate its relationships. '
            "Arrows point from the foreign key to the table it references. "
            "Use browser zoom to enlarge.</p>"
        )
        return (
            f'<div class="legend">{legend}</div>'
            f'<div class="diagram-frame">{render_erd(self.model)}</div>{hint}'
        )


# =========================================================
# Report mapping
# =========================================================


def build_physical_document(
    package: PhysicalModelPackage, generated_at: datetime | None = None
) -> ReportDocument:
    """Map the physical model onto the shared report framework."""
    model = package.physical_model
    stamp = generated_at or datetime.now()

    counts = {c: 0 for c in TableClassification}
    for table in model.tables:
        counts[table.classification] += 1
    column_total = sum(len(t.columns) for t in model.tables)

    # -- 1. Executive Summary --------------------------------------------
    summary = ProseSection(title="Executive Summary", paragraphs=[model.summary])

    # -- 2. Physical Architecture Overview --------------------------------
    architecture = CardGridSection(
        title="Physical Architecture Overview",
        description=(
            f"Naming: {model.naming_convention.style}, capped at "
            f"{model.naming_convention.max_identifier_length} characters so no "
            f"identifier needs shortening again per target platform."
        ),
        cards=[
            Card(
                title=classification.value.title(),
                badge=f"{counts[classification]} tables",
                body=_CLASSIFICATION_BLURB[classification],
                tags=sorted(
                    t.name for t in model.tables if t.classification == classification
                ),
                accent=CLASSIFICATION_ACCENT[classification],
            )
            for classification in TableClassification
        ],
    )

    # -- 3. Physical Tables ------------------------------------------------
    table_cards = [
        Card(
            title=table.name,
            subtitle=table.subject_area or "Unassigned",
            badge=table.classification.value.title(),
            fields=[
                CardField("Columns", str(len(table.columns))),
                CardField("Primary key", ", ".join(table.primary_key_columns()) or "None"),
                CardField(
                    "Size / growth",
                    f"{table.size_category.value.replace('_', ' ').title()} · "
                    f"{table.growth_rate.value.title()} growth",
                ),
                CardField("Logical entity", table.logical_entity),
            ],
            accent=CLASSIFICATION_ACCENT[table.classification],
        )
        for table in model.tables
    ]
    tables = CardGridSection(
        title="Physical Tables",
        description=(
            f"{len(model.tables)} tables and {column_total} columns. Classification "
            f"is inferred from table shape and is worth a review before it drives "
            f"sizing decisions."
        ),
        cards=table_cards,
        compact=True,
    )

    # -- 4. Column Definitions ---------------------------------------------
    columns = CardGridSection(
        title="Column Definitions",
        description="Generic storage classes with inferred sizing and nullability.",
        cards=[
            Card(
                title=table.name,
                badge=f"{len(table.columns)} columns",
                fields=[
                    CardField(
                        _column_marker(column) or "—",
                        f"{column.name} · {column.type_signature()} · "
                        f"{'NULL' if column.nullable else 'NOT NULL'}"
                        + (f" · default {column.default_value}" if column.default_value else ""),
                    )
                    for column in table.columns
                ],
                accent=CLASSIFICATION_ACCENT[table.classification],
            )
            for table in model.tables
        ],
    )

    # -- 5. Constraints ----------------------------------------------------
    constraint_cards = [
        Card(
            title=constraint.name,
            subtitle=constraint.table,
            badge=constraint.constraint_type.value.replace("_", " ").title(),
            fields=[
                CardField("Columns", ", ".join(constraint.columns)),
                *(
                    [
                        CardField(
                            "References",
                            f"{constraint.referenced_table}"
                            f"({', '.join(constraint.referenced_columns)})",
                        )
                    ]
                    if constraint.referenced_table
                    else []
                ),
                *([CardField("Rule", constraint.expression)] if constraint.expression else []),
            ],
            body=constraint.rationale or "",
            accent=_CONSTRAINT_ACCENT[constraint.constraint_type],
        )
        for constraint in model.all_constraints()
    ]
    constraints = CardGridSection(
        title="Constraints",
        description=(
            "Keys carried through from the logical model, plus check constraints "
            "added only where the domain makes the rule certain."
        ),
        cards=constraint_cards,
        compact=True,
    )

    # -- 6. Index Recommendations ------------------------------------------
    indexes = CardGridSection(
        title="Index Recommendations",
        description=(
            "Every foreign key carries an index. Unindexed foreign keys are a "
            "routine cause of slow joins and of lock escalation on parent deletes."
        ),
        cards=[
            Card(
                title=index.name,
                subtitle=index.table,
                badge="Unique" if index.is_unique else "Non-unique",
                fields=[CardField("Columns", ", ".join(index.columns))],
                body=index.rationale,
                accent=1 if index.is_unique else 7,
            )
            for index in model.all_indexes()
        ],
        compact=True,
    )

    # -- 7. Storage Recommendations ----------------------------------------
    storage = CardGridSection(
        title="Storage Recommendations",
        description=(
            "Partitioning is recommended only where there is volume to prune; "
            "clustering co-locates rows that are read together."
        ),
        cards=[
            Card(
                title=table.name,
                badge=table.size_category.value.replace("_", " ").title(),
                fields=[
                    CardField(
                        "Partition by",
                        ", ".join(table.storage.partition_candidates) or "Not recommended",
                    ),
                    CardField(
                        "Cluster by",
                        ", ".join(table.storage.clustering_candidates) or "Not recommended",
                    ),
                ],
                body=table.storage.rationale,
                accent=CLASSIFICATION_ACCENT[table.classification],
            )
            for table in model.tables
            if table.storage
        ],
    )

    # -- 8. Physical Relationship Diagram ----------------------------------
    diagram = ErdSection(
        title="Physical Relationship Diagram",
        description=(
            "Column-level ERD. Each table shows its key markers, column names "
            "and generic storage types."
        ),
        model=model,
    )

    notes = BulletSection(
        title="Design Notes",
        description="Decisions taken while deriving the physical design.",
        items=list(model.design_notes) + list(model.naming_convention.notes),
    )

    return ReportDocument(
        platform="Enterprise AI Data Modernization Platform",
        title="Physical Data Model",
        meta=[
            MetaItem("Database", model.database_name),
            MetaItem("Generated", stamp.strftime("%d %b %Y, %H:%M")),
            MetaItem("Tables", str(len(model.tables))),
            MetaItem("Columns", str(column_total)),
            MetaItem("Constraints", str(len(model.all_constraints()))),
            MetaItem("Indexes", str(len(model.all_indexes()))),
        ],
        sections=[
            summary,
            architecture,
            tables,
            columns,
            constraints,
            indexes,
            storage,
            diagram,
            notes,
        ],
        provenance=(
            f"Derived deterministically from "
            f"{package.generated_from or 'the logical model'}. This model is "
            "platform-independent: types, lengths and precision are generic storage "
            "classes, and no vendor SQL appears until DDL generation. Business "
            "descriptions are not repeated here — each table names the logical entity "
            "it came from."
        ),
        footer=(
            "Generated by the Enterprise AI Data Modernization Platform. "
            "physical_model.json is the source of truth for DDL generation."
        ),
    )


_CLASSIFICATION_BLURB = {
    TableClassification.LOOKUP: (
        "Small reference data. Read constantly, written rarely, cheap to cache or "
        "scan in full."
    ),
    TableClassification.MASTER: (
        "Core business records with their own identity and lifecycle. Referenced by "
        "transactions and looked up by key."
    ),
    TableClassification.TRANSACTION: (
        "Event and activity records. These are the tables that grow, and the ones "
        "partitioning and clustering are aimed at."
    ),
}

_CONSTRAINT_ACCENT = {
    ConstraintType.PRIMARY_KEY: 0,
    ConstraintType.FOREIGN_KEY: 3,
    ConstraintType.UNIQUE: 1,
    ConstraintType.CHECK: 4,
}


def _column_marker(column) -> str:
    markers = []
    if column.is_primary_key:
        markers.append("PK")
    if column.is_foreign_key:
        markers.append("FK")
    if column.is_unique:
        markers.append("AK")
    return " ".join(markers)


def render_physical_html(
    package: PhysicalModelPackage, generated_at: datetime | None = None
) -> str:
    """Render `physical_model.html` from a validated package."""
    return render_report(build_physical_document(package, generated_at))
