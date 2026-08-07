"""Tests for migration.conceptual.context_builder.

The context builder is fully deterministic — no AI involved — so these are
ordinary unit tests over in-memory models.
"""

from __future__ import annotations

import json

from migration.conceptual.context_builder import ContextBuilder
from migration.conceptual.models import BusinessContext
from migration.relationship.engine import RelationshipEngine
from tests.conceptual_fixtures import sample_packages
from tests.relationship_fixtures import (
    column,
    foreign_key,
    metadata,
    table,
)


def _context(**kwargs) -> BusinessContext:
    meta, prof, rels = sample_packages()
    return ContextBuilder(**kwargs).build(meta.metadata, prof.profile, rels.relationships)


def test_context_summarizes_the_database():
    context = _context()

    assert context.database_name == "testdb"
    assert context.schemas == ["app"]
    assert context.total_tables == 11
    assert context.total_relationships > 0


def test_context_never_reveals_the_source_system():
    """Source independence is a platform principle, not a nicety: the
    business answer must not change because the metadata came from Oracle."""
    context = _context()
    serialized = ContextBuilder.to_prompt_json(context).lower()

    assert "postgres" not in serialized
    assert "source_database_type" not in serialized


def test_context_includes_relationships_as_compact_lines():
    context = _context()

    assert any("app.orders" in line and "app.customer" in line for line in context.relationships)
    assert all(isinstance(line, str) for line in context.relationships)


def test_context_includes_junction_tables():
    context = _context()

    junctions = {j.table_name for j in context.junction_tables}
    assert "app.product_promotion" in junctions


def test_context_includes_self_references_and_orphans():
    context = _context()

    assert any("employee" in ref for ref in context.self_referencing)
    assert "app.audit_log" in context.orphan_tables


def test_columns_carry_business_roles_not_data_types():
    context = _context()
    customer = next(t for t in context.tables if t.table_name == "customer")

    roles = {c.name: c.role for c in customer.columns}
    assert roles["customer_id"] == "identifier"
    assert roles["city_id"] == "reference"
    # A conceptual model is about meaning; data types are withheld on purpose.
    serialized = json.loads(ContextBuilder.to_prompt_json(context))
    assert "data_type" not in json.dumps(serialized)


def test_foreign_key_columns_record_their_target():
    context = _context()
    orders = next(t for t in context.tables if t.table_name == "orders")
    customer_id = next(c for c in orders.columns if c.name == "customer_id")

    assert customer_id.references == "app.customer"


def test_profile_statistics_are_attached_when_available():
    context = _context()
    orders = next(t for t in context.tables if t.table_name == "orders")

    assert orders.row_count == 4000


def test_builds_without_a_profile():
    meta, _, rels = sample_packages()
    context = ContextBuilder().build(meta.metadata, None, rels.relationships)

    assert context.tables
    assert any("No data profile" in note for note in context.notes)


def test_builds_without_relationships():
    meta, prof, _ = sample_packages()
    context = ContextBuilder().build(meta.metadata, prof.profile, None)

    assert context.tables
    assert context.relationships == []
    assert any("No relationship graph" in note for note in context.notes)


def test_builds_with_metadata_only():
    meta, _, _ = sample_packages()
    context = ContextBuilder().build(meta.metadata)

    assert context.tables
    assert len(context.notes) >= 2


# -- Scale behaviour -------------------------------------------------------


def test_table_cap_truncates_and_records_the_omission():
    context = _context(max_tables=3)

    assert len(context.tables) == 3
    assert len(context.omitted_tables) == 8
    assert any("omitted from detail" in note for note in context.notes)


def test_table_cap_keeps_the_most_connected_tables():
    """When the schema is too large to describe, structure must survive.

    The hub is referenced by four tables; the orphan by none. Under a tight
    cap the hub must be kept and the orphan dropped.
    """
    tables = [
        table("hub", [column("hub_id", nullable=False)], primary_key=["hub_id"]),
        table("orphan", [column("orphan_id", nullable=False)], primary_key=["orphan_id"]),
    ]
    for index in range(4):
        tables.append(
            table(
                f"child_{index}",
                [column(f"child_{index}_id", nullable=False), column("hub_id")],
                primary_key=[f"child_{index}_id"],
                foreign_keys=[foreign_key(f"fk_{index}", "hub_id", "hub", "hub_id")],
            )
        )

    meta = metadata(tables)
    rels = RelationshipEngine(meta).discover()
    context = ContextBuilder(max_tables=2).build(meta, None, rels.relationships)
    kept = {t.table_name for t in context.tables}

    assert "hub" in kept
    assert "orphan" not in kept
    assert "app.orphan" in context.omitted_tables


def test_column_cap_truncates_and_records_the_count():
    meta = metadata(
        [
            table(
                "wide",
                [column("id", nullable=False)]
                + [column(f"attr_{i}", "text", position=i + 2) for i in range(40)],
                primary_key=["id"],
            )
        ]
    )
    context = ContextBuilder(max_columns_per_table=5).build(meta)
    wide = context.tables[0]

    assert len(wide.columns) == 5
    assert wide.column_count == 41
    assert wide.omitted_column_count == 36


def test_key_columns_survive_column_truncation():
    """Keys define identity and relationships — they must never be the
    columns that get dropped."""
    meta = metadata(
        [
            table("parent", [column("parent_id", nullable=False)], primary_key=["parent_id"]),
            table(
                "child",
                [column("child_id", nullable=False)]
                + [column(f"attr_{i}", "text", position=i + 2) for i in range(30)]
                + [column("parent_id", position=40)],
                primary_key=["child_id"],
                foreign_keys=[foreign_key("fk", "parent_id", "parent", "parent_id")],
            ),
        ]
    )
    rels = RelationshipEngine(meta).discover()
    context = ContextBuilder(max_columns_per_table=4).build(
        meta, None, rels.relationships
    )
    child = next(t for t in context.tables if t.table_name == "child")
    names = {c.name for c in child.columns}

    assert "child_id" in names
    assert "parent_id" in names


def test_views_are_excluded_from_the_context():
    meta = metadata(
        [
            table("real_table", [column("id", nullable=False)], primary_key=["id"]),
            table("a_view", [column("id", nullable=False)], table_type="VIEW"),
        ]
    )
    context = ContextBuilder().build(meta)

    assert [t.table_name for t in context.tables] == ["real_table"]


# -- Serialization ---------------------------------------------------------


def test_prompt_json_is_deterministic():
    first = ContextBuilder.to_prompt_json(_context())
    second = ContextBuilder.to_prompt_json(_context())

    assert first == second


def test_prompt_json_omits_nulls_and_is_valid_json():
    serialized = ContextBuilder.to_prompt_json(_context())
    payload = json.loads(serialized)

    assert payload["database_name"] == "testdb"
    for table_context in payload["tables"]:
        for column_context in table_context["columns"]:
            assert None not in column_context.values()
