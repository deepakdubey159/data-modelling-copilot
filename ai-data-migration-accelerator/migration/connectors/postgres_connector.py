"""
PostgreSQL connector.

Implements `BaseConnector` for PostgreSQL using SQLAlchemy (engine/connection
management) with psycopg as the driver. Metadata is pulled from
`information_schema` and `pg_catalog`, which are stable, well-documented
sources — this avoids depending on any single ORM's introspection quirks.

Milestone 1 provides working implementations of `extract_tables` and
`extract_columns` (required for the first successful run). The remaining
`extract_*` methods are implemented now too since PostgreSQL's queries are
straightforward, keeping this connector complete rather than partially
stubbed — but only tables/columns are exercised by Milestone 1's CLI flow.
"""


from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.exc import SQLAlchemyError

from migration.connectors.base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class PostgresConnector(BaseConnector):
    """Source connector for PostgreSQL databases."""

    def __init__(self, host: str, port: int, database: str, username: str, password: str):
        super().__init__(host, port, database, username, password)
        self._engine: Engine | None = None

    # -- Lifecycle -----------------------------------------------------

    def connect(self) -> None:
        url =  URL.create(drivername="postgresql+psycopg",
                             username=self.username,
                                password=self.password,
                                host=self.host,
                                port=self.port,
                                database=self.database,
        )
        try:
            self._engine = create_engine(url, pool_pre_ping=True)
            # Force an actual connection attempt now, rather than lazily
            # on first query, so connect() fails fast and loudly.
            with self._engine.connect():
                pass
            self._is_connected = True
            logger.info(
                "Connected to PostgreSQL database '%s' at %s:%s",
                self.database, self.host, self.port,
            )
        except SQLAlchemyError as exc:
            self._is_connected = False
            raise ConnectorError(
                f"Failed to connect to PostgreSQL at {self.host}:{self.port}/{self.database}: {exc}"
            ) from exc

    def disconnect(self) -> None:
        if self._engine is not None:
            self._engine.dispose()
            self._engine = None
        self._is_connected = False

    def validate_connection(self) -> bool:
        if self._engine is None:
            return False
        try:
            with self._engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return True
        except SQLAlchemyError as exc:
            logger.warning("Connection validation failed: %s", exc)
            return False

    # -- Internal helper --------------------------------------------------

    def _require_engine(self) -> Engine:
        if self._engine is None:
            raise ConnectorError("Not connected. Call connect() before extracting metadata.")
        return self._engine

    def _query(self, sql: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        engine = self._require_engine()
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql), params)
                return [dict(row._mapping) for row in result]
        except SQLAlchemyError as exc:
            raise ConnectorError(f"Metadata query failed: {exc}") from exc

    # -- Metadata extraction --------------------------------------------

    def extract_tables(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT table_schema, table_name, table_type
            FROM information_schema.tables
            WHERE table_schema = ANY(:schemas)
            ORDER BY table_schema, table_name
        """
        return self._query(sql, {"schemas": schemas})

    def extract_columns(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT table_schema, table_name, column_name, data_type,
                   is_nullable, column_default, ordinal_position,
                   character_maximum_length, numeric_precision, numeric_scale
            FROM information_schema.columns
            WHERE table_schema = ANY(:schemas)
            ORDER BY table_schema, table_name, ordinal_position
        """
        return self._query(sql, {"schemas": schemas})

    def extract_primary_keys(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT tc.table_schema, tc.table_name, kcu.column_name,
                   tc.constraint_name, kcu.ordinal_position
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = ANY(:schemas)
            ORDER BY tc.table_schema, tc.table_name, kcu.ordinal_position
        """
        return self._query(sql, {"schemas": schemas})

    def extract_foreign_keys(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT
                tc.table_schema, tc.table_name, kcu.column_name,
                ccu.table_schema AS foreign_table_schema,
                ccu.table_name AS foreign_table_name,
                ccu.column_name AS foreign_column_name,
                tc.constraint_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.constraint_column_usage ccu
              ON tc.constraint_name = ccu.constraint_name
             AND tc.table_schema = ccu.table_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = ANY(:schemas)
            ORDER BY tc.table_schema, tc.table_name
        """
        return self._query(sql, {"schemas": schemas})

    def extract_constraints(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT table_schema, table_name, constraint_name, constraint_type
            FROM information_schema.table_constraints
            WHERE table_schema = ANY(:schemas)
            ORDER BY table_schema, table_name
        """
        return self._query(sql, {"schemas": schemas})

    def extract_indexes(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT schemaname AS table_schema, tablename AS table_name,
                   indexname AS index_name, indexdef AS index_definition
            FROM pg_indexes
            WHERE schemaname = ANY(:schemas)
            ORDER BY schemaname, tablename, indexname
        """
        return self._query(sql, {"schemas": schemas})

    def extract_views(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT table_schema, table_name AS view_name, view_definition
            FROM information_schema.views
            WHERE table_schema = ANY(:schemas)
            ORDER BY table_schema, table_name
        """
        return self._query(sql, {"schemas": schemas})

    def extract_procedures(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT routine_schema, routine_name, routine_definition
            FROM information_schema.routines
            WHERE routine_schema = ANY(:schemas) AND routine_type = 'PROCEDURE'
            ORDER BY routine_schema, routine_name
        """
        return self._query(sql, {"schemas": schemas})

    def extract_functions(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT routine_schema, routine_name, routine_definition, data_type AS return_type
            FROM information_schema.routines
            WHERE routine_schema = ANY(:schemas) AND routine_type = 'FUNCTION'
            ORDER BY routine_schema, routine_name
        """
        return self._query(sql, {"schemas": schemas})

    def extract_triggers(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT trigger_schema, trigger_name, event_manipulation,
                   event_object_table, action_timing, action_statement
            FROM information_schema.triggers
            WHERE trigger_schema = ANY(:schemas)
            ORDER BY trigger_schema, trigger_name
        """
        return self._query(sql, {"schemas": schemas})

    def extract_statistics(self, schemas: list[str]) -> list[dict[str, Any]]:
        sql = """
            SELECT schemaname AS table_schema, relname AS table_name,
                   n_live_tup AS row_estimate, n_dead_tup AS dead_row_estimate,
                   last_analyze, last_autoanalyze
            FROM pg_stat_user_tables
            WHERE schemaname = ANY(:schemas)
            ORDER BY schemaname, relname
        """
        return self._query(sql, {"schemas": schemas})

    # -- Data profiling ---------------------------------------------------
    # These methods query actual row data (not catalog metadata), so unlike
    # extract_*, identifiers here can't be parameterized with SQLAlchemy
    # bind params — Postgres doesn't allow binding table/column names.
    # `_quote_ident` is used everywhere an identifier is interpolated to
    # guard against SQL injection via a malicious schema/table/column name.

    @staticmethod
    def _quote_ident(name: str) -> str:
        """Double-quote a Postgres identifier, escaping embedded quotes."""
        return '"' + name.replace('"', '""') + '"'

    def profile_table(
        self, schema: str, table: str, columns: list[dict[str, Any]]
    ) -> dict[str, Any]:
        engine = self._require_engine()
        qualified_table = f"{self._quote_ident(schema)}.{self._quote_ident(table)}"

        if not columns:
            row_count = self._scalar(f"SELECT COUNT(*) FROM {qualified_table}")
            return {"row_count": row_count, "duplicate_row_count": None, "columns": {}}

        aggregate_exprs = ["COUNT(*) AS row_count"]
        for col in columns:
            col_ident = self._quote_ident(col["name"])
            # One aggregate expression per column, packed into a single
            # table scan rather than one round trip per column.
            aggregate_exprs.append(
                f'COUNT(*) FILTER (WHERE {col_ident} IS NULL) AS "{col["name"]}__null_count"'
            )
            aggregate_exprs.append(
                f'COUNT(DISTINCT {col_ident}) AS "{col["name"]}__distinct_count"'
            )
            aggregate_exprs.append(f'MIN({col_ident}::text) AS "{col["name"]}__min_value"')
            aggregate_exprs.append(f'MAX({col_ident}::text) AS "{col["name"]}__max_value"')
            aggregate_exprs.append(
                f'MIN(LENGTH({col_ident}::text)) AS "{col["name"]}__min_length"'
            )
            aggregate_exprs.append(
                f'MAX(LENGTH({col_ident}::text)) AS "{col["name"]}__max_length"'
            )

        sql = f"SELECT {', '.join(aggregate_exprs)} FROM {qualified_table}"

        try:
            with engine.connect() as conn:
                row = conn.execute(text(sql)).mappings().one()
        except SQLAlchemyError as exc:
            raise ConnectorError(
                f"Profiling query failed for {schema}.{table}: {exc}"
            ) from exc

        row_count = row["row_count"]
        column_stats: dict[str, Any] = {}
        for col in columns:
            name = col["name"]
            column_stats[name] = {
                "null_count": row[f"{name}__null_count"],
                "distinct_count": row[f"{name}__distinct_count"],
                "min_value": row[f"{name}__min_value"],
                "max_value": row[f"{name}__max_value"],
                "min_length": row[f"{name}__min_length"],
                "max_length": row[f"{name}__max_length"],
            }

        duplicate_row_count = self._duplicate_row_count(qualified_table, columns, row_count)

        return {
            "row_count": row_count,
            "duplicate_row_count": duplicate_row_count,
            "columns": column_stats,
        }

    def _duplicate_row_count(
        self, qualified_table: str, columns: list[dict[str, Any]], row_count: int
    ) -> int | None:
        """Best-effort full-row duplicate count.

        Returns None (unknown) rather than raising if the table contains a
        column type that can't be used with PARTITION BY (e.g. json/array),
        since that's a routine occurrence, not an error worth failing the
        whole profiling run over.
        """
        if row_count == 0:
            return 0
        if not columns:
            return None

        col_list = ", ".join(self._quote_ident(c["name"]) for c in columns)
        sql = (
            f"SELECT COUNT(*) - COUNT(*) FILTER (WHERE rn = 1) FROM ("
            f"SELECT ROW_NUMBER() OVER (PARTITION BY {col_list}) AS rn "
            f"FROM {qualified_table}) t"
        )
        try:
            return self._scalar(sql)
        except ConnectorError as exc:
            logger.warning(
                "Could not compute duplicate row count for %s (%s); leaving as unknown.",
                qualified_table,
                exc,
            )
            return None

    def sample_column_values(
        self, schema: str, table: str, column: str, limit: int = 200
    ) -> list[Any]:
        qualified_table = f"{self._quote_ident(schema)}.{self._quote_ident(table)}"
        col_ident = self._quote_ident(column)
        sql = (
            f"SELECT {col_ident} FROM {qualified_table} "
            f"WHERE {col_ident} IS NOT NULL LIMIT :limit"
        )
        engine = self._require_engine()
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql), {"limit": limit})
                return [row[0] for row in result]
        except SQLAlchemyError as exc:
            raise ConnectorError(
                f"Sampling failed for {schema}.{table}.{column}: {exc}"
            ) from exc

    def _scalar(self, sql: str) -> Any:
        engine = self._require_engine()
        try:
            with engine.connect() as conn:
                return conn.execute(text(sql)).scalar_one()
        except SQLAlchemyError as exc:
            raise ConnectorError(f"Query failed: {sql}: {exc}") from exc
