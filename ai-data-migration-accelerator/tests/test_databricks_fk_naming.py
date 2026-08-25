"""Tests for Databricks foreign key constraint naming.

Reproduces the production failure: a physical-model FK constraint name is
built generically (table + column) and truncated to a conservative
30-character, multi-platform limit by dropping trailing words. When a long
table name (e.g. an M:N junction table) carries two FKs, both names can
truncate down to the same prefix - the column name that distinguished them
is exactly what gets dropped. `DatabricksTargetAdapter` must rename every FK
deterministically from (table, referenced_table, column(s)) - unique by
construction - and never drop, merge, or skip an FK to avoid a collision.
"""

from __future__ import annotations

import re

import pytest

from migration.physical.models import (
    ConstraintType,
    PhysicalColumn,
    PhysicalConstraint,
    PhysicalDataType,
    PhysicalModel,
    PhysicalModelPackage,
    PhysicalTable,
)
from migration.target.databricks import DatabricksTargetAdapter
from migration.conceptual.models import ConceptualModel, ConceptualModelPackage
from migration.logical.engine import LogicalModelEngine
from migration.physical.engine import PhysicalModelEngine


def _junction_table_package() -> PhysicalModelPackage:
    """Reproduces the exact failure: a long-named M:N junction table
    ("product_promotion_association", 29 chars) whose two FK constraint
    names - built generically as fk_{table}_{column} and truncated to 30
    chars by dropping trailing words - both collapse to
    "fk_product_promotion" once the column suffix is dropped."""

    # Referenced tables must exist and have matching PK constraints
    product_table = PhysicalTable(
        name="product",
        logical_entity="Product",
        columns=[
            PhysicalColumn(
                name="product_id",
                data_type=PhysicalDataType.IDENTIFIER,
                nullable=False,
                is_primary_key=True,
                ordinal_position=1,
            ),
        ],
        constraints=[
            PhysicalConstraint(
                name="pk_product",
                constraint_type=ConstraintType.PRIMARY_KEY,
                table="product",
                columns=["product_id"],
            ),
        ],
    )

    promotion_table = PhysicalTable(
        name="promotion",
        logical_entity="Promotion",
        columns=[
            PhysicalColumn(
                name="promotion_id",
                data_type=PhysicalDataType.IDENTIFIER,
                nullable=False,
                is_primary_key=True,
                ordinal_position=1,
            ),
        ],
        constraints=[
            PhysicalConstraint(
                name="pk_promotion",
                constraint_type=ConstraintType.PRIMARY_KEY,
                table="promotion",
                columns=["promotion_id"],
            ),
        ],
    )

    table_name = "product_promotion_association"
    junction_table = PhysicalTable(
        name=table_name,
        logical_entity="Product Promotion Association",
        columns=[
            PhysicalColumn(
                name="product_id",
                data_type=PhysicalDataType.IDENTIFIER,
                nullable=False,
                is_primary_key=True,
                is_foreign_key=True,
                ordinal_position=1,
            ),
            PhysicalColumn(
                name="promotion_id",
                data_type=PhysicalDataType.IDENTIFIER,
                nullable=False,
                is_primary_key=True,
                is_foreign_key=True,
                ordinal_position=2,
            ),
        ],
        constraints=[
            PhysicalConstraint(
                name="pk_product_promotion_association",
                constraint_type=ConstraintType.PRIMARY_KEY,
                table=table_name,
                columns=["product_id", "promotion_id"],
            ),
            # Both names collide once truncated to 30 chars by the generic
            # physical-model naming convention - this is the exact bug.
            PhysicalConstraint(
                name="fk_product_promotion",  # Truncated: was fk_..._product_id
                constraint_type=ConstraintType.FOREIGN_KEY,
                table=table_name,
                columns=["product_id"],
                referenced_table="product",
                referenced_columns=["product_id"],
            ),
            PhysicalConstraint(
                name="fk_product_promotion",  # Truncated: was fk_..._promotion_id
                constraint_type=ConstraintType.FOREIGN_KEY,
                table=table_name,
                columns=["promotion_id"],
                referenced_table="promotion",
                referenced_columns=["promotion_id"],
            ),
        ],
    )

    model = PhysicalModel(
        database_name="shop",
        summary="A shop database with a product/promotion junction table.",
        tables=[product_table, promotion_table, junction_table],
    )
    return PhysicalModelPackage(physical_model=model, generated_by="PhysicalModelEngine")


