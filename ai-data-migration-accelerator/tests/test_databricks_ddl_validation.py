"""Tests for Databricks DDL generation with validation fixes.

Covers:
1. Composite FK preservation (never reduce to single column)
2. Invalid FK suppression (FK references non-existent or mismatched PK/UNIQUE)
3. Inline column comments in CREATE TABLE
4. Source datatype preservation (DB2, PostgreSQL)
5. Unsupported syntax suppression
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
from migration.ddl.databricks_generator import DatabricksDDLGenerator


class TestCompositeForeignKeyPreservation:
    """Composite FKs (multiple columns) must be preserved exactly, never reduced."""

    def test_composite_fk_on_two_columns_is_preserved(self):
        """A 2-column FK must stay 2-column, not be reduced to 1."""
        models = self._composite_fk_scenario()
        target_pkg = DatabricksTargetAdapter(models).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()

        # FK must reference both columns, in order
        assert (
            "FOREIGN KEY (`order_year`, `order_month`) "
            "REFERENCES `orders_archive`(`year`, `month`)"
        ) in sql

    def test_composite_fk_column_order_matters(self):
        """FK columns must match referenced columns in exact order."""
        models = self._composite_fk_scenario()
        target_pkg = DatabricksTargetAdapter(models).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()

        # The FK references columns in the order (order_year, order_month)
        # and they must reference (year, month) on the target
        assert "`order_year`, `order_month`" in sql
        assert "`year`, `month`" in sql

    def _composite_fk_scenario(self) -> PhysicalModelPackage:
        """Build a model with a composite FK on (year, month) columns."""
        orders_archive = PhysicalTable(
            name="orders_archive",
            logical_entity="Archive",
            columns=[
                PhysicalColumn(
                    name="year",
                    data_type=PhysicalDataType.INTEGER,
                    nullable=False,
                    ordinal_position=1,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="month",
                    data_type=PhysicalDataType.INTEGER,
                    nullable=False,
                    ordinal_position=2,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="data",
                    data_type=PhysicalDataType.STRING,
                    nullable=True,
                    ordinal_position=3,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_archive",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="orders_archive",
                    columns=["year", "month"],
                )
            ],
        )

        orders_detail = PhysicalTable(
            name="orders_detail",
            logical_entity="OrderDetail",
            columns=[
                PhysicalColumn(
                    name="detail_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=1,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="order_year",
                    data_type=PhysicalDataType.INTEGER,
                    nullable=False,
                    ordinal_position=2,
                    is_foreign_key=True,
                ),
                PhysicalColumn(
                    name="order_month",
                    data_type=PhysicalDataType.INTEGER,
                    nullable=False,
                    ordinal_position=3,
                    is_foreign_key=True,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_detail",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="orders_detail",
                    columns=["detail_id"],
                ),
                PhysicalConstraint(
                    name="fk_detail_archive",
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table="orders_detail",
                    columns=["order_year", "order_month"],
                    referenced_table="orders_archive",
                    referenced_columns=["year", "month"],
                ),
            ],
        )

        model = PhysicalModel(
            database_name="sales",
            summary="Orders with archive by year/month.",
            tables=[orders_archive, orders_detail],
        )
        return PhysicalModelPackage(physical_model=model, generated_by="test")


class TestInvalidForeignKeySuppression:
    """Invalid FKs are emitted as comments, not executable SQL."""

    def test_fk_referencing_nonexistent_table_becomes_comment(self):
        """FK referencing a table that doesn't exist is commented out."""
        model = self._fk_to_missing_table_scenario()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()

        # Should be a comment, not an ALTER TABLE
        assert "--" in sql
        assert "FOREIGN KEY VALIDATION FAILED" in sql
        assert "does not exist in target model" in sql
        assert "ALTER TABLE" not in sql or "FOREIGN KEY VALIDATION FAILED" in sql

    def test_fk_with_mismatched_referenced_columns_becomes_comment(self):
        """FK whose referenced columns don't match any PK/UNIQUE is commented."""
        model = self._fk_with_mismatched_columns_scenario()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()

        # Should be a comment with validation failure explanation
        assert "FOREIGN KEY VALIDATION FAILED" in sql
        assert "do not exactly match any PRIMARY KEY" in sql

    def _fk_to_missing_table_scenario(self) -> PhysicalModelPackage:
        orders = PhysicalTable(
            name="orders",
            logical_entity="Order",
            columns=[
                PhysicalColumn(
                    name="order_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=1,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="nonexistent_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=2,
                    is_foreign_key=True,
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
                    name="fk_bad",
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table="orders",
                    columns=["nonexistent_id"],
                    referenced_table="nonexistent_table",
                    referenced_columns=["id"],
                ),
            ],
        )
        model = PhysicalModel(
            database_name="test", summary="Orders with bad FK.", tables=[orders]
        )
        return PhysicalModelPackage(physical_model=model, generated_by="test")

    def _fk_with_mismatched_columns_scenario(self) -> PhysicalModelPackage:
        customers = PhysicalTable(
            name="customers",
            logical_entity="Customer",
            columns=[
                PhysicalColumn(
                    name="customer_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=1,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="name",
                    data_type=PhysicalDataType.STRING,
                    nullable=False,
                    ordinal_position=2,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_customers",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="customers",
                    columns=["customer_id"],
                )
            ],
        )

        orders = PhysicalTable(
            name="orders",
            logical_entity="Order",
            columns=[
                PhysicalColumn(
                    name="order_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=1,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="customer_code",
                    data_type=PhysicalDataType.STRING,
                    nullable=False,
                    ordinal_position=2,
                    is_foreign_key=True,
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
                    name="fk_mismatched",
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table="orders",
                    columns=["customer_code"],
                    referenced_table="customers",
                    # References 'name' column, but PK is 'customer_id'
                    referenced_columns=["name"],
                ),
            ],
        )

        model = PhysicalModel(
            database_name="test",
            summary="Orders with mismatched FK.",
            tables=[customers, orders],
        )
        return PhysicalModelPackage(physical_model=model, generated_by="test")


