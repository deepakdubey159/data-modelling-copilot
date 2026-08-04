"""Tests for naming-based inference and profile-based scoring.

Covers the rules module directly, plus the engine's inference phase.
"""

from __future__ import annotations

from migration.relationship import rules
from migration.relationship.engine import RelationshipEngine
from migration.relationship.models import ConfidenceBand, DiscoveryMethod
from tests.relationship_fixtures import (
    column,
    column_profile,
    metadata,
    profile,
    table,
    table_profile,
)


def _inferred(meta, prof=None):
    graph = RelationshipEngine(meta, prof).discover().relationships
    return [
        r
        for r in graph.relationships
        if r.discovery_method
        in (DiscoveryMethod.INFERRED_NAMING, DiscoveryMethod.INFERRED_PROFILE)
    ]


def _two_tables(source_column: str, source_type: str = "integer", target_type: str = "integer"):
    """A `customer` table plus an `orders` table holding one loose column."""
    return metadata(
        [
            table(
                "customer",
                [column("customer_id", target_type, nullable=False)],
                primary_key=["customer_id"],
            ),
            table(
                "orders",
                [column("order_id", nullable=False), column(source_column, source_type)],
                primary_key=["order_id"],
            ),
        ]
    )


# ---------------------------------------------------------
# rules module
# ---------------------------------------------------------


def test_normalize_identifier_handles_case_and_separators():
    assert rules.normalize_identifier("CustomerID") == "customerid"
    assert rules.normalize_identifier("CUSTOMER_ID") == "customer_id"
    assert rules.normalize_identifier("  customer id  ") == "customer_id"


def test_name_variants_cover_plural_and_singular():
    assert "orders" in rules.name_variants("order")
    assert "order" in rules.name_variants("orders")
    assert "categories" in rules.name_variants("category")
    assert "category" in rules.name_variants("categories")


def test_entity_candidates_strip_id_suffixes():
    assert rules.entity_candidates("customer_id")[0][:2] == ("customer", "N2")
    assert rules.entity_candidates("customerid")[0][:2] == ("customer", "N3")
    assert rules.entity_candidates("description") == []


def test_type_class_orders_temporal_before_integer():
    # "interval" contains "int"; the ordering in _TYPE_CLASS_KEYWORDS matters.
    assert rules.type_class("interval") == "TEMPORAL"
    assert rules.type_class("bigint") == "INTEGER"
    assert rules.type_class("timestamp without time zone") == "TEMPORAL"
    assert rules.type_class("character varying") == "TEXT"
    assert rules.type_class("uuid") == "UUID"


def test_integer_and_numeric_are_cross_compatible():
    assert rules.types_compatible("integer", "numeric") is True
    assert rules.types_compatible("text", "integer") is False
    # Unrecognized types are not treated as evidence against a relationship.
    assert rules.types_compatible("weird_custom_type", "integer") is True


def test_confidence_bands():
    assert rules.confidence_band(1.0) == ConfidenceBand.CERTAIN
    assert rules.confidence_band(0.9) == ConfidenceBand.HIGH
    assert rules.confidence_band(0.75) == ConfidenceBand.MEDIUM
    assert rules.confidence_band(0.61) == ConfidenceBand.LOW


# ---------------------------------------------------------
# Naming inference
# ---------------------------------------------------------


def test_exact_primary_key_name_match_is_inferred():
    inferred = _inferred(_two_tables("customer_id"))

    assert len(inferred) == 1
    assert inferred[0].source_table == "orders"
    assert inferred[0].target_table == "customer"
    assert any("naming rule N1" in e for e in inferred[0].evidence)
    assert any("no declared foreign key constraint" in e for e in inferred[0].evidence)


def test_plural_table_name_resolves_from_singular_column():
    meta = metadata(
        [
            table("orders", [column("order_id", nullable=False)], primary_key=["order_id"]),
            table(
                "payment",
                [column("payment_id", nullable=False), column("order_id")],
                primary_key=["payment_id"],
            ),
        ]
    )

    inferred = _inferred(meta)

    assert len(inferred) == 1
    assert inferred[0].target_table == "orders"


def test_no_separator_variant_is_inferred():
    meta = metadata(
        [
            table("customer", [column("cust_key", nullable=False)], primary_key=["cust_key"]),
            table(
                "orders",
                [column("order_id", nullable=False), column("customerid")],
                primary_key=["order_id"],
            ),
        ]
    )

    inferred = _inferred(meta)

    assert len(inferred) == 1
    assert any("naming rule N3" in e for e in inferred[0].evidence)


def test_type_mismatch_is_rejected():
    assert _inferred(_two_tables("customer_id", source_type="text")) == []


def test_composite_primary_key_target_is_rejected():
    # A lone column cannot responsibly be matched to part of a composite key.
    meta = metadata(
        [
            table(
                "customer",
                [
                    column("customer_id", nullable=False),
                    column("region_id", nullable=False, position=2),
                ],
                primary_key=["customer_id", "region_id"],
            ),
            table(
                "orders",
                [column("order_id", nullable=False), column("customer_id")],
                primary_key=["order_id"],
            ),
        ]
    )

    assert _inferred(meta) == []


def test_table_without_primary_key_is_not_a_target():
    meta = metadata(
        [
            table("customer", [column("customer_id", nullable=False)]),
            table(
                "orders",
                [column("order_id", nullable=False), column("customer_id")],
                primary_key=["order_id"],
            ),
        ]
    )

    assert _inferred(meta) == []


def test_degenerate_self_match_is_rejected():
    # customer.customer_id must not be inferred as pointing at customer.
    meta = metadata(
        [table("customer", [column("customer_id", nullable=False)], primary_key=["customer_id"])]
    )

    assert _inferred(meta) == []