class TestFKConstraintNamingCollisionFix:
    def test_both_foreign_keys_survive_the_rename(self):
        """Neither FK is dropped, merged, or skipped just because their
        physical-model names collided."""
        pkg = _junction_table_package()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        # Find the junction table (product_promotion_association)
        table = next(t for t in target_pkg.target_model.tables if t.name == "product_promotion_association")
        fks = [c for c in table.constraints if c.constraint_type == "FOREIGN_KEY"]
        assert len(fks) == 2

        referenced = {fk.referenced_table for fk in fks}
        assert referenced == {"product", "promotion"}

    def test_renamed_foreign_keys_are_unique(self):
        pkg = _junction_table_package()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        table = target_pkg.target_model.tables[0]
        fks = [c for c in table.constraints if c.constraint_type == "FOREIGN_KEY"]
        names = [fk.name for fk in fks]

        assert len(names) == len(set(names)), f"Duplicate FK constraint names: {names}"

    def test_renamed_foreign_keys_encode_table_column(self):
        """Names are deterministic and traceable: source table + target
        table + source column(s) - exactly what the report asked for."""
        pkg = _junction_table_package()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        # Find the junction table (product_promotion_association)
        table = next(t for t in target_pkg.target_model.tables if t.name == "product_promotion_association")
        fks = {fk.referenced_table: fk for fk in table.constraints if fk.constraint_type == "FOREIGN_KEY"}

        product_fk = fks["product"]
        promotion_fk = fks["promotion"]

        assert "product_id" in product_fk.name
        assert "promotion_id" in promotion_fk.name
        assert product_fk.name != promotion_fk.name

    def test_original_physical_constraint_name_preserved_as_source_constraint(self):
        """Renaming for Databricks must not erase lineage back to the
        physical model's own (colliding) name."""
        pkg = _junction_table_package()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        table = target_pkg.target_model.tables[0]
        fks = [c for c in table.constraints if c.constraint_type == "FOREIGN_KEY"]
        for fk in fks:
            assert fk.source_constraint == "fk_product_promotion"

    def test_generated_ddl_contains_both_foreign_keys_with_unique_names(self):
        """The full DDL text: two ALTER TABLE ADD CONSTRAINT statements,
        distinct names, both FKs present - and the validator's duplicate-
        name check (run inside generate()) does not raise."""
        from migration.ddl.databricks_generator import DatabricksDDLGenerator

        pkg = _junction_table_package()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        ddl = DatabricksDDLGenerator(target_pkg, catalog="dblearn", schema="bronze").generate()
        sql = ddl.ddl_script.to_sql()

        fk_names = re.findall(r"ADD CONSTRAINT `([^`]+)`\s+FOREIGN KEY", sql)
        assert len(fk_names) == 2
        assert len(set(fk_names)) == 2

        assert "REFERENCES `dblearn`.`bronze`.`product`(`product_id`)" in sql
        assert "REFERENCES `dblearn`.`bronze`.`promotion`(`promotion_id`)" in sql

    def test_deduplicate_appends_suffix_on_genuine_collision(self):
        """Defensive backstop: even if two FK names somehow computed
        identically, the adapter still keeps both, distinguished by a
        numeric suffix, rather than dropping one."""
        pkg = _junction_table_package()
        adapter = DatabricksTargetAdapter(pkg)

        first = adapter._deduplicate("fk_a_b_c")
        second = adapter._deduplicate("fk_a_b_c")
        third = adapter._deduplicate("fk_a_b_c")

        assert first == "fk_a_b_c"
        assert second == "fk_a_b_c_2"
        assert third == "fk_a_b_c_3"
        assert len({first, second, third}) == 3


