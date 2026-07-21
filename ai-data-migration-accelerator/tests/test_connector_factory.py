"""Tests for migration.connectors.factory."""

from __future__ import annotations

import pytest

from migration.connectors.factory import UnsupportedSourceError, create_connector
from migration.connectors.postgres_connector import PostgresConnector
from migration.models.config import SourceConfig, SourceType


def _source_config(source_type: SourceType) -> SourceConfig:
    return SourceConfig(
        type=source_type,
        host="localhost",
        port=5432,
        database="sales",
        username="postgres",
        password="postgres",
        schema=["public"],
    )


def test_create_postgres_connector():
    connector = create_connector(_source_config(SourceType.POSTGRES))
    assert isinstance(connector, PostgresConnector)
    assert connector.host == "localhost"
    assert connector.database == "sales"


def test_unsupported_source_type_raises():
    with pytest.raises(UnsupportedSourceError, match="oracle"):
        create_connector(_source_config(SourceType.ORACLE))
