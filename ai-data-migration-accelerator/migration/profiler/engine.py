"""
Data Profiler

Walks the canonical metadata model (Milestone 2 input: `DatabaseMetadata`,
produced by `migration/metadata/builder.py`) and, for each table, asks the
connector for row-level statistics via `BaseConnector.profile_table` /
`sample_column_values`.

This module contains no SQL and no vendor-specific logic — that lives in
the connector, exactly like `metadata/builder.py` stays SQL-free. The
profiler's job is orchestration (which tables/columns to profile, how to
combine connector output into the canonical profile models) and the one
piece of genuinely cross-vendor logic: lightweight pattern detection over
sampled values, done in Python so every connector gets it for free.
"""

from __future__ import annotations

import logging
import re

from migration.canonical.models import ColumnMetadata, DatabaseMetadata, TableMetadata
from migration.connectors.base import BaseConnector, ConnectorError
from migration.profiler.models import (
    ColumnProfile,
    DatabaseProfile,
    ProfilePackage,
    SchemaProfile,
    TableProfile,
)

logger = logging.getLogger(__name__)

# Sample-based pattern classifiers. Order doesn't matter — the best match
# (by match ratio) wins. A pattern must match at least MIN_PATTERN_RATIO of
# the sampled non-null values to be reported at all; below that, the column
# is left unclassified rather than reporting a low-confidence guess.
_PATTERNS: dict[str, re.Pattern[str]] = {
    "email": re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$"),
    "uuid": re.compile(
        r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
    ),
    "date_iso": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
    "phone_like": re.compile(r"^\+?[0-9()\-\s]{7,15}$"),
    "numeric_string": re.compile(r"^-?\d+(\.\d+)?$"),
    "upper_code": re.compile(r"^[A-Z0-9_\-]+$"),
}

_MIN_PATTERN_RATIO = 0.8

# Postgres data types worth sampling for pattern detection. Numeric/date
# types already get exact min/max from profile_table; pattern detection is
# aimed at free-form text columns.
_TEXT_TYPES = {"character varying", "varchar", "character", "char", "text", "citext"}


class DataProfiler:
    """Profiles every table in a `DatabaseMetadata` using a connected connector."""

    def __init__(self, connector: BaseConnector, sample_size: int = 200):
        self.connector = connector
        self.sample_size = sample_size

    def profile(self, metadata: DatabaseMetadata) -> ProfilePackage:
        """Profile every schema/table in `metadata`. Returns a ProfilePackage."""
        schema_profiles = []
        for schema in metadata.schemas:
            table_profiles = [
                self._profile_table(schema.schema_name, table) for table in schema.tables
            ]
            schema_profiles.append(
                SchemaProfile(schema_name=schema.schema_name, tables=table_profiles)
            )

        database_profile = DatabaseProfile(
            database_name=metadata.database_name, schemas=schema_profiles
        )
        return ProfilePackage(profile=database_profile)

    # -- Internal ----------------------------------------------------------

    def _profile_table(self, schema_name: str, table: TableMetadata) -> TableProfile:
        logger.info("Profiling %s.%s", schema_name, table.table_name)

        try:
            raw = self.connector.profile_table(
                schema_name,
                table.table_name,
                [{"name": col.name, "data_type": col.data_type} for col in table.columns],
            )
        except ConnectorError as exc:
            logger.warning(
                "Skipping profile for %s.%s due to error: %s",
                schema_name,
                table.table_name,
                exc,
            )
            return TableProfile(table_name=table.table_name, profiling_error=str(exc))

        row_count: int = raw["row_count"]
        raw_columns: dict = raw.get("columns", {})

        columns = [
            self._build_column_profile(schema_name, table.table_name, col, row_count, raw_columns)
            for col in table.columns
        ]

        duplicate_row_count = raw.get("duplicate_row_count")
        duplicate_percentage = (
            round(duplicate_row_count / row_count * 100, 2)
            if row_count and duplicate_row_count is not None
            else None
        )

        return TableProfile(
            table_name=table.table_name,
            row_count=row_count,
            duplicate_row_count=duplicate_row_count,
            duplicate_percentage=duplicate_percentage,
            columns=columns,
        )

    def _build_column_profile(
        self,
        schema_name: str,
        table_name: str,
        column: ColumnMetadata,
        row_count: int,
        raw_columns: dict,
    ) -> ColumnProfile:
        stats = raw_columns.get(column.name, {})
        null_count = stats.get("null_count") or 0
        distinct_count = stats.get("distinct_count") or 0

        detected_pattern: str | None = None
        pattern_match_ratio: float | None = None
        if column.data_type.lower() in _TEXT_TYPES:
            detected_pattern, pattern_match_ratio = self._detect_pattern(
                schema_name, table_name, column.name
            )

        return ColumnProfile(
            name=column.name,
            data_type=column.data_type,
            null_count=null_count,
            null_percentage=round(null_count / row_count * 100, 2) if row_count else 0.0,
            distinct_count=distinct_count,
            distinct_percentage=round(distinct_count / row_count * 100, 2) if row_count else 0.0,
            min_value=stats.get("min_value"),
            max_value=stats.get("max_value"),
            min_length=stats.get("min_length"),
            max_length=stats.get("max_length"),
            detected_pattern=detected_pattern,
            pattern_match_ratio=pattern_match_ratio,
        )

    def _detect_pattern(
        self, schema_name: str, table_name: str, column_name: str
    ) -> tuple[str | None, float | None]:
        try:
            samples = self.connector.sample_column_values(
                schema_name, table_name, column_name, self.sample_size
            )
        except ConnectorError as exc:
            logger.debug(
                "Pattern sampling failed for %s.%s.%s: %s",
                schema_name,
                table_name,
                column_name,
                exc,
            )
            return None, None

        values = [str(v).strip() for v in samples if v is not None and str(v).strip() != ""]
        if not values:
            return None, None

        best_name: str | None = None
        best_ratio = 0.0
        for name, pattern in _PATTERNS.items():
            matches = sum(1 for v in values if pattern.match(v))
            ratio = matches / len(values)
            if ratio > best_ratio:
                best_name, best_ratio = name, ratio

        if best_ratio >= _MIN_PATTERN_RATIO:
            return best_name, round(best_ratio, 2)
        return None, None