class TestMultipleForeignKeysBetweenSameTables:
    """A table may have more than one FK to the same referenced table
    (e.g. `orders.billing_address_id` and `orders.shipping_address_id`,
    both -> `address`). Names must stay unique per FK column, not just per
    referenced table."""

    def _two_fks_to_same_table(self) -> PhysicalModelPackage:
        table = PhysicalTable(
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
                    name="billing_address_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    is_foreign_key=True,
                    ordinal_position=2,
                ),
                PhysicalColumn(
                    name="shipping_address_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=True,
                    is_foreign_key=True,
                    ordinal_position=3,
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
                    name="fk_orders_address_billing",
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table="orders",
                    columns=["billing_address_id"],
                    referenced_table="address",
                    referenced_columns=["address_id"],
                ),
                PhysicalConstraint(
                    name="fk_orders_address_shipping",
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table="orders",
                    columns=["shipping_address_id"],
                    referenced_table="address",
                    referenced_columns=["address_id"],
                ),
            ],
        )
        model = PhysicalModel(database_name="shop", summary="Orders with two FKs to address.", tables=[table])
        return PhysicalModelPackage(physical_model=model, generated_by="PhysicalModelEngine")

    def test_both_fks_to_the_same_referenced_table_are_preserved_and_unique(self):
        pkg = self._two_fks_to_same_table()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        table = target_pkg.target_model.tables[0]
        fks = [c for c in table.constraints if c.constraint_type == "FOREIGN_KEY"]
        assert len(fks) == 2

        names = [fk.name for fk in fks]
        assert len(set(names)) == 2
        columns = {fk.columns[0] for fk in fks}
        assert columns == {"billing_address_id", "shipping_address_id"}
        for fk in fks:
            assert fk.columns[0] in fk.name


class TestManyToManyAcrossMultipleJunctionTables:
    """A schema with several M:N junction tables must keep every FK unique
    across the whole model, not just within one table."""

    def _two_junction_tables(self) -> PhysicalModelPackage:
        # Create the referenced tables with matching PK constraints
        product_table = PhysicalTable(
            name="product",
            logical_entity="Product",
            columns=[
                PhysicalColumn(
                    name="product_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    is_primary_key=True,
                    ordinal_position=1,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_product",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="product",
                    columns=["product_id"],
                ),
            ],
        )

        promotion_table = PhysicalTable(
            name="promotion",
            logical_entity="Promotion",
            columns=[
                PhysicalColumn(
                    name="promotion_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    is_primary_key=True,
                    ordinal_position=1,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_promotion",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="promotion",
                    columns=["promotion_id"],
                ),
            ],
        )

        warehouse_table = PhysicalTable(
            name="warehouse",
            logical_entity="Warehouse",
            columns=[
                PhysicalColumn(
                    name="warehouse_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    is_primary_key=True,
                    ordinal_position=1,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_warehouse",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="warehouse",
                    columns=["warehouse_id"],
                ),
            ],
        )

        def junction(name, left_col, left_ref, right_col, right_ref):
            return PhysicalTable(
                name=name,
                logical_entity=name,
                columns=[
                    PhysicalColumn(
                        name=left_col,
                        data_type=PhysicalDataType.IDENTIFIER,
                        nullable=False,
                        is_primary_key=True,
                        is_foreign_key=True,
                        ordinal_position=1,
                    ),
                    PhysicalColumn(
                        name=right_col,
                        data_type=PhysicalDataType.IDENTIFIER,
                        nullable=False,
                        is_primary_key=True,
                        is_foreign_key=True,
                        ordinal_position=2,
                    ),
                ],
                constraints=[
                    PhysicalConstraint(
                        name=f"pk_{name}",
                        constraint_type=ConstraintType.PRIMARY_KEY,
                        table=name,
                        columns=[left_col, right_col],
                    ),
                    PhysicalConstraint(
                        name="fk_junction",  # Deliberately identical across tables.
                        constraint_type=ConstraintType.FOREIGN_KEY,
                        table=name,
                        columns=[left_col],
                        referenced_table=left_ref,
                        referenced_columns=[f"{left_ref}_id"],
                    ),
                    PhysicalConstraint(
                        name="fk_junction",  # Deliberately identical across tables.
                        constraint_type=ConstraintType.FOREIGN_KEY,
                        table=name,
                        columns=[right_col],
                        referenced_table=right_ref,
                        referenced_columns=[f"{right_ref}_id"],
                    ),
                ],
            )

        tables = [
            product_table,
            promotion_table,
            warehouse_table,
            junction("product_promotion", "product_id", "product", "promotion_id", "promotion"),
            junction("warehouse_product", "warehouse_id", "warehouse", "product_id", "product"),
        ]
        model = PhysicalModel(
            database_name="shop", summary="Two M:N junction tables.", tables=tables
        )
        return PhysicalModelPackage(physical_model=model, generated_by="PhysicalModelEngine")

    def test_all_four_foreign_keys_across_both_junction_tables_are_unique(self):
        pkg = self._two_junction_tables()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        all_fk_names = [
            c.name
            for table in target_pkg.target_model.tables
            for c in table.constraints
            if c.constraint_type == "FOREIGN_KEY"
        ]
        assert len(all_fk_names) == 4
        assert len(set(all_fk_names)) == 4, f"Expected 4 unique FK names, got: {all_fk_names}"

    def test_generated_ddl_for_multiple_junction_tables_passes_validation(self):
        """The full pipeline, including the duplicate-name validator, must
        succeed - proving generate() doesn't raise DDLValidationError."""
        from migration.ddl.databricks_generator import DatabricksDDLGenerator

        pkg = self._two_junction_tables()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        # Must not raise.
        ddl = DatabricksDDLGenerator(target_pkg, catalog="dblearn", schema="bronze").generate()
        sql = ddl.ddl_script.to_sql()

        fk_names = re.findall(r"ADD CONSTRAINT `([^`]+)`\s+FOREIGN KEY", sql)
        assert len(fk_names) == 4
        assert len(set(fk_names)) == 4


