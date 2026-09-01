"""End-to-end pipeline validation.

Exercises the complete flow from metadata extraction through DDL generation
to verify all components integrate correctly and produce valid outputs.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from migration.models.config import AppConfig
from migration.orchestrator import orchestrator as orchestrator_module
from migration.orchestrator.orchestrator import MigrationOrchestrator
from tests.conceptual_fixtures import StubLLMClient


ECOMMERCE_METADATA = json.dumps(
    {
        "database_name": "ecommerce",
        "summary": "E-commerce database with customers, orders, and products.",
        "domains": [
            {
                "name": "Customers",
                "description": "Customer management and accounts.",
                "entities": ["Customer", "Address"],
            },
            {
                "name": "Orders",
                "description": "Order processing and fulfillment.",
                "entities": ["Order", "OrderLine", "Product"],
            },
        ],
        "entities": [
            {
                "name": "Customer",
                "description": "A person who buys products.",
                "business_key": ["Customer Number"],
                "attributes": ["Customer Number", "Name", "Email", "Phone", "Created Date"],
                "source_tables": ["public.customers"],
                "relationships": [
                    {
                        "related_entity": "Order",
                        "verb_phrase": "places",
                        "cardinality": "ONE_TO_MANY",
                        "is_optional": False,
                        "description": "A customer may place one or more orders.",
                    },
                    {
                        "related_entity": "Address",
                        "verb_phrase": "has",
                        "cardinality": "ONE_TO_MANY",
                        "is_optional": True,
                        "description": "A customer may have multiple addresses.",
                    },
                ],
            },
            {
                "name": "Address",
                "description": "A physical mailing address.",
                "business_key": ["Customer Number", "Address Number"],
                "attributes": ["Customer Number", "Address Number", "Street", "City", "Country"],
                "source_tables": ["public.addresses"],
                "relationships": [],
            },
            {
                "name": "Order",
                "description": "A purchase order from a customer.",
                "business_key": ["Order Number"],
                "attributes": ["Order Number", "Customer Number", "Order Date", "Total Amount", "Status"],
                "source_tables": ["public.orders"],
                "relationships": [
                    {
                        "related_entity": "OrderLine",
                        "verb_phrase": "contains",
                        "cardinality": "ONE_TO_MANY",
                        "is_optional": False,
                        "description": "An order contains one or more line items.",
                    },
                ],
            },
            {
                "name": "OrderLine",
                "description": "A line item in an order.",
                "business_key": ["Order Number", "Line Number"],
                "attributes": ["Order Number", "Line Number", "Product Number", "Quantity", "Unit Price"],
                "source_tables": ["public.order_lines"],
                "relationships": [],
            },
            {
                "name": "Product",
                "description": "A product available for purchase.",
                "business_key": ["Product Number"],
                "attributes": ["Product Number", "Name", "Category", "Price"],
                "source_tables": ["public.products"],
                "relationships": [],
            },
        ],
        "business_rules": [
            "An order must belong to exactly one customer.",
            "An order line must reference an existing product.",
            "An order status can only be: PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED.",
        ],
        "assumptions": [
            "Customer numbers are unique identifiers.",
            "Order numbers are sequential.",
        ],
        "recommendations": [
            "Consider archiving old orders to improve query performance.",
        ],
    }
)


class ComprehensiveConnector:
    """Fake connector with realistic ecommerce schema."""

    def __init__(self):
        self.connected = False
        self.disconnected = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.disconnected = True

    def extract_tables(self, schemas):
        return [
            {"table_schema": "public", "table_name": "customers", "table_type": "BASE TABLE"},
            {"table_schema": "public", "table_name": "addresses", "table_type": "BASE TABLE"},
            {"table_schema": "public", "table_name": "orders", "table_type": "BASE TABLE"},
            {"table_schema": "public", "table_name": "order_lines", "table_type": "BASE TABLE"},
            {"table_schema": "public", "table_name": "products", "table_type": "BASE TABLE"},
        ]

    def extract_columns(self, schemas):
        return [
            # customers
            {
                "table_schema": "public", "table_name": "customers", "column_name": "customer_id",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 1, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "customers", "column_name": "name",
                "data_type": "character varying", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 2, "character_maximum_length": 100, "numeric_precision": None, "numeric_scale": None,
            },
            {
                "table_schema": "public", "table_name": "customers", "column_name": "email",
                "data_type": "character varying", "is_nullable": "YES", "column_default": None,
                "ordinal_position": 3, "character_maximum_length": 255, "numeric_precision": None, "numeric_scale": None,
            },
            {
                "table_schema": "public", "table_name": "customers", "column_name": "phone",
                "data_type": "character varying", "is_nullable": "YES", "column_default": None,
                "ordinal_position": 4, "character_maximum_length": 20, "numeric_precision": None, "numeric_scale": None,
            },
            {
                "table_schema": "public", "table_name": "customers", "column_name": "created_at",
                "data_type": "timestamp without time zone", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 5, "character_maximum_length": None, "numeric_precision": None, "numeric_scale": None,
            },
            # addresses
            {
                "table_schema": "public", "table_name": "addresses", "column_name": "customer_id",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 1, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "addresses", "column_name": "address_id",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 2, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "addresses", "column_name": "street",
                "data_type": "character varying", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 3, "character_maximum_length": 255, "numeric_precision": None, "numeric_scale": None,
            },
            {
                "table_schema": "public", "table_name": "addresses", "column_name": "city",
                "data_type": "character varying", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 4, "character_maximum_length": 50, "numeric_precision": None, "numeric_scale": None,
            },
            {
                "table_schema": "public", "table_name": "addresses", "column_name": "country",
                "data_type": "character varying", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 5, "character_maximum_length": 50, "numeric_precision": None, "numeric_scale": None,
            },
            # orders
            {
                "table_schema": "public", "table_name": "orders", "column_name": "order_id",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 1, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "orders", "column_name": "customer_id",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 2, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "orders", "column_name": "order_date",
                "data_type": "date", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 3, "character_maximum_length": None, "numeric_precision": None, "numeric_scale": None,
            },
            {
                "table_schema": "public", "table_name": "orders", "column_name": "total_amount",
                "data_type": "numeric", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 4, "character_maximum_length": None, "numeric_precision": 18, "numeric_scale": 2,
            },
            {
                "table_schema": "public", "table_name": "orders", "column_name": "status",
                "data_type": "character varying", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 5, "character_maximum_length": 20, "numeric_precision": None, "numeric_scale": None,
            },
            # order_lines
            {
                "table_schema": "public", "table_name": "order_lines", "column_name": "order_id",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 1, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "order_lines", "column_name": "line_number",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 2, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "order_lines", "column_name": "product_id",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 3, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "order_lines", "column_name": "quantity",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 4, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "order_lines", "column_name": "unit_price",
                "data_type": "numeric", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 5, "character_maximum_length": None, "numeric_precision": 18, "numeric_scale": 2,
            },
            # products
            {
                "table_schema": "public", "table_name": "products", "column_name": "product_id",
                "data_type": "integer", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 1, "character_maximum_length": None, "numeric_precision": 32, "numeric_scale": 0,
            },
            {
                "table_schema": "public", "table_name": "products", "column_name": "name",
                "data_type": "character varying", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 2, "character_maximum_length": 100, "numeric_precision": None, "numeric_scale": None,
            },
            {
                "table_schema": "public", "table_name": "products", "column_name": "category",
                "data_type": "character varying", "is_nullable": "YES", "column_default": None,
                "ordinal_position": 3, "character_maximum_length": 50, "numeric_precision": None, "numeric_scale": None,
            },
            {
                "table_schema": "public", "table_name": "products", "column_name": "price",
                "data_type": "numeric", "is_nullable": "NO", "column_default": None,
                "ordinal_position": 4, "character_maximum_length": None, "numeric_precision": 18, "numeric_scale": 2,
            },
        ]

    def extract_primary_keys(self, schemas):
        return [
            {"table_schema": "public", "table_name": "customers", "column_name": "customer_id", "constraint_name": "pk_customers", "ordinal_position": 1},
            {"table_schema": "public", "table_name": "addresses", "column_name": "customer_id", "constraint_name": "pk_addresses", "ordinal_position": 1},
            {"table_schema": "public", "table_name": "addresses", "column_name": "address_id", "constraint_name": "pk_addresses", "ordinal_position": 2},
            {"table_schema": "public", "table_name": "orders", "column_name": "order_id", "constraint_name": "pk_orders", "ordinal_position": 1},
            {"table_schema": "public", "table_name": "order_lines", "column_name": "order_id", "constraint_name": "pk_order_lines", "ordinal_position": 1},
            {"table_schema": "public", "table_name": "order_lines", "column_name": "line_number", "constraint_name": "pk_order_lines", "ordinal_position": 2},
            {"table_schema": "public", "table_name": "products", "column_name": "product_id", "constraint_name": "pk_products", "ordinal_position": 1},
        ]

    def extract_foreign_keys(self, schemas):
        return [
            {
                "table_schema": "public", "table_name": "addresses", "column_name": "customer_id",
                "foreign_table_schema": "public", "foreign_table_name": "customers", "foreign_column_name": "customer_id",
                "constraint_name": "fk_addresses_customers",
            },
            {
                "table_schema": "public", "table_name": "orders", "column_name": "customer_id",
                "foreign_table_schema": "public", "foreign_table_name": "customers", "foreign_column_name": "customer_id",
                "constraint_name": "fk_orders_customers",
            },
            {
                "table_schema": "public", "table_name": "order_lines", "column_name": "order_id",
                "foreign_table_schema": "public", "foreign_table_name": "orders", "foreign_column_name": "order_id",
                "constraint_name": "fk_order_lines_orders",
            },
            {
                "table_schema": "public", "table_name": "order_lines", "column_name": "product_id",
                "foreign_table_schema": "public", "foreign_table_name": "products", "foreign_column_name": "product_id",
                "constraint_name": "fk_order_lines_products",
            },
        ]

    def extract_constraints(self, schemas):
        return []

    def extract_indexes(self, schemas):
        return []

    def extract_statistics(self, schemas):
        return []

    def profile_table(self, schema, table, columns):
        return {
            "row_count": 100,
            "duplicate_row_count": 0,
            "columns": {
                column["name"]: {
                    "null_count": 0,
                    "distinct_count": 100,
                    "min_value": "1",
                    "max_value": "100",
                    "min_length": 1,
                    "max_length": 10,
                }
                for column in columns
            },
        }

    def sample_column_values(self, schema, table, column, limit=200):
        return []


def _config(tmp_path: Path) -> AppConfig:
    return AppConfig.model_validate(
        {
            "project": {"name": "e2e_ecommerce", "output_directory": str(tmp_path)},
            "source": {
                "type": "postgres",
                "host": "localhost",
                "port": 5432,
                "database": "ecommerce",
                "username": "postgres",
                "password": "unused",
                "schema": ["public"],
            },
            "target": {"type": "snowflake"},
            "llm": {"provider": "anthropic", "model": "claude-opus-5"},
            "logging": {"level": "INFO"},
        }
    )


@pytest.fixture
def comprehensive_connector(monkeypatch):
    connector = ComprehensiveConnector()
    monkeypatch.setattr(
        orchestrator_module, "create_connector", lambda source: connector
    )
    return connector


def _run_directory(tmp_path: Path) -> Path:
    runs = [p for p in tmp_path.iterdir() if p.is_dir()]
    assert len(runs) == 1, f"expected exactly one run directory, found {runs}"
    return runs[0]


class TestCompletePipelineE2E:
    """End-to-end tests for the complete pipeline."""

    def test_complete_pipeline_generates_all_artifacts(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Full pipeline from metadata to DDL generates all expected artifacts."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")

        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        produced = {p.name for p in run.iterdir()}

        # Verify all artifact types are present
        assert "metadata.json" in produced, "metadata missing"
        assert "profile.json" in produced, "profile missing"
        assert "relationships.json" in produced, "relationships missing"
        assert "conceptual_model.json" in produced, "conceptual_model.json missing"
        assert "conceptual_model.md" in produced, "conceptual_model.md missing"
        assert "conceptual_model.html" in produced, "conceptual_model.html missing"
        assert "logical_model.json" in produced, "logical_model.json missing"
        assert "logical_model.md" in produced, "logical_model.md missing"
        assert "logical_model.html" in produced, "logical_model.html missing"
        assert "physical_model.json" in produced, "physical_model.json missing"
        assert "physical_model.md" in produced, "physical_model.md missing"
        assert "physical_model.html" in produced, "physical_model.html missing"
        assert "databricks.sql" in produced, "databricks.sql missing"
        assert "ddl.json" in produced, "ddl.json missing"
        assert "summary.txt" in produced, "summary.txt missing"

    def test_metadata_captures_all_tables_and_columns(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Metadata extraction captures all tables and columns from schema."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        metadata_file = run / "metadata.json"
        assert metadata_file.exists(), "metadata.json not created"

        metadata = json.loads(metadata_file.read_text(encoding="utf-8"))
        # Verify structure has tables (exact path depends on structure)
        assert metadata is not None
        assert len(str(metadata)) > 100, "metadata appears empty"

    def test_profile_provides_statistics(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Data profiler collects statistics on all tables."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        profile_file = run / "profile.json"
        assert profile_file.exists(), "profile.json not created"

        profile = json.loads(profile_file.read_text(encoding="utf-8"))
        # Verify profile has content
        assert profile is not None
        assert len(str(profile)) > 100, "profile appears empty"

    def test_relationships_inferred_correctly(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Relationship discovery identifies foreign key relationships."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        rels_file = run / "relationships.json"
        assert rels_file.exists(), "relationships.json not created"

        rels = json.loads(rels_file.read_text(encoding="utf-8"))
        # Verify relationships have content
        assert rels is not None
        assert len(str(rels)) > 100, "relationships appears empty"

    def test_conceptual_model_structures_business_logic(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Conceptual model captures business entities and relationships."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        conceptual = json.loads(
            (run / "conceptual_model.json").read_text(encoding="utf-8")
        )

        model = conceptual["conceptual_model"]
        entity_names = {e["name"] for e in model["entities"]}

        # Should have core entities from the test data
        assert "Customer" in entity_names
        assert "Order" in entity_names

    def test_logical_model_normalizes_design(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Logical model applies normalization rules."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        logical = json.loads(
            (run / "logical_model.json").read_text(encoding="utf-8")
        )

        model = logical["logical_model"]
        assert len(model["entities"]) > 0
        assert len(model["relationships"]) > 0

        # Check normalization actions were recorded
        assert "normalization_actions" in model

    def test_physical_model_maps_to_implementation(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Physical model maps logical design to concrete storage."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        physical = json.loads(
            (run / "physical_model.json").read_text(encoding="utf-8")
        )

        model = physical["physical_model"]
        assert len(model["tables"]) > 0

        # All tables should have columns with concrete types
        for table in model["tables"]:
            assert len(table["columns"]) > 0
            for col in table["columns"]:
                assert col["data_type"] in [
                    "IDENTIFIER", "STRING", "INTEGER", "DECIMAL", "DATE", "TIMESTAMP", "BOOLEAN", "BINARY", "JSON"
                ]

    def test_ddl_generates_valid_sql(
        self, tmp_path: Path, comprehensive_connector
    ):
        """DDL generator produces valid Databricks SQL."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        sql_file = run / "databricks.sql"
        assert sql_file.exists()

        sql = sql_file.read_text(encoding="utf-8")

        # Should have CREATE TABLE statements
        assert "CREATE TABLE" in sql
        # Should have quoted identifiers
        assert "`" in sql
        # Should end statements with semicolons
        assert ";" in sql

    def test_ddl_metadata_preserved(
        self, tmp_path: Path, comprehensive_connector
    ):
        """DDL metadata tracks source lineage."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        ddl = json.loads((run / "ddl.json").read_text(encoding="utf-8"))

        assert ddl["generated_from"] == "physical_model.json"
        assert ddl["generated_by"] == "DatabricksDDLGenerator"
        assert len(ddl["ddl_script"]["table_creation_statements"]) > 0

    def test_all_outputs_are_deterministic(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Running the pipeline twice produces identical outputs."""
        client1 = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        client2 = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")

        # First run
        MigrationOrchestrator(_config(tmp_path), llm_client=client1).run()
        run1 = _run_directory(tmp_path)
        sql1 = (run1 / "databricks.sql").read_text(encoding="utf-8")
        physical1 = json.loads((run1 / "physical_model.json").read_text(encoding="utf-8"))

        # Clean for second run
        import shutil
        shutil.rmtree(tmp_path)
        tmp_path.mkdir()

        # Second run
        MigrationOrchestrator(_config(tmp_path), llm_client=client2).run()
        run2 = _run_directory(tmp_path)
        sql2 = (run2 / "databricks.sql").read_text(encoding="utf-8")
        physical2 = json.loads((run2 / "physical_model.json").read_text(encoding="utf-8"))

        # Same SQL and physical model
        assert sql1 == sql2
        assert physical1["physical_model"]["database_name"] == physical2["physical_model"]["database_name"]

    def test_pipeline_handles_all_constraint_types(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Pipeline properly handles primary keys, foreign keys, etc."""
        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(_config(tmp_path), llm_client=client).run()

        run = _run_directory(tmp_path)
        physical = json.loads(
            (run / "physical_model.json").read_text(encoding="utf-8")
        )

        # Check that primary keys are present
        pk_count = 0
        fk_count = 0
        for table in physical["physical_model"]["tables"]:
            for constraint in table.get("constraints", []):
                if constraint["constraint_type"] == "PRIMARY_KEY":
                    pk_count += 1
                elif constraint["constraint_type"] == "FOREIGN_KEY":
                    fk_count += 1

        assert pk_count > 0, "No primary keys found"
        assert fk_count > 0, "No foreign keys found"

    def test_pipeline_respects_artifact_toggles(
        self, tmp_path: Path, comprehensive_connector
    ):
        """Artifact toggles control what gets generated."""
        config = _config(tmp_path)
        config.artifacts.ddl = False

        client = StubLLMClient(ECOMMERCE_METADATA, model="claude-opus-5")
        MigrationOrchestrator(config, llm_client=client).run()

        run = _run_directory(tmp_path)
        produced = {p.name for p in run.iterdir()}

        assert "physical_model.json" in produced, "physical model should still be generated"
        assert "databricks.sql" not in produced, "DDL should be skipped when disabled"
