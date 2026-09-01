"""Databricks target adapter.

Maps the generic physical model to Databricks-specific types and capabilities.
Databricks is a lakehouse platform: it supports transactions and ACID
properties, and Unity Catalog Delta tables support declarative PRIMARY KEY,
FOREIGN KEY and CHECK constraints - but not UNIQUE constraints (there is no
UNIQUE constraint DDL in Delta Lake) and not traditional secondary indexes
(CREATE INDEX is not part of Databricks SQL for Delta tables). Declaring
UNIQUE_CONSTRAINTS or INDEXES here would tell the base adapter to emit SQL
Databricks cannot execute, so both are deliberately absent.
"""

from __future__ import annotations

import hashlib
import re

from migration.physical.models import (
    PhysicalConstraint,
    PhysicalDataType,
    PhysicalColumn,
    PhysicalModelPackage,
    PhysicalTable,
)
from migration.physical.source_types import classify_source_type
from migration.target.base import BaseTargetAdapter
from migration.target.models import (
    TargetCapability,
    TargetConstraint,
    TargetDataTypeMapping,
    TargetIdentifierRule,
)

_IDENTIFIER_CHARS = re.compile(r"[^a-z0-9_]+")

# Source type name -> concrete Databricks type, for the cases where a
# native, narrower Databricks type exists that the generic PhysicalDataType
# classification (necessarily coarser - it has no separate "small integer"
# or "single-precision float" storage class) would otherwise widen. Keyed on
# the same base type names as migration.physical.source_types, so a type
# recognized there but absent here simply uses the generic mapping below.
_NARROW_INTEGER_TYPES: dict[str, str] = {
    "SMALLINT": "INT",
    "INTEGER": "INT",
    "INT": "INT",
    "BIGINT": "BIGINT",
    "SMALLSERIAL": "INT",
    "SERIAL": "INT",
    "BIGSERIAL": "BIGINT",
}

_FLOAT_TYPES: dict[str, str] = {
    "REAL": "FLOAT",
    "FLOAT": "FLOAT",
    "DOUBLE": "DOUBLE",
    "DOUBLE PRECISION": "DOUBLE",
}


