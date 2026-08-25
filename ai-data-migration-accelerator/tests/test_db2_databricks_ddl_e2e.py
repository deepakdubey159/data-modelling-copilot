"""End-to-end DB2 -> Databricks DDL generation.

Runs the full deterministic pipeline - canonical metadata (DB2-shaped) ->
relationship discovery -> conceptual model (stubbed LLM) -> logical model ->
physical model -> Databricks target adapter -> DDL generator - and verifies
the final `databricks.sql` text is valid, source-faithful Databricks SQL:

- source PK/FK preserved exactly, with no invented constraints
- every foreign key gets a unique constraint name
- a reserved word used as a table name ("order") is safely quoted
- catalog.schema.table qualification is applied everywhere
- DECIMAL precision/scale and other DB2 types survive from source to DDL
- no CREATE INDEX, no PostgreSQL/DB2-only physical syntax, ever
"""

from __future__ import annotations

import json
import re

import pytest

from migration.canonical.models import (
    ColumnMetadata,
    DatabaseMetadata,
    ForeignKeyMetadata,
    MetadataPackage,
    PrimaryKeyMetadata,
    SchemaMetadata,
    TableMetadata,
)
from migration.conceptual.engine import ConceptualModelEngine
from migration.ddl.databricks_generator import DatabricksDDLGenerator
from migration.logical.engine import LogicalModelEngine
from migration.physical.engine import PhysicalModelEngine
from migration.relationship.engine import RelationshipEngine
from migration.target.databricks import DatabricksTargetAdapter
from tests.conceptual_fixtures import StubLLMClient

SCHEMA = "ECOMMERCE"


def _db2_metadata() -> DatabaseMetadata:
    """A small DB2 (mainframe-style) schema: two parents and a child table
    named `order` - a reserved word in Databricks SQL - with two foreign
    keys, DB2-specific types (GRAPHIC, CHAR, DECIMAL with explicit
    precision/scale) and DB2 NULL/DEFAULT semantics."""
    customer = TableMetadata(
        table_name="customer",
        table_type="BASE TABLE",
        columns=[
            ColumnMetadata(
                name="customer_id",
                data_type="BIGINT",
                nullable=False,
                ordinal_position=1,
                numeric_precision=19,
                numeric_scale=0,
                is_primary_key=True,
            ),
            ColumnMetadata(
                name="customer_name",
                data_type="VARCHAR",
                nullable=False,
                ordinal_position=2,
                character_length=100,
            ),
            ColumnMetadata(
                name="contact_address",
                data_type="VARCHAR",
                nullable=True,
                ordinal_position=3,
                character_length=255,
            ),
        ],
        primary_keys=[PrimaryKeyMetadata(constraint_name="pk_customer", columns=["customer_id"])],
    )

    product = TableMetadata(
        table_name="product",
        table_type="BASE TABLE",
        columns=[
            ColumnMetadata(
                name="product_id",
                data_type="INTEGER",
                nullable=False,
                ordinal_position=1,
                numeric_precision=10,
                numeric_scale=0,
                is_primary_key=True,
            ),
            ColumnMetadata(
                name="product_label",
                data_type="CHAR",
                nullable=False,
                ordinal_position=2,
                character_length=20,
            ),
        ],
        primary_keys=[PrimaryKeyMetadata(constraint_name="pk_product", columns=["product_id"])],
    )

    order = TableMetadata(
        table_name="order",  # Reserved word in Databricks SQL.
        table_type="BASE TABLE",
        columns=[
            ColumnMetadata(
                name="order_id",
                data_type="BIGINT",
                nullable=False,
                ordinal_position=1,
                numeric_precision=19,
                numeric_scale=0,
                is_primary_key=True,
            ),
            ColumnMetadata(
                name="customer_id",
                data_type="BIGINT",
                nullable=False,
                ordinal_position=2,
                numeric_precision=19,
                numeric_scale=0,
                is_foreign_key=True,
            ),
            ColumnMetadata(
                name="product_id",
                data_type="INTEGER",
                nullable=False,
                ordinal_position=3,
                numeric_precision=10,
                numeric_scale=0,
                is_foreign_key=True,
            ),
            ColumnMetadata(
                name="order_date",
                data_type="DATE",
                nullable=False,
                ordinal_position=4,
            ),
            ColumnMetadata(
                name="total",
                data_type="DECIMAL",
                nullable=True,
                ordinal_position=5,
                numeric_precision=10,
                numeric_scale=2,
            ),
            ColumnMetadata(
                name="description",
                data_type="GRAPHIC",
                nullable=True,
                ordinal_position=6,
                character_length=50,
            ),
        ],
        primary_keys=[PrimaryKeyMetadata(constraint_name="pk_order", columns=["order_id"])],
        foreign_keys=[
            ForeignKeyMetadata(
                constraint_name="fk_order_customer",
                column="customer_id",
                referenced_schema=SCHEMA,
                referenced_table="customer",
                referenced_column="customer_id",
            ),
            ForeignKeyMetadata(
                constraint_name="fk_order_product",
                column="product_id",
                referenced_schema=SCHEMA,
                referenced_table="product",
                referenced_column="product_id",
            ),
        ],
    )

    return DatabaseMetadata(
        database_name="ecommerce_db2",
        source_database_type="db2",
        schemas=[SchemaMetadata(schema_name=SCHEMA, tables=[customer, product, order])],
    )


