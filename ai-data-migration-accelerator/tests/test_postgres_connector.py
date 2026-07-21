"""Tests for migration.connectors.postgres_connector.

These tests avoid requiring a live PostgreSQL instance: they exercise the
connector's state-management logic (raising before connect, disconnect
being idempotent) rather than real SQL execution, which is covered by
integration testing against an actual database.
"""

from __future__ import annotations

import pytest

from migration.connectors.base import ConnectorError
from migration.connectors.postgres_connector import PostgresConnector


@pytest.fixture
def connector() -> PostgresConnector:
    return PostgresConnector(
        host="localhost",
        port=5432,
        database="sales",
        username="postgres",
        password="postgres",
    )


def test_validate_connection_false_when_not_connected(connector: PostgresConnector):
    assert connector.validate_connection() is False


def test_extract_tables_raises_before_connect(connector: PostgresConnector):
    with pytest.raises(ConnectorError, match="Not connected"):
        connector.extract_tables(["public"])


def test_disconnect_is_idempotent(connector: PostgresConnector):
    # Should not raise even though connect() was never called.
    connector.disconnect()
    connector.disconnect()


def test_context_manager_calls_connect_and_disconnect(monkeypatch, connector: PostgresConnector):
    calls = []
    monkeypatch.setattr(connector, "connect", lambda: calls.append("connect"))
    monkeypatch.setattr(connector, "disconnect", lambda: calls.append("disconnect"))

    with connector:
        pass

    assert calls == ["connect", "disconnect"]
