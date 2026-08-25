"""
Tests for migration.target.databricks_executor.DatabricksExecutor.

No real Databricks connection is ever made - the `databricks.sql` module is
mocked wherever a live connection would be opened. Dry-run is exercised
against a real (but tiny) DDLScript with no mocking at all, since dry-run
must never touch the network.
"""

from __future__ import annotations

from unittest import mock

import pytest

from migration.ddl.models import DDLScript, DDLStatement
from migration.models.config import TargetConfig, TargetType
from migration.target.databricks_executor import (
    DatabricksExecutionError,
    DatabricksExecutor,
    MissingDatabricksCredentialsError,
)


def _script() -> DDLScript:
    return DDLScript(
        database_name="testdb",
        target_type="databricks",
        table_creation_statements=[
            DDLStatement(statement="CREATE TABLE customer (id BIGINT)", statement_type="CREATE"),
            DDLStatement(statement="CREATE TABLE orders (id BIGINT)", statement_type="CREATE"),
        ],
        constraint_statements=[
            DDLStatement(statement="ALTER TABLE orders ADD CONSTRAINT fk_customer ...", statement_type="ALTER"),
        ],
    )


def _target(**overrides) -> TargetConfig:
    values = {"type": TargetType.DATABRICKS}
    values.update(overrides)
    return TargetConfig(**values)


class TestDryRun:
    """Dry-run must never require credentials or open a connection."""

    def test_dry_run_requires_no_environment_variables(self, monkeypatch):
        monkeypatch.delenv("DATABRICKS_HOST", raising=False)
        monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
        monkeypatch.delenv("DATABRICKS_HTTP_PATH", raising=False)

        executor = DatabricksExecutor(_target())
        result = executor.run(_script(), dry_run=True)

        assert result.dry_run is True
        assert result.statement_count == 3
        assert result.succeeded is True

    def test_dry_run_does_not_mark_statements_as_executed(self):
        executor = DatabricksExecutor(_target())
        result = executor.run(_script(), dry_run=True)

        assert all(not r.executed for r in result.results)

    def test_dry_run_preserves_statement_order(self):
        executor = DatabricksExecutor(_target())
        result = executor.run(_script(), dry_run=True)

        statements = [r.statement.statement for r in result.results]
        assert statements == [
            "CREATE TABLE customer (id BIGINT)",
            "CREATE TABLE orders (id BIGINT)",
            "ALTER TABLE orders ADD CONSTRAINT fk_customer ...",
        ]


class TestCredentialValidation:
    """Live execution must fail fast and clearly when credentials are missing."""

    def test_missing_host_env_raises_clear_error(self, monkeypatch):
        monkeypatch.delenv("DATABRICKS_HOST", raising=False)
        monkeypatch.setenv("DATABRICKS_TOKEN", "secret-token")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")

        executor = DatabricksExecutor(_target(catalog="main"))

        with pytest.raises(MissingDatabricksCredentialsError, match="DATABRICKS_HOST"):
            executor.resolve_connection_params()

    def test_missing_token_env_raises_clear_error(self, monkeypatch):
        monkeypatch.setenv("DATABRICKS_HOST", "adb-123.azuredatabricks.net")
        monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")

        executor = DatabricksExecutor(_target(catalog="main"))

        with pytest.raises(MissingDatabricksCredentialsError, match="DATABRICKS_TOKEN"):
            executor.resolve_connection_params()

    def test_missing_catalog_raises_clear_error(self, monkeypatch):
        monkeypatch.setenv("DATABRICKS_HOST", "adb-123.azuredatabricks.net")
        monkeypatch.setenv("DATABRICKS_TOKEN", "secret-token")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")

        executor = DatabricksExecutor(_target())  # no catalog

        with pytest.raises(MissingDatabricksCredentialsError, match="catalog"):
            executor.resolve_connection_params()

    def test_error_message_never_contains_the_secret_value(self, monkeypatch):
        monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
        monkeypatch.setenv("DATABRICKS_HOST", "adb-123.azuredatabricks.net")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")

        executor = DatabricksExecutor(_target(catalog="main"))

        with pytest.raises(MissingDatabricksCredentialsError) as excinfo:
            executor.resolve_connection_params()

        assert "secret-token" not in str(excinfo.value)

    def test_credentials_resolve_from_custom_env_var_names(self, monkeypatch):
        """A client can point host_env/token_env at their own naming scheme."""
        monkeypatch.setenv("MY_DBX_HOST", "adb-999.azuredatabricks.net")
        monkeypatch.setenv("MY_DBX_TOKEN", "tok-abc")
        monkeypatch.setenv("MY_DBX_PATH", "/sql/1.0/warehouses/xyz")

        executor = DatabricksExecutor(
            _target(
                host_env="MY_DBX_HOST",
                token_env="MY_DBX_TOKEN",
                http_path_env="MY_DBX_PATH",
                catalog="main",
            )
        )

        params = executor.resolve_connection_params()
        assert params["server_hostname"] == "adb-999.azuredatabricks.net"
        assert params["access_token"] == "tok-abc"
        assert params["http_path"] == "/sql/1.0/warehouses/xyz"


