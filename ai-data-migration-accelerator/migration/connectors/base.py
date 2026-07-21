"""
Base connector interface for the AI Data Migration Accelerator.

Every source database connector (PostgreSQL now; Oracle, SQL Server, MySQL,
SAP HANA, Snowflake, Databricks, BigQuery, Redshift later) must implement
this interface. Nothing outside `migration/connectors/` should ever import a
vendor-specific driver directly — the rest of the application depends only
on `BaseConnector`, which keeps the metadata-extraction pipeline agnostic to
the source platform.

Each `extract_*` method returns plain Python data structures (lists of
dicts) representing *native* metadata for that vendor. Translating that
native shape into the canonical metadata model is the job of the
`migration/canonical/` layer (Milestone 2), not the connector — this keeps
each connector's responsibility limited to "talk to this one database."
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ConnectorError(Exception):
    """Raised for any connector-level failure (connect, query, etc.)."""


class BaseConnector(ABC):
    """Abstract contract for a source database connector."""

    def __init__(self, host: str, port: int, database: str, username: str, password: str):
        self.host = host
        self.port = port
        self.database = database
        self.username = username
        self.password = password
        self._is_connected: bool = False

    # -- Lifecycle -----------------------------------------------------

    @abstractmethod
    def connect(self) -> None:
        """Open a connection to the source database.

        Implementations should raise `ConnectorError` on failure rather than
        letting a driver-specific exception leak out of this layer.
        """

    @abstractmethod
    def disconnect(self) -> None:
        """Close the connection. Must be safe to call even if not connected."""

    @abstractmethod
    def validate_connection(self) -> bool:
        """Run a lightweight round-trip (e.g. `SELECT 1`) to confirm the
        connection is live and usable. Returns True/False rather than
        raising, so callers can decide how to react.
        """

    # -- Metadata extraction --------------------------------------------
    # Each of these returns a list of dicts in the connector's *native*
    # shape. Milestone 1 only requires extract_tables + extract_columns to
    # have a working PostgreSQL implementation; the remaining methods are
    # part of the contract now so later milestones don't need to touch the
    # interface again.

    @abstractmethod
    def extract_tables(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return table metadata for the given schemas."""

    @abstractmethod
    def extract_columns(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return column metadata for the given schemas."""

    @abstractmethod
    def extract_primary_keys(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return primary key metadata for the given schemas."""

    @abstractmethod
    def extract_foreign_keys(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return foreign key metadata for the given schemas."""

    @abstractmethod
    def extract_constraints(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return check/unique/not-null constraint metadata."""

    @abstractmethod
    def extract_indexes(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return index metadata for the given schemas."""

    @abstractmethod
    def extract_views(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return view metadata (including view definitions)."""

    @abstractmethod
    def extract_procedures(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return stored procedure metadata."""

    @abstractmethod
    def extract_functions(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return user-defined function metadata."""

    @abstractmethod
    def extract_triggers(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return trigger metadata."""

    @abstractmethod
    def extract_statistics(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Return table/column statistics (row counts, sizes, etc.)."""

    # -- Context manager convenience -------------------------------------

    def __enter__(self) -> "BaseConnector":
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        self.disconnect()
