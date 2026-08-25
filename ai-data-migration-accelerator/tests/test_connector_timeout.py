"""
Tests for connection timeout propagation from config to drivers.

Verifies that SourceConfig.connection_timeout correctly propagates
through the factory and connector layers to database drivers.
"""

from __future__ import annotations

from unittest import mock

import pytest

from migration.connectors.factory import create_connector
from migration.models.config import SourceConfig, SourceType


class TestPostgresTimeoutPropagation:
    """Verify PostgreSQL timeout propagates through SQLAlchemy to psycopg."""

    def test_postgres_connector_receives_timeout_from_config(self):
        """Factory should pass connection_timeout to PostgresConnector."""
        source = SourceConfig(
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass",
            schema=["public"],
            connection_timeout=15,
        )

        connector = create_connector(source)

        assert connector.connection_timeout == 15

    def test_postgres_connect_passes_timeout_to_sqlalchemy(self):
        """PostgresConnector should pass connect_timeout to create_engine."""
        source = SourceConfig(
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass",
            schema=["public"],
            connection_timeout=20,
        )

        connector = create_connector(source)

        with mock.patch("migration.connectors.postgres_connector.create_engine") as mock_create:
            mock_engine = mock.MagicMock()
            mock_engine.connect.return_value.__enter__ = lambda self: None
            mock_engine.connect.return_value.__exit__ = (
                lambda self, *args: None
            )
            mock_create.return_value = mock_engine

            connector.connect()

            # Verify create_engine was called with connect_args containing timeout
            call_kwargs = mock_create.call_args[1]
            assert "connect_args" in call_kwargs
            assert call_kwargs["connect_args"]["connect_timeout"] == 20

    def test_postgres_default_timeout_is_30(self):
        """PostgreSQL should default to 30 second timeout."""
        source = SourceConfig(
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass",
            schema=["public"],
            # connection_timeout not specified
        )

        assert source.connection_timeout == 30

        connector = create_connector(source)
        assert connector.connection_timeout == 30


class TestDB2TimeoutPropagation:
    """Verify DB2 timeout propagates through ibm_db DSN."""

    def test_db2_connector_receives_timeout_from_config(self):
        """Factory should pass connection_timeout to DB2Connector."""
        source = SourceConfig(
            type=SourceType.DB2,
            host="localhost",
            port=50000,
            database="testdb",
            username="user",
            password="pass",
            schema=["schema1"],
            connection_timeout=25,
        )

        connector = create_connector(source)

        assert connector.connection_timeout == 25

    def test_db2_connect_includes_timeout_in_dsn(self):
        """DB2Connector should include ConnectTimeout in DSN string."""
        source = SourceConfig(
            type=SourceType.DB2,
            host="localhost",
            port=50000,
            database="testdb",
            username="user",
            password="pass",
            schema=["schema1"],
            connection_timeout=10,
        )

        connector = create_connector(source)

        with mock.patch("migration.connectors.db2_connector.ibm_db") as mock_ibm:
            mock_connection = mock.MagicMock()
            mock_ibm.connect.return_value = mock_connection

            connector.connect()

            # Verify ibm_db.connect was called with DSN containing timeout
            call_args = mock_ibm.connect.call_args[0]
            dsn = call_args[0]

            assert "ConnectTimeout=10" in dsn, (
                f"DSN should contain ConnectTimeout=10, got: {dsn}"
            )
            assert "DATABASE=testdb" in dsn
            assert "HOSTNAME=localhost" in dsn
            assert "PORT=50000" in dsn
            assert "PROTOCOL=TCPIP" in dsn

    def test_db2_default_timeout_is_30(self):
        """DB2 should default to 30 second timeout."""
        source = SourceConfig(
            type=SourceType.DB2,
            host="localhost",
            port=50000,
            database="testdb",
            username="user",
            password="pass",
            schema=["schema1"],
            # connection_timeout not specified
        )

        assert source.connection_timeout == 30

        connector = create_connector(source)
        assert connector.connection_timeout == 30


class TestTimeoutConfigValidation:
    """Verify connection_timeout configuration validation."""

    def test_zero_timeout_is_rejected(self):
        """connection_timeout must be > 0."""
        with pytest.raises(ValueError):
            SourceConfig(
                type=SourceType.POSTGRES,
                host="localhost",
                port=5432,
                database="testdb",
                username="user",
                password="pass",
                schema=["public"],
                connection_timeout=0,
            )

    def test_negative_timeout_is_rejected(self):
        """connection_timeout must be > 0."""
        with pytest.raises(ValueError):
            SourceConfig(
                type=SourceType.POSTGRES,
                host="localhost",
                port=5432,
                database="testdb",
                username="user",
                password="pass",
                schema=["public"],
                connection_timeout=-5,
            )

    def test_large_timeout_is_accepted(self):
        """connection_timeout can be large (e.g., 300 seconds)."""
        source = SourceConfig(
            type=SourceType.POSTGRES,
            host="localhost",
            port=5432,
            database="testdb",
            username="user",
            password="pass",
            schema=["public"],
            connection_timeout=300,
        )

        assert source.connection_timeout == 300
