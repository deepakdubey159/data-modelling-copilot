"""Tests for cardinality classification and junction (bridge) table detection."""

from __future__ import annotations

from migration.relationship import rules
from migration.relationship.engine import RelationshipEngine
from migration.relationship.models import (
    Cardinality,
    CardinalitySource,
    DiscoveryMethod,
    RelationshipType,
)
from tests.relationship_fixtures import (
    column,
    column_profile,
    foreign_key,
    metadata,
    profile,
    sample_metadata,
    table,
    table_profile,
)


def _discover(meta, prof=None):
    return RelationshipEngine(meta, prof).discover().relationships


def _by_source_column(graph, table_name: str, column_name: str):
    for relationship in graph.relationships:
        if relationship.source_table == table_name and relationship.source_columns == [
            column_name
        ]:
            return relationship
    raise AssertionError(f"no relationship found for {table_name}.{column_name}")


# ---------------------------------------------------------
# Cardinality
# ---------------------------------------------------------


def test_full_primary_key_foreign_key_is_one_to_one():
    meta = metadata(
        [
            table("person", [column("person_id", nullable=False)], primary_key=["person_id"]),
            table(
                "passport",
                [column("person_id", nullable=False)],
                primary_key=["person_id"],
                foreign_keys=[foreign_key("pp_fk", "person_id", "person", "person_id")],
            ),
        ]
    )

    relationship = _by_source_column(_discover(meta), "passport", "person_id")

    assert relationship.cardinality == Cardinality.ONE_TO_ONE
    assert relationship.cardinality_source == CardinalitySource.STRUCTURAL
    assert relationship.relationship_type == RelationshipType.IDENTIFYING
    assert relationship.is_identifying is True
    assert any("complete primary key" in e for e in relationship.evidence)


def test_partial_primary_key_foreign_key_is_many_to_one_identifying():
    graph = _discover(sample_metadata())
    relationship = _by_source_column(graph, "order_item", "order_id")

    assert relationship.cardinality == Cardinality.MANY_TO_ONE
    assert relationship.relationship_type == RelationshipType.IDENTIFYING
    assert any("proper subset of the primary key" in e for e in relationship.evidence)


def test_non_key_foreign_key_is_many_to_one_non_identifying():
    graph = _discover(sample_metadata())
    relationship = _by_source_column(graph, "order_item", "product_id")

    assert relationship.cardinality == Cardinality.MANY_TO_ONE
    assert relationship.relationship_type == RelationshipType.NON_IDENTIFYING
    assert relationship.is_identifying is False


def test_self_reference_wins_over_identifying_classification():
    graph = _discover(sample_metadata())
    relationship = _by_source_column(graph, "employee", "manager_id")

    assert relationship.relationship_type == RelationshipType.SELF_REFERENCING
    assert relationship.is_self_referencing is True
    assert relationship.cardinality == Cardinality.MANY_TO_ONE


def test_nullable_foreign_key_is_optional():
    graph = _discover(sample_metadata())

    assert _by_source_column(graph, "employee", "manager_id").is_optional is True
    assert _by_source_column(graph, "order_item", "order_id").is_optional is False


def test_observed_one_to_one_requires_enough_rows():
    """Ten rows with ten distinct values must not manufacture a 1:1 claim."""
    meta = metadata(
        [
            table("customer", [column("customer_id", nullable=False)], primary_key=["customer_id"]),
            table(
                "profile_row",
                [column("profile_id", nullable=False), column("customer_id", nullable=False)],
                primary_key=["profile_id"],
                foreign_keys=[
                    foreign_key("pr_fk", "customer_id", "customer", "customer_id")
                ],
            ),
        ]
    )
    small = profile(
        [
            table_profile("customer", 10, [column_profile("customer_id", distinct_count=10)]),
            table_profile(
                "profile_row",
                10,
                [
                    column_profile("profile_id", distinct_count=10),
                    column_profile("customer_id", distinct_count=10),
                ],
            ),
        ]
    )

    relationship = _by_source_column(_discover(meta, small), "profile_row", "customer_id")

    assert relationship.cardinality == Cardinality.MANY_TO_ONE
    assert relationship.cardinality_source == CardinalitySource.STRUCTURAL


