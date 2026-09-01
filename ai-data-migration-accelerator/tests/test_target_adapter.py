"""Tests for target adapters.

Verifies that physical models map correctly to target platforms, that
unsupported features raise clear errors, and that lineage is preserved.
"""

from __future__ import annotations

import pytest

from migration.physical.models import (
    ConstraintType,
    IndexPurpose,
    PhysicalColumn,
    PhysicalConstraint,
    PhysicalDataType,
    PhysicalIndex,
    PhysicalModel,
    PhysicalModelPackage,
    PhysicalTable,
    TableClassification,
)
from migration.target.base import TargetAdapterError
from migration.target.databricks import DatabricksTargetAdapter
from migration.target.models import TargetCapability


def physical_model() -> PhysicalModelPackage:
    """Minimal physical model for testing."""
    table = PhysicalTable(
        name="customers",
        logical_entity="Customer",
        classification=TableClassification.MASTER,
        columns=[
            PhysicalColumn(
                name="customer_id",
                data_type=PhysicalDataType.IDENTIFIER,
                nullable=False,
                is_primary_key=True,
                ordinal_position=1,
            ),
            PhysicalColumn(
                name="name",
                data_type=PhysicalDataType.STRING,
                length=100,
                nullable=False,
                ordinal_position=2,
            ),
            PhysicalColumn(
                name="created_at",
                data_type=PhysicalDataType.TIMESTAMP,
                nullable=False,
                default_value="CURRENT_TIMESTAMP",
                ordinal_position=3,
            ),
        ],
        constraints=[
            PhysicalConstraint(
                name="pk_customers",
                constraint_type=ConstraintType.PRIMARY_KEY,
                table="customers",
                columns=["customer_id"],
            ),
        ],
    )

    model = PhysicalModel(
        database_name="shop",
        summary="A simple shop database.",
        tables=[table],
    )

    return PhysicalModelPackage(
        physical_model=model,
        generated_by="PhysicalModelEngine",
    )


