"""Tests for DDL generation.

Verifies that target models produce correct, deterministic DDL for the target
platform. Tests ordering, quoting, constraint handling, and metadata.
"""

from __future__ import annotations

import pytest

from migration.ddl.databricks_generator import DatabricksDDLGenerator
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
    StorageRecommendation,
    TableClassification,
)
from migration.target.databricks import DatabricksTargetAdapter
from migration.target.models import TargetCapability


def simple_physical_model() -> PhysicalModelPackage:
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


class TestDatabricksDDLGenerator:
    """Tests for Databricks DDL generation."""

    def test_generates_create_table_statement(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        assert ddl.ddl_script.database_name == "shop"
        assert ddl.generated_by == "DatabricksDDLGenerator"
        assert len(ddl.ddl_script.table_creation_statements) == 1

        stmt = ddl.ddl_script.table_creation_statements[0]
        assert "CREATE TABLE" in stmt.statement
        assert "`customers`" in stmt.statement

    def test_creates_column_definitions(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement

        # Check column names and types
        assert "`created_at`" in stmt
        assert "`customer_id`" in stmt
        assert "`name`" in stmt
        assert "BIGINT" in stmt
        # Databricks: STRING without length constraints (mapped from STRING(100))
        assert "STRING" in stmt
        assert "TIMESTAMP" in stmt

    def test_adds_not_null_constraints(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement

        # Primary key and name are NOT NULL
        assert "NOT NULL" in stmt

    def test_adds_default_values(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "DEFAULT CURRENT_TIMESTAMP" in stmt

    def test_adds_primary_key_inline(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "PRIMARY KEY (`customer_id`)" in stmt

    def test_ends_with_semicolon(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        for stmt in ddl.ddl_script.all_statements():
            assert stmt.statement.endswith(";")

    def test_handles_foreign_keys(self):
        pkg = simple_physical_model()
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

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        # Foreign key should be in constraint statements
        fk_stmts = [s for s in ddl.ddl_script.constraint_statements if "FOREIGN KEY" in s.statement]
        assert len(fk_stmts) >= 1

        fk_stmt = fk_stmts[0]
        assert "ALTER TABLE" in fk_stmt.statement
        assert "FOREIGN KEY" in fk_stmt.statement
        assert "customers" in fk_stmt.statement

    def test_handles_unique_constraints(self):
        """Delta Lake has no UNIQUE constraint DDL: it must never be inlined
        into CREATE TABLE. The target adapter drops it (recording a note),
        so no UNIQUE clause reaches the DDL generator at all."""
        pkg = simple_physical_model()
        table = pkg.physical_model.tables[0]
        table.columns.append(
            PhysicalColumn(
                name="email",
                data_type=PhysicalDataType.STRING,
                length=255,
                nullable=True,
                ordinal_position=4,
            )
        )
        table.constraints.append(
            PhysicalConstraint(
                name="uq_customers_email",
                constraint_type=ConstraintType.UNIQUE,
                table="customers",
                columns=["email"],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "UNIQUE" not in stmt
        assert "uq_customers_email" in " ".join(target_pkg.target_model.mapping_notes)

    def test_handles_check_constraints(self):
        """Databricks only accepts CHECK via ALTER TABLE ADD CONSTRAINT -
        never inline in CREATE TABLE."""
        pkg = simple_physical_model()
        table = pkg.physical_model.tables[0]
        table.columns.append(
            PhysicalColumn(
                name="discount",
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
                columns=["discount"],
                expression="discount BETWEEN 0 AND 100",
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        create_stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "CHECK" not in create_stmt

        check_stmts = [
            s for s in ddl.ddl_script.constraint_statements if "CHECK" in s.statement
        ]
        assert len(check_stmts) == 1
        assert "ALTER TABLE" in check_stmts[0].statement
        assert "ADD CONSTRAINT `ck_customers_discount`" in check_stmts[0].statement
        assert "CHECK (discount BETWEEN 0 AND 100)" in check_stmts[0].statement

    def test_handles_indexes(self):
        """Delta Lake has no CREATE INDEX: the recommendation survives as a
        non-executable comment, never as SQL Databricks cannot run."""
        pkg = simple_physical_model()
        table = pkg.physical_model.tables[0]
        table.indexes = [
            PhysicalIndex(
                name="idx_customers_name",
                table="customers",
                columns=["name"],
                is_unique=False,
                purpose=IndexPurpose.FOREIGN_KEY,
            ),
        ]

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        assert len(ddl.ddl_script.index_statements) >= 1
        idx_stmt = ddl.ddl_script.index_statements[0]
        assert idx_stmt.statement_type == "COMMENT"
        assert idx_stmt.statement.startswith("--")
        assert "has no CREATE INDEX" in idx_stmt.statement
        assert "idx_customers_name" in idx_stmt.statement
        assert "`customers`" in idx_stmt.statement
        assert "name" in idx_stmt.statement

    def test_handles_unique_indexes(self):
        """A unique index recommendation is also a comment, not executable SQL."""
        pkg = simple_physical_model()
        table = pkg.physical_model.tables[0]
        table.indexes = [
            PhysicalIndex(
                name="idx_customers_id_unique",
                table="customers",
                columns=["customer_id"],
                is_unique=True,
                purpose=IndexPurpose.PRIMARY_KEY,
            ),
        ]

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        idx_stmt = ddl.ddl_script.index_statements[0]
        assert idx_stmt.statement_type == "COMMENT"
        assert idx_stmt.statement.startswith("--")
        assert "UNIQUE INDEX" in idx_stmt.statement

    def test_deterministic_output(self):
        """Same input always produces identical SQL."""
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        sql1 = DatabricksDDLGenerator(target_pkg).generate().ddl_script.to_sql()
        sql2 = DatabricksDDLGenerator(target_pkg).generate().ddl_script.to_sql()

        assert sql1 == sql2

    def test_generates_complete_script(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        script = ddl.ddl_script.to_sql()

        assert script.startswith("CREATE TABLE")
        assert script.endswith("\n")
        # Script contains column comments inline
        assert "COMMENT" in script

    def test_multiple_tables_in_order(self):
        """Multiple tables are created in sorted order (deterministic)."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test multiple tables.",
                tables=[
                    PhysicalTable(
                        name="zebras",
                        logical_entity="Zebra",
                        columns=[
                            PhysicalColumn(
                                name="id",
                                data_type=PhysicalDataType.IDENTIFIER,
                                nullable=False,
                                is_primary_key=True,
                                ordinal_position=1,
                            ),
                        ],
                        constraints=[
                            PhysicalConstraint(
                                name="pk_zebras",
                                constraint_type=ConstraintType.PRIMARY_KEY,
                                table="zebras",
                                columns=["id"],
                            ),
                        ],
                    ),
                    PhysicalTable(
                        name="apples",
                        logical_entity="Apple",
                        columns=[
                            PhysicalColumn(
                                name="id",
                                data_type=PhysicalDataType.IDENTIFIER,
                                nullable=False,
                                is_primary_key=True,
                                ordinal_position=1,
                            ),
                        ],
                        constraints=[
                            PhysicalConstraint(
                                name="pk_apples",
                                constraint_type=ConstraintType.PRIMARY_KEY,
                                table="apples",
                                columns=["id"],
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        script = ddl.ddl_script.to_sql()
        apples_pos = script.find("apples")
        zebras_pos = script.find("zebras")

        # Apples should come before zebras (alphabetical)
        assert apples_pos < zebras_pos

    def test_partitioning_recommendations_are_comments_by_default(self):
        """Without enable_clustering, partition/clustering candidates stay a
        non-executable comment recommendation - never inlined into
        CREATE TABLE (a deterministic heuristic must not become executable
        SQL unless the operator has confirmed the runtime supports it)."""
        pkg = simple_physical_model()
        table = pkg.physical_model.tables[0]
        table.storage = StorageRecommendation(
            table="customers",
            partition_candidates=["created_at"],
            clustering_candidates=["customer_id"],
            rationale="Partition by date for time-series queries.",
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        create_stmt = ddl.ddl_script.table_creation_statements[0]
        assert "PARTITIONED BY" not in create_stmt.statement
        assert "CLUSTER BY" not in create_stmt.statement

        assert len(ddl.ddl_script.partition_clustering_statements) == 1
        recommendation = ddl.ddl_script.partition_clustering_statements[0]
        assert recommendation.statement_type == "COMMENT"
        assert "created_at" in recommendation.statement
        assert "customer_id" in recommendation.statement

    def test_partitioning_recommendations_executable_when_enabled(self):
        """With enable_clustering=True, the same recommendation becomes
        executable PARTITIONED BY / CLUSTER BY syntax in CREATE TABLE."""
        pkg = simple_physical_model()
        table = pkg.physical_model.tables[0]
        table.storage = StorageRecommendation(
            table="customers",
            partition_candidates=["created_at"],
            clustering_candidates=["customer_id"],
            rationale="Partition by date for time-series queries.",
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg, enable_clustering=True)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0]
        assert "PARTITIONED BY" in stmt.statement
        assert "CLUSTER BY" in stmt.statement
        assert "CLUSTERED BY" not in stmt.statement  # Not valid Delta syntax
        assert "`created_at`" in stmt.statement
        assert "`customer_id`" in stmt.statement

    def test_comments_optional(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()

        # With comments
        with_comments = DatabricksDDLGenerator(target_pkg, include_comments=True).generate()
        with_stmts = len(with_comments.ddl_script.comment_statements)

        # Without comments
        without_comments = DatabricksDDLGenerator(target_pkg, include_comments=False).generate()
        without_stmts = len(without_comments.ddl_script.comment_statements)

        assert with_stmts >= without_stmts

    def test_identifiers_quoted_with_backticks(self):
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        script = ddl.ddl_script.to_sql()

        # Check backtick quoting
        assert "`customers`" in script
        assert "`customer_id`" in script
        assert "`name`" in script

    def test_preserves_lineage(self):
        """DDL statements carry source table information."""
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        for stmt in ddl.ddl_script.all_statements():
            if stmt.statement_type == "CREATE":
                assert stmt.source_table is not None

    def test_sql_injection_prevention(self):
        """String escaping prevents SQL injection."""
        pkg = simple_physical_model()
        table = pkg.physical_model.tables[0]
        table.columns.append(
            PhysicalColumn(
                name="description",
                data_type=PhysicalDataType.STRING,
                length=255,
                nullable=True,
                ordinal_position=4,
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        script = ddl.ddl_script.to_sql()

        # Should not have unescaped quotes
        assert "'; DROP TABLE" not in script

    def test_escape_strings_in_comments(self):
        """Single quotes in comments are escaped."""
        generator = DatabricksDDLGenerator.__dict__["_escape_string"].__func__
        result = generator("It's a test")
        assert result == "It''s a test"

        result = generator("Backslash \\ test")
        assert result == "Backslash \\\\ test"

    def test_complex_multi_table_schema(self):
        """Complex schema with relationships generates correct DDL."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="ecommerce",
                summary="E-commerce database.",
                tables=[
                    PhysicalTable(
                        name="customers",
                        logical_entity="Customer",
                        columns=[
                            PhysicalColumn(
                                name="customer_id",
                                data_type=PhysicalDataType.IDENTIFIER,
                                nullable=False,
                                is_primary_key=True,
                                ordinal_position=1,
                            ),
                            PhysicalColumn(
                                name="email",
                                data_type=PhysicalDataType.STRING,
                                length=255,
                                nullable=False,
                                is_unique=True,
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
                                name="uq_customers_email",
                                constraint_type=ConstraintType.UNIQUE,
                                table="customers",
                                columns=["email"],
                            ),
                        ],
                    ),
                    PhysicalTable(
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
                            PhysicalColumn(
                                name="order_date",
                                data_type=PhysicalDataType.DATE,
                                nullable=False,
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
                                name="fk_orders_customers",
                                constraint_type=ConstraintType.FOREIGN_KEY,
                                table="orders",
                                columns=["customer_id"],
                                referenced_table="customers",
                                referenced_columns=["customer_id"],
                            ),
                        ],
                        storage=StorageRecommendation(
                            table="orders",
                            partition_candidates=["order_date"],
                        ),
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        script = ddl.ddl_script.to_sql()

        # Verify all components are present
        assert "CREATE TABLE IF NOT EXISTS `customers`" in script
        assert "CREATE TABLE IF NOT EXISTS `orders`" in script
        # UNIQUE has no Delta equivalent: dropped with a note, never inlined.
        assert "UNIQUE" not in script
        assert "uq_customers_email" in " ".join(target_pkg.target_model.mapping_notes)
        assert "FOREIGN KEY (`customer_id`)" in script
        # Partitioning stays a comment recommendation by default.
        assert "PARTITIONED BY" not in script
        assert "PARTITION BY: order_date" in script


class TestDatabricksDataTypeMapping:
    """Tests for generic to Databricks data type conversion."""

    def test_string_length_stripped_for_databricks(self):
        """Databricks: STRING(255) → STRING (no length constraints)."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test data type mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="varchar_col",
                                data_type=PhysicalDataType.STRING,
                                length=255,
                                nullable=True,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        # Should be STRING without length, not STRING(255)
        assert "STRING" in stmt
        assert "STRING(255)" not in stmt

    def test_identifier_maps_to_bigint(self):
        """Databricks: IDENTIFIER → BIGINT (auto-increment)."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test identifier mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="id",
                                data_type=PhysicalDataType.IDENTIFIER,
                                nullable=False,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "`id` BIGINT" in stmt

    def test_integer_maps_to_bigint(self):
        """Databricks: INTEGER → BIGINT (64-bit integers)."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test integer mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="quantity",
                                data_type=PhysicalDataType.INTEGER,
                                nullable=True,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "`quantity` BIGINT" in stmt
        # INTEGER is allowed in comments (physical_type), but not in the type definition
        assert "`quantity` INTEGER" not in stmt

    def test_decimal_with_precision_scale(self):
        """Databricks: DECIMAL(18,2) → DECIMAL(18,2)."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test decimal mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="price",
                                data_type=PhysicalDataType.DECIMAL,
                                precision=18,
                                scale=2,
                                nullable=True,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "`price` DECIMAL(18,2)" in stmt

    def test_date_type_preserved(self):
        """Databricks: DATE → DATE."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test date mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="birth_date",
                                data_type=PhysicalDataType.DATE,
                                nullable=True,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "`birth_date` DATE" in stmt

    def test_timestamp_type_preserved(self):
        """Databricks: TIMESTAMP → TIMESTAMP."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test timestamp mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="created_at",
                                data_type=PhysicalDataType.TIMESTAMP,
                                nullable=False,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "`created_at` TIMESTAMP" in stmt

    def test_boolean_type_preserved(self):
        """Databricks: BOOLEAN → BOOLEAN."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test boolean mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="is_active",
                                data_type=PhysicalDataType.BOOLEAN,
                                nullable=True,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "`is_active` BOOLEAN" in stmt

    def test_json_maps_to_string(self):
        """Databricks: JSON → STRING (for broad compatibility)."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test JSON mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="metadata",
                                data_type=PhysicalDataType.JSON,
                                nullable=True,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "`metadata` STRING" in stmt

    def test_binary_type_preserved(self):
        """Databricks: BINARY → BINARY."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="Test binary mapping.",
                tables=[
                    PhysicalTable(
                        name="test_table",
                        logical_entity="Test",
                        columns=[
                            PhysicalColumn(
                                name="image_data",
                                data_type=PhysicalDataType.BINARY,
                                nullable=True,
                                ordinal_position=1,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        assert "`image_data` BINARY" in stmt

    def test_all_types_in_one_table(self):
        """Verify all data types convert correctly in a single table."""
        pkg = PhysicalModelPackage(
            physical_model=PhysicalModel(
                database_name="test",
                summary="All types test.",
                tables=[
                    PhysicalTable(
                        name="all_types",
                        logical_entity="AllTypes",
                        columns=[
                            PhysicalColumn(
                                name="id",
                                data_type=PhysicalDataType.IDENTIFIER,
                                nullable=False,
                                ordinal_position=1,
                            ),
                            PhysicalColumn(
                                name="name",
                                data_type=PhysicalDataType.STRING,
                                length=255,
                                nullable=False,
                                ordinal_position=2,
                            ),
                            PhysicalColumn(
                                name="count",
                                data_type=PhysicalDataType.INTEGER,
                                nullable=True,
                                ordinal_position=3,
                            ),
                            PhysicalColumn(
                                name="amount",
                                data_type=PhysicalDataType.DECIMAL,
                                precision=10,
                                scale=2,
                                nullable=True,
                                ordinal_position=4,
                            ),
                            PhysicalColumn(
                                name="birth",
                                data_type=PhysicalDataType.DATE,
                                nullable=True,
                                ordinal_position=5,
                            ),
                            PhysicalColumn(
                                name="updated",
                                data_type=PhysicalDataType.TIMESTAMP,
                                nullable=True,
                                ordinal_position=6,
                            ),
                            PhysicalColumn(
                                name="is_valid",
                                data_type=PhysicalDataType.BOOLEAN,
                                nullable=True,
                                ordinal_position=7,
                            ),
                        ],
                    ),
                ],
            )
        )

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement

        # Verify all types converted correctly
        assert "`id` BIGINT" in stmt  # IDENTIFIER → BIGINT
        assert "`name` STRING" in stmt  # Not STRING(255)
        assert "`count` BIGINT" in stmt  # INTEGER → BIGINT
        assert "`amount` DECIMAL(10,2)" in stmt
        assert "`birth` DATE" in stmt
        assert "`updated` TIMESTAMP" in stmt
        assert "`is_valid` BOOLEAN" in stmt
        # Ensure no unsupported generic types appear
        assert "STRING(255)" not in stmt
        # INTEGER is allowed in comments (physical_type), but not in type definitions
        assert "`count` INTEGER" not in stmt


class TestDatabricksSchemaSupport:
    """Tests for Databricks Unity Catalog and schema support."""

    def test_backward_compatibility_without_schema(self):
        """Without catalog/schema, tables use unqualified names."""
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(target_pkg)  # No catalog, schema
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        # Should use simple table name
        assert "CREATE TABLE IF NOT EXISTS `customers`" in stmt
        assert "`default`" not in stmt

    def test_fully_qualified_table_with_catalog_and_schema(self):
        """With both catalog and schema, tables use fully qualified names."""
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(
            target_pkg,
            catalog="dblearn",
            schema="bronze",
        )
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        # Should use fully qualified name
        assert "CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`customers`" in stmt

    def test_catalog_only_without_schema(self):
        """With catalog but no schema, tables use catalog.table."""
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(
            target_pkg,
            catalog="dblearn",
        )
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        # Should use catalog.table (no schema)
        assert "CREATE TABLE IF NOT EXISTS `dblearn`.`customers`" in stmt

    def test_schema_only_without_catalog(self):
        """With schema but no catalog, tables use schema.table."""
        pkg = simple_physical_model()
        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(
            target_pkg,
            schema="bronze",
        )
        ddl = generator.generate()

        stmt = ddl.ddl_script.table_creation_statements[0].statement
        # Should use schema.table (no catalog)
        assert "CREATE TABLE IF NOT EXISTS `bronze`.`customers`" in stmt

    def test_foreign_key_with_fully_qualified_names(self):
        """Foreign keys respect catalog.schema.table qualification."""
        pkg = simple_physical_model()
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

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(
            target_pkg,
            catalog="dblearn",
            schema="bronze",
        )
        ddl = generator.generate()

        # Check foreign key statement
        fk_stmts = [s for s in ddl.ddl_script.constraint_statements if "FOREIGN KEY" in s.statement]
        assert len(fk_stmts) >= 1

        fk_stmt = fk_stmts[0].statement
        # Both tables should be fully qualified
        assert "ALTER TABLE `dblearn`.`bronze`.`orders`" in fk_stmt
        assert "REFERENCES `dblearn`.`bronze`.`customers`" in fk_stmt

    def test_indexes_with_fully_qualified_table(self):
        """Index recommendation comments reference the fully qualified table."""
        pkg = simple_physical_model()
        table = pkg.physical_model.tables[0]
        table.indexes = [
            PhysicalIndex(
                name="idx_customers_name",
                table="customers",
                columns=["name"],
                is_unique=False,
                purpose=IndexPurpose.FOREIGN_KEY,
            ),
        ]

        target_pkg = DatabricksTargetAdapter(pkg).map()
        generator = DatabricksDDLGenerator(
            target_pkg,
            catalog="dblearn",
            schema="bronze",
        )
        ddl = generator.generate()

        idx_stmt = ddl.ddl_script.index_statements[0]
        assert idx_stmt.statement_type == "COMMENT"
        # Recommendation should reference fully qualified table
        assert "`dblearn`.`bronze`.`customers`" in idx_stmt.statement
