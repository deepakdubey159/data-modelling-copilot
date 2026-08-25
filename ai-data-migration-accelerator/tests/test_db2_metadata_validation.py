"""Validation tests for DB2 connector output with MetadataBuilder.

Ensures DB2 connector produces output compatible with the canonical
metadata pipeline (MetadataBuilder).
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from migration.connectors.db2_connector import DB2Connector
from migration.metadata.builder import MetadataBuilder


@pytest.fixture
def db2_connector():
    return DB2Connector(
        host="localhost",
        port=50000,
        database="testdb",
        username="db2admin",
        password="password123",
    )


@pytest.fixture
def mock_ibm_db():
    with patch("migration.connectors.db2_connector.ibm_db") as mock:
        yield mock


class TestDB2MetadataValidation:
    """Validate DB2 connector output for MetadataBuilder compatibility."""

    def _setup_connector_mocks(
        self, db2_connector, mock_ibm_db, tables, columns, pks, fks, constraints, indexes, statistics
    ):
        """Setup mocks for full metadata extraction."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        # Setup query mock to return data based on SQL content. Order matters:
        # check the most specific SQL shapes first, since PK/FK/constraint
        # queries also reference SYSCAT.TABLES via JOINs.
        def mock_query(sql):
            if "SYSCAT.TABCONST" in sql and "TYPE = 'P'" in sql:
                data = pks
            elif "SYSCAT.REFERENCES" in sql:
                data = fks
            elif "SYSCAT.TABCONST" in sql:
                data = constraints
            elif "SYSCAT.INDEXES" in sql:
                data = indexes
            elif "SYSCAT.COLUMNS" in sql:
                data = columns
            elif "SYSCAT.TABLES" in sql and "TABTYPE = 'T'" in sql:
                data = statistics
            elif "SYSCAT.TABLES" in sql:
                data = tables
            else:
                data = []

            # Normalize keys the same way the real _query() method does,
            # so tests exercise the actual connector contract.
            return [db2_connector._normalize_keys(row) for row in data]

        db2_connector._query = mock_query
        db2_connector.connect()

    def test_builder_accepts_db2_table_metadata(self, db2_connector, mock_ibm_db):
        """MetadataBuilder can process DB2 table metadata."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "TABTYPE": "T",
            }
        ]
        columns = []
        pks = []
        fks = []
        constraints = []
        indexes = []
        statistics = []

        self._setup_connector_mocks(
            db2_connector, mock_ibm_db, tables, columns, pks, fks, constraints, indexes, statistics
        )

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        assert result.metadata.database_name == "testdb"
        assert result.metadata.source_database_type == "db2"
        assert len(result.metadata.schemas) == 1
        assert result.metadata.schemas[0].schema_name == "DB2ADMIN"
        assert len(result.metadata.schemas[0].tables) == 1
        assert result.metadata.schemas[0].tables[0].table_name == "customers"

    def test_builder_accepts_db2_column_metadata(self, db2_connector, mock_ibm_db):
        """MetadataBuilder correctly processes DB2 column metadata."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
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
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "COLNAME": "name",
                "COLTYPE": "VARCHAR",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 2,
                "LENGTH": 100,
                "SCALE": None,
                "PRECISION": None,
            },
        ]
        pks = []
        fks = []
        constraints = []
        indexes = []
        statistics = []

        self._setup_connector_mocks(
            db2_connector, mock_ibm_db, tables, columns, pks, fks, constraints, indexes, statistics
        )

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.columns) == 2

        col1 = table.columns[0]
        assert col1.name == "customer_id"
        assert col1.data_type == "BIGINT"
        assert col1.nullable is False
        assert col1.numeric_precision == 19

        col2 = table.columns[1]
        assert col2.name == "name"
        assert col2.data_type == "VARCHAR"
        assert col2.nullable is True
        assert col2.character_length == 100

    def test_builder_handles_db2_primary_keys(self, db2_connector, mock_ibm_db):
        """MetadataBuilder correctly processes DB2 primary keys."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "COLNAME": "customer_id",
                "COLTYPE": "BIGINT",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 19,
            }
        ]
        pks = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "COLNAME": "customer_id",
                "CONSTNAME": "pk_customers",
                "COLSEQ": 1,
            }
        ]
        fks = []
        constraints = []
        indexes = []
        statistics = []

        self._setup_connector_mocks(
            db2_connector, mock_ibm_db, tables, columns, pks, fks, constraints, indexes, statistics
        )

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.primary_keys) == 1
        assert table.primary_keys[0].constraint_name == "pk_customers"
        assert table.primary_keys[0].columns == ["customer_id"]

        # Column should be marked as PK
        col = table.columns[0]
        assert col.is_primary_key is True

    def test_builder_handles_db2_foreign_keys(self, db2_connector, mock_ibm_db):
        """MetadataBuilder correctly processes DB2 foreign keys."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "orders",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "orders",
                "COLNAME": "customer_id",
                "COLTYPE": "BIGINT",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 19,
            }
        ]
        pks = []
        fks = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "orders",
                "COLNAME": "customer_id",
                "REFTABSCHEMA": "DB2ADMIN",
                "REFTABNAME": "customers",
                "REFCOLNAME": "customer_id",
                "CONSTNAME": "fk_orders_customers",
            }
        ]
        constraints = []
        indexes = []
        statistics = []

        self._setup_connector_mocks(
            db2_connector, mock_ibm_db, tables, columns, pks, fks, constraints, indexes, statistics
        )

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.foreign_keys) == 1

        fk = table.foreign_keys[0]
        assert fk.constraint_name == "fk_orders_customers"
        assert fk.column == "customer_id"
        assert fk.referenced_table == "customers"
        assert fk.referenced_column == "customer_id"

        # Column should be marked as FK
        col = table.columns[0]
        assert col.is_foreign_key is True

    def test_db2_type_preservation(self, db2_connector, mock_ibm_db):
        """DB2 native types are preserved in canonical metadata."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "types_test",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "types_test",
                "COLNAME": "col_char",
                "COLTYPE": "CHAR",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": 10,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "types_test",
                "COLNAME": "col_varchar",
                "COLTYPE": "VARCHAR",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 2,
                "LENGTH": 255,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "types_test",
                "COLNAME": "col_integer",
                "COLTYPE": "INTEGER",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 3,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 10,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "types_test",
                "COLNAME": "col_decimal",
                "COLTYPE": "DECIMAL",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 4,
                "LENGTH": None,
                "SCALE": 2,
                "PRECISION": 10,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "types_test",
                "COLNAME": "col_date",
                "COLTYPE": "DATE",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 5,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "types_test",
                "COLNAME": "col_timestamp",
                "COLTYPE": "TIMESTAMP",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 6,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": None,
            },
        ]
        pks = []
        fks = []
        constraints = []
        indexes = []
        statistics = []

        self._setup_connector_mocks(
            db2_connector, mock_ibm_db, tables, columns, pks, fks, constraints, indexes, statistics
        )

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        expected_types = {
            "col_char": "CHAR",
            "col_varchar": "VARCHAR",
            "col_integer": "INTEGER",
            "col_decimal": "DECIMAL",
            "col_date": "DATE",
            "col_timestamp": "TIMESTAMP",
        }

        for col in table.columns:
            assert col.data_type == expected_types[col.name]

    def test_db2_constraint_handling(self, db2_connector, mock_ibm_db):
        """DB2 constraint metadata is correctly processed."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "users",
                "TABTYPE": "T",
            }
        ]
        columns = []
        pks = []
        fks = []
        constraints = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "users",
                "CONSTNAME": "u_email",
                "TYPE": "U",
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "users",
                "CONSTNAME": "chk_age",
                "TYPE": "C",
            },
        ]
        indexes = []
        statistics = []

        self._setup_connector_mocks(
            db2_connector, mock_ibm_db, tables, columns, pks, fks, constraints, indexes, statistics
        )

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.constraints) == 2


