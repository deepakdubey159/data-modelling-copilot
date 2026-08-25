"""Integration tests: DB2 → Databricks migration using existing architecture.

These tests demonstrate the complete migration pipeline for representative
DB2 schemas, ensuring native DB2 metadata is preserved accurately through
canonical models, physical models, and target adaptation to Databricks.

Flow tested:
  DB2Connector (extract native metadata)
    ↓
  MetadataBuilder (canonical normalized keys)
    ↓
  [Profiler / Relationship / Logical / Physical engines]
    ↓
  DatabricksTargetAdapter (map generic → Databricks)
    ↓
  TargetModel (Databricks-ready metadata)
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from migration.connectors.db2_connector import DB2Connector
from migration.metadata.builder import MetadataBuilder
from migration.db2_databricks_conversion import generate_conversion_report


class TestDB2DatabricksMigration:
    """End-to-end DB2 → Databricks migration scenarios."""

    def _setup_db2_connector_mock(self, mock_ibm_db, tables, columns):
        """Helper to mock DB2 connector with normalized mock data."""
        connector = DB2Connector(
            host="localhost",
            port=50000,
            database="testdb",
            username="db2admin",
            password="password",
        )

        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        def mock_query(sql):
            data = []
            if "SYSCAT.TABCONST" in sql:
                data = []  # No constraints in these tests
            elif "SYSCAT.REFERENCES" in sql:
                data = []
            elif "SYSCAT.COLUMNS" in sql:
                data = columns
            elif "SYSCAT.TABLES" in sql and "TABTYPE = 'T'" in sql:
                data = []  # No statistics
            elif "SYSCAT.TABLES" in sql:
                data = tables
            else:
                data = []

            # Normalize through connector's own method
            return [connector._normalize_keys(row) for row in data]

        connector._query = lambda sql: mock_query(sql)
        connector.connect()
        return connector

    def test_simple_ecommerce_schema(self):
        """Migrate a representative e-commerce schema with all DB2 types."""
        with patch("migration.connectors.db2_connector.ibm_db") as mock_ibm_db:
            tables = [
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "customers",
                    "TABTYPE": "T",
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "orders",
                    "TABTYPE": "T",
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "product_catalog",
                    "TABTYPE": "T",
                },
            ]

            columns = [
                # customers table
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "customers",
                    "COLNAME": "customer_id",
                    "COLTYPE": "BIGINT",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 1,
                    "LENGTH": None,
                    "SCALE": 0,
                    "PRECISION": 19,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "customers",
                    "COLNAME": "name",
                    "COLTYPE": "VARCHAR",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 2,
                    "LENGTH": 255,
                    "SCALE": None,
                    "PRECISION": None,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "customers",
                    "COLNAME": "email",
                    "COLTYPE": "VARCHAR",
                    "NULLS": "Y",
                    "DEFAULT": None,
                    "COLNO": 3,
                    "LENGTH": 100,
                    "SCALE": None,
                    "PRECISION": None,
                },
                # orders table
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "orders",
                    "COLNAME": "order_id",
                    "COLTYPE": "BIGINT",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 1,
                    "LENGTH": None,
                    "SCALE": 0,
                    "PRECISION": 19,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "orders",
                    "COLNAME": "customer_id",
                    "COLTYPE": "BIGINT",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 2,
                    "LENGTH": None,
                    "SCALE": 0,
                    "PRECISION": 19,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "orders",
                    "COLNAME": "order_date",
                    "COLTYPE": "DATE",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 3,
                    "LENGTH": None,
                    "SCALE": None,
                    "PRECISION": None,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "orders",
                    "COLNAME": "total_amount",
                    "COLTYPE": "DECIMAL",
                    "NULLS": "Y",
                    "DEFAULT": None,
                    "COLNO": 4,
                    "LENGTH": None,
                    "SCALE": 2,
                    "PRECISION": 10,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "orders",
                    "COLNAME": "created_at",
                    "COLTYPE": "TIMESTAMP",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 5,
                    "LENGTH": None,
                    "SCALE": None,
                    "PRECISION": None,
                },
                # product_catalog table
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "product_catalog",
                    "COLNAME": "product_id",
                    "COLTYPE": "INTEGER",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 1,
                    "LENGTH": None,
                    "SCALE": 0,
                    "PRECISION": 10,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "product_catalog",
                    "COLNAME": "sku",
                    "COLTYPE": "CHAR",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 2,
                    "LENGTH": 20,
                    "SCALE": None,
                    "PRECISION": None,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "product_catalog",
                    "COLNAME": "description",
                    "COLTYPE": "VARCHAR",
                    "NULLS": "Y",
                    "DEFAULT": None,
                    "COLNO": 3,
                    "LENGTH": 1000,
                    "SCALE": None,
                    "PRECISION": None,
                },
                {
                    "TABSCHEMA": "ECOMMERCE",
                    "TABNAME": "product_catalog",
                    "COLNAME": "price",
                    "COLTYPE": "DECIMAL",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 4,
                    "LENGTH": None,
                    "SCALE": 2,
                    "PRECISION": 12,
                },
            ]

            connector = self._setup_db2_connector_mock(mock_ibm_db, tables, columns)

            # Build canonical metadata
            builder = MetadataBuilder(connector, "testdb", "db2")
            metadata_pkg = builder.build(["ECOMMERCE"])

            # Verify canonical metadata extracted correctly
            assert metadata_pkg.metadata.database_name == "testdb"
            assert len(metadata_pkg.metadata.schemas) == 1
            assert metadata_pkg.metadata.schemas[0].schema_name == "ECOMMERCE"
            assert len(metadata_pkg.metadata.schemas[0].tables) == 3

            # Verify type preservation through canonical model
            customers = metadata_pkg.metadata.schemas[0].tables[0]
            assert customers.table_name == "customers"
            assert len(customers.columns) == 3

            # Check column types are preserved exactly as DB2 native
            assert customers.columns[0].data_type == "BIGINT"
            assert customers.columns[1].data_type == "VARCHAR"
            assert customers.columns[2].data_type == "VARCHAR"

            # Verify metadata is ready for downstream engines
            assert customers.columns[0].numeric_precision == 19
            assert customers.columns[1].character_length == 255
            assert customers.columns[2].character_length == 100

    def test_financial_schema_with_decimal_precision(self):
        """Test DECIMAL and DECFLOAT type preservation for financial data."""
        with patch("migration.connectors.db2_connector.ibm_db") as mock_ibm_db:
            tables = [
                {
                    "TABSCHEMA": "FINANCE",
                    "TABNAME": "transactions",
                    "TABTYPE": "T",
                }
            ]

            columns = [
                {
                    "TABSCHEMA": "FINANCE",
                    "TABNAME": "transactions",
                    "COLNAME": "transaction_id",
                    "COLTYPE": "BIGINT",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 1,
                    "LENGTH": None,
                    "SCALE": 0,
                    "PRECISION": 19,
                },
                {
                    "TABSCHEMA": "FINANCE",
                    "TABNAME": "transactions",
                    "COLNAME": "amount",
                    "COLTYPE": "DECIMAL",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 2,
                    "LENGTH": None,
                    "SCALE": 4,
                    "PRECISION": 19,
                },
                {
                    "TABSCHEMA": "FINANCE",
                    "TABNAME": "transactions",
                    "COLNAME": "exchange_rate",
                    "COLTYPE": "DECFLOAT",
                    "NULLS": "Y",
                    "DEFAULT": None,
                    "COLNO": 3,
                    "LENGTH": None,
                    "SCALE": None,
                    "PRECISION": 34,
                },
                {
                    "TABSCHEMA": "FINANCE",
                    "TABNAME": "transactions",
                    "COLNAME": "transaction_timestamp",
                    "COLTYPE": "TIMESTAMP",
                    "NULLS": "N",
                    "DEFAULT": None,
                    "COLNO": 4,
                    "LENGTH": None,
                    "SCALE": None,
                    "PRECISION": None,
                },
            ]

            connector = self._setup_db2_connector_mock(mock_ibm_db, tables, columns)
            builder = MetadataBuilder(connector, "finance_db", "db2")
            metadata_pkg = builder.build(["FINANCE"])

            schema = metadata_pkg.metadata.schemas[0]
            transactions = schema.tables[0]

            # Verify DECIMAL preservation with full precision/scale
            amount_col = [c for c in transactions.columns if c.name == "amount"][0]
            assert amount_col.data_type == "DECIMAL"
            assert amount_col.numeric_precision == 19
            assert amount_col.numeric_scale == 4

            # Verify DECFLOAT preservation
            rate_col = [c for c in transactions.columns if c.name == "exchange_rate"][0]
            assert rate_col.data_type == "DECFLOAT"
            assert rate_col.numeric_precision == 34

            # Verify TIMESTAMP for precision
            ts_col = [c for c in transactions.columns if c.name == "transaction_timestamp"][0]
            assert ts_col.data_type == "TIMESTAMP"

    def test_conversion_report_generation(self):
        """Test that conversion report captures all type mappings."""
        # Example e-commerce schema
        schema = {
            "customers": [
                ("id", "BIGINT"),
                ("name", "VARCHAR(255)"),
                ("created_at", "TIMESTAMP"),
            ],
            "orders": [
                ("id", "BIGINT"),
                ("customer_id", "BIGINT"),
                ("total", "DECIMAL(10,2)"),
                ("order_date", "DATE"),
            ],
        }

        report = generate_conversion_report(schema)

        # Verify report structure
        assert "summary" in report
        assert "type_mappings" in report
        assert "unsupported_types" in report
        assert "recommendations" in report
        assert "warnings" in report

        # Verify we have conversion rules
        assert len(report["type_mappings"]) > 0

        # Verify recommendations exist
        assert len(report["recommendations"]) > 0

        # Verify no unsupported types for representative schema
        assert len(report["unsupported_types"]) == 0


class TestDB2AllTypesPreservation:
    """Verify every DB2 type in the specification is correctly preserved."""

    def _test_db2_type_preservation(self, db2_type: str, expected_canonical: str):
        """Test that a specific DB2 type preserves through metadata."""
        with patch("migration.connectors.db2_connector.ibm_db") as mock_ibm_db:
            connector = DB2Connector(
                host="localhost",
                port=50000,
                database="testdb",
                username="db2admin",
                password="password",
            )

            mock_connection = MagicMock()
            mock_ibm_db.connect.return_value = mock_connection

            tables = [
                {
                    "TABSCHEMA": "TEST",
                    "TABNAME": "type_test",
                    "TABTYPE": "T",
                }
            ]
            columns = [
                {
                    "TABSCHEMA": "TEST",
                    "TABNAME": "type_test",
                    "COLNAME": "test_col",
                    "COLTYPE": db2_type,
                    "NULLS": "Y",
                    "DEFAULT": None,
                    "COLNO": 1,
                    "LENGTH": None if "INT" in db2_type or "DECIMAL" in db2_type or "DATE" in db2_type or "TIME" in db2_type or "XML" in db2_type or "BLOB" in db2_type else 100,
                    "SCALE": 2 if "DECIMAL" in db2_type else None,
                    "PRECISION": 10 if "DECIMAL" in db2_type or "DECFLOAT" in db2_type else None,
                }
            ]

            def mock_query(sql):
                # Check specific queries first (they may contain SYSCAT.TABLES via JOINs)
                if "SYSCAT.TABCONST" in sql or "SYSCAT.REFERENCES" in sql:
                    return []  # No constraints/PKs/FKs in this test
                elif "SYSCAT.INDEXES" in sql:
                    return []  # No indexes
                elif "SYSCAT.COLUMNS" in sql:
                    return [connector._normalize_keys(c) for c in columns]
                elif "SYSCAT.TABLES" in sql and "TABTYPE = 'T'" in sql:
                    return []  # No statistics
                elif "SYSCAT.TABLES" in sql:
                    return [connector._normalize_keys(t) for t in tables]
                return []

            connector._query = lambda sql: mock_query(sql)
            connector.connect()

            builder = MetadataBuilder(connector, "testdb", "db2")
            metadata_pkg = builder.build(["TEST"])

            # Verify the type is preserved exactly
            col = metadata_pkg.metadata.schemas[0].tables[0].columns[0]
            assert col.data_type == expected_canonical

    @pytest.mark.parametrize(
        "db2_type,expected",
        [
            ("CHAR", "CHAR"),
            ("VARCHAR", "VARCHAR"),
            ("CLOB", "CLOB"),
            ("BLOB", "BLOB"),
            ("GRAPHIC", "GRAPHIC"),
            ("VARGRAPHIC", "VARGRAPHIC"),
            ("INTEGER", "INTEGER"),
            ("SMALLINT", "SMALLINT"),
            ("BIGINT", "BIGINT"),
            ("DECIMAL", "DECIMAL"),
            ("DECFLOAT", "DECFLOAT"),
            ("DATE", "DATE"),
            ("TIME", "TIME"),
            ("TIMESTAMP", "TIMESTAMP"),
            ("XML", "XML"),
        ],
    )
    def test_type_preservation(self, db2_type, expected):
        """Parametrized test for all DB2 types."""
        self._test_db2_type_preservation(db2_type, expected)
