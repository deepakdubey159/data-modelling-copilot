"""Deterministic validation for generated Databricks DDL.

Runs as the last, pure-code step of DDL generation - no LLM, no network,
same script in always produces the same verdict. This is a backstop, not the
primary correctness mechanism: the generator is expected to never produce
the patterns checked for here. Its job is to turn "the generator has a bug"
into a loud, specific failure at generation time rather than a silently
broken `databricks.sql` a human discovers only when Databricks rejects it.
"""

from __future__ import annotations

import re

from migration.ddl.models import DDLScript

logger = __import__("logging").getLogger(__name__)


class DDLValidationError(Exception):
    """Raised when generated DDL contains a known-invalid pattern."""


# Source-database-specific syntax that must never appear in Databricks DDL.
# Matched case-insensitively; each pattern names the dialect it belongs to
# so a failure message says exactly what leaked through and from where.
_FORBIDDEN_SYNTAX: tuple[tuple[str, str], ...] = (
    (r"\bCOLLATE\b", "PostgreSQL COLLATE clause"),
    (r"\bTABLESPACE\b", "PostgreSQL/DB2 TABLESPACE clause"),
    (r"\bOWNER\s+TO\b", "PostgreSQL OWNER TO clause"),
    (r"\bUSING\s+BTREE\b", "PostgreSQL USING btree index method"),
    (r"::regclass\b", "PostgreSQL ::regclass cast"),
    (r"\bCREATE\s+SEQUENCE\b", "PostgreSQL sequence syntax"),
    (r"\bBUFFERPOOL\b", "DB2 BUFFERPOOL clause"),
    (r"\bIN\s+TABLESPACE\b", "DB2 tablespace placement clause"),
    (r"\bCREATE\s+(?:UNIQUE\s+)?INDEX\b", "CREATE INDEX (not supported by Delta tables)"),
    (r"\bCLUSTERED\s+BY\b", "Hive/Spark CLUSTERED BY (Databricks uses CLUSTER BY)"),
)

# Databricks SQL types this generator is allowed to emit. Kept in sync with
# DatabricksDDLGenerator._format_databricks_type and DatabricksTargetAdapter
# data_type_mappings - any other bare type name reaching a CREATE TABLE
# column is a generator bug, not a legitimate new type.
_VALID_BASE_TYPES = frozenset(
    {
        "STRING",
        "BIGINT",
        "INT",
        "SMALLINT",
        "TINYINT",
        "DECIMAL",
        "DOUBLE",
        "FLOAT",
        "BOOLEAN",
        "BINARY",
        "DATE",
        "TIMESTAMP",
        "TIMESTAMP_NTZ",
        "VOID",
    }
)

_COLUMN_LINE = re.compile(r"^\s*`([^`]+)`\s+([A-Z_]+)(?:\(([^)]*)\))?")
_CONSTRAINT_NAME = re.compile(r"CONSTRAINT\s+`([^`]+)`")
_EMPTY_IDENTIFIER = re.compile(r"``")
# Unbounded run of dot-separated backtick-quoted segments, so a name with
# more than 3 segments is captured whole (and rejected below) rather than
# silently matching only its first 3 segments.
_QUALIFIED_NAME = re.compile(r"(`[^`]*`(?:\.`[^`]*`)*)")


def validate_ddl_script(script: DDLScript, *, enable_clustering: bool = False) -> None:
    """Validate a generated DDLScript, raising DDLValidationError on any
    known-invalid pattern. Call before the script is written to disk.
    """
    statements = script.all_statements()

    _check_forbidden_syntax(statements)
    _check_statement_boundaries(statements)
    _check_empty_identifiers(statements)
    _check_duplicate_constraint_names(statements)
    _check_qualified_names(statements)
    _check_column_types(script)
    _check_clustering_gate(script, enable_clustering)


def _check_forbidden_syntax(statements) -> None:
    for stmt in statements:
        if stmt.statement_type == "COMMENT":
            # Comments are never executed - a recommendation is free to
            # mention, in prose, the very syntax it explains Databricks
            # doesn't support (e.g. "Delta Lake has no CREATE INDEX").
            continue
        for pattern, label in _FORBIDDEN_SYNTAX:
            if re.search(pattern, stmt.statement, re.IGNORECASE):
                raise DDLValidationError(
                    f"Generated DDL contains {label}, which Databricks does not "
                    f"support: {stmt.statement.strip()[:200]!r}"
                )


def _check_statement_boundaries(statements) -> None:
    for stmt in statements:
        if stmt.statement_type == "COMMENT":
            continue
        text = stmt.statement.strip()
        if not text.endswith(";"):
            raise DDLValidationError(
                f"Statement does not end with ';' (malformed statement boundary): "
                f"{text[:200]!r}"
            )


def _check_empty_identifiers(statements) -> None:
    for stmt in statements:
        if _EMPTY_IDENTIFIER.search(stmt.statement):
            raise DDLValidationError(
                f"Statement contains an empty quoted identifier (``): "
                f"{stmt.statement.strip()[:200]!r}"
            )


def _check_duplicate_constraint_names(statements) -> None:
    seen: dict[str, str] = {}
    for stmt in statements:
        for name in _CONSTRAINT_NAME.findall(stmt.statement):
            if name in seen and seen[name] != stmt.statement:
                raise DDLValidationError(
                    f"Duplicate constraint name '{name}' appears in more than one statement."
                )
            seen[name] = stmt.statement


def _check_qualified_names(statements) -> None:
    """Every `catalog`.`schema`.`table`-shaped reference must have 1-3
    non-empty, backtick-quoted, dot-separated segments."""
    for stmt in statements:
        if stmt.statement_type not in ("CREATE", "ALTER"):
            continue
        for match in _QUALIFIED_NAME.finditer(stmt.statement):
            segments = [s for s in match.group(1).split(".")]
            if len(segments) > 3:
                raise DDLValidationError(
                    f"Invalid catalog.schema.table reference (more than 3 segments): "
                    f"{match.group(1)!r} in {stmt.statement.strip()[:200]!r}"
                )
            for segment in segments:
                if segment in ("``", ""):
                    raise DDLValidationError(
                        f"Invalid catalog.schema.table reference (empty segment): "
                        f"{match.group(1)!r} in {stmt.statement.strip()[:200]!r}"
                    )


def _check_column_types(script: DDLScript) -> None:
    for stmt in script.table_creation_statements:
        for line in stmt.statement.splitlines():
            match = _COLUMN_LINE.match(line)
            if not match:
                continue
            base_type = match.group(2)
            if base_type not in _VALID_BASE_TYPES:
                raise DDLValidationError(
                    f"Column `{match.group(1)}` declares unsupported Databricks "
                    f"type '{base_type}' in table statement: {line.strip()!r}"
                )


def _check_clustering_gate(script: DDLScript, enable_clustering: bool) -> None:
    if enable_clustering:
        return
    for stmt in script.table_creation_statements:
        if "PARTITIONED BY" in stmt.statement or "CLUSTER BY" in stmt.statement:
            raise DDLValidationError(
                f"CREATE TABLE emits PARTITIONED BY / CLUSTER BY while clustering is "
                f"not enabled for this target: {stmt.statement.strip()[:200]!r}"
            )
