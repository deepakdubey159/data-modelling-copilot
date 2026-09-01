"""
DB2 connector.

Implements `BaseConnector` for IBM DB2 using ibm_db driver.
Metadata is pulled from SYSCAT (system catalog tables), which are
stable and well-documented sources for DB2 metadata extraction.

Supports both DB2 for LUX and DB2 for i (with minor SQL dialect differences).
"""

from __future__ import annotations

import logging
from typing import Any

try:
    import ibm_db
    import ibm_db_dbi
except ImportError:
    ibm_db = None
    ibm_db_dbi = None

from migration.connectors.base import BaseConnector, ConnectorError

logger = logging.getLogger(__name__)


class DB2Connector(BaseConnector):
    """Source connector for IBM DB2 databases."""

    def __init__(
        self,
        host: str,
        port: int,
        database: str,
        username: str,
        password: str,
        connection_timeout: int = 30,
    ):
        super().__init__(host, port, database, username, password, connection_timeout)
        self._connection = None

    # -- Lifecycle -----------------------------------------------

    def connect(self) -> None:
        """Open a connection to the DB2 database."""
        if ibm_db is None:
            raise ConnectorError(
                "ibm_db driver not installed. Install with: pip install ibm-db"
            )

        try:
            dsn = (
                f"DATABASE={self.database};"
                f"HOSTNAME={self.host};"
                f"PORT={self.port};"
                f"PROTOCOL=TCPIP;"
                f"UID={self.username};"
                f"PWD={self.password};"
                f"ConnectTimeout={self.connection_timeout};"
            )
            self._connection = ibm_db.connect(dsn, "", "")
            self._is_connected = True
            logger.info(
                "Connected to DB2 database '%s' at %s:%s (timeout=%ds)",
                self.database,
                self.host,
                self.port,
                self.connection_timeout,
            )
        except Exception as exc:
            self._is_connected = False
            raise ConnectorError(
                f"Failed to connect to DB2 at {self.host}:{self.port}/{self.database}: {exc}"
            ) from exc

    def disconnect(self) -> None:
        """Close the connection."""
        if self._connection is not None:
            try:
                ibm_db.close(self._connection)
            except Exception as exc:
                logger.warning("Error closing DB2 connection: %s", exc)
            self._connection = None
        self._is_connected = False

    def validate_connection(self) -> bool:
        """Validate that the connection is live and usable."""
        if self._connection is None:
            return False
        try:
            stmt = ibm_db.exec_immediate(self._connection, "SELECT 1 FROM SYSIBM.SYSDUMMY1")
            ibm_db.fetch_row(stmt)
            ibm_db.free_stmt(stmt)
            return True
        except Exception as exc:
            logger.warning("Connection validation failed: %s", exc)
            return False

    # -- Internal helpers ----------------------------------------

    def _require_connection(self):
        """Ensure we are connected."""
        if self._connection is None:
            raise ConnectorError("Not connected. Call connect() before extracting metadata.")
        return self._connection

    def _query(self, sql: str) -> list[dict[str, Any]]:
        """Execute a query and return results as list of dicts."""
        conn = self._require_connection()
        try:
            stmt = ibm_db.exec_immediate(conn, sql)
            if stmt is False:
                raise ConnectorError(f"Query execution failed: {ibm_db.stmt_errormsg()}")

            result = []
            while ibm_db.fetch_row(stmt):
                # Fetch as dictionary
                row_dict = ibm_db.fetch_assoc(stmt)
                if row_dict:
                    # ibm_db returns keys in uppercase; normalize to PostgreSQL-compatible keys
                    row_dict = self._normalize_keys(row_dict)
                    result.append(row_dict)

            ibm_db.free_stmt(stmt)
            return result
        except Exception as exc:
            raise ConnectorError(f"Metadata query failed: {exc}") from exc

    def _normalize_keys(self, row: dict[str, Any]) -> dict[str, Any]:
        """Normalize DB2 column names and values to PostgreSQL-compatible canonical keys."""
        # Mapping from DB2 uppercase keys to PostgreSQL-compatible lowercase keys
        key_mapping = {
            "TABSCHEMA": "table_schema",
            "TABNAME": "table_name",
            "TABTYPE": "table_type",
            "COLNAME": "column_name",
            "COLTYPE": "data_type",
            "NULLS": "is_nullable",
            "DEFAULT": "column_default",
            "COLNO": "ordinal_position",
            "LENGTH": "character_maximum_length",
            "SCALE": "numeric_scale",
            "PRECISION": "numeric_precision",
            "CONSTNAME": "constraint_name",
            "TYPE": "constraint_type",
            "COLSEQ": "ordinal_position",
            "REFTABSCHEMA": "foreign_table_schema",
            "REFTABNAME": "foreign_table_name",
            "REFCOLNAME": "foreign_column_name",
            "INDNAME": "index_name",
            "INDSCHEMA": "index_schema",
            "INDEXDEF": "index_definition",
            "UNIQUERULE": "uniqueness",
            "INDEXTYPE": "index_type",
            "VIEWSCHEMA": "view_schema",
            "VIEWNAME": "view_name",
            "TEXT": "definition",
            "ROUTINESCHEMA": "routine_schema",
            "ROUTINENAME": "routine_name",
            "ROUTINETYPE": "routine_type",
            "RETURNS": "return_type",
            "TRIGSCHEMA": "trigger_schema",
            "TRIGNAME": "trigger_name",
            "TRIGTIME": "trigger_timing",
            "TRIGEVENT": "trigger_event",
            "CARD": "card",
            "NPAGES": "npages",
            "FPAGES": "fpages",
            "OVERFLOW": "overflow",
        }

        normalized = {}
        for key, value in row.items():
            normalized_key = key_mapping.get(key, key.lower())
            normalized_value = value

            # Normalize DB2 nullable values (Y/N) to PostgreSQL format (YES/NO)
            if normalized_key == "is_nullable" and normalized_value in ("Y", "N"):
                normalized_value = "YES" if normalized_value == "Y" else "NO"

            normalized[normalized_key] = normalized_value

        return normalized

    # -- Metadata extraction ------------------------------------

    def extract_tables(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract table metadata from SYSCAT.TABLES."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                TABSCHEMA,
                TABNAME,
                TABTYPE
            FROM SYSCAT.TABLES
            WHERE TABSCHEMA IN ('{schema_list}')
                AND TABTYPE IN ('T', 'V')
            ORDER BY TABSCHEMA, TABNAME
        """
        return self._query(sql)

    def extract_columns(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract column metadata from SYSCAT.COLUMNS."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                TABSCHEMA,
                TABNAME,
                COLNAME,
                COLTYPE,
                NULLS,
                DEFAULT,
                COLNO,
                LENGTH,
                SCALE,
                PRECISION
            FROM SYSCAT.COLUMNS
            WHERE TABSCHEMA IN ('{schema_list}')
            ORDER BY TABSCHEMA, TABNAME, COLNO
        """
        return self._query(sql)

    def extract_primary_keys(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract primary key metadata."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                T.TABSCHEMA,
                T.TABNAME,
                C.COLNAME,
                K.CONSTNAME,
                K.COLSEQ
            FROM SYSCAT.TABCONST K
            JOIN SYSCAT.TABLES T ON K.TABID = T.TABID
            JOIN SYSCAT.KEYCOLUSE C ON K.CONSTID = C.CONSTID
            WHERE K.TYPE = 'P'
                AND T.TABSCHEMA IN ('{schema_list}')
            ORDER BY T.TABSCHEMA, T.TABNAME, C.COLSEQ
        """
        return self._query(sql)

    def extract_foreign_keys(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract foreign key metadata."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                T.TABSCHEMA,
                T.TABNAME,
                C.COLNAME,
                RT.TABSCHEMA AS REFTABSCHEMA,
                RT.TABNAME AS REFTABNAME,
                RC.COLNAME AS REFCOLNAME,
                R.CONSTNAME
            FROM SYSCAT.REFERENCES R
            JOIN SYSCAT.TABLES T ON R.TABID = T.TABID
            JOIN SYSCAT.TABLES RT ON R.REFTABID = RT.TABID
            JOIN SYSCAT.KEYCOLUSE C ON R.CONSTID = C.CONSTID
            JOIN SYSCAT.KEYCOLUSE RC ON R.REFCONID = RC.CONSTID
                AND C.COLSEQ = RC.COLSEQ
            WHERE T.TABSCHEMA IN ('{schema_list}')
            ORDER BY T.TABSCHEMA, T.TABNAME
        """
        return self._query(sql)

    def extract_constraints(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract check and unique constraint metadata."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                TABSCHEMA,
                TABNAME,
                CONSTNAME,
                TYPE
            FROM SYSCAT.TABCONST
            WHERE TABSCHEMA IN ('{schema_list}')
                AND TYPE IN ('U', 'C')
            ORDER BY TABSCHEMA, TABNAME
        """
        return self._query(sql)

    def extract_indexes(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract index metadata from SYSCAT.INDEXES.

        Note: unlike PostgreSQL's pg_indexes.indexdef, DB2's SYSCAT.INDEXES
        does not store the full CREATE INDEX statement. index_definition is
        normalized to an empty string (the canonical model requires a str);
        UNIQUERULE and index_type are preserved separately for downstream
        tools that need to reconstruct index semantics.
        """
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                INDSCHEMA,
                INDNAME,
                TABSCHEMA,
                TABNAME,
                UNIQUERULE,
                INDEXTYPE,
                CAST(NULL AS VARCHAR(1)) AS INDEXDEF
            FROM SYSCAT.INDEXES
            WHERE TABSCHEMA IN ('{schema_list}')
            ORDER BY TABSCHEMA, TABNAME, INDNAME
        """
        result = self._query(sql)
        for row in result:
            if row.get("index_definition") is None:
                row["index_definition"] = ""
        return result

    def extract_views(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract view metadata from SYSCAT.VIEWS."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                VIEWSCHEMA,
                VIEWNAME,
                TEXT
            FROM SYSCAT.VIEWS
            WHERE VIEWSCHEMA IN ('{schema_list}')
            ORDER BY VIEWSCHEMA, VIEWNAME
        """
        return self._query(sql)

    def extract_procedures(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract stored procedure metadata from SYSCAT.ROUTINES."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                ROUTINESCHEMA,
                ROUTINENAME,
                TEXT,
                ROUTINETYPE
            FROM SYSCAT.ROUTINES
            WHERE ROUTINESCHEMA IN ('{schema_list}')
                AND ROUTINETYPE = 'P'
            ORDER BY ROUTINESCHEMA, ROUTINENAME
        """
        return self._query(sql)

    def extract_functions(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract user-defined function metadata from SYSCAT.ROUTINES."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                ROUTINESCHEMA,
                ROUTINENAME,
                TEXT,
                RETURNS
            FROM SYSCAT.ROUTINES
            WHERE ROUTINESCHEMA IN ('{schema_list}')
                AND ROUTINETYPE = 'F'
            ORDER BY ROUTINESCHEMA, ROUTINENAME
        """
        return self._query(sql)

    def extract_triggers(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract trigger metadata from SYSCAT.TRIGGERS."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                TRIGSCHEMA,
                TRIGNAME,
                TRIGTIME,
                TRIGEVENT,
                TABNAME,
                TEXT
            FROM SYSCAT.TRIGGERS
            WHERE TRIGSCHEMA IN ('{schema_list}')
            ORDER BY TRIGSCHEMA, TRIGNAME
        """
        return self._query(sql)

    def extract_statistics(self, schemas: list[str]) -> list[dict[str, Any]]:
        """Extract table statistics from SYSCAT.TABLES."""
        schema_list = "', '".join(schemas)
        sql = f"""
            SELECT
                TABSCHEMA,
                TABNAME,
                CARD,
                NPAGES,
                FPAGES,
                OVERFLOW,
                CAST(NULL AS VARCHAR(1)) AS LAST_ANALYZE,
                CAST(NULL AS VARCHAR(1)) AS LAST_AUTOANALYZE
            FROM SYSCAT.TABLES
            WHERE TABSCHEMA IN ('{schema_list}')
                AND TABTYPE = 'T'
            ORDER BY TABSCHEMA, TABNAME
        """
        result = self._query(sql)
        # Rename CARD to ROW_ESTIMATE for builder compatibility
        for row in result:
            if "row_estimate" not in row and "card" in row:
                row["row_estimate"] = row.pop("card")
            if "dead_row_estimate" not in row:
                row["dead_row_estimate"] = None
            if "last_analyze" not in row:
                row["last_analyze"] = None
            if "last_autoanalyze" not in row:
                row["last_autoanalyze"] = None
        return result

    # -- Data profiling ------------------------------------------

    def profile_table(
        self, schema: str, table: str, columns: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Return data-profiling statistics for one table."""
        qualified_table = f"{self._quote_ident(schema)}.{self._quote_ident(table)}"

        if not columns:
            row_count = self._scalar(f"SELECT COUNT(*) FROM {qualified_table}")
            return {"row_count": row_count, "duplicate_row_count": None, "columns": {}}

        # Build aggregate expressions for all columns
        aggregate_exprs = ["COUNT(*) AS row_count"]
        for col in columns:
            col_ident = self._quote_ident(col["name"])
            aggregate_exprs.append(
                f'COUNT(*) - COUNT({col_ident}) AS "{col["name"]}__null_count"'
            )
            aggregate_exprs.append(
                f'COUNT(DISTINCT {col_ident}) AS "{col["name"]}__distinct_count"'
            )
            aggregate_exprs.append(f'MIN(CAST({col_ident} AS VARCHAR(4000))) AS "{col["name"]}__min_value"')
            aggregate_exprs.append(f'MAX(CAST({col_ident} AS VARCHAR(4000))) AS "{col["name"]}__max_value"')
            aggregate_exprs.append(
                f'MIN(LENGTH(CAST({col_ident} AS VARCHAR(4000)))) AS "{col["name"]}__min_length"'
            )
            aggregate_exprs.append(
                f'MAX(LENGTH(CAST({col_ident} AS VARCHAR(4000)))) AS "{col["name"]}__max_length"'
            )

        sql = f"SELECT {', '.join(aggregate_exprs)} FROM {qualified_table}"

        try:
            result_list = self._query(sql)
            if not result_list:
                raise ConnectorError("No result from profiling query")
            row = result_list[0]
        except Exception as exc:
            raise ConnectorError(
                f"Profiling query failed for {schema}.{table}: {exc}"
            ) from exc

        row_count = int(row.get("row_count", 0))
        column_stats: dict[str, Any] = {}
        for col in columns:
            name = col["name"]
            column_stats[name] = {
                "null_count": int(row.get(f"{name}__null_count", 0)),
                "distinct_count": int(row.get(f"{name}__distinct_count", 0)),
                "min_value": row.get(f"{name}__min_value"),
                "max_value": row.get(f"{name}__max_value"),
                "min_length": int(row.get(f"{name}__min_length") or 0) if row.get(f"{name}__min_length") else None,
                "max_length": int(row.get(f"{name}__max_length") or 0) if row.get(f"{name}__max_length") else None,
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
        """Best-effort full-row duplicate count."""
        if row_count == 0:
            return 0
        if not columns:
            return None

        col_list = ", ".join(self._quote_ident(c["name"]) for c in columns)
        sql = (
            f"SELECT COUNT(*) - COUNT(CASE WHEN rn = 1 THEN 1 END) FROM ("
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
        """Return up to `limit` non-null sample values from one column."""
        qualified_table = f"{self._quote_ident(schema)}.{self._quote_ident(table)}"
        col_ident = self._quote_ident(column)
        sql = (
            f"SELECT {col_ident} FROM {qualified_table} "
            f"WHERE {col_ident} IS NOT NULL "
            f"FETCH FIRST {limit} ROWS ONLY"
        )
        try:
            result_list = self._query(sql)
            return [row.get(column.lower()) for row in result_list if row]
        except Exception as exc:
            raise ConnectorError(
                f"Sampling failed for {schema}.{table}.{column}: {exc}"
            ) from exc

    @staticmethod
    def _quote_ident(name: str) -> str:
        """Quote a DB2 identifier, escaping embedded quotes."""
        return '"' + name.replace('"', '""') + '"'

    def _scalar(self, sql: str) -> Any:
        """Execute a query and return a single scalar value."""
        try:
            result_list = self._query(sql)
            if result_list:
                row = result_list[0]
                return list(row.values())[0]
            return None
        except Exception as exc:
            raise ConnectorError(f"Scalar query failed: {sql}: {exc}") from exc
