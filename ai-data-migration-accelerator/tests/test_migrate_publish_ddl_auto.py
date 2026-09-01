"""Tests for --publish flag (automatic end-to-end DDL generation and publishing)."""

import os
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch, call

import pytest

from migrate import _run_publish_and_migrate_mode, _migrate_schemas


class FakeSchemaResult:
    """Fake schema execution result."""
    def __init__(self, schema_name, status, run_directory=None, error=None):
        self.schema_name = schema_name
        self.status = status
        self.run_directory = run_directory
        self.error = error


class TestPublishAndMigrateMode:
    """Test the --publish end-to-end flow."""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration."""
        config = MagicMock()
        config.target.host_env = "DATABRICKS_HOST"
        config.target.token_env = "DATABRICKS_TOKEN"
        config.target.workspace_path_env = "DATABRICKS_WORKSPACE_PATH"
        config.source.schema_ = ["SALES"]
        return config

    @pytest.fixture
    def mock_args(self):
        """Mock command-line arguments."""
        args = MagicMock()
        args.schemas = None
        args.force = False
        return args

    def test_parse_args_publish_flag(self):
        """Verify --publish flag is recognized."""
        from migrate import parse_args
        args = parse_args(["--config", "config.yaml", "--publish"])
        assert args.publish is True
        assert args.config == "config.yaml"

    def test_publish_flag_is_store_true(self):
        """Verify --publish is a boolean flag."""
        from migrate import parse_args
        args = parse_args(["--config", "config.yaml"])
        assert args.publish is False

    def test_migrate_schemas_returns_results_and_failed_flag(self, mock_config, mock_args):
        """Verify _migrate_schemas returns (results, any_failed)."""
        fake_result = FakeSchemaResult("SALES", "completed", "/tmp/output/SALES/20260101_000000")

        with patch("migrate.run_schemas") as mock_run:
            mock_run.return_value = [fake_result]
            with patch("migrate._print_schema_results") as mock_print:
                mock_print.return_value = False
                with patch("migrate._build_llm_client", return_value=None):
                    results, any_failed = _migrate_schemas(mock_config, mock_args)

        assert len(results) == 1
        assert results[0].schema_name == "SALES"
        assert any_failed is False

    def test_publish_mode_missing_databricks_host(self, mock_config, mock_args, monkeypatch):
        """Verify error when DATABRICKS_HOST env var missing."""
        monkeypatch.delenv("DATABRICKS_HOST", raising=False)
        monkeypatch.delenv("DATABRICKS_TOKEN", raising=False)
        monkeypatch.delenv("DATABRICKS_WORKSPACE_PATH", raising=False)

        fake_result = FakeSchemaResult("SALES", "completed", "/tmp/output/SALES/20260101_000000")

        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = ([fake_result], False)
            result = _run_publish_and_migrate_mode(mock_config, mock_args)

        assert result == 1

    def test_publish_mode_migration_failed(self, mock_config, mock_args):
        """Verify error when migration fails."""
        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = ([], True)
            result = _run_publish_and_migrate_mode(mock_config, mock_args)

        assert result == 1

    def test_publish_mode_migration_empty_results(self, mock_config, mock_args):
        """Verify error when migration returns empty results."""
        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = ([], False)
            result = _run_publish_and_migrate_mode(mock_config, mock_args)

        assert result == 1

    def test_publish_mode_publishes_generated_sql(self, mock_config, mock_args, tmp_path, monkeypatch):
        """Verify --publish finds and publishes generated databricks.sql."""
        # Setup environment variables
        monkeypatch.setenv("DATABRICKS_HOST", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi123456")
        monkeypatch.setenv("DATABRICKS_WORKSPACE_PATH", "/migration")

        # Create mock output directory with generated SQL
        output_dir = tmp_path / "SALES" / "20260101_000000"
        output_dir.mkdir(parents=True)
        sql_file = output_dir / "databricks.sql"
        sql_file.write_text("CREATE TABLE `dblearn`.`bronze`.`customers` (...);")

        fake_result = FakeSchemaResult("SALES", "completed", str(output_dir))

        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = ([fake_result], False)
            with patch("migrate.DatabricksWorkspaceClient") as mock_workspace_client:
                mock_client = MagicMock()
                mock_workspace_client.return_value = mock_client

                result = _run_publish_and_migrate_mode(mock_config, mock_args)

        # Verify client was initialized with correct credentials
        mock_workspace_client.assert_called_once_with(
            host="https://test.databricks.com",
            token="dapi123456"
        )

        # Verify publish_sql_file was called with correct SQL file
        mock_client.publish_sql_file.assert_called_once()
        call_args = mock_client.publish_sql_file.call_args
        assert call_args[1]["sql_file_path"] == sql_file
        assert call_args[1]["workspace_path"] == "/migration"

        # Verify success
        assert result == 0

    def test_publish_mode_sql_file_not_found(self, mock_config, mock_args, tmp_path, monkeypatch):
        """Verify warning when databricks.sql is not found."""
        monkeypatch.setenv("DATABRICKS_HOST", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi123456")
        monkeypatch.setenv("DATABRICKS_WORKSPACE_PATH", "/migration")

        # Create output directory WITHOUT SQL file
        output_dir = tmp_path / "SALES" / "20260101_000000"
        output_dir.mkdir(parents=True)

        fake_result = FakeSchemaResult("SALES", "completed", str(output_dir))

        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = ([fake_result], False)
            with patch("migrate.DatabricksWorkspaceClient") as mock_workspace_client:
                result = _run_publish_and_migrate_mode(mock_config, mock_args)

        # Should succeed (0) because it's just a warning, not a failure
        # The function handles missing SQL gracefully with continue
        assert result == 0
        mock_workspace_client.return_value.publish_sql_file.assert_not_called()

    def test_publish_mode_publish_fails(self, mock_config, mock_args, tmp_path, monkeypatch):
        """Verify error when publishing fails."""
        monkeypatch.setenv("DATABRICKS_HOST", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi123456")
        monkeypatch.setenv("DATABRICKS_WORKSPACE_PATH", "/migration")

        # Create output directory with SQL file
        output_dir = tmp_path / "SALES" / "20260101_000000"
        output_dir.mkdir(parents=True)
        sql_file = output_dir / "databricks.sql"
        sql_file.write_text("CREATE TABLE ...")

        fake_result = FakeSchemaResult("SALES", "completed", str(output_dir))

        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = ([fake_result], False)
            with patch("migrate.DatabricksWorkspaceClient") as mock_workspace_client:
                mock_client = MagicMock()
                mock_client.publish_sql_file.side_effect = Exception("Network error")
                mock_workspace_client.return_value = mock_client

                result = _run_publish_and_migrate_mode(mock_config, mock_args)

        # Verify failure is reported
        assert result == 1

    def test_publish_mode_multiple_schemas(self, mock_config, mock_args, tmp_path, monkeypatch):
        """Verify --publish publishes SQL for all successfully completed schemas."""
        monkeypatch.setenv("DATABRICKS_HOST", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi123456")
        monkeypatch.setenv("DATABRICKS_WORKSPACE_PATH", "/migration")

        # Create output for two schemas
        output_dir1 = tmp_path / "SALES" / "20260101_000000"
        output_dir1.mkdir(parents=True)
        sql_file1 = output_dir1 / "databricks.sql"
        sql_file1.write_text("CREATE TABLE sales_table (...);")

        output_dir2 = tmp_path / "MARKETING" / "20260101_000000"
        output_dir2.mkdir(parents=True)
        sql_file2 = output_dir2 / "databricks.sql"
        sql_file2.write_text("CREATE TABLE marketing_table (...);")

        results = [
            FakeSchemaResult("SALES", "completed", str(output_dir1)),
            FakeSchemaResult("MARKETING", "completed", str(output_dir2)),
        ]

        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = (results, False)
            with patch("migrate.DatabricksWorkspaceClient") as mock_workspace_client:
                mock_client = MagicMock()
                mock_workspace_client.return_value = mock_client

                result = _run_publish_and_migrate_mode(mock_config, mock_args)

        # Verify both files were published
        assert mock_client.publish_sql_file.call_count == 2
        calls = mock_client.publish_sql_file.call_args_list
        assert calls[0][1]["sql_file_path"] == sql_file1
        assert calls[1][1]["sql_file_path"] == sql_file2

        assert result == 0

    def test_publish_mode_skips_non_completed_schemas(self, mock_config, mock_args, tmp_path, monkeypatch):
        """Verify --publish skips schemas that didn't complete."""
        monkeypatch.setenv("DATABRICKS_HOST", "https://test.databricks.com")
        monkeypatch.setenv("DATABRICKS_TOKEN", "dapi123456")
        monkeypatch.setenv("DATABRICKS_WORKSPACE_PATH", "/migration")

        # Create output only for first schema
        output_dir1 = tmp_path / "SALES" / "20260101_000000"
        output_dir1.mkdir(parents=True)
        sql_file1 = output_dir1 / "databricks.sql"
        sql_file1.write_text("CREATE TABLE sales (...);")

        results = [
            FakeSchemaResult("SALES", "completed", str(output_dir1)),
            FakeSchemaResult("MARKETING", "skipped", None),  # Not completed
            FakeSchemaResult("FINANCE", "failed", None, "Some error"),  # Failed
        ]

        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = (results, False)
            with patch("migrate.DatabricksWorkspaceClient") as mock_workspace_client:
                mock_client = MagicMock()
                mock_workspace_client.return_value = mock_client

                result = _run_publish_and_migrate_mode(mock_config, mock_args)

        # Only one schema was completed, so only one publish call
        assert mock_client.publish_sql_file.call_count == 1
        assert result == 0

    def test_normal_migration_mode_unchanged(self, mock_config, mock_args):
        """Verify normal migration mode still works (regression test)."""
        fake_result = FakeSchemaResult("SALES", "completed", "/tmp/output/SALES/20260101_000000")

        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = ([fake_result], False)
            from migrate import _run_migration_mode
            result = _run_migration_mode(mock_config, mock_args)

        assert result == 0

    def test_publish_not_called_in_normal_mode(self, mock_config, mock_args):
        """Verify --publish-ddl and normal mode don't call new publish logic."""
        fake_result = FakeSchemaResult("SALES", "completed", "/tmp/output/SALES/20260101_000000")

        with patch("migrate._migrate_schemas") as mock_migrate:
            mock_migrate.return_value = ([fake_result], False)
            with patch("migrate.DatabricksWorkspaceClient") as mock_workspace_client:
                from migrate import _run_migration_mode
                result = _run_migration_mode(mock_config, mock_args)

        # Workspace client should never be called in normal mode
        mock_workspace_client.assert_not_called()
        assert result == 0