def _conceptual_response() -> str:
    """A hand-authored conceptual model response mirroring the source FKs
    exactly (as an LLM response would, on a good day) - business_key and
    attributes use the literal source column names so source resolution is
    unambiguous, and the FK columns are deliberately omitted from the
    child's own attribute list so LogicalModelEngine's relationship
    propagation introduces them, matching the source FK direction."""
    return json.dumps(
        {
            "database_name": "ecommerce_db2",
            "summary": "An order management system with customers and products.",
            "domains": [
                {
                    "name": "Sales",
                    "description": "Customers, products and their orders.",
                    "entities": ["Customer", "Product", "Order"],
                }
            ],
            "entities": [
                {
                    "name": "Customer",
                    "description": "A person or organisation that places orders.",
                    "business_key": ["customer_id"],
                    "attributes": ["customer_id", "customer_name", "contact_address"],
                    "source_tables": [f"{SCHEMA}.customer"],
                    "relationships": [],
                },
                {
                    "name": "Product",
                    "description": "A sellable item.",
                    "business_key": ["product_id"],
                    "attributes": ["product_id", "product_label"],
                    "source_tables": [f"{SCHEMA}.product"],
                    "relationships": [],
                },
                {
                    "name": "Order",
                    "description": "A purchase made by a customer for one product.",
                    "business_key": ["order_id"],
                    "attributes": ["order_id", "order_date", "total", "description"],
                    "source_tables": [f"{SCHEMA}.order"],
                    "relationships": [
                        {
                            "related_entity": "Customer",
                            "verb_phrase": "places",
                            "cardinality": "MANY_TO_ONE",
                            "is_optional": False,
                            "description": "Every order is placed by exactly one customer.",
                        },
                        {
                            "related_entity": "Product",
                            "verb_phrase": "contains",
                            "cardinality": "MANY_TO_ONE",
                            "is_optional": False,
                            "description": "Every order is for exactly one product.",
                        },
                    ],
                },
            ],
            "business_rules": [],
            "assumptions": [],
            "recommendations": [],
        }
    )


@pytest.fixture(scope="module")
def generated_sql() -> str:
    """Run the full pipeline once and return the generated databricks.sql text."""
    db2_metadata = _db2_metadata()
    metadata_pkg = MetadataPackage(metadata=db2_metadata)

    relationships_pkg = RelationshipEngine(db2_metadata).discover()
    assert len(relationships_pkg.relationships.relationships) == 2

    client = StubLLMClient(_conceptual_response())
    conceptual_pkg = ConceptualModelEngine(client=client).generate(
        metadata_pkg, None, relationships_pkg
    )

    logical_pkg = LogicalModelEngine(conceptual_pkg, metadata=metadata_pkg).generate()
    physical_pkg = PhysicalModelEngine(logical_pkg, metadata=metadata_pkg).generate()
    target_pkg = DatabricksTargetAdapter(physical_pkg).map()

    ddl_pkg = DatabricksDDLGenerator(
        target_pkg, catalog="dblearn", schema="bronze"
    ).generate()
    return ddl_pkg.ddl_script.to_sql()


def _executable_only(sql: str) -> str:
    """Strip non-executable comment blocks (index/partition/clustering
    recommendations, column comments), leaving only statements Databricks
    would actually run. Comments are free to mention, in prose, syntax they
    explain Databricks doesn't support - a naive substring search over the
    full script would misread that prose as the generator emitting it."""
    return "\n\n".join(
        block for block in sql.split("\n\n") if not block.strip().startswith("--")
    )


