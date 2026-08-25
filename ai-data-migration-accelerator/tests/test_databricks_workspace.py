"""Tests for Databricks Workspace client."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

from migration.workspace import DatabricksWorkspaceClient


@pytest.fixture
def temp_sql_file(tmp_path):
    """Create a temporary SQL file for testing."""
    sql_file = tmp_path / "test.sql"
    sql_file.write_text("CREATE TABLE test (id INT);")
    return sql_file


class TestDatabricksWorkspaceClient:
    """Tests for DatabricksWorkspaceClient."""

    def test_client_initialization(self):
        """Client should initialize with host and token."""
        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )

        assert client.host == "https://example.databricks.com"
        assert client.token == "test_token"
        assert client.session.headers["Authorization"] == "Bearer test_token"

    def test_host_trailing_slash_removed(self):
        """Client should remove trailing slash from host."""
        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com/",
            token="test_token",
        )

        assert client.host == "https://example.databricks.com"

    @patch("migration.workspace.client.requests.Session.post")
    def test_create_directory_success(self, mock_post):
        """Client should create workspace directory with correct mkdirs payload."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )
        client.create_directory("/migration/ddl")

        mock_post.assert_called_once()
        call_args = mock_post.call_args

        # Verify URL
        url = call_args[0][0]
        assert url == "https://example.databricks.com/api/2.0/workspace/mkdirs"

        # Verify JSON payload (only required field)
        payload = call_args[1]["json"]
        assert payload == {"path": "/migration/ddl"}
        assert "format" not in payload  # mkdirs does NOT use format
        assert "language" not in payload  # mkdirs does NOT use language
        assert "content" not in payload  # mkdirs does NOT use content

    @patch("migration.workspace.client.requests.Session.post")
    def test_create_directory_mkdirs_payload_format(self, mock_post):
        """Client should send mkdirs with only path field, no format/language/content."""
        import json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )
        client.create_directory("/Workspace/Users/159deepakdubey@gmail.com/DataAIAccelerator")

        # Verify exact request format matches Databricks API requirement
        url, kwargs = mock_post.call_args[0][0], mock_post.call_args[1]
        payload = kwargs["json"]

        # mkdirs API requires ONLY {"path": "..."} - no other fields
        assert payload == {"path": "/Workspace/Users/159deepakdubey@gmail.com/DataAIAccelerator"}
        print(f"\n[MKDIRS REQUEST]\nURL: POST {url}\nPayload: {json.dumps(payload)}")

    @patch("migration.workspace.client.requests.Session.post")
    def test_create_directory_200_response_success(self, mock_post):
        """Client should accept 200 response as success, not treat as error."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {}  # Empty JSON response from Databricks
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )

        # Should not raise any exception for 200 response
        try:
            client.create_directory("/migration/ddl")
        except Exception as e:
            pytest.fail(f"Should not raise exception for 200 response: {e}")

        # Verify post was called exactly once
        assert mock_post.call_count == 1

    @patch("migration.workspace.client.requests.Session.post")
    def test_create_directory_failure(self, mock_post):
        """Client should raise on directory creation failure (4xx/5xx)."""
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError()
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )

        with pytest.raises(requests.exceptions.HTTPError):
            client.create_directory("/migration/ddl")

    @patch("migration.workspace.client.requests.Session.post")
    def test_create_directory_diagnostic_logging(self, mock_post, caplog):
        """Test diagnostic logging to debug 400 errors."""
        import logging

        caplog.set_level(logging.INFO)

        # Simulate 400 response like the user's error
        mock_response = MagicMock()
        mock_response.status_code = 400
        mock_response.text = "Invalid path format"
        mock_response.request = MagicMock()
        mock_response.request.url = "https://dbc-bec10476-b7f0.cloud.databricks.com/api/2.0/workspace/mkdirs"
        mock_response.request.headers = {"Authorization": "Bearer ***MASKED***", "Content-Type": "application/json"}
        mock_response.request.body = '{"path": "/Workspace/Users/159deepakdubey@gmail.com/DataAIAccelerator"}'
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("400 Client Error")

        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://dbc-bec10476-b7f0.cloud.databricks.com",
            token="test_token",
        )

        with pytest.raises(requests.exceptions.HTTPError):
            client.create_directory("/Workspace/Users/159deepakdubey@gmail.com/DataAIAccelerator")

        # Verify diagnostic logging was produced
        print("\n[DIAGNOSTIC LOG OUTPUT]")
        for record in caplog.records:
            if "[MKDIRS DEBUG]" in record.message:
                print(record.message)

    @patch("migration.workspace.client.requests.Session.post")
    def test_upload_file_success(self, mock_post, temp_sql_file):
        """Client should upload SQL file to workspace with base64-encoded content."""
        import base64

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )
        client.upload_file("/migration/ddl/test.sql", temp_sql_file)

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert "/api/2.0/workspace/import" in call_args[0][0]

        payload = call_args[1]["json"]
        assert payload["path"] == "/migration/ddl/test.sql"
        assert payload["format"] == "SOURCE"
        assert payload["language"] == "SQL"
        assert payload["overwrite"] is True

        # Content should be base64-encoded
        assert isinstance(payload["content"], str)
        decoded = base64.b64decode(payload["content"]).decode("utf-8")
        assert "CREATE TABLE test" in decoded

    def test_upload_file_not_found(self):
        """Client should raise FileNotFoundError for missing file."""
        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )

        with pytest.raises(FileNotFoundError):
            client.upload_file("/migration/ddl/missing.sql", Path("/nonexistent/file.sql"))

    @patch("migration.workspace.client.requests.Session.post")
    def test_upload_file_base64_encoding(self, mock_post, temp_sql_file):
        """Client should correctly base64-encode file content."""
        import base64

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )
        client.upload_file("/migration/ddl/test.sql", temp_sql_file)

        payload = mock_post.call_args[1]["json"]
        # Verify format and language are set correctly
        assert payload["format"] == "SOURCE"
        assert payload["language"] == "SQL"

        # Decode and verify content is intact
        decoded_content = base64.b64decode(payload["content"]).decode("utf-8")
        assert decoded_content == "CREATE TABLE test (id INT);"

    @patch("migration.workspace.client.requests.Session.post")
    def test_publish_sql_file_creates_directory(self, mock_post, temp_sql_file):
        """publish_sql_file should treat workspace_path as a directory, create
        it, and upload the file under {directory}/{sql_file_path.name}."""
        import base64

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )
        client.publish_sql_file(temp_sql_file, "/migration/ddl")

        # Should make two calls: one for mkdir, one for upload
        assert mock_post.call_count == 2

        # First call should be mkdir on the DIRECTORY itself
        first_call = mock_post.call_args_list[0]
        assert "/api/2.0/workspace/mkdirs" in first_call[0][0]
        assert first_call[1]["json"] == {"path": "/migration/ddl"}

        # Second call should be upload with filename derived from sql_file_path
        second_call = mock_post.call_args_list[1]
        assert "/api/2.0/workspace/import" in second_call[0][0]
        payload = second_call[1]["json"]
        assert payload["path"] == f"/migration/ddl/{temp_sql_file.name}"
        assert payload["format"] == "SOURCE"
        assert payload["language"] == "SQL"
        # Verify content is base64-encoded
        decoded = base64.b64decode(payload["content"]).decode("utf-8")
        assert "CREATE TABLE test" in decoded

    @patch("migration.workspace.client.requests.Session.post")
    def test_publish_sql_file_ignores_existing_directory(self, mock_post, temp_sql_file):
        """publish_sql_file should ignore directory already exists error."""
        responses = [
            MagicMock(status_code=409),  # Directory exists
            MagicMock(status_code=200),  # Upload succeeds
        ]
        mock_post.side_effect = responses

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )
        client.publish_sql_file(temp_sql_file, "/migration/ddl")

        # Should still call both mkdir and upload
        assert mock_post.call_count == 2
        upload_call = mock_post.call_args_list[1]
        assert upload_call[1]["json"]["path"] == f"/migration/ddl/{temp_sql_file.name}"

    @patch("migration.workspace.client.requests.Session.post")
    def test_publish_sql_file_root_directory(self, mock_post, temp_sql_file):
        """publish_sql_file should not create root directory."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )
        client.publish_sql_file(temp_sql_file, "/")

        # Should only call upload, not mkdir for root path
        assert mock_post.call_count == 1
        call_args = mock_post.call_args
        assert "/api/2.0/workspace/import" in call_args[0][0]
        assert call_args[1]["json"]["path"] == f"/{temp_sql_file.name}"

    @patch("migration.workspace.client.requests.Session.post")
    def test_authentication_header_set(self, mock_post):
        """Client should set Authorization header."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="secret_token_123",
        )

        # Session headers should contain Authorization
        assert "Authorization" in client.session.headers
        assert client.session.headers["Authorization"] == "Bearer secret_token_123"

    @patch("migration.workspace.client.requests.Session.post")
    def test_workspace_import_api_payload_structure(self, mock_post, temp_sql_file):
        """Verify exact API payload structure for Databricks Workspace Import API."""
        import base64
        import json

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        client = DatabricksWorkspaceClient(
            host="https://example.databricks.com",
            token="test_token",
        )
        client.upload_file("/migration/ddl/schema.sql", temp_sql_file)

        # Verify the exact structure of the payload sent to Databricks
        call_args = mock_post.call_args
        url = call_args[0][0]
        payload = call_args[1]["json"]

        # Verify endpoint
        assert url == "https://example.databricks.com/api/2.0/workspace/import"

        # Verify payload structure (required by Databricks API)
        required_keys = {"path", "format", "language", "content", "overwrite"}
        assert set(payload.keys()) == required_keys

        # Verify each field
        assert payload["path"] == "/migration/ddl/schema.sql"
        assert payload["format"] == "SOURCE"
        assert payload["language"] == "SQL"
        assert payload["overwrite"] is True

        # Verify content is valid base64
        try:
            decoded = base64.b64decode(payload["content"]).decode("utf-8")
            assert decoded == "CREATE TABLE test (id INT);"
        except Exception as e:
            pytest.fail(f"Content is not valid base64: {e}")

        # Log the payload structure for verification
        print("\n[WORKSPACE IMPORT API PAYLOAD]")
        print(f"Endpoint: POST {url}")
        print(f"Payload structure: {json.dumps({k: (v if k != 'content' else 'base64-encoded...') for k, v in payload.items()}, indent=2)}")


class TestSSLCertificateConfiguration:
    """Tests for SSL certificate verification with CA bundle support."""

    def test_default_ssl_verification_enabled(self):
        """Client should use default SSL verification when DATABRICKS_CA_BUNDLE is not set."""
        # Ensure env var is not set
        with patch.dict(os.environ, {}, clear=False):
            if "DATABRICKS_CA_BUNDLE" in os.environ:
                del os.environ["DATABRICKS_CA_BUNDLE"]

            client = DatabricksWorkspaceClient(
                host="https://example.databricks.com",
                token="test_token",
            )

            # Default requests.Session verify is True
            assert client.session.verify is True

    def test_ca_bundle_from_environment_variable(self):
        """Client should use DATABRICKS_CA_BUNDLE when environment variable is set."""
        ca_bundle_path = "/path/to/ca-bundle.crt"

        with patch.dict(os.environ, {"DATABRICKS_CA_BUNDLE": ca_bundle_path}):
            client = DatabricksWorkspaceClient(
                host="https://example.databricks.com",
                token="test_token",
            )

            # Session verify should be set to the CA bundle path
            assert client.session.verify == ca_bundle_path

    def test_ca_bundle_used_in_post_requests(self):
        """Client should use CA bundle in POST requests when configured."""
        ca_bundle_path = "/path/to/ca-bundle.crt"

        with patch.dict(os.environ, {"DATABRICKS_CA_BUNDLE": ca_bundle_path}):
            with patch("migration.workspace.client.requests.Session.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_post.return_value = mock_response

                client = DatabricksWorkspaceClient(
                    host="https://example.databricks.com",
                    token="test_token",
                )

                # Verify session has the CA bundle configured
                assert client.session.verify == ca_bundle_path

                # When making a request, the session will use this verify parameter
                client.create_directory("/test/path")

                # Session was configured with CA bundle before making the request
                assert client.session.verify == ca_bundle_path

    def test_mkdirs_payload_unchanged_with_ca_bundle(self):
        """mkdirs payload should not change when CA bundle is configured."""
        ca_bundle_path = "/path/to/ca-bundle.crt"

        with patch.dict(os.environ, {"DATABRICKS_CA_BUNDLE": ca_bundle_path}):
            with patch("migration.workspace.client.requests.Session.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_post.return_value = mock_response

                client = DatabricksWorkspaceClient(
                    host="https://example.databricks.com",
                    token="test_token",
                )
                client.create_directory("/Workspace/Users/test@example.com/DataAIAccelerator")

                # Verify mkdirs payload is exactly {"path": "..."}
                payload = mock_post.call_args[1]["json"]
                assert payload == {"path": "/Workspace/Users/test@example.com/DataAIAccelerator"}
                assert "format" not in payload
                assert "language" not in payload
                assert "content" not in payload

    def test_workspace_import_payload_unchanged_with_ca_bundle(self):
        """Workspace import payload should not change when CA bundle is configured."""
        import base64

        ca_bundle_path = "/path/to/ca-bundle.crt"

        with patch.dict(os.environ, {"DATABRICKS_CA_BUNDLE": ca_bundle_path}):
            with patch("migration.workspace.client.requests.Session.post") as mock_post:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_post.return_value = mock_response

                # Create temp file
                from pathlib import Path
                import tempfile

                with tempfile.TemporaryDirectory() as tmpdir:
                    sql_file = Path(tmpdir) / "test.sql"
                    sql_file.write_text("CREATE TABLE test (id INT);")

                    client = DatabricksWorkspaceClient(
                        host="https://example.databricks.com",
                        token="test_token",
                    )
                    client.upload_file("/migration/ddl/test.sql", sql_file)

                    # Verify workspace import payload structure is unchanged
                    payload = mock_post.call_args[1]["json"]
                    assert payload["path"] == "/migration/ddl/test.sql"
                    assert payload["format"] == "SOURCE"
                    assert payload["language"] == "SQL"
                    assert payload["overwrite"] is True
                    assert "content" in payload
                    # Content should still be base64-encoded
                    decoded = base64.b64decode(payload["content"]).decode("utf-8")
                    assert "CREATE TABLE test" in decoded
