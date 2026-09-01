"""Tests for migrate.py --publish-ddl CLI option."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from migrate import parse_args, _run_publish_ddl_mode


class TestPublishDDLArgument:
    """Tests for --publish-ddl CLI argument parsing."""

    def test_publish_ddl_argument_recognized(self):
        """CLI should recognize --publish-ddl argument."""
        args = parse_args(["--config", "config.yaml", "--publish-ddl", "output/test.sql"])
        assert args.publish_ddl == "output/test.sql"
        assert args.config == "config.yaml"

    def test_publish_ddl_optional(self):
        """--publish-ddl should be optional."""
        args = parse_args(["--config", "config.yaml"])
        assert args.publish_ddl is None

    def test_publish_ddl_exclusive_with_other_modes(self):
        """--publish-ddl should be usable with other flags."""
        args = parse_args(
            ["--config", "config.yaml", "--publish-ddl", "output/test.sql", "--force"]
        )
        assert args.publish_ddl == "output/test.sql"
        assert args.force is True


class TestPublishDDLMode:
    """Tests for _run_publish_ddl_mode function."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock config object."""
        config = MagicMock()
        config.target.host_env = "DATABRICKS_HOST"
        config.target.token_env = "DATABRICKS_TOKEN"
        config.target.workspace_path_env = "DATABRICKS_WORKSPACE_PATH"
        return config

    @pytest.fixture
    def mock_args(self, tmp_path):
        """Create mock args with a temp SQL file."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("CREATE TABLE test (id INT);")
        args = MagicMock()
        args.publish_ddl = str(sql_file)
        return args

    @patch.dict("os.environ", {
        "DATABRICKS_HOST": "https://example.databricks.com",
        "DATABRICKS_TOKEN": "test_token",
        "DATABRICKS_WORKSPACE_PATH": "/migration/ddl/test.sql",
    })
    @patch("migrate.DatabricksWorkspaceClient")
    def test_publish_ddl_success(self, mock_client_class, mock_config, mock_args):
        """--publish-ddl should successfully publish SQL file."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        result = _run_publish_ddl_mode(mock_config, mock_args)

        assert result == 0
        mock_client_class.assert_called_once_with(
            host="https://example.databricks.com",
            token="test_token",
        )
        mock_client.publish_sql_file.assert_called_once()

    def test_publish_ddl_file_not_found(self, mock_config):
        """--publish-ddl should fail if SQL file doesn't exist."""
        args = MagicMock()
        args.publish_ddl = "/nonexistent/file.sql"

        result = _run_publish_ddl_mode(mock_config, args)

        assert result == 1

    @patch.dict("os.environ", {
        "DATABRICKS_TOKEN": "test_token",
        "DATABRICKS_WORKSPACE_PATH": "/migration/ddl/test.sql",
    }, clear=False)
    def test_publish_ddl_missing_host_env(self, mock_config, mock_args):
        """--publish-ddl should fail if DATABRICKS_HOST env var is missing."""
        # Ensure DATABRICKS_HOST is not set
        import os
        os.environ.pop("DATABRICKS_HOST", None)

        result = _run_publish_ddl_mode(mock_config, mock_args)

        assert result == 1

    @patch.dict("os.environ", {
        "DATABRICKS_HOST": "https://example.databricks.com",
        "DATABRICKS_WORKSPACE_PATH": "/migration/ddl/test.sql",
    }, clear=False)
    def test_publish_ddl_missing_token_env(self, mock_config, mock_args):
        """--publish-ddl should fail if DATABRICKS_TOKEN env var is missing."""
        # Ensure DATABRICKS_TOKEN is not set
        import os
        os.environ.pop("DATABRICKS_TOKEN", None)

        result = _run_publish_ddl_mode(mock_config, mock_args)

        assert result == 1

    @patch.dict("os.environ", {
        "DATABRICKS_HOST": "https://example.databricks.com",
        "DATABRICKS_TOKEN": "test_token",
    }, clear=False)
    def test_publish_ddl_missing_workspace_path_env(self, mock_config, mock_args):
        """--publish-ddl should fail if DATABRICKS_WORKSPACE_PATH env var is missing."""
        # Ensure DATABRICKS_WORKSPACE_PATH is not set
        import os
        os.environ.pop("DATABRICKS_WORKSPACE_PATH", None)

        result = _run_publish_ddl_mode(mock_config, mock_args)

        assert result == 1

    @patch.dict("os.environ", {
        "DATABRICKS_HOST": "https://example.databricks.com",
        "DATABRICKS_TOKEN": "test_token",
        "DATABRICKS_WORKSPACE_PATH": "/migration/ddl/test.sql",
    })
    @patch("migrate.DatabricksWorkspaceClient")
    def test_publish_ddl_client_error(self, mock_client_class, mock_config, mock_args):
        """--publish-ddl should handle workspace client errors."""
        mock_client = MagicMock()
        mock_client.publish_sql_file.side_effect = Exception("API error")
        mock_client_class.return_value = mock_client

        result = _run_publish_ddl_mode(mock_config, mock_args)

        assert result == 1

    @patch.dict("os.environ", {
        "DATABRICKS_HOST": "https://example.databricks.com",
        "DATABRICKS_TOKEN": "test_token",
        "DATABRICKS_WORKSPACE_PATH": "/migration/ddl/test.sql",
    })
    @patch("migrate.DatabricksWorkspaceClient")
    def test_publish_ddl_dispatches_correctly(self, mock_client_class, mock_config, mock_args):
        """--publish-ddl should dispatch to workspace client with correct params."""
        mock_client = MagicMock()
        mock_client_class.return_value = mock_client

        _run_publish_ddl_mode(mock_config, mock_args)

        # Verify client was created with correct credentials
        assert mock_client_class.call_count == 1
        call_kwargs = mock_client_class.call_args[1]
        assert call_kwargs["host"] == "https://example.databricks.com"
        assert call_kwargs["token"] == "test_token"

        # Verify publish_sql_file was called
        assert mock_client.publish_sql_file.call_count == 1
        publish_kwargs = mock_client.publish_sql_file.call_args[1]
        assert publish_kwargs["workspace_path"] == "/migration/ddl/test.sql"


class TestPublishDDLIntegration:
    """Integration tests for --publish-ddl with run() function."""

    def test_publish_ddl_parsed_before_migration(self, tmp_path):
        """--publish-ddl should be parsed and available in args."""
        sql_file = tmp_path / "test.sql"
        sql_file.write_text("CREATE TABLE test (id INT);")

        args = parse_args(
            ["--config", "config.yaml", "--publish-ddl", str(sql_file)]
        )

        assert args.publish_ddl == str(sql_file)

    def test_execute_ddl_and_publish_ddl_different(self):
        """--execute-ddl and --publish-ddl should be separate options."""
        args1 = parse_args(
            ["--config", "config.yaml", "--execute-ddl", "output/ddl.json"]
        )
        args2 = parse_args(
            ["--config", "config.yaml", "--publish-ddl", "output/schema.sql"]
        )

        assert args1.execute_ddl == "output/ddl.json"
        assert args1.publish_ddl is None
        assert args2.publish_ddl == "output/schema.sql"
        assert args2.execute_ddl is None