class TestMockedExecution:
    """Live execution path, fully mocked - no real connection is ever opened."""

    def test_successful_execution_runs_every_statement(self, monkeypatch):
        monkeypatch.setenv("DATABRICKS_HOST", "adb-123.azuredatabricks.net")
        monkeypatch.setenv("DATABRICKS_TOKEN", "secret-token")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")

        mock_cursor = mock.MagicMock()
        mock_connection = mock.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_databricks_sql = mock.MagicMock()
        mock_databricks_sql.connect.return_value = mock_connection

        with mock.patch.dict("sys.modules", {"databricks": mock.MagicMock(sql=mock_databricks_sql), "databricks.sql": mock_databricks_sql}):
            executor = DatabricksExecutor(_target(catalog="main"))
            result = executor.run(_script(), dry_run=False)

        assert result.dry_run is False
        assert result.succeeded is True
        assert result.statement_count == 3
        assert mock_cursor.execute.call_count == 4  # USE CATALOG + 3 statements
        mock_connection.close.assert_called_once()

    def test_failed_statement_stops_execution_and_reports_error(self, monkeypatch):
        monkeypatch.setenv("DATABRICKS_HOST", "adb-123.azuredatabricks.net")
        monkeypatch.setenv("DATABRICKS_TOKEN", "secret-token")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")

        mock_cursor = mock.MagicMock()
        # USE CATALOG succeeds, first CREATE TABLE succeeds, second fails
        mock_cursor.execute.side_effect = [None, None, Exception("table already exists")]
        mock_connection = mock.MagicMock()
        mock_connection.cursor.return_value = mock_cursor

        mock_databricks_sql = mock.MagicMock()
        mock_databricks_sql.connect.return_value = mock_connection

        with mock.patch.dict("sys.modules", {"databricks": mock.MagicMock(sql=mock_databricks_sql), "databricks.sql": mock_databricks_sql}):
            executor = DatabricksExecutor(_target(catalog="main"))
            result = executor.run(_script(), dry_run=False)

        assert result.succeeded is False
        assert result.failed_count == 1
        assert "table already exists" in result.first_error
        # Execution stopped after the failure - third statement never ran
        assert mock_cursor.execute.call_count == 3

    def test_connection_error_raises_databricks_execution_error(self, monkeypatch):
        monkeypatch.setenv("DATABRICKS_HOST", "adb-123.azuredatabricks.net")
        monkeypatch.setenv("DATABRICKS_TOKEN", "secret-token")
        monkeypatch.setenv("DATABRICKS_HTTP_PATH", "/sql/1.0/warehouses/abc")

        mock_databricks_sql = mock.MagicMock()
        mock_databricks_sql.connect.side_effect = Exception("network unreachable")

        with mock.patch.dict("sys.modules", {"databricks": mock.MagicMock(sql=mock_databricks_sql), "databricks.sql": mock_databricks_sql}):
            executor = DatabricksExecutor(_target(catalog="main"))

            with pytest.raises(DatabricksExecutionError, match="Failed to connect"):
                executor.run(_script(), dry_run=False)