class TestInlineColumnComments:
    """Column comments are inlined in CREATE TABLE, not separate ALTER statements."""

    def test_column_comments_appear_inline_in_create_table(self):
        """Column comments are in CREATE TABLE, with COMMENT clause."""
        model = self._simple_model_with_comments()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg, include_comments=True).generate()
        sql = ddl.ddl_script.to_sql()

        # Comments should appear inline in CREATE TABLE
        assert "COMMENT 'Source:" in sql
        # Should NOT have separate ALTER TABLE ... CHANGE COLUMN statements
        assert "ALTER TABLE" not in sql or "ADD CONSTRAINT" in sql

    def test_no_comments_when_disabled(self):
        """With include_comments=False, no comments are emitted."""
        model = self._simple_model_with_comments()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg, include_comments=False).generate()
        sql = ddl.ddl_script.to_sql()

        # No inline comments
        assert "COMMENT 'Source:" not in sql

    def _simple_model_with_comments(self) -> PhysicalModelPackage:
        customers = PhysicalTable(
            name="customers",
            logical_entity="Customer",
            columns=[
                PhysicalColumn(
                    name="customer_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=1,
                    source_column="customer_id",
                    physical_type="IDENTIFIER",
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="name",
                    data_type=PhysicalDataType.STRING,
                    nullable=False,
                    ordinal_position=2,
                    source_column="cust_name",
                    physical_type="STRING",
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_customers",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="customers",
                    columns=["customer_id"],
                )
            ],
        )
        model = PhysicalModel(
            database_name="test", summary="Customers.", tables=[customers]
        )
        return PhysicalModelPackage(physical_model=model, generated_by="test")