class TestDB2ToDatabricksEndToEnd:
    """Full-pipeline assertions on the final generated SQL."""

    def test_catalog_schema_table_qualification(self, generated_sql):
        assert "CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`customer`" in generated_sql
        assert "CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`product`" in generated_sql

    def test_reserved_word_table_name_is_quoted(self, generated_sql):
        """`order` is a reserved word in Databricks SQL and must be safely
        quoted everywhere it appears - as a table and in every reference."""
        assert "CREATE TABLE IF NOT EXISTS `dblearn`.`bronze`.`order`" in generated_sql
        assert re.search(r"ALTER TABLE `dblearn`\.`bronze`\.`order`", generated_sql)
        # Never appears unquoted as a bare keyword.
        assert not re.search(r"(?<!`)\border\b(?!`)", generated_sql.replace("`order`", ""))

    def test_source_primary_keys_preserved_and_not_invented(self, generated_sql):
        """Every table's PK matches its source primary key exactly - no
        extra, missing, or invented PRIMARY KEY constraint."""
        assert "CONSTRAINT `pk_customer` PRIMARY KEY (`customer_id`)" in generated_sql
        assert "CONSTRAINT `pk_product` PRIMARY KEY (`product_id`)" in generated_sql
        assert "CONSTRAINT `pk_order` PRIMARY KEY (`order_id`)" in generated_sql
        assert generated_sql.count("PRIMARY KEY") == 3

    def test_source_foreign_keys_preserved_with_unique_names(self, generated_sql):
        """Both source FKs survive, each with its own constraint name -
        never a duplicate, never merged, never dropped."""
        fk_statements = re.findall(
            r"ADD CONSTRAINT `([^`]+)`\s+FOREIGN KEY", generated_sql
        )
        assert len(fk_statements) == 2
        assert len(set(fk_statements)) == 2, "Foreign key constraint names must be unique"

        assert "REFERENCES `dblearn`.`bronze`.`customer`(`customer_id`)" in generated_sql
        assert "REFERENCES `dblearn`.`bronze`.`product`(`product_id`)" in generated_sql

    def test_no_invented_constraints(self, generated_sql):
        """Only the constraints traceable to source metadata appear: three
        primary keys and two foreign keys. Nothing else - no CHECK, no
        UNIQUE, no surprise constraint the source never declared. Checked
        against the executable SQL only - an index recommendation comment
        is free to say "UNIQUE INDEX" in prose without that being executed."""
        executable = _executable_only(generated_sql)
        assert executable.count("PRIMARY KEY") == 3
        assert executable.count("FOREIGN KEY") == 2
        assert "CHECK" not in executable
        assert "UNIQUE" not in executable

    def test_decimal_precision_and_scale_preserved_from_source(self, generated_sql):
        """DB2 DECIMAL(10,2) survives to Databricks DECIMAL(10,2) - not the
        generic AMOUNT domain's default of DECIMAL(18,2)."""
        assert "`total` DECIMAL(10,2)" in generated_sql
        assert "DECIMAL(18,2)" not in generated_sql

    def test_db2_integer_types_use_narrow_databricks_types(self, generated_sql):
        """DB2 BIGINT columns map to BIGINT; DB2 INTEGER maps to INT."""
        assert "`customer_id` BIGINT" in generated_sql
        assert "`product_id` INT" in generated_sql

    def test_db2_char_and_graphic_types_map_to_string_without_length(self, generated_sql):
        """DB2 CHAR(20) and GRAPHIC(50) both map to Databricks STRING, with
        no length constraint (Databricks STRING has none)."""
        assert "`product_label` STRING" in generated_sql
        assert "`description` STRING" in generated_sql
        assert "STRING(" not in generated_sql

    def test_db2_date_type_preserved(self, generated_sql):
        assert "`order_date` DATE" in generated_sql

    def test_no_create_index(self, generated_sql):
        """No executable CREATE INDEX - an index recommendation may still
        explain, in a comment, that Delta Lake has none."""
        executable = _executable_only(generated_sql)
        assert "CREATE INDEX" not in executable.upper()
        assert "CREATE UNIQUE INDEX" not in executable.upper()

        # The recommendation itself is preserved, just as a comment.
        assert any(
            block.strip().startswith("--") and "idx_" in block
            for block in generated_sql.split("\n\n")
        )

    def test_no_postgresql_or_db2_physical_syntax(self, generated_sql):
        """No source-database-specific executable syntax leaks into the
        generated Databricks SQL."""
        forbidden = [
            "COLLATE",
            "TABLESPACE",
            "OWNER TO",
            "USING BTREE",
            "::regclass",
            "CREATE SEQUENCE",
            "BUFFERPOOL",
            "CLUSTERED BY",
        ]
        upper_sql = generated_sql.upper()
        for token in forbidden:
            assert token.upper() not in upper_sql, f"Found forbidden syntax: {token}"

    def test_create_table_uses_if_not_exists(self, generated_sql):
        """Every CREATE TABLE is safe to rerun."""
        create_statements = re.findall(r"CREATE TABLE[^\n]*", generated_sql)
        assert len(create_statements) == 3
        assert all(s.startswith("CREATE TABLE IF NOT EXISTS") for s in create_statements)

    def test_no_executable_clustering_by_default(self, generated_sql):
        """Without enable_clustering, no CREATE TABLE gets an executable
        PARTITIONED BY / CLUSTER BY clause - the heuristic recommendation
        may still appear as a comment (checked separately)."""
        for stmt in generated_sql.split("\n\n"):
            if stmt.strip().startswith("CREATE TABLE"):
                assert "PARTITIONED BY" not in stmt
                assert "CLUSTER BY" not in stmt

    def test_all_statements_well_formed(self, generated_sql):
        """Every executable statement ends with a semicolon; every quoted
        identifier is non-empty."""
        assert "``" not in generated_sql
        for line in generated_sql.split("\n\n"):
            stripped = line.strip()
            if not stripped or stripped.startswith("--"):
                continue
            assert stripped.endswith(";"), f"Statement not terminated: {stripped[:100]!r}"
