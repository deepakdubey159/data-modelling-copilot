"""
Connector factory.

Single responsibility: given a validated `SourceConfig`, return the correct
`BaseConnector` implementation.
"""

from __future__ import annotations

from migration.connectors.base import BaseConnector
from migration.connectors.db2_connector import DB2Connector
from migration.connectors.postgres_connector import PostgresConnector
from migration.models.config import SourceConfig, SourceType


class UnsupportedSourceError(Exception):
    """Raised when a config requests a source type with no connector yet."""


def create_connector(source: SourceConfig) -> BaseConnector:
    """Instantiate the connector for the given source configuration."""

    if source.type == SourceType.POSTGRES:
        return PostgresConnector(
            host=source.host,
            port=source.port,
            database=source.database,
            username=source.username,
            password=source.password,
            connection_timeout=source.connection_timeout,
        )

    if source.type == SourceType.DB2:
        return DB2Connector(
            host=source.host,
            port=source.port,
            database=source.database,
            username=source.username,
            password=source.password,
            connection_timeout=source.connection_timeout,
        )

    raise UnsupportedSourceError(
        f"No connector implemented yet for source type '{source.type.value}'. "
        "Supported: 'postgres', 'db2'."
    )