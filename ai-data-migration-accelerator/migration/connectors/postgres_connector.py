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
        url = (
            f"postgresql+psycopg://{self.username}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
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