class TestDB2TypePreservation:
    """Test that native DB2 types are preserved accurately in canonical metadata.

    These tests ensure that all DB2 data types are extracted and canonicalized
    correctly for downstream logical/physical modelling.
    """

    def _setup_connector_mocks(
        self, db2_connector, mock_ibm_db, tables, columns, pks=None, fks=None, constraints=None, indexes=None, statistics=None
    ):
        """Setup mocks for full metadata extraction."""
        pks = pks or []
        fks = fks or []
        constraints = constraints or []
        indexes = indexes or []
        statistics = statistics or []

        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        # Setup query mock to return normalized data based on SQL content
        # Check more specific conditions first to avoid false matches
        def mock_query(sql):
            data = []
            if "SYSCAT.TABCONST" in sql and "TYPE = 'P'" in sql:
                data = pks
            elif "SYSCAT.REFERENCES" in sql:
                data = fks
            elif "SYSCAT.TABCONST" in sql:
                data = constraints
            elif "SYSCAT.INDEXES" in sql:
                data = indexes
            elif "SYSCAT.COLUMNS" in sql:
                data = columns
            elif "SYSCAT.TABLES" in sql and "TABTYPE = 'T'" in sql:
                data = statistics
            elif "SYSCAT.TABLES" in sql:
                data = tables

            # Normalize keys just like the real _query method does
            return [db2_connector._normalize_keys(row) for row in data]

        db2_connector._query = lambda sql: mock_query(sql)
        db2_connector.connect()

    def _mock_query_results(self, mock_ibm_db, data):
        """Mock query results."""
        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        mock_ibm_db.fetch_row.side_effect = [True] * len(data) + [False]
        mock_ibm_db.fetch_assoc.side_effect = data
        mock_ibm_db.free_stmt.return_value = None
        return data

    def _mock_query_results(self, mock_ibm_db, data):
        """Mock query results."""
        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        mock_ibm_db.fetch_row.side_effect = [True] * len(data) + [False]
        mock_ibm_db.fetch_assoc.side_effect = data
        mock_ibm_db.free_stmt.return_value = None
        return data

    def test_string_types_char_varchar_clob(self, db2_connector, mock_ibm_db):
        """String types CHAR, VARCHAR, CLOB are preserved correctly."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "string_test",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "string_test",
                "COLNAME": "col_char",
                "COLTYPE": "CHAR",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": 50,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "string_test",
                "COLNAME": "col_varchar",
                "COLTYPE": "VARCHAR",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 2,
                "LENGTH": 1000,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "string_test",
                "COLNAME": "col_clob",
                "COLTYPE": "CLOB",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 3,
                "LENGTH": 2147483647,  # DB2 CLOB max length
                "SCALE": None,
                "PRECISION": None,
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.columns) == 3

        # Verify CHAR
        char_col = table.columns[0]
        assert char_col.name == "col_char"
        assert char_col.data_type == "CHAR"
        assert char_col.nullable is False
        assert char_col.character_length == 50

        # Verify VARCHAR
        varchar_col = table.columns[1]
        assert varchar_col.name == "col_varchar"
        assert varchar_col.data_type == "VARCHAR"
        assert varchar_col.nullable is True
        assert varchar_col.character_length == 1000

        # Verify CLOB
        clob_col = table.columns[2]
        assert clob_col.name == "col_clob"
        assert clob_col.data_type == "CLOB"
        assert clob_col.nullable is True
        assert clob_col.character_length == 2147483647

    def test_graphic_types_graphic_vargraphic(self, db2_connector, mock_ibm_db):
        """Graphic types GRAPHIC and VARGRAPHIC are preserved correctly."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "graphic_test",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "graphic_test",
                "COLNAME": "col_graphic",
                "COLTYPE": "GRAPHIC",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": 100,  # Length in bytes for GRAPHIC
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "graphic_test",
                "COLNAME": "col_vargraphic",
                "COLTYPE": "VARGRAPHIC",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 2,
                "LENGTH": 1000,
                "SCALE": None,
                "PRECISION": None,
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.columns) == 2

        graphic_col = table.columns[0]
        assert graphic_col.name == "col_graphic"
        assert graphic_col.data_type == "GRAPHIC"
        assert graphic_col.character_length == 100

        vargraphic_col = table.columns[1]
        assert vargraphic_col.name == "col_vargraphic"
        assert vargraphic_col.data_type == "VARGRAPHIC"
        assert vargraphic_col.character_length == 1000

    def test_binary_type_blob(self, db2_connector, mock_ibm_db):
        """Binary type BLOB is preserved correctly."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "binary_test",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "binary_test",
                "COLNAME": "col_blob",
                "COLTYPE": "BLOB",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": 2147483647,  # DB2 BLOB max length
                "SCALE": None,
                "PRECISION": None,
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        blob_col = table.columns[0]
        assert blob_col.name == "col_blob"
        assert blob_col.data_type == "BLOB"
        assert blob_col.nullable is True
        assert blob_col.character_length == 2147483647

    def test_integer_types_smallint_integer_bigint(self, db2_connector, mock_ibm_db):
        """Integer types SMALLINT, INTEGER, BIGINT are preserved correctly."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "integer_test",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "integer_test",
                "COLNAME": "col_smallint",
                "COLTYPE": "SMALLINT",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 5,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "integer_test",
                "COLNAME": "col_integer",
                "COLTYPE": "INTEGER",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 2,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 10,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "integer_test",
                "COLNAME": "col_bigint",
                "COLTYPE": "BIGINT",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 3,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 19,
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.columns) == 3

        # Verify SMALLINT
        smallint_col = table.columns[0]
        assert smallint_col.name == "col_smallint"
        assert smallint_col.data_type == "SMALLINT"
        assert smallint_col.nullable is False
        assert smallint_col.numeric_precision == 5
        assert smallint_col.numeric_scale == 0

        # Verify INTEGER
        integer_col = table.columns[1]
        assert integer_col.name == "col_integer"
        assert integer_col.data_type == "INTEGER"
        assert integer_col.nullable is False
        assert integer_col.numeric_precision == 10
        assert integer_col.numeric_scale == 0

        # Verify BIGINT
        bigint_col = table.columns[2]
        assert bigint_col.name == "col_bigint"
        assert bigint_col.data_type == "BIGINT"
        assert bigint_col.nullable is False
        assert bigint_col.numeric_precision == 19
        assert bigint_col.numeric_scale == 0

    def test_decimal_types_decimal_decfloat(self, db2_connector, mock_ibm_db):
        """Decimal types DECIMAL and DECFLOAT are preserved correctly."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "decimal_test",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "decimal_test",
                "COLNAME": "col_decimal",
                "COLTYPE": "DECIMAL",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": 2,
                "PRECISION": 15,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "decimal_test",
                "COLNAME": "col_decfloat",
                "COLTYPE": "DECFLOAT",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 2,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": 34,  # DECFLOAT(34) is DB2's highest precision
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.columns) == 2

        # Verify DECIMAL
        decimal_col = table.columns[0]
        assert decimal_col.name == "col_decimal"
        assert decimal_col.data_type == "DECIMAL"
        assert decimal_col.nullable is True
        assert decimal_col.numeric_precision == 15
        assert decimal_col.numeric_scale == 2

        # Verify DECFLOAT
        decfloat_col = table.columns[1]
        assert decfloat_col.name == "col_decfloat"
        assert decfloat_col.data_type == "DECFLOAT"
        assert decfloat_col.nullable is True
        assert decfloat_col.numeric_precision == 34

    def test_temporal_types_date_time_timestamp(self, db2_connector, mock_ibm_db):
        """Temporal types DATE, TIME, TIMESTAMP are preserved correctly."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "temporal_test",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "temporal_test",
                "COLNAME": "col_date",
                "COLTYPE": "DATE",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "temporal_test",
                "COLNAME": "col_time",
                "COLTYPE": "TIME",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 2,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "temporal_test",
                "COLNAME": "col_timestamp",
                "COLTYPE": "TIMESTAMP",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 3,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": None,
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.columns) == 3

        # Verify DATE
        date_col = table.columns[0]
        assert date_col.name == "col_date"
        assert date_col.data_type == "DATE"
        assert date_col.nullable is True

        # Verify TIME
        time_col = table.columns[1]
        assert time_col.name == "col_time"
        assert time_col.data_type == "TIME"
        assert time_col.nullable is True

        # Verify TIMESTAMP
        timestamp_col = table.columns[2]
        assert timestamp_col.name == "col_timestamp"
        assert timestamp_col.data_type == "TIMESTAMP"
        assert timestamp_col.nullable is True

    def test_xml_type(self, db2_connector, mock_ibm_db):
        """XML type is preserved correctly."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "xml_test",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "xml_test",
                "COLNAME": "col_xml",
                "COLTYPE": "XML",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": None,
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        xml_col = table.columns[0]
        assert xml_col.name == "col_xml"
        assert xml_col.data_type == "XML"
        assert xml_col.nullable is True

    def test_comprehensive_type_mix(self, db2_connector, mock_ibm_db):
        """All DB2 types together in one table are preserved correctly."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "comprehensive_types",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "comprehensive_types",
                "COLNAME": "id",
                "COLTYPE": "BIGINT",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 19,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "comprehensive_types",
                "COLNAME": "short_text",
                "COLTYPE": "VARCHAR",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 2,
                "LENGTH": 255,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "comprehensive_types",
                "COLNAME": "long_text",
                "COLTYPE": "CLOB",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 3,
                "LENGTH": 2147483647,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "comprehensive_types",
                "COLNAME": "binary_data",
                "COLTYPE": "BLOB",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 4,
                "LENGTH": 1000000,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "comprehensive_types",
                "COLNAME": "price",
                "COLTYPE": "DECIMAL",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 5,
                "LENGTH": None,
                "SCALE": 2,
                "PRECISION": 10,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "comprehensive_types",
                "COLNAME": "created_at",
                "COLTYPE": "TIMESTAMP",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 6,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": None,
            },
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "comprehensive_types",
                "COLNAME": "xml_payload",
                "COLTYPE": "XML",
                "NULLS": "Y",
                "DEFAULT": None,
                "COLNO": 7,
                "LENGTH": None,
                "SCALE": None,
                "PRECISION": None,
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.columns) == 7

        # Verify all types are present and correct
        expected_types = {
            "id": ("BIGINT", False, 19, 0),
            "short_text": ("VARCHAR", True, None, None),
            "long_text": ("CLOB", True, None, None),
            "binary_data": ("BLOB", True, None, None),
            "price": ("DECIMAL", True, 10, 2),
            "created_at": ("TIMESTAMP", False, None, None),
            "xml_payload": ("XML", True, None, None),
        }

        for col in table.columns:
            expected = expected_types[col.name]
            assert col.data_type == expected[0], f"{col.name}: expected {expected[0]}, got {col.data_type}"
            assert col.nullable == expected[1], f"{col.name}: expected nullable={expected[1]}, got {col.nullable}"
            if expected[2] is not None:
                assert col.numeric_precision == expected[2]
            if expected[3] is not None:
                assert col.numeric_scale == expected[3]


