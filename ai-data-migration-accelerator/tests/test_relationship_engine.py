"""Tests for migration.relationship.engine — declared extraction and graph
assembly.

No database and no fake connector: the engine consumes in-memory models only.
"""

from __future__ import annotations

from migration.relationship.engine import RelationshipEngine
from migration.relationship.models import (
    Cardinality,
    ConfidenceBand,
    DiscoveryMethod,
    RelationshipType,
)
from tests.relationship_fixtures import (
    column,
    foreign_key,
    metadata,
    sample_metadata,
    table,
)


def _discover(meta, prof=None):
    return RelationshipEngine(meta, prof).discover().relationships


# ---------------------------------------------------------
# Declared foreign keys
# ---------------------------------------------------------


def test_single_column_declared_foreign_key():
    meta = metadata(
        [
            table("parent", [column("parent_id", nullable=False)], primary_key=["parent_id"]),
            table(
                "child",
                [column("child_id", nullable=False), column("parent_id")],
                primary_key=["child_id"],
                foreign_keys=[foreign_key("child_parent_fk", "parent_id", "parent", "parent_id")],
            ),
        ]
    )

    declared = [
        r for r in _discover(meta).relationships if r.discovery_method == DiscoveryMethod.DECLARED
    ]

    assert len(declared) == 1
    relationship = declared[0]
    assert relationship.source_table == "child"
    assert relationship.target_table == "parent"
    assert relationship.confidence == 1.0
    assert relationship.confidence_band == ConfidenceBand.CERTAIN
    assert relationship.constraint_name == "child_parent_fk"
    assert relationship.cardinality == Cardinality.MANY_TO_ONE


def test_composite_foreign_key_becomes_one_relationship():
    meta = metadata(
        [
            table(
                "parent",
                [
                    column("company_id", nullable=False),
                    column("doc_id", nullable=False, position=2),
                ],
                primary_key=["company_id", "doc_id"],
            ),
            table(
                "child",
                [
                    column("line_id", nullable=False),
                    column("company_id", position=2),
                    column("doc_id", position=3),
                ],
                primary_key=["line_id"],
                foreign_keys=[
                    foreign_key("child_parent_fk", "company_id", "parent", "company_id"),
                    foreign_key("child_parent_fk", "doc_id", "parent", "doc_id"),
                ],
            ),
        ]
    )

    declared = [
        r for r in _discover(meta).relationships if r.discovery_method == DiscoveryMethod.DECLARED
    ]

    assert len(declared) == 1
    assert declared[0].source_columns == ["company_id", "doc_id"]
    assert declared[0].target_columns == ["company_id", "doc_id"]
    assert any("composite key of 2 columns" in e for e in declared[0].evidence)


def test_duplicated_foreign_key_rows_are_deduplicated():
    # Some catalog queries emit a cartesian product for composite keys.
    # The same column pair repeated must not become extra relationships.
    meta = metadata(
        [
            table("parent", [column("parent_id", nullable=False)], primary_key=["parent_id"]),
            table(
                "child",
                [column("child_id", nullable=False), column("parent_id")],
                primary_key=["child_id"],
                foreign_keys=[
                    foreign_key("child_parent_fk", "parent_id", "parent", "parent_id"),
                    foreign_key("child_parent_fk", "parent_id", "parent", "parent_id"),
                ],
            ),
        ]
    )

    declared = [
        r for r in _discover(meta).relationships if r.discovery_method == DiscoveryMethod.DECLARED
    ]

    assert len(declared) == 1
    assert declared[0].source_columns == ["parent_id"]


def test_table_with_no_foreign_keys_yields_no_relationships():
    meta = metadata(
        [table("standalone", [column("id", nullable=False)], primary_key=["id"])]
    )

    graph = _discover(meta)

    assert graph.relationships == []
    assert graph.orphan_tables == ["app.standalone"]


def test_declared_relationship_suppresses_naming_candidate():
    # customer_id would also be found by naming inference; the declared
    # constraint must win, and only one relationship may be emitted.
    meta = metadata(
        [
            table("customer", [column("customer_id", nullable=False)], primary_key=["customer_id"]),
            table(
                "orders",
                [column("order_id", nullable=False), column("customer_id")],
                primary_key=["order_id"],
                foreign_keys=[
                    foreign_key("orders_customer_fk", "customer_id", "customer", "customer_id")
                ],
            ),
        ]
    )

    relationships = _discover(meta).relationships

    assert len(relationships) == 1
    assert relationships[0].discovery_method == DiscoveryMethod.DECLARED