class DatabricksTargetAdapter(BaseTargetAdapter):
    """Maps physical models to Databricks SQL."""

    def __init__(self, package: PhysicalModelPackage, source_artifact: str = "physical_model.json"):
        super().__init__(package, source_artifact)
        self._used_fk_constraint_names: set[str] = set()
        """Tracks every FK constraint name assigned across the whole model,
        not just within one table - a physical-model FK name that collided
        with another table's FK name (see _map_constraint) must still be
        caught here."""

    def target_type(self) -> str:
        return "databricks"

    def adapter_name(self) -> str:
        return "DatabricksTargetAdapter"

    def supported_capabilities(self) -> list[TargetCapability]:
        """What Unity Catalog Delta tables actually support as executable DDL.

        UNIQUE_CONSTRAINTS is intentionally absent: Delta Lake has no UNIQUE
        constraint syntax at all, so the base adapter drops it and records a
        note rather than emitting invalid SQL.

        INDEXES stays declared even though Delta has no CREATE INDEX: this
        capability only controls whether index recommendations survive into
        the target model at all (`TargetTable.indexes`), not whether the DDL
        generator emits them as executable SQL - it doesn't; see
        DatabricksDDLGenerator, which renders them as comments.
        """
        return [
            TargetCapability.PRIMARY_KEYS,
            TargetCapability.FOREIGN_KEYS,
            TargetCapability.CHECK_CONSTRAINTS,
            TargetCapability.INDEXES,
            TargetCapability.PARTITIONING,
            TargetCapability.CLUSTERING,
            TargetCapability.DEFAULT_VALUES,
            TargetCapability.TRANSACTIONS,
        ]

    def identifier_rules(self) -> TargetIdentifierRule:
        """Databricks identifier rules.

        Names are case-insensitive by default but can be case-sensitive if quoted.
        Max identifier length is 255 characters.
        """
        return TargetIdentifierRule(
            max_length=255,
            allow_unicode=True,
            reserved_words=[
                "ADD", "AFTER", "ALL", "ALTER", "ANALYZE", "AND", "ANY",
                "ARRAY", "AS", "ASC", "ASSERT", "AT", "BETWEEN", "BY",
                "CASE", "CAST", "CHECK", "CLUSTER", "CLUSTERED", "COALESCE",
                "COLLATE", "COLUMN", "COMMENT", "COMMIT", "CONSTRAINT",
                "CREATE", "CROSS", "CUBE", "CURRENT", "CURRENT_DATE",
                "CURRENT_TIMESTAMP", "CURRENT_USER", "DATE", "DAY", "DBPROPERTIES",
                "DEFAULT", "DELETE", "DESC", "DESCRIBE", "DISTINCT", "DROP",
                "ELSE", "END", "EXCEPT", "EXCHANGE", "EXISTS", "EXPLAIN",
                "FALSE", "FILTER", "FIRST", "FLOAT", "FOLLOWING", "FOR",
                "FOREIGN", "FORMAT", "FROM", "FULL", "FUNCTION", "GRANT",
                "GROUP", "GROUP_CONCAT", "HAVING", "HOUR", "IF", "IN",
                "INNER", "INSERT", "INT", "INTERSECT", "INTO", "IS",
                "ISNULL", "INTERVAL", "JOIN", "KEY", "LAST", "LATERAL",
                "LEFT", "LIKE", "LIMIT", "LONG", "MATCH", "MERGE", "MINUTE",
                "MONTH", "NOT", "NOTNULL", "NULL", "OF", "ON", "OR",
                "ORDER", "OUTER", "OVER", "PARTITION", "PERCENT", "PRECEDING",
                "PRIMARY", "RANGE", "REFERENCES", "REGEXP", "REVOKE", "RIGHT",
                "RLIKE", "ROW", "ROWS", "SECOND", "SELECT", "SET", "SHORT",
                "SHOW", "SORT", "SPARK", "STRUCT", "TABLE", "TABLESAMPLE",
                "THEN", "TO", "TRUE", "TRY_CAST", "UNBOUND", "UNION",
                "UPDATE", "UPSERT", "USING", "WHEN", "WHERE", "WINDOW",
                "WITH", "YEAR",
            ],
            quote_char="`",
            supports_case_sensitivity=True,
        )

    def _map_source_database_type(
        self, column: "PhysicalColumn"
    ) -> tuple[str, int | None, int | None, int | None] | None:
        """Map a source column directly to a native Databricks type.

        Uses the source's own structured length/precision/scale
        (`column.source_length`/`source_precision`/`source_scale`) - never a
        composite string parsed with a regex, which silently never matched
        in production because the source catalog reports the base type name
        and its size as separate fields, not one combined string.

        Returns None when the source type name isn't recognized, so the
        caller falls back to the generic physical-type mapping (which
        `PhysicalModelEngine` has already classified correctly from the same
        source facts) rather than guessing.
        """
        source_type = column.source_database_type
        if not source_type:
            return None

        base = source_type.strip().upper()

        if base in _NARROW_INTEGER_TYPES:
            return _NARROW_INTEGER_TYPES[base], None, None, None

        if base in _FLOAT_TYPES:
            return _FLOAT_TYPES[base], None, None, None

        classification = classify_source_type(
            source_type,
            length=column.source_length,
            precision=column.source_precision,
            scale=column.source_scale,
        )
        if not classification.is_explicit:
            # Not a recognized DB2/PostgreSQL type - let the generic
            # PhysicalDataType mapping (STRING, the documented lossless
            # fallback) handle it instead of duplicating that decision here.
            return None

        return self._render_generic_type(
            classification.data_type,
            classification.length,
            classification.precision,
            classification.scale,
        )

    def _render_generic_type(
        self,
        data_type: PhysicalDataType,
        length: int | None,
        precision: int | None,
        scale: int | None,
    ) -> tuple[str, int | None, int | None, int | None]:
        """Render a generic (PhysicalDataType, size) as a Databricks type.

        Shares the same target_type strings as `data_type_mappings()` so a
        source-derived classification and the generic fallback never
        disagree on what a given PhysicalDataType looks like in Databricks.
        """
        mapping = self.data_type_mappings()[data_type]
        target_type = mapping.target_type

        if data_type == PhysicalDataType.DECIMAL and precision is not None:
            return target_type, None, precision, scale if scale is not None else 0
        if data_type == PhysicalDataType.STRING:
            return target_type, None, None, None
        return target_type, None, None, None

    def _map_data_type(self, column: "PhysicalColumn") -> tuple[str, int | None, int | None, int | None]:
        """Override to check source database type first, then fall back to generic mapping."""
        mapped = self._map_source_database_type(column)
        if mapped is not None:
            return mapped

        # Fall back to generic physical type mapping
        return super()._map_data_type(column)

    def data_type_mappings(self) -> dict[PhysicalDataType, TargetDataTypeMapping]:
        """Map generic physical types to Databricks types."""
        return {
            PhysicalDataType.IDENTIFIER: TargetDataTypeMapping(
                generic_type="IDENTIFIER",
                target_type="BIGINT",
                rationale="Databricks auto-increment uses BIGINT; identifiers are typically int64.",
            ),
            PhysicalDataType.STRING: TargetDataTypeMapping(
                generic_type="STRING",
                target_type="STRING",
                parameters="{length}",
                rationale="Databricks strings are variable-length; length is metadata only.",
            ),
            PhysicalDataType.INTEGER: TargetDataTypeMapping(
                generic_type="INTEGER",
                target_type="BIGINT",
                rationale="Databricks uses 64-bit integers for counts and whole numbers.",
            ),
            PhysicalDataType.DECIMAL: TargetDataTypeMapping(
                generic_type="DECIMAL",
                target_type="DECIMAL",
                parameters="{precision},{scale}",
                rationale="Precision and scale are preserved.",
            ),
            PhysicalDataType.DATE: TargetDataTypeMapping(
                generic_type="DATE",
                target_type="DATE",
                rationale="Databricks DATE is ISO 8601 (YYYY-MM-DD).",
            ),
            PhysicalDataType.TIMESTAMP: TargetDataTypeMapping(
                generic_type="TIMESTAMP",
                target_type="TIMESTAMP",
                rationale="Databricks TIMESTAMP is TIMESTAMP NTZ (no timezone).",
            ),
            PhysicalDataType.BOOLEAN: TargetDataTypeMapping(
                generic_type="BOOLEAN",
                target_type="BOOLEAN",
                rationale="Databricks BOOLEAN is true/false.",
            ),
            PhysicalDataType.BINARY: TargetDataTypeMapping(
                generic_type="BINARY",
                target_type="BINARY",
                rationale="Databricks BINARY stores uninterpreted bytes.",
            ),
            PhysicalDataType.JSON: TargetDataTypeMapping(
                generic_type="JSON",
                target_type="STRING",
                rationale="Databricks stores JSON as STRING; parsing is done in queries.",
            ),
        }

    # -- Foreign key constraint naming --------------------------------------

    def _map_constraint(
        self, constraint: PhysicalConstraint, table: PhysicalTable
    ) -> TargetConstraint | None:
        """Map a constraint, then - for foreign keys only - replace whatever
        name the physical model assigned with a Databricks-specific,
        deterministic, globally unique one.

        The physical model's generic naming convention truncates a long
        constraint name to a conservative 30-character, multi-platform limit
        by dropping trailing words - which can drop the very column name
        that distinguished two different foreign keys on the same table
        (e.g. a product<->promotion junction table's `product_id` and
        `promotion_id` FKs both truncating to `fk_product_promotion`).
        Databricks allows identifiers up to 255 characters, so it never
        needs to make that trade: every FK name here is built from the
        table, the table it references, and its own column(s), which is
        unique by construction for any given FK - and even the rare
        oversized case is shortened with a content hash rather than by
        dropping words, so uniqueness survives truncation too.
        """
        mapped = super()._map_constraint(constraint, table)
        if mapped is None or mapped.constraint_type != "FOREIGN_KEY":
            return mapped

        mapped.name = self._unique_fk_constraint_name(
            table.name, mapped.referenced_table, mapped.columns
        )
        return mapped

    def _unique_fk_constraint_name(
        self, table_name: str, referenced_table: str | None, columns: list[str]
    ) -> str:
        """Build a deterministic FK constraint name from source table +
        target table + source column(s), then guarantee it is globally
        unique across every table this adapter has mapped so far.
        """
        target = referenced_table or "unknown"
        column_part = "_".join(columns) if columns else "col"
        base = _sanitize_identifier(f"fk_{table_name}_{target}_{column_part}")

        max_length = self.identifier_rules().max_length
        if len(base) > max_length:
            # A content hash keeps the name deterministic and, crucially,
            # keeps it unique - unlike truncating by dropping trailing
            # words, which is what caused this bug in the first place.
            digest = hashlib.sha1(base.encode("utf-8")).hexdigest()[:8]
            keep = max_length - len(digest) - 1
            base = f"{base[:keep]}_{digest}"

        return self._deduplicate(base)

    def _deduplicate(self, candidate: str) -> str:
        """Append a numeric suffix if `candidate` was already used.

        A defensive backstop only - the (table, referenced_table, columns)
        tuple is already unique for any distinct foreign key, so this
        should never actually trigger in practice.
        """
        name = candidate
        suffix = 2
        while name in self._used_fk_constraint_names:
            name = f"{candidate}_{suffix}"
            suffix += 1
        self._used_fk_constraint_names.add(name)
        return name


def _sanitize_identifier(name: str) -> str:
    """Lower-case and collapse anything that isn't [a-z0-9_] to a single
    underscore, so a constraint name is always a safe bare identifier."""
    return _IDENTIFIER_CHARS.sub("_", name.lower()).strip("_")
