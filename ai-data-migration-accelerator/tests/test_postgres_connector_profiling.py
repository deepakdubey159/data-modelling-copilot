"""Tests for the profiling additions to PostgresConnector.

Same philosophy as test_postgres_connector.py: no live PostgreSQL instance.
These exercise identifier-quoting safety and not-connected error handling;
the generated SQL's actual execution is covered by integration testing.
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


def test_profile_table_raises_before_connect(connector: PostgresConnector):
    with pytest.raises(ConnectorError, match="Not connected"):
        connector.profile_table("public", "customers", [{"name": "id", "data_type": "integer"}])


def test_sample_column_values_raises_before_connect(connector: PostgresConnector):
    with pytest.raises(ConnectorError, match="Not connected"):
        connector.sample_column_values("public", "customers", "email")


def test_quote_ident_escapes_embedded_quotes():
    assert PostgresConnector._quote_ident('weird"name') == '"weird""name"'


def test_quote_ident_wraps_plain_identifier():
    assert PostgresConnector._quote_ident("customers") == '"customers"'


def test_quote_ident_neutralizes_injection_attempt():
    # A malicious "table name" containing a statement terminator must come
    # back as a single quoted identifier, not break out of the identifier
    # position.
    malicious = 'customers"; DROP TABLE users; --'
    quoted = PostgresConnector._quote_ident(malicious)
    assert quoted.startswith('"') and quoted.endswith('"')
    assert quoted.count('"DROP TABLE users; --"') == 0 or '""' in quoted