def test_cross_schema_declared_foreign_key_is_honoured():
    meta = metadata(
        [
            table(
                "child",
                [column("child_id", nullable=False), column("parent_id")],
                primary_key=["child_id"],
                foreign_keys=[
                    foreign_key(
                        "x_fk", "parent_id", "parent", "parent_id", referenced_schema="other"
                    )
                ],
            )
        ]
    )

    relationships = _discover(meta).relationships

    assert len(relationships) == 1
    assert relationships[0].target_schema == "other"


# ---------------------------------------------------------
# Graph assembly
# ---------------------------------------------------------


def test_sample_schema_dependency_order_is_parents_first():
    graph = _discover(sample_metadata())
    order = graph.dependency_order

    assert order.index("app.country") < order.index("app.state")
    assert order.index("app.state") < order.index("app.city")
    assert order.index("app.city") < order.index("app.customer")
    assert order.index("app.customer") < order.index("app.orders")
    assert order.index("app.orders") < order.index("app.order_item")
    assert len(order) == graph.summary.tables_analyzed


def test_sample_schema_orphan_and_self_reference():
    graph = _discover(sample_metadata())

    assert graph.orphan_tables == ["app.audit_log"]
    assert graph.summary.self_referencing_count == 1
    # A self-referencing table is not an orphan and not a cycle.
    assert "app.employee" not in graph.orphan_tables
    assert graph.cycles == []


def test_self_referencing_relationship_is_typed_correctly():
    graph = _discover(sample_metadata())
    self_refs = [r for r in graph.relationships if r.is_self_referencing]

    assert len(self_refs) == 1
    assert self_refs[0].source_table == "employee"
    assert self_refs[0].relationship_type == RelationshipType.SELF_REFERENCING
    assert self_refs[0].is_optional is True


def test_true_cycle_is_reported_and_no_table_is_lost():
    meta = metadata(
        [
            table(
                "department",
                [column("department_id", nullable=False), column("manager_id")],
                primary_key=["department_id"],
                foreign_keys=[
                    foreign_key("dept_mgr_fk", "manager_id", "employee", "employee_id")
                ],
            ),
            table(
                "employee",
                [column("employee_id", nullable=False), column("department_id")],
                primary_key=["employee_id"],
                foreign_keys=[
                    foreign_key("emp_dept_fk", "department_id", "department", "department_id")
                ],
            ),
        ]
    )

    graph = _discover(meta)

    assert graph.cycles == [["app.department", "app.employee"]]
    assert graph.summary.cycle_count == 1
    assert sorted(graph.dependency_order) == ["app.department", "app.employee"]


def test_node_degrees_and_depth():
    graph = _discover(sample_metadata())
    nodes = {f"{n.schema_name}.{n.table_name}": n for n in graph.nodes}

    assert nodes["app.country"].depth == 0
    assert nodes["app.state"].depth == 1
    assert nodes["app.customer"].inbound_relationship_count == 1
    assert nodes["app.orders"].outbound_relationship_count == 1
    assert graph.summary.max_dependency_depth >= 4


def test_views_are_nodes_but_never_inference_targets():
    meta = metadata(
        [
            table(
                "customer_v",
                [column("customer_id", nullable=False)],
                primary_key=["customer_id"],
                table_type="VIEW",
            ),
            table(
                "orders",
                [column("order_id", nullable=False), column("customer_id")],
                primary_key=["order_id"],
            ),
        ]
    )

    graph = _discover(meta)

    assert graph.relationships == []
    assert {n.table_name for n in graph.nodes} == {"customer_v", "orders"}


def test_summary_counts_are_populated():
    graph = _discover(sample_metadata())
    summary = graph.summary

    assert summary.total_relationships == len(graph.relationships)
    assert summary.declared_count == 9
    assert summary.derived_count == 1  # product <-> promotion
    assert summary.junction_table_count == 1
    assert summary.tables_analyzed == 11
    assert summary.columns_analyzed > 0
    assert summary.orphan_table_count == 1


def test_output_is_deterministic_across_runs():
    meta = sample_metadata()

    first = RelationshipEngine(meta).discover().model_dump_json()
    second = RelationshipEngine(sample_metadata()).discover().model_dump_json()

    assert first == second


def test_relationship_ids_are_stable_and_readable():
    graph = _discover(sample_metadata())
    ids = {r.id for r in graph.relationships}

    assert "app.city(state_id)->app.state(state_id)" in ids


def test_engine_runs_without_a_profile():
    graph = _discover(sample_metadata(), None)

    assert graph.summary.declared_count == 9
    assert graph.dependency_order