class TestRealPipelineManyToManyReproduction:
    """Reproduces the exact production failure through the real pipeline:
    LogicalModelEngine resolves a MANY_TO_MANY conceptual relationship into
    an associative "Product Promotion Association" entity with two FK
    attributes, exactly as it did in the failing run - no hand-built
    physical model, no shortcuts."""

    def _conceptual_package(self) -> ConceptualModelPackage:
        from migration.conceptual.models import ConceptualEntity, ConceptualRelationship
        from migration.relationship.models import Cardinality

        model = ConceptualModel(
            database_name="shop",
            summary="A shop with products and promotions, many-to-many.",
            entities=[
                ConceptualEntity(
                    name="Product",
                    description="A sellable item.",
                    business_key=["product_id"],
                    attributes=["product_id"],
                    source_tables=["bronze.product"],
                    relationships=[
                        ConceptualRelationship(
                            related_entity="Promotion",
                            verb_phrase="is discounted by",
                            cardinality=Cardinality.MANY_TO_MANY,
                            is_optional=True,
                        )
                    ],
                ),
                ConceptualEntity(
                    name="Promotion",
                    description="A discount campaign.",
                    business_key=["promotion_id"],
                    attributes=["promotion_id"],
                    source_tables=["bronze.promotion"],
                    relationships=[],
                ),
            ],
        )
        return ConceptualModelPackage(conceptual_model=model, generated_by="test")

    def test_many_to_many_resolution_produces_two_distinct_fk_names(self):
        conceptual_pkg = self._conceptual_package()
        logical_pkg = LogicalModelEngine(conceptual_pkg).generate()
        physical_pkg = PhysicalModelEngine(logical_pkg).generate()

        junction_tables = [
            t for t in physical_pkg.physical_model.tables if len(t.source_tables) == 0 and any(
                c.constraint_type == ConstraintType.FOREIGN_KEY for c in t.constraints
            )
        ]
        # The associative table has two FK constraints, in the physical
        # model, which may or may not already collide depending on name
        # length - the Databricks adapter must fix this regardless.
        assert len(junction_tables) == 1
        physical_fks = [
            c for c in junction_tables[0].constraints if c.constraint_type == ConstraintType.FOREIGN_KEY
        ]
        assert len(physical_fks) == 2

        target_pkg = DatabricksTargetAdapter(physical_pkg).map()
        target_table = next(
            t for t in target_pkg.target_model.tables if t.name == junction_tables[0].name
        )
        target_fks = [c for c in target_table.constraints if c.constraint_type == "FOREIGN_KEY"]

        assert len(target_fks) == 2, "Both FKs must survive - never dropped or merged"
        names = [fk.name for fk in target_fks]
        assert len(set(names)) == 2, f"FK constraint names must be unique: {names}"
        assert {fk.referenced_table for fk in target_fks} == {"product", "promotion"}

    def test_generated_ddl_passes_validation_end_to_end(self):
        """The full run - through DDL generation and its built-in
        duplicate-name validator - must not raise."""
        from migration.ddl.databricks_generator import DatabricksDDLGenerator

        conceptual_pkg = self._conceptual_package()
        logical_pkg = LogicalModelEngine(conceptual_pkg).generate()
        physical_pkg = PhysicalModelEngine(logical_pkg).generate()
        target_pkg = DatabricksTargetAdapter(physical_pkg).map()

        ddl = DatabricksDDLGenerator(target_pkg, catalog="dblearn", schema="bronze").generate()
        sql = ddl.ddl_script.to_sql()

        fk_names = re.findall(r"ADD CONSTRAINT `([^`]+)`\s+FOREIGN KEY", sql)
        assert len(fk_names) == 2
        assert len(set(fk_names)) == 2
        assert "product" in sql
        assert "promotion" in sql