def test_inference_does_not_cross_schema_boundaries():
    from migration.canonical.models import DatabaseMetadata, SchemaMetadata

    meta = DatabaseMetadata(
        database_name="testdb",
        source_database_type="postgres",
        schemas=[
            SchemaMetadata(
                schema_name="bronze",
                tables=[
                    table(
                        "customer",
                        [column("customer_id", nullable=False)],
                        primary_key=["customer_id"],
                    )
                ],
            ),
            SchemaMetadata(
                schema_name="silver",
                tables=[
                    table(
                        "orders",
                        [column("order_id", nullable=False), column("customer_id")],
                        primary_key=["order_id"],
                    )
                ],
            ),
        ],
    )

    assert _inferred(meta) == []


# ---------------------------------------------------------
# Profile scoring
# ---------------------------------------------------------


def _profile_for(source_distinct: int, target_distinct: int, **kwargs):
    return profile(
        [
            table_profile(
                "customer",
                kwargs.get("target_rows", 500),
                [
                    column_profile(
                        "customer_id",
                        distinct_count=target_distinct,
                        min_value=kwargs.get("target_min", "1"),
                        max_value=kwargs.get("target_max", "500"),
                    )
                ],
            ),
            table_profile(
                "orders",
                kwargs.get("source_rows", 800),
                [
                    column_profile(
                        "customer_id",
                        distinct_count=source_distinct,
                        min_value=kwargs.get("source_min", "1"),
                        max_value=kwargs.get("source_max", "500"),
                    )
                ],
            ),
        ]
    )


def test_distinct_inclusion_violation_is_a_hard_reject():
    # 900 distinct child values cannot fit into 500 distinct parent keys.
    meta = _two_tables("customer_id")
    prof = _profile_for(source_distinct=900, target_distinct=500)

    assert _inferred(meta, prof) == []


def test_distinct_inclusion_holding_raises_confidence():
    meta = _two_tables("customer_id")

    without = _inferred(meta)[0]
    with_profile = _inferred(meta, _profile_for(source_distinct=400, target_distinct=500))[0]

    assert with_profile.confidence > without.confidence
    assert with_profile.discovery_method == DiscoveryMethod.INFERRED_PROFILE
    assert any("distinct value inclusion holds" in e for e in with_profile.evidence)


def test_numeric_ranges_are_compared_numerically_not_lexicographically():
    # Child range [1, 9], parent range [1, 10]. Compared as text, "9" > "10"
    # and this would be a false violation.
    meta = _two_tables("customer_id")
    prof = _profile_for(
        source_distinct=9,
        target_distinct=10,
        source_min="1",
        source_max="9",
        target_min="1",
        target_max="10",
    )

    inferred = _inferred(meta, prof)

    assert len(inferred) == 1
    assert any("range containment holds" in e for e in inferred[0].evidence)


def test_range_violation_penalises_but_does_not_hard_reject():
    meta = _two_tables("customer_id")
    prof = _profile_for(
        source_distinct=10,
        target_distinct=500,
        source_min="1",
        source_max="99999",
        target_min="1",
        target_max="500",
    )

    inferred = _inferred(meta, prof)

    assert len(inferred) == 1
    assert any("range containment violated" in e for e in inferred[0].evidence)
    assert inferred[0].confidence < 0.95


def test_unparseable_extremes_skip_the_range_signal():
    meta = _two_tables("customer_id")
    prof = _profile_for(
        source_distinct=10,
        target_distinct=500,
        source_min="not-a-number",
        source_max="also-not",
        target_min="1",
        target_max="500",
    )

    inferred = _inferred(meta, prof)

    assert len(inferred) == 1
    assert any("range containment skipped" in e for e in inferred[0].evidence)


def test_empty_tables_yield_no_corroborating_evidence():
    meta = _two_tables("customer_id")
    prof = _profile_for(source_distinct=0, target_distinct=0, source_rows=0, target_rows=0)

    inferred = _inferred(meta, prof)

    assert len(inferred) == 1
    assert any("no data to corroborate" in e for e in inferred[0].evidence)


def test_missing_column_profile_is_handled():
    meta = _two_tables("customer_id")
    prof = profile([table_profile("customer", 500, [])])

    inferred = _inferred(meta, prof)

    assert len(inferred) == 1
    assert any("no profile statistics" in e for e in inferred[0].evidence)


def test_pattern_agreement_adds_confidence():
    meta = _two_tables("customer_id", source_type="uuid", target_type="uuid")
    prof = profile(
        [
            table_profile(
                "customer",
                500,
                [
                    column_profile(
                        "customer_id",
                        data_type="uuid",
                        distinct_count=500,
                        detected_pattern="uuid",
                    )
                ],
            ),
            table_profile(
                "orders",
                800,
                [
                    column_profile(
                        "customer_id",
                        data_type="uuid",
                        distinct_count=400,
                        detected_pattern="uuid",
                    )
                ],
            ),
        ]
    )

    inferred = _inferred(meta, prof)

    assert len(inferred) == 1
    assert any("format pattern agreement" in e for e in inferred[0].evidence)


def test_candidate_below_threshold_is_dropped(monkeypatch):
    monkeypatch.setattr(rules, "MIN_INFERENCE_CONFIDENCE", 0.99)

    assert _inferred(_two_tables("customer_id")) == []


def test_confidence_never_exceeds_one():
    meta = _two_tables("customer_id")
    prof = _profile_for(source_distinct=400, target_distinct=500)

    assert _inferred(meta, prof)[0].confidence <= 1.0