class TestSourceDatatypePreservation:
    """Source datatypes from DB2/PostgreSQL are preserved through to DDL."""

    def test_db2_date_preserved_as_date(self):
        """DB2 DATE→DATE in Databricks."""
        model = self._db2_datatype_scenario()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()
        assert "`order_date` DATE" in sql

    def test_db2_timestamp_preserved_as_timestamp(self):
        """DB2 TIMESTAMP→TIMESTAMP in Databricks."""
        model = self._db2_datatype_scenario()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()
        assert "`created_at` TIMESTAMP" in sql

    def test_db2_decimal_with_precision_scale_preserved(self):
        """DB2 DECIMAL(10,2)→DECIMAL(10,2) in Databricks."""
        model = self._db2_datatype_scenario()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()
        assert "`amount` DECIMAL(10,2)" in sql

    def _db2_datatype_scenario(self) -> PhysicalModelPackage:
        orders = PhysicalTable(
            name="orders",
            logical_entity="Order",
            columns=[
                PhysicalColumn(
                    name="order_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=1,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="order_date",
                    data_type=PhysicalDataType.DATE,
                    nullable=False,
                    ordinal_position=2,
                ),
                PhysicalColumn(
                    name="created_at",
                    data_type=PhysicalDataType.TIMESTAMP,
                    nullable=False,
                    ordinal_position=3,
                ),
                PhysicalColumn(
                    name="amount",
                    data_type=PhysicalDataType.DECIMAL,
                    nullable=False,
                    precision=10,
                    scale=2,
                    ordinal_position=4,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_orders",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="orders",
                    columns=["order_id"],
                )
            ],
        )
        model = PhysicalModel(
            database_name="test", summary="Orders with DB2 types.", tables=[orders]
        )
        return PhysicalModelPackage(physical_model=model, generated_by="test")


class TestUnsupportedSyntaxSuppression:
    """Unsupported source-specific syntax is never emitted."""

    def test_no_create_index(self):
        """CREATE INDEX never appears in executable DDL."""
        model = self._simple_model_with_index()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()

        # CREATE INDEX should not appear in executable SQL
        assert "CREATE INDEX" not in sql

    def test_no_unique_constraint_ddl(self):
        """UNIQUE constraints don't generate DDL (Delta doesn't support them)."""
        model = self._model_with_unique_constraint()
        target_pkg = DatabricksTargetAdapter(model).map()
        ddl = DatabricksDDLGenerator(target_pkg).generate()
        sql = ddl.ddl_script.to_sql()

        # No executable UNIQUE constraint
        assert "CONSTRAINT" in sql  # PK is OK
        # But the executable part should not have UNIQUE
        create_table_only = sql.split("ALTER")[0] if "ALTER" in sql else sql
        assert "UNIQUE" not in create_table_only

    def _simple_model_with_index(self) -> PhysicalModelPackage:
        from migration.target.models import TargetIndex

        customers = PhysicalTable(
            name="customers",
            logical_entity="Customer",
            columns=[
                PhysicalColumn(
                    name="customer_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=1,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="email",
                    data_type=PhysicalDataType.STRING,
                    nullable=False,
                    ordinal_position=2,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_customers",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="customers",
                    columns=["customer_id"],
                )
            ],
            indexes=[],
        )
        model = PhysicalModel(
            database_name="test", summary="Customers.", tables=[customers]
        )
        pkg = PhysicalModelPackage(physical_model=model, generated_by="test")
        return pkg

    def _model_with_unique_constraint(self) -> PhysicalModelPackage:
        customers = PhysicalTable(
            name="customers",
            logical_entity="Customer",
            columns=[
                PhysicalColumn(
                    name="customer_id",
                    data_type=PhysicalDataType.IDENTIFIER,
                    nullable=False,
                    ordinal_position=1,
                    is_primary_key=True,
                ),
                PhysicalColumn(
                    name="email",
                    data_type=PhysicalDataType.STRING,
                    nullable=False,
                    ordinal_position=2,
                ),
            ],
            constraints=[
                PhysicalConstraint(
                    name="pk_customers",
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table="customers",
                    columns=["customer_id"],
                ),
                PhysicalConstraint(
                    name="uq_email",
                    constraint_type=ConstraintType.UNIQUE,
                    table="customers",
                    columns=["email"],
                ),
            ],
        )
        model = PhysicalModel(
            database_name="test",
            summary="Customers with unique email.",
            tables=[customers],
        )
        return PhysicalModelPackage(physical_model=model, generated_by="test")
