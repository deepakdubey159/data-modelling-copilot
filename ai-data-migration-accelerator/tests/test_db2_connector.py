"""Tests for migration.connectors.db2_connector.

Tests exercise the connector's state-management logic and metadata extraction
with mocked ibm_db responses. No live DB2 instance required.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from migration.connectors.base import ConnectorError
from migration.connectors.db2_connector import DB2Connector


@pytest.fixture
def connector() -> DB2Connector:
    return DB2Connector(
        host="localhost",
        port=50000,
        database="testdb",
        username="db2admin",
        password="password123",
    )


@pytest.fixture
def mock_ibm_db():
    """Mock the ibm_db module."""
    with patch("migration.connectors.db2_connector.ibm_db") as mock:
        yield mock


class TestDB2ConnectorLifecycle:
    """Tests for connection lifecycle management."""

    def test_connect_success(self, connector: DB2Connector, mock_ibm_db):
        """Successful connection sets internal state."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        connector.connect()

        assert connector._is_connected is True
        assert connector._connection is mock_connection

    def test_connect_failure_raises_connector_error(self, connector: DB2Connector, mock_ibm_db):
        """Connection failure raises ConnectorError."""
        mock_ibm_db.connect.side_effect = Exception("Connection refused")

        with pytest.raises(ConnectorError, match="Failed to connect"):
            connector.connect()

        assert connector._is_connected is False

    def test_validate_connection_false_when_not_connected(self, connector: DB2Connector):
        """Connection validation returns False before connect."""
        assert connector.validate_connection() is False

    def test_validate_connection_true_when_connected(
        self, connector: DB2Connector, mock_ibm_db
    ):
        """Connection validation returns True after successful connection."""
        mock_connection = MagicMock()
        mock_stmt = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        mock_ibm_db.fetch_row.return_value = True
        mock_ibm_db.free_stmt.return_value = None

        connector.connect()
        result = connector.validate_connection()

        assert result is True

    def test_validate_connection_returns_false_on_error(
        self, connector: DB2Connector, mock_ibm_db
    ):
        """Connection validation returns False on error."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection
        mock_ibm_db.exec_immediate.side_effect = Exception("Query failed")

        connector.connect()
        result = connector.validate_connection()

        assert result is False

    def test_disconnect_is_idempotent(self, connector: DB2Connector):
        """Disconnect can be called multiple times safely."""
        # Should not raise even though connect() was never called
        connector.disconnect()
        connector.disconnect()

    def test_disconnect_closes_connection(self, connector: DB2Connector, mock_ibm_db):
        """Disconnect closes the connection."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        connector.connect()
        connector.disconnect()

        mock_ibm_db.close.assert_called_once_with(mock_connection)
        assert connector._is_connected is False
        assert connector._connection is None

    def test_context_manager_lifecycle(self, connector: DB2Connector, mock_ibm_db):
        """Context manager calls connect and disconnect."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        with connector:
            assert connector._is_connected is True

        mock_ibm_db.close.assert_called_once()


class TestDB2ConnectorMetadataExtraction:
    """Tests for metadata extraction methods."""

    def _setup_query_mock(self, mock_ibm_db, return_rows: list[dict]):
        """Helper to mock query execution."""
        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt

        # Setup fetch_row to return True for each row, False at end
        fetch_row_returns = [True] * len(return_rows) + [False]
        mock_ibm_db.fetch_row.side_effect = fetch_row_returns

        # Setup fetch_assoc to return rows in order
        mock_ibm_db.fetch_assoc.side_effect = return_rows
        mock_ibm_db.free_stmt.return_value = None

    def test_extract_tables_not_connected_raises(self, connector: DB2Connector):
        """extract_tables raises before connection."""
        with pytest.raises(ConnectorError, match="Not connected"):
            connector.extract_tables(["public"])

    def test_extract_tables_returns_tables(self, connector: DB2Connector, mock_ibm_db):
        """extract_tables returns table metadata."""
        return_rows = [
            {"TABSCHEMA": "DB2ADMIN", "TABNAME": "customers", "TABTYPE": "T"},
            {"TABSCHEMA": "DB2ADMIN", "TABNAME": "orders", "TABTYPE": "T"},
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_tables(["DB2ADMIN"])

        assert len(result) == 2
        assert result[0]["table_schema"] == "DB2ADMIN"
        assert result[0]["table_name"] == "customers"

    def test_extract_columns_not_connected_raises(self, connector: DB2Connector):
        """extract_columns raises before connection."""
        with pytest.raises(ConnectorError, match="Not connected"):
            connector.extract_columns(["public"])

    def test_extract_columns_returns_columns(self, connector: DB2Connector, mock_ibm_db):
        """extract_columns returns column metadata."""
        return_rows = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "COLNAME": "customer_id",
                "COLTYPE": "INTEGER",
                "NULLS": "N",
                "DEFAULT": None,
                "COLNO": 1,
                "LENGTH": None,
                "SCALE": 0,
                "PRECISION": 10,
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_columns(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["column_name"] == "customer_id"
        assert result[0]["data_type"] == "INTEGER"
        assert result[0]["is_nullable"] == "NO"

    def test_extract_primary_keys_returns_keys(self, connector: DB2Connector, mock_ibm_db):
        """extract_primary_keys returns primary key metadata."""
        return_rows = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "COLNAME": "customer_id",
                "CONSTNAME": "pk_customers",
                "COLSEQ": 1,
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_primary_keys(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["constraint_name"] == "pk_customers"
        assert result[0]["column_name"] == "customer_id"

    def test_extract_foreign_keys_returns_keys(self, connector: DB2Connector, mock_ibm_db):
        """extract_foreign_keys returns foreign key metadata."""
        return_rows = [
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
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_foreign_keys(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["constraint_name"] == "fk_orders_customers"
        assert result[0]["foreign_table_name"] == "customers"

    def test_extract_constraints_returns_constraints(
        self, connector: DB2Connector, mock_ibm_db
    ):
        """extract_constraints returns constraint metadata."""
        return_rows = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "CONSTNAME": "u_email",
                "TYPE": "U",
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_constraints(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["constraint_name"] == "u_email"
        assert result[0]["constraint_type"] == "U"

    def test_extract_indexes_returns_indexes(self, connector: DB2Connector, mock_ibm_db):
        """extract_indexes returns index metadata."""
        return_rows = [
            {
                "INDSCHEMA": "DB2ADMIN",
                "INDNAME": "idx_email",
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "UNIQUERULE": "U",
                "INDEXTYPE": "REG",
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_indexes(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["index_name"] == "idx_email"
        assert result[0]["table_name"] == "customers"

    def test_extract_views_returns_views(self, connector: DB2Connector, mock_ibm_db):
        """extract_views returns view metadata."""
        return_rows = [
            {
                "VIEWSCHEMA": "DB2ADMIN",
                "VIEWNAME": "active_customers",
                "TEXT": "SELECT * FROM customers WHERE status = 'active'",
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_views(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["view_name"] == "active_customers"
        assert result[0]["definition"] is not None

    def test_extract_procedures_returns_procedures(
        self, connector: DB2Connector, mock_ibm_db
    ):
        """extract_procedures returns stored procedure metadata."""
        return_rows = [
            {
                "ROUTINESCHEMA": "DB2ADMIN",
                "ROUTINENAME": "sp_create_customer",
                "TEXT": "CREATE PROCEDURE sp_create_customer(...) ...",
                "ROUTINETYPE": "P",
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_procedures(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["routine_name"] == "sp_create_customer"
        assert result[0]["definition"] is not None

    def test_extract_functions_returns_functions(self, connector: DB2Connector, mock_ibm_db):
        """extract_functions returns user-defined function metadata."""
        return_rows = [
            {
                "ROUTINESCHEMA": "DB2ADMIN",
                "ROUTINENAME": "fn_calculate_age",
                "TEXT": "CREATE FUNCTION fn_calculate_age(...) ...",
                "RETURNS": "INT",
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_functions(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["routine_name"] == "fn_calculate_age"
        assert result[0]["return_type"] == "INT"

    def test_extract_triggers_returns_triggers(self, connector: DB2Connector, mock_ibm_db):
        """extract_triggers returns trigger metadata."""
        return_rows = [
            {
                "TRIGSCHEMA": "DB2ADMIN",
                "TRIGNAME": "trg_update_timestamp",
                "TRIGTIME": "A",
                "TRIGEVENT": "U",
                "TABNAME": "customers",
                "TEXT": "CREATE TRIGGER trg_update_timestamp ...",
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_triggers(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["trigger_name"] == "trg_update_timestamp"
        assert result[0]["table_name"] == "customers"

    def test_extract_statistics_returns_statistics(
        self, connector: DB2Connector, mock_ibm_db
    ):
        """extract_statistics returns table statistics."""
        return_rows = [
            {
                "TABSCHEMA": "DB2ADMIN",
                "TABNAME": "customers",
                "CARD": 10000,
                "NPAGES": 50,
                "FPAGES": 45,
                "OVERFLOW": 0,
            }
        ]
        self._setup_query_mock(mock_ibm_db, return_rows)
        mock_ibm_db.connect.return_value = MagicMock()

        connector.connect()
        result = connector.extract_statistics(["DB2ADMIN"])

        assert len(result) == 1
        assert result[0]["table_schema"] == "DB2ADMIN"
        assert result[0]["table_name"] == "customers"
        assert result[0]["row_estimate"] == 10000
        assert result[0]["npages"] == 50
        assert result[0]["fpages"] == 45
        assert result[0]["overflow"] == 0


class TestDB2ConnectorProfiling:
    """Tests for data profiling methods."""

    def test_profile_table_not_connected_raises(self, connector: DB2Connector):
        """profile_table raises before connection."""
        with pytest.raises(ConnectorError, match="Not connected"):
            connector.profile_table("DB2ADMIN", "customers", [])

    def test_profile_table_empty_columns(self, connector: DB2Connector, mock_ibm_db):
        """profile_table with no columns returns row count only."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        mock_ibm_db.fetch_row.side_effect = [True, False]
        mock_ibm_db.fetch_assoc.return_value = {"row_count": 1000}
        mock_ibm_db.free_stmt.return_value = None

        connector.connect()
        result = connector.profile_table("DB2ADMIN", "customers", [])

        assert result["row_count"] == 1000
        assert result["duplicate_row_count"] is None

    def test_profile_table_with_columns(self, connector: DB2Connector, mock_ibm_db):
        """profile_table returns statistics for specified columns."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        mock_ibm_db.fetch_row.side_effect = [True, False, True, False]
        mock_ibm_db.fetch_assoc.side_effect = [
            {
                "row_count": 1000,
                "id__null_count": 0,
                "id__distinct_count": 1000,
                "id__min_value": "1",
                "id__max_value": "1000",
                "id__min_length": 1,
                "id__max_length": 4,
            },
            {"rn": 0},
        ]
        mock_ibm_db.free_stmt.return_value = None

        connector.connect()
        result = connector.profile_table(
            "DB2ADMIN",
            "customers",
            [{"name": "id", "data_type": "INTEGER"}],
        )

        assert result["row_count"] == 1000
        assert "id" in result["columns"]
        assert result["columns"]["id"]["distinct_count"] == 1000

    def test_sample_column_values_not_connected_raises(self, connector: DB2Connector):
        """sample_column_values raises before connection."""
        with pytest.raises(ConnectorError, match="Not connected"):
            connector.sample_column_values("DB2ADMIN", "customers", "email")

    def test_sample_column_values_returns_samples(self, connector: DB2Connector, mock_ibm_db):
        """sample_column_values returns sample column values."""
        mock_connection = MagicMock()
        mock_ibm_db.connect.return_value = mock_connection

        mock_stmt = MagicMock()
        mock_ibm_db.exec_immediate.return_value = mock_stmt
        mock_ibm_db.fetch_row.side_effect = [True, True, False]
        mock_ibm_db.fetch_assoc.side_effect = [
            {"EMAIL": "john@example.com"},
            {"EMAIL": "jane@example.com"},
        ]
        mock_ibm_db.free_stmt.return_value = None

        connector.connect()
        result = connector.sample_column_values("DB2ADMIN", "customers", "email", limit=200)

        assert len(result) == 2
        assert "john@example.com" in result


class TestDB2ConnectorIdentifierQuoting:
    """Tests for SQL injection safety via identifier quoting."""

    @staticmethod
    def test_quote_ident_wraps_plain_identifier():
        """quote_ident wraps a plain identifier."""
        assert DB2Connector._quote_ident("customers") == '"customers"'

    @staticmethod
    def test_quote_ident_escapes_embedded_quotes():
        """quote_ident escapes embedded quotes."""
        assert DB2Connector._quote_ident('weird"name') == '"weird""name"'

    @staticmethod
    def test_quote_ident_neutralizes_injection():
        """quote_ident prevents SQL injection via malicious identifier."""
        malicious = 'customers"; DROP TABLE users; --'
        quoted = DB2Connector._quote_ident(malicious)
        assert quoted.startswith('"') and quoted.endswith('"')
        # The injection attempt becomes part of the quoted identifier
        # so it's no longer an active SQL statement separator
        assert quoted == '"customers""; DROP TABLE users; --"'


class TestDB2ConnectorFactory:
    """Tests for DB2 connector factory integration."""

    def test_create_db2_connector(self, mock_ibm_db):
        """Factory creates DB2 connector for DB2 source type."""
        from migration.connectors.factory import create_connector
        from migration.models.config import SourceConfig, SourceType

        config = SourceConfig(
            type=SourceType.DB2,
            host="db2.example.com",
            port=50000,
            database="testdb",
            username="db2admin",
            password="password",
            schema=["DB2ADMIN"],
        )

        connector = create_connector(config)

        assert isinstance(connector, DB2Connector)
        assert connector.host == "db2.example.com"
        assert connector.port == 50000
        assert connector.database == "testdb"


class TestDB2LiveConnectivity:
    """Optional smoke tests for real DB2 database connectivity.

    These tests only run when DB2_TEST_* environment variables are set.
    They verify the connector can establish and validate a live connection.

    Required environment variables:
      DB2_TEST_HOST: Hostname or IP of DB2 server
      DB2_TEST_PORT: Port number (default: 50000)
      DB2_TEST_DATABASE: Database name
      DB2_TEST_USERNAME: Username with connection privilege
      DB2_TEST_PASSWORD: Password
      DB2_TEST_SCHEMA: Optional comma-separated schemas to query (default: "DB2INST1")

    To run live DB2 smoke tests:
      DB2_TEST_HOST=prod-db2 DB2_TEST_PORT=50000 DB2_TEST_DATABASE=production \\
      DB2_TEST_USERNAME=db2admin DB2_TEST_PASSWORD=secret \\
      pytest tests/test_db2_connector.py::TestDB2LiveConnectivity -v

    Skipped by default; requires operational DB2 instance.
    """

    @pytest.fixture
    def db2_credentials(self):
        """Load DB2 credentials from environment; skip if unavailable."""
        import os

        host = os.getenv("DB2_TEST_HOST")
        port_str = os.getenv("DB2_TEST_PORT", "50000")
        database = os.getenv("DB2_TEST_DATABASE")
        username = os.getenv("DB2_TEST_USERNAME")
        password = os.getenv("DB2_TEST_PASSWORD")
        schema = os.getenv("DB2_TEST_SCHEMA", "DB2INST1")

        if not all([host, database, username, password]):
            pytest.skip(
                "DB2 live connectivity test skipped. "
                "Set DB2_TEST_HOST, DB2_TEST_DATABASE, DB2_TEST_USERNAME, DB2_TEST_PASSWORD to run."
            )

        try:
            port = int(port_str)
        except ValueError:
            pytest.skip(f"Invalid DB2_TEST_PORT: {port_str}")

        return {
            "host": host,
            "port": port,
            "database": database,
            "username": username,
            "password": password,
            "schemas": [s.strip() for s in schema.split(",")],
        }

    def test_connect_to_live_db2(self, db2_credentials):
        """Smoke test: connect to real DB2 instance."""
        connector = DB2Connector(
            host=db2_credentials["host"],
            port=db2_credentials["port"],
            database=db2_credentials["database"],
            username=db2_credentials["username"],
            password=db2_credentials["password"],
        )

        try:
            connector.connect()
            assert connector._is_connected is True
            assert connector._connection is not None
        finally:
            connector.disconnect()

    def test_validate_live_connection(self, db2_credentials):
        """Smoke test: validate connection to real DB2 instance."""
        connector = DB2Connector(
            host=db2_credentials["host"],
            port=db2_credentials["port"],
            database=db2_credentials["database"],
            username=db2_credentials["username"],
            password=db2_credentials["password"],
        )

        try:
            connector.connect()
            is_valid = connector.validate_connection()
            assert is_valid is True
        finally:
            connector.disconnect()

    def test_extract_tables_from_live_db2(self, db2_credentials):
        """Smoke test: extract table metadata from real DB2 instance."""
        connector = DB2Connector(
            host=db2_credentials["host"],
            port=db2_credentials["port"],
            database=db2_credentials["database"],
            username=db2_credentials["username"],
            password=db2_credentials["password"],
        )

        try:
            connector.connect()

            # Extract tables from specified schemas
            tables = connector.extract_tables(db2_credentials["schemas"])

            # Verify we got a list (may be empty if schemas don't exist)
            assert isinstance(tables, list)

            # If tables exist, verify structure
            for table in tables:
                assert "table_schema" in table
                assert "table_name" in table
                assert "table_type" in table
                assert table["table_type"] in ("T", "V")

        finally:
            connector.disconnect()