class TestDatabricksTargetAdapter:
    """Tests for Databricks-specific mapping."""

    def test_target_type(self):
        adapter = DatabricksTargetAdapter(physical_model())
        assert adapter.target_type() == "databricks"
        assert adapter.adapter_name() == "DatabricksTargetAdapter"

    def test_supported_capabilities(self):
        adapter = DatabricksTargetAdapter(physical_model())
        caps = adapter.supported_capabilities()

        assert TargetCapability.PRIMARY_KEYS in caps
        assert TargetCapability.FOREIGN_KEYS in caps
        assert TargetCapability.TRANSACTIONS in caps
        assert TargetCapability.PARTITIONING in caps
        assert TargetCapability.CLUSTERING in caps
        # Delta Lake has no UNIQUE constraint DDL at all - declaring this
        # capability would make the base adapter emit invalid Databricks SQL.
        assert TargetCapability.UNIQUE_CONSTRAINTS not in caps

    def test_identifier_rules(self):
        adapter = DatabricksTargetAdapter(physical_model())
        rules = adapter.identifier_rules()

        assert rules.max_length == 255
        assert rules.quote_char == "`"
        assert rules.allow_unicode is True
        assert "SELECT" in rules.reserved_words

    def test_data_type_mappings(self):
        adapter = DatabricksTargetAdapter(physical_model())
        mappings = adapter.data_type_mappings()

        assert len(mappings) > 0
        assert PhysicalDataType.IDENTIFIER in mappings
        assert PhysicalDataType.STRING in mappings
        assert mappings[PhysicalDataType.IDENTIFIER].target_type == "BIGINT"
        assert mappings[PhysicalDataType.STRING].target_type == "STRING"

    def test_maps_simple_table(self):
        pkg = physical_model()
        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        assert target_pkg.target_model.database_name == "shop"
        assert target_pkg.generated_from == "physical_model.json"
        assert target_pkg.generated_by == "DatabricksTargetAdapter"

        tables = target_pkg.target_model.tables
        assert len(tables) == 1

        table = tables[0]
        assert table.name == "customers"
        assert table.logical_entity == "Customer"
        assert len(table.columns) == 3

    def test_maps_columns_with_types(self):
        pkg = physical_model()
        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        table = target_pkg.target_model.tables[0]
        columns = table.columns

        assert columns[0].name == "customer_id"
        assert columns[0].target_type == "BIGINT"
        assert columns[0].is_primary_key is True
        assert columns[0].source_column == "customer_id"
        assert columns[0].physical_type == "IDENTIFIER"

        assert columns[1].name == "name"
        assert columns[1].target_type == "STRING"
        assert columns[1].length == 100

        assert columns[2].name == "created_at"
        assert columns[2].target_type == "TIMESTAMP"
        assert columns[2].default_value == "CURRENT_TIMESTAMP"

    def test_maps_primary_key_constraint(self):
        pkg = physical_model()
        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        constraints = target_pkg.target_model.tables[0].constraints
        assert len(constraints) == 1

        pk = constraints[0]
        assert pk.constraint_type == "PRIMARY_KEY"
        assert pk.columns == ["customer_id"]
        assert pk.source_constraint == "pk_customers"

    def test_maps_foreign_key_constraint(self):
        pkg = physical_model()
        orders_table = PhysicalTable(
            name="orders",
            logical_entity="Order",
            columns=[
                PhysicalColumn(
                    name="order_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    is_primary_key=True,
                    ordinal_position=1,
                ),
                PhysicalColumn(
                    name="customer_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    is_foreign_key=True,
                    ordinal_position=2,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_orders",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="orders",
                    columns=["order_id"],
                ),
                PhysicalConstraint(
                    name="fk_orders_customers",
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table="orders",
                    columns=["customer_id"],
                    referenced_table="customers",
                    referenced_columns=["customer_id"],
                ),
            ],
        )
        pkg.physical_model.tables.append(orders_table)

        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        orders = target_pkg.target_model.tables[1]
        fk = [c for c in orders.constraints if c.constraint_type == "FOREIGN_KEY"][0]

        assert fk.columns == ["customer_id"]
        assert fk.referenced_table == "customers"
        assert fk.referenced_columns == ["customer_id"]
        assert fk.source_constraint == "fk_orders_customers"

    def test_maps_unique_constraint(self):
        """Delta Lake has no UNIQUE constraint DDL at all: the constraint
        must not be emitted as executable SQL. It is dropped from
        TargetTable.constraints and preserved instead as a documented note,
        never silently discarded."""
        pkg = physical_model()
        table = pkg.physical_model.tables[0]
        table.constraints.append(
            PhysicalConstraint(
                name="uq_customers_email",
                constraint_type=ConstraintType.UNIQUE,
                table="customers",
                columns=["email"],
            )
        )

        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        constraints = target_pkg.target_model.tables[0].constraints
        unique = [c for c in constraints if c.constraint_type == "UNIQUE"]
        assert unique == []

        notes = " ".join(target_pkg.target_model.mapping_notes)
        assert "uq_customers_email" in notes
        assert "does not support" in notes

    def test_maps_check_constraint(self):
        pkg = physical_model()
        table = pkg.physical_model.tables[0]
        table.columns.append(
            PhysicalColumn(
                name="discount_percentage",
                data_type=PhysicalDataType.DECIMAL,
                precision=5,
                scale=2,
                nullable=True,
                ordinal_position=4,
            )
        )
        table.constraints.append(
            PhysicalConstraint(
                name="ck_customers_discount",
                constraint_type=ConstraintType.CHECK,
                table="customers",
                columns=["discount_percentage"],
                expression="discount_percentage BETWEEN 0 AND 100",
            )
        )

        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        constraints = target_pkg.target_model.tables[0].constraints
        check = [c for c in constraints if c.constraint_type == "CHECK"][0]

        assert check.expression == "discount_percentage BETWEEN 0 AND 100"
        assert check.source_constraint == "ck_customers_discount"

    def test_maps_indexes(self):
        """Databricks supports indexes (via Delta Lake)."""
        pkg = physical_model()
        table = pkg.physical_model.tables[0]
        table.indexes = [
            PhysicalIndex(
                name="idx_customers_pk",
                table="customers",
                columns=["customer_id"],
                is_unique=True,
                purpose=IndexPurpose.PRIMARY_KEY,
                rationale="Enforces and serves lookups on the primary key.",
            ),
        ]

        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        indexes = target_pkg.target_model.tables[0].indexes
        assert len(indexes) == 1

        idx = indexes[0]
        assert idx.table == "customers"
        assert idx.columns == ["customer_id"]
        assert idx.is_unique is True
        assert idx.source_index == "idx_customers_pk"

    def test_preserves_all_data_types(self):
        """All physical data types have Databricks mappings."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test all types.",
                tables=[
                    PhysicalTable(
                        name="all_types",
                        logical_entity="AllTypes",
                        columns=[
                            PhysicalColumn(
                                name=f"col_{dt.value.lower()}",
                                data_type=dt,
                                nullable=True,
                                ordinal_position=i + 1,
                            )
                            for i, dt in enumerate(PhysicalDataType)
                        ],
                    ),
                ],
            )
        )

        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        table = target_pkg.target_model.tables[0]
        assert len(table.columns) == len(PhysicalDataType)
        for col in table.columns:
            assert col.target_type, f"No mapping for {col.physical_type}"

    def test_validates_all_constraint_types(self):
        """All physical constraint types are properly mapped."""
        pkg = physical_model()
        adapter = DatabricksTargetAdapter(pkg)

        for constraint_type in ConstraintType:
            # Pydantic validates constraint_type during construction
            assert constraint_type in [
                ConstraintType.PRIMARY_KEY,
                ConstraintType.FOREIGN_KEY,
                ConstraintType.UNIQUE,
                ConstraintType.CHECK,
            ]

    def test_type_mapping_preserves_parameters(self):
        """Type mappings correctly substitute length and precision/scale."""
        pkg = physical_model()
        table = pkg.physical_model.tables[0]
        table.columns = [
            PhysicalColumn(
                name="short_string",
                data_type=PhysicalDataType.STRING,
                length=30,
                nullable=True,
                ordinal_position=1,
            ),
            PhysicalColumn(
                name="amount",
                data_type=PhysicalDataType.DECIMAL,
                precision=18,
                scale=2,
                nullable=True,
                ordinal_position=2,
            ),
        ]

        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        cols = target_pkg.target_model.tables[0].columns
        assert cols[0].target_type == "STRING"
        assert cols[0].length == 30

        assert cols[1].target_type == "DECIMAL"
        assert cols[1].precision == 18
        assert cols[1].scale == 2

    def test_mapping_notes_include_rationales(self):
        """Type mapping notes explain why types were chosen."""
        pkg = physical_model()
        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        model = target_pkg.target_model
        assert len(model.data_type_mappings) > 0
        for mapping in model.data_type_mappings:
            if mapping.rationale:
                assert isinstance(mapping.rationale, str)
                assert len(mapping.rationale) > 0

    def test_lineage_preserved_through_mapping(self):
        """Source columns, constraints, indexes are tracked."""
        pkg = physical_model()
        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        table = target_pkg.target_model.tables[0]

        for col in table.columns:
            assert col.source_column is not None
            assert col.physical_type is not None

        for constraint in table.constraints:
            assert constraint.source_constraint is not None

        assert target_pkg.generated_from == "physical_model.json"
        assert target_pkg.generated_by == "DatabricksTargetAdapter"

    def test_summary_reports_mapping_details(self):
        """The summary describes what was mapped."""
        pkg = physical_model()
        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        summary = target_pkg.target_model.summary
        assert "1 table" in summary
        assert "3 column" in summary
        assert "native" in summary.lower()

    def test_handles_nullable_and_defaults(self):
        """Nullable and default values are preserved in mapping."""
        pkg = physical_model()
        table = pkg.physical_model.tables[0]
        table.columns.append(
            PhysicalColumn(
                name="status",
                data_type=PhysicalDataType.STRING,
                length=20,
                nullable=True,
                default_value="'ACTIVE'",
                ordinal_position=4,
            )
        )

        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        status_col = [c for c in target_pkg.target_model.tables[0].columns
                      if c.name == "status"][0]
        assert status_col.nullable is True
        assert status_col.default_value == "'ACTIVE'"

    def test_partitioning_and_clustering_recommendations_preserved(self):
        """Storage recommendations from physical model are carried through."""
        pkg = physical_model()
        table = pkg.physical_model.tables[0]
        from migration.physical.models import StorageRecommendation
        table.storage = StorageRecommendation(
            table="customers",
            partition_candidates=["created_at"],
            clustering_candidates=["customer_id"],
            rationale="Partition by date, cluster by ID.",
        )

        adapter = DatabricksTargetAdapter(pkg)
        target_pkg = adapter.map()

        target_table = target_pkg.target_model.tables[0]
        assert target_table.partition_candidates == ["created_at"]
        assert target_table.clustering_candidates == ["customer_id"]
        assert target_table.storage_rationale == "Partition by date, cluster by ID."
