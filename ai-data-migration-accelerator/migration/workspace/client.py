"""Databricks Workspace REST API client for publishing SQL files."""

import base64
import logging
import os
from pathlib import Path

import requests

logger = logging.getLogger(__name__)


class DatabricksWorkspaceClient:
    """Client for uploading files to Databricks Workspace."""

    def __init__(self, host: str, token: str):
        """Initialize Databricks Workspace client.

        Args:
            host: Databricks workspace hostname.
            token: Databricks personal access token.

        Environment Variables:
            DATABRICKS_CA_BUNDLE:
                Optional path to a CA certificate bundle for SSL verification.
        """
        self.host = host.rstrip("/")
        self.token = token

        self.session = requests.Session()
        self.session.headers.update(
            {
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

        # Optional custom CA bundle.
        ca_bundle = os.environ.get("DATABRICKS_CA_BUNDLE")
        if ca_bundle:
            self.session.verify = ca_bundle

    # ------------------------------------------------------------------
    # Workspace path handling
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_workspace_path(workspace_path: str) -> str:
        """Normalize a Databricks Workspace API path.

        IMPORTANT:
        Workspace paths are Databricks POSIX/API paths and must NOT be
        processed using Windows filesystem path functions such as
        os.path.abspath(), os.path.normpath(), or pathlib.Path().

        Git Bash/MSYS can sometimes transform:

            /Workspace/Users/user@example.com/DataAIAccelerator

        into:

            C:/Program Files/Git/Workspace/Users/user@example.com/DataAIAccelerator

        This method converts that value back to the correct Databricks
        Workspace path.
        """
        if not workspace_path:
            return "/"

        path = workspace_path.strip()

        # Normalize Windows separators if they appear.
        path = path.replace("\\", "/")

        # Recover Git Bash/MSYS path conversion.
        msys_prefixes = (
            "C:/Program Files/Git/Workspace/",
            "C:/Program Files/Git/Workspace",
        )

        for prefix in msys_prefixes:
            if path.startswith(prefix):
                path = "/" + path[len("C:/Program Files/Git/") :]
                break

        # Workspace API paths must begin with "/".
        if not path.startswith("/"):
            path = "/" + path

        # Remove duplicate trailing slash except for root.
        if path != "/":
            path = path.rstrip("/")

        return path

    # ------------------------------------------------------------------
    # Workspace directory operations
    # ------------------------------------------------------------------

    def create_directory(self, workspace_path: str) -> None:
        """Create a directory in Databricks Workspace."""
        workspace_path = self._normalize_workspace_path(workspace_path)

        url = f"{self.host}/api/2.0/workspace/mkdirs"

        payload = {
            "path": workspace_path,
        }

        response = self.session.post(
            url,
            json=payload,
            timeout=30,
        )

        # Directory already exists.
        if response.status_code == 409:
            logger.info(
                "Workspace directory already exists: %s",
                workspace_path,
            )
            return

        response.raise_for_status()

        logger.info(
            "Created workspace directory: %s",
            workspace_path,
        )

    def ensure_directory(self, workspace_path: str) -> None:
        """Ensure that a Workspace directory exists.

        Uses mkdirs idempotency: if the directory already exists,
        mkdirs returns 409, which is handled gracefully.
        """
        self.create_directory(workspace_path)

    # ------------------------------------------------------------------
    # Workspace file upload
    # ------------------------------------------------------------------

    def upload_file(
        self,
        workspace_path: str,
        local_file_path: Path,
    ) -> None:
        """Upload a local file to Databricks Workspace.

        Databricks Workspace Import API requires the file content to be
        base64 encoded when using the JSON request format.
        """
        workspace_path = self._normalize_workspace_path(workspace_path)

        if not local_file_path.exists():
            raise FileNotFoundError(
                f"File not found: {local_file_path}"
            )

        if not local_file_path.is_file():
            raise ValueError(
                f"Path is not a file: {local_file_path}"
            )

        # Read the local SQL file as UTF-8 bytes.
        content_bytes = local_file_path.read_bytes()

        # Databricks Workspace Import API expects base64 content.
        content_b64 = base64.b64encode(content_bytes).decode("utf-8")

        url = f"{self.host}/api/2.0/workspace/import"

        payload = {
            "path": workspace_path,
            "format": "SOURCE",
            "language": "SQL",
            "content": content_b64,
            "overwrite": True,
        }

        response = self.session.post(
            url,
            json=payload,
            timeout=30,
        )

        response.raise_for_status()

        logger.info(
            "Uploaded file to workspace: %s",
            workspace_path,
        )

    # ------------------------------------------------------------------
    # SQL publishing
    # ------------------------------------------------------------------

    def publish_sql_file(
        self,
        sql_file_path: Path,
        workspace_path: str,
    ) -> None:
        """Publish a SQL file to Databricks Workspace.

        Args:
            sql_file_path:
                Local SQL file.

            workspace_path:
                Databricks Workspace DIRECTORY.

        Example:

            Local:
                output/bronze/databricks.sql

            Workspace directory:
                /Workspace/Users/user@example.com/DataAIAccelerator

            Final Workspace file:
                /Workspace/Users/user@example.com/
                DataAIAccelerator/databricks.sql

        The SQL is uploaded only. It is NOT executed.
        """
        if not sql_file_path.exists():
            raise FileNotFoundError(
                f"SQL file not found: {sql_file_path}"
            )

        workspace_dir = self._normalize_workspace_path(
            workspace_path
        )

        # Ensure target Workspace directory exists.
        if workspace_dir != "/":
            self.ensure_directory(workspace_dir)

        # Keep the local filename.
        filename = sql_file_path.name

        # Build a Databricks Workspace API path.
        if workspace_dir == "/":
            destination_path = f"/{filename}"
        else:
            destination_path = (
                f"{workspace_dir}/{filename}"
            )

        destination_path = self._normalize_workspace_path(
            destination_path
        )

        logger.info(
            "Publishing SQL file: %s -> %s",
            sql_file_path,
            destination_path,
        )

        # Upload only. No SQL execution.
        self.upload_file(
            destination_path,
            sql_file_path,
        )