"""Tests for migration.connectors.factory."""

from __future__ import annotations

import pytest

from migration.connectors.db2_connector import DB2Connector
from migration.connectors.factory import UnsupportedSourceError, create_connector
from migration.connectors.postgres_connector import PostgresConnector
from migration.models.config import SourceConfig, SourceType


def _source_config(source_type: SourceType, **overrides) -> SourceConfig:
    defaults = {
        "type": source_type,
        "host": "localhost",
        "port": 5432,
        "database": "sales",
        "username": "postgres",
        "password": "postgres",
        "schema": ["public"],
    }
    defaults.update(overrides)
    return SourceConfig(**defaults)


def test_create_postgres_connector():
    connector = create_connector(_source_config(SourceType.POSTGRES))
    assert isinstance(connector, PostgresConnector)
    assert connector.host == "localhost"
    assert connector.database == "sales"


def test_create_db2_connector():
    connector = create_connector(
        _source_config(
            SourceType.DB2,
            host="db2.example.com",
            port=50000,
            database="testdb",
            username="db2admin",
            password="password123",
        )
    )
    assert isinstance(connector, DB2Connector)
    assert connector.host == "db2.example.com"
    assert connector.port == 50000
    assert connector.database == "testdb"


def test_unsupported_source_type_raises():
    with pytest.raises(UnsupportedSourceError, match="oracle"):
        create_connector(_source_config(SourceType.ORACLE))