class TestDB2IndexExtraction:
    """Test that DB2 index metadata is extracted and canonicalized correctly."""

    def _setup_connector_mocks(self, db2_connector, mock_ibm_db, tables, columns, indexes):
        """Setup mocks for index extraction."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        # Order matters: PK/FK/constraint queries also reference SYSCAT.TABLES
        # via JOINs, so they must be checked (and excluded) before the
        # generic SYSCAT.TABLES branch. This test has no PK/FK/constraint
        # fixtures, so those queries should always return empty.
        def mock_query(sql):
            data = []
            if "SYSCAT.TABCONST" in sql or "SYSCAT.REFERENCES" in sql:
                data = []
            elif "SYSCAT.INDEXES" in sql:
                data = indexes
            elif "SYSCAT.COLUMNS" in sql:
                data = columns
            elif "SYSCAT.TABLES" in sql and "TABTYPE = 'T'" in sql:
                data = []  # No statistics in index tests
            elif "SYSCAT.TABLES" in sql:
                data = tables

            # Normalize keys just like the real _query method does
            return [db2_connector._normalize_keys(row) for row in data]

        db2_connector._query = lambda sql: mock_query(sql)
        db2_connector.connect()

    def _mock_query_results(self, mock_ibm_db, data):
        """Mock query results."""
        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        mock_ibm_db.fetch_row.side_effect = [True] * len(data) + [False]
        mock_ibm_db.fetch_assoc.side_effect = data
        mock_ibm_db.free_stmt.return_value = None
        return data

    def test_index_extraction_with_null_definition(self, db2_connector, mock_ibm_db):
        """DB2 indexes are extracted with null definition (DB2 doesn't store full DDL)."""
        tables = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "indexed_table",
                "TABTYPE": "T",
            }
        ]
        columns = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "indexed_table",
                "COLNAME": "id",
                "COLTYPE": "BIGINT",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 19,
            }
        ]
        indexes = [
            {
                "INDSCHEMA": "DB2ADMIN",
                "INDNAME": "idx_primary",
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "indexed_table",
                "UNIQUERULE": "U",
                "INDEXTYPE": "REG",
                "INDEXDEF": None,
            },
            {
                "INDSCHEMA": "DB2ADMIN",
                "INDNAME": "idx_non_unique",
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "indexed_table",
                "UNIQUERULE": "D",
                "INDEXTYPE": "REG",
                "INDEXDEF": None,
            },
        ]

        self._setup_connector_mocks(db2_connector, mock_ibm_db, tables, columns, indexes)

        builder = MetadataBuilder(db2_connector, "testdb", "db2")
        result = builder.build(["DB2ADMIN"])

        table = result.metadata.schemas[0].tables[0]
        assert len(table.indexes) == 2

        # Verify unique index (DB2 has no DDL text for indexes; definition
        # is normalized to "" to satisfy the canonical model's str contract)
        unique_index = table.indexes[0]
        assert unique_index.index_name == "idx_primary"
        assert unique_index.definition == ""

        # Verify non-unique index
        nonunique_index = table.indexes[1]
        assert nonunique_index.index_name == "idx_non_unique"
        assert nonunique_index.definition == ""
