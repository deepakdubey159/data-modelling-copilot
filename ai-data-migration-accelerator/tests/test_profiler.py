"""Tests for migration.profiler.engine.

Follows the same approach as test_postgres_connector.py: no live database.
A minimal fake connector stands in for BaseConnector so the profiler's
orchestration logic (percentage math, pattern detection, error handling)
can be tested in isolation from real SQL.
"""

from __future__ import annotations

from typing import Any

import pytest

from migration.canonical.models import ColumnMetadata, DatabaseMetadata, SchemaMetadata, TableMetadata
from migration.connectors.base import ConnectorError
from migration.profiler.engine import DataProfiler


class FakeConnector:
    """Minimal stand-in for BaseConnector's profiling methods."""

    def __init__(self, profile_result: dict[str, Any], samples: dict[str, list] | None = None):
        self._profile_result = profile_result
        self._samples = samples or {}
        self.profile_calls: list[tuple] = []

    def profile_table(self, schema: str, table: str, columns: list[dict[str, Any]]) -> dict[str, Any]:
        self.profile_calls.append((schema, table, columns))
        return self._profile_result

    def sample_column_values(self, schema: str, table: str, column: str, limit: int = 200) -> list:
        return self._samples.get(column, [])


def _one_table_metadata(columns: list[ColumnMetadata]) -> DatabaseMetadata:
    table = TableMetadata(table_name="customers", table_type="BASE TABLE", columns=columns)
    schema = SchemaMetadata(schema_name="public", tables=[table])
    return DatabaseMetadata(database_name="sales", source_database_type="postgres", schemas=[schema])


def test_profile_computes_null_and_distinct_percentages():
    metadata = _one_table_metadata(
        [ColumnMetadata(name="id", data_type="integer", nullable=False, ordinal_position=1)]
    )
    connector = FakeConnector(
        {
            "row_count": 200,
            "duplicate_row_count": 10,
            "columns": {"id": {"null_count": 20, "distinct_count": 180}},
        }
    )

    result = DataProfiler(connector).profile(metadata)
    table_profile = result.profile.schemas[0].tables[0]

    assert table_profile.row_count == 200
    assert table_profile.duplicate_row_count == 10
    assert table_profile.duplicate_percentage == 5.0

    col = table_profile.columns[0]
    assert col.null_count == 20
    assert col.null_percentage == 10.0
    assert col.distinct_count == 180
    assert col.distinct_percentage == 90.0


def test_profile_handles_zero_rows_without_division_error():
    metadata = _one_table_metadata(
        [ColumnMetadata(name="id", data_type="integer", nullable=False, ordinal_position=1)]
    )
    connector = FakeConnector(
        {"row_count": 0, "duplicate_row_count": 0, "columns": {"id": {"null_count": 0, "distinct_count": 0}}}
    )

    result = DataProfiler(connector).profile(metadata)
    col = result.profile.schemas[0].tables[0].columns[0]

    assert col.null_percentage == 0.0
    assert col.distinct_percentage == 0.0


def test_profile_table_error_is_captured_not_raised():
    metadata = _one_table_metadata(
        [ColumnMetadata(name="id", data_type="integer", nullable=False, ordinal_position=1)]
    )

    class FailingConnector(FakeConnector):
        def profile_table(self, schema, table, columns):
            raise ConnectorError("permission denied")

    result = DataProfiler(FailingConnector({})).profile(metadata)
    table_profile = result.profile.schemas[0].tables[0]

    assert table_profile.profiling_error == "permission denied"
    assert table_profile.columns == []


def test_duplicate_row_count_none_is_preserved_as_unknown():
    metadata = _one_table_metadata(
        [ColumnMetadata(name="payload", data_type="json", nullable=True, ordinal_position=1)]
    )
    connector = FakeConnector(
        {
            "row_count": 100,
            "duplicate_row_count": None,
            "columns": {"payload": {"null_count": 0, "distinct_count": 100}},
        }
    )

    result = DataProfiler(connector).profile(metadata)
    table_profile = result.profile.schemas[0].tables[0]

    assert table_profile.duplicate_row_count is None
    assert table_profile.duplicate_percentage is None


def test_pattern_detection_matches_email_column():
    metadata = _one_table_metadata(
        [ColumnMetadata(name="email", data_type="character varying", nullable=True, ordinal_position=1)]
    )
    connector = FakeConnector(
        {
            "row_count": 3,
            "duplicate_row_count": 0,
            "columns": {"email": {"null_count": 0, "distinct_count": 3}},
        },
        samples={"email": ["a@example.com", "b@example.com", "c@example.com"]},
    )

    result = DataProfiler(connector).profile(metadata)
    col = result.profile.schemas[0].tables[0].columns[0]

    assert col.detected_pattern == "email"
    assert col.pattern_match_ratio == 1.0


def test_pattern_detection_skipped_for_non_text_columns():
    metadata = _one_table_metadata(
        [ColumnMetadata(name="id", data_type="integer", nullable=False, ordinal_position=1)]
    )
    connector = FakeConnector(
        {"row_count": 3, "duplicate_row_count": 0, "columns": {"id": {"null_count": 0, "distinct_count": 3}}},
        samples={"id": ["1", "2", "3"]},
    )

    result = DataProfiler(connector).profile(metadata)
    col = result.profile.schemas[0].tables[0].columns[0]

    # Numeric columns already get exact min/max from profile_table; pattern
    # detection is reserved for free-form text types.
    assert col.detected_pattern is None


def test_pattern_below_confidence_threshold_is_unclassified():
    metadata = _one_table_metadata(
        [ColumnMetadata(name="notes", data_type="text", nullable=True, ordinal_position=1)]
    )
    connector = FakeConnector(
        {"row_count": 4, "duplicate_row_count": 0, "columns": {"notes": {"null_count": 0, "distinct_count": 4}}},
        samples={"notes": ["a@example.com", "just some free text", "another note", "42"]},
    )

    result = DataProfiler(connector).profile(metadata)
    col = result.profile.schemas[0].tables[0].columns[0]

    assert col.detected_pattern is None
    assert col.pattern_match_ratio is None
