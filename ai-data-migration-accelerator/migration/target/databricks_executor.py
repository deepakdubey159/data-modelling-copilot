"""
Databricks DDL executor.

Takes an already-generated `DDLScript` (produced by `DatabricksDDLGenerator`,
unchanged) and either previews it (dry-run, the default and the only mode
that needs no live connection) or executes it against a real Databricks SQL
warehouse.

Connection details come exclusively from environment variables named by
`TargetConfig` (`host_env`, `token_env`, `http_path_env`) - never from
source code or config.yaml literals - so the same code runs unmodified in
any client's Azure/AWS/GCP Databricks workspace.
"""

from __future__ import annotations

import logging
import os

from migration.ddl.models import DDLScript, DDLStatement
from migration.models.config import TargetConfig

logger = logging.getLogger(__name__)


class DatabricksExecutionError(Exception):
    """Raised for any failure connecting to or executing against Databricks."""


class MissingDatabricksCredentialsError(DatabricksExecutionError):
    """Raised when live execution is requested but required env vars are unset."""


class StatementResult:
    """Outcome of one executed (or dry-run-previewed) DDL statement."""

    def __init__(self, statement: DDLStatement, executed: bool, error: str | None = None):
        self.statement = statement
        self.executed = executed
        self.error = error

    @property
    def succeeded(self) -> bool:
        return self.executed and self.error is None


class ExecutionResult:
    """Outcome of an entire DDL script run (dry-run or live)."""

    def __init__(self, dry_run: bool, results: list[StatementResult]):
        self.dry_run = dry_run
        self.results = results

    @property
    def statement_count(self) -> int:
        return len(self.results)

    @property
    def failed_count(self) -> int:
        return sum(1 for r in self.results if r.error is not None)

    @property
    def succeeded(self) -> bool:
        return self.failed_count == 0

    @property
    def first_error(self) -> str | None:
        for r in self.results:
            if r.error is not None:
                return r.error
        return None


def _resolve_required_env(env_var_name: str, purpose: str) -> str:
    """Read a required credential/endpoint from the environment.

    Raises with the *variable name*, never the value, in the message - a
    missing-credential error must be actionable without ever risking a
    secret reaching a log or console.
    """
    value = os.environ.get(env_var_name, "").strip()
    if not value:
        raise MissingDatabricksCredentialsError(
            f"Databricks {purpose} is not configured. Set the environment "
            f"variable '{env_var_name}' (referenced by target.{purpose.replace(' ', '_')}_env "
            f"in config.yaml)."
        )
    return value


class DatabricksExecutor:
    """Executes (or previews) a `DDLScript` against a Databricks workspace."""

    def __init__(self, target: TargetConfig):
        self.target = target

    def resolve_connection_params(self) -> dict:
        """Resolve host/token/http_path from environment variables.

        Raises `MissingDatabricksCredentialsError` if any is unset. Called
        only when live execution is requested - dry-run never needs a
        connection, so it never calls this.
        """
        host = _resolve_required_env(self.target.host_env, "workspace host")
        token = _resolve_required_env(self.target.token_env, "access token")
        http_path = _resolve_required_env(self.target.http_path_env, "http path")

        if not self.target.catalog:
            raise MissingDatabricksCredentialsError(
                "target.catalog is not set in config.yaml. A Unity Catalog "
                "catalog name is required to execute DDL against Databricks."
            )

        return {"server_hostname": host, "http_path": http_path, "access_token": token}

    def _connect(self):
        """Open a live Databricks SQL connection. Lazy-imported so the
        `databricks-sql-connector` package is only required when execution
        is actually requested, matching how the Anthropic SDK is only
        imported inside `AnthropicClient.complete`."""
        try:
            from databricks import sql as databricks_sql
        except ImportError as exc:
            raise DatabricksExecutionError(
                "The 'databricks-sql-connector' package is required to execute "
                "DDL against Databricks. Install it with: "
                "pip install databricks-sql-connector"
            ) from exc

        params = self.resolve_connection_params()
        logger.info(
            "Connecting to Databricks workspace (catalog=%s)", self.target.catalog
        )
        try:
            return databricks_sql.connect(**params)
        except Exception as exc:
            raise DatabricksExecutionError(f"Failed to connect to Databricks: {exc}") from exc

    def run(self, script: DDLScript, dry_run: bool = True) -> ExecutionResult:
        """Preview (`dry_run=True`, default) or execute a DDL script.

        Dry-run never opens a connection and never requires credentials -
        it is always safe to call regardless of whether Databricks is
        configured yet. Live execution stops at the first failing
        statement rather than continuing past a broken schema state.
        """
        statements = script.all_statements()

        if dry_run:
            logger.info(
                "Dry run: %d statement(s) would be executed against Databricks "
                "(catalog=%s). No connection was opened.",
                len(statements),
                self.target.catalog or "<not configured>",
            )
            return ExecutionResult(
                dry_run=True,
                results=[StatementResult(stmt, executed=False) for stmt in statements],
            )

        connection = self._connect()
        results: list[StatementResult] = []
        try:
            cursor = connection.cursor()
            try:
                if self.target.catalog:
                    cursor.execute(f"USE CATALOG {self.target.catalog}")

                for stmt in statements:
                    try:
                        cursor.execute(stmt.statement)
                        results.append(StatementResult(stmt, executed=True))
                    except Exception as exc:
                        results.append(StatementResult(stmt, executed=True, error=str(exc)))
                        logger.error(
                            "Statement failed (%s): %s", stmt.statement_type, exc
                        )
                        break
            finally:
                cursor.close()
        finally:
            connection.close()

        return ExecutionResult(dry_run=False, results=results)