def test_observed_one_to_one_is_reported_when_data_supports_it():
    meta = metadata(
        [
            table("customer", [column("customer_id", nullable=False)], primary_key=["customer_id"]),
            table(
                "profile_row",
                [column("profile_id", nullable=False), column("customer_id", nullable=False)],
                primary_key=["profile_id"],
                foreign_keys=[
                    foreign_key("pr_fk", "customer_id", "customer", "customer_id")
                ],
            ),
        ]
    )
    large = profile(
        [
            table_profile("customer", 5000, [column_profile("customer_id", distinct_count=5000)]),
            table_profile(
                "profile_row",
                5000,
                [
                    column_profile("profile_id", distinct_count=5000),
                    column_profile("customer_id", distinct_count=5000, null_count=0),
                ],
            ),
        ]
    )

    relationship = _by_source_column(_discover(meta, large), "profile_row", "customer_id")

    assert relationship.cardinality == Cardinality.ONE_TO_ONE
    # Observation is never presented as a guarantee.
    assert relationship.cardinality_source == CardinalitySource.OBSERVED
    assert any("not enforced" in e for e in relationship.evidence)


def test_observed_cardinality_threshold_is_the_documented_constant():
    assert rules.MIN_ROWS_FOR_OBSERVED_CARDINALITY == 100


# ---------------------------------------------------------
# Junction tables
# ---------------------------------------------------------


def test_pure_junction_table_is_detected():
    graph = _discover(sample_metadata())

    assert len(graph.junction_tables) == 1
    junction = graph.junction_tables[0]
    assert junction.table_name == "product_promotion"
    assert junction.connected_tables == ["app.product", "app.promotion"]
    assert junction.key_columns == ["product_id", "promotion_id"]
    assert junction.payload_columns == []
    assert junction.is_pure is True


def test_junction_with_payload_is_an_associative_entity():
    meta = metadata(
        [
            table("product", [column("product_id", nullable=False)], primary_key=["product_id"]),
            table(
                "warehouse", [column("warehouse_id", nullable=False)], primary_key=["warehouse_id"]
            ),
            table(
                "inventory",
                [
                    column("warehouse_id", nullable=False),
                    column("product_id", nullable=False, position=2),
                    column("quantity", position=3),
                ],
                primary_key=["warehouse_id", "product_id"],
                foreign_keys=[
                    foreign_key("inv_wh_fk", "warehouse_id", "warehouse", "warehouse_id"),
                    foreign_key("inv_pr_fk", "product_id", "product", "product_id"),
                ],
            ),
        ]
    )

    graph = _discover(meta)

    assert len(graph.junction_tables) == 1
    junction = graph.junction_tables[0]
    assert junction.is_pure is False
    assert junction.payload_columns == ["quantity"]


def test_dependent_entity_is_not_a_junction():
    """order_item has a composite primary key, but line_number is not a
    foreign key — so it is a weak entity, not a bridge table."""
    graph = _discover(sample_metadata())

    assert "order_item" not in {j.table_name for j in graph.junction_tables}


def test_composite_key_referencing_one_table_is_not_a_junction():
    meta = metadata(
        [
            table(
                "parent",
                [
                    column("a", nullable=False),
                    column("b", nullable=False, position=2),
                ],
                primary_key=["a", "b"],
            ),
            table(
                "child",
                [column("a", nullable=False), column("b", nullable=False, position=2)],
                primary_key=["a", "b"],
                foreign_keys=[
                    foreign_key("c_fk", "a", "parent", "a"),
                    foreign_key("c_fk", "b", "parent", "b"),
                ],
            ),
        ]
    )

    assert _discover(meta).junction_tables == []


def test_many_to_many_is_derived_from_junction():
    graph = _discover(sample_metadata())
    derived = [
        r for r in graph.relationships if r.discovery_method == DiscoveryMethod.DERIVED_JUNCTION
    ]

    assert len(derived) == 1
    relationship = derived[0]
    assert relationship.cardinality == Cardinality.MANY_TO_MANY
    assert relationship.relationship_type == RelationshipType.MANY_TO_MANY_LOGICAL
    assert {relationship.source_table, relationship.target_table} == {"product", "promotion"}
    assert any("derived from junction table" in e for e in relationship.evidence)
    assert "<->" in relationship.id


def test_derived_relationships_do_not_affect_dependency_order():
    """A logical many-to-many must not create an ordering constraint between
    two parents that have no direct dependency."""
    graph = _discover(sample_metadata())

    # product and promotion are independent; both must sit at depth 0.
    depths = {f"{n.schema_name}.{n.table_name}": n.depth for n in graph.nodes}
    assert depths["app.product"] == 0
    assert depths["app.promotion"] == 0
