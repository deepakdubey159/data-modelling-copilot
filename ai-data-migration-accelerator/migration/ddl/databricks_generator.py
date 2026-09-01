"""Databricks DDL generator.

Produces Databricks SQL from target models. Deterministic: same input always
produces identical SQL (same formatting, column order, constraint order).
"""

from __future__ import annotations

import logging

from migration.ddl.models import DDLPackage, DDLScript, DDLStatement
from migration.ddl.validator import validate_ddl_script
from migration.target.models import TargetCapability, TargetModelPackage, TargetTable

logger = logging.getLogger(__name__)


class DatabricksDDLGenerator:
    """Generates Databricks SQL DDL from a target model."""

    def __init__(
        self,
        package: TargetModelPackage,
        include_comments: bool = True,
        generated_from: str = "physical_model.json",
        catalog: str | None = None,
        schema: str | None = None,
        enable_clustering: bool = False,
    ):
        self.package = package
        self.model = package.target_model
        self.include_comments = include_comments
        self.generated_from = generated_from
        self.catalog = catalog
        self.schema = schema
        self.enable_clustering = enable_clustering
        """Whether PARTITIONED BY / CLUSTERED BY may be emitted as executable
        SQL in CREATE TABLE. False (default) keeps them as a non-executable
        comment recommendation only - see PARTITION_CLUSTERING_STATEMENTS,
        which is emitted unconditionally regardless of this flag."""

        self._capabilities = set(self.model.capabilities)

    def generate(self) -> DDLPackage:
        """Generate DDL script from the target model."""
        script = DDLScript(
            database_name=self.model.database_name,
            target_type=self.model.target_type,
        )

        # Create tables in sorted order (deterministic)
        for table in sorted(self.model.tables, key=lambda t: t.name):
            self._add_table_ddl(table, script)

        validate_ddl_script(script, enable_clustering=self.enable_clustering)

        logger.info(
            "DDL generated: %s CREATE TABLE, %s constraints, %s indexes, %s comments",
            len(script.table_creation_statements),
            len(script.constraint_statements),
            len(script.index_statements),
            len(script.comment_statements),
        )

        return DDLPackage(
            ddl_script=script,
            generated_from=self.generated_from,
            generated_by="DatabricksDDLGenerator",
        )

    def _add_table_ddl(self, table: TargetTable, script: DDLScript) -> None:
        """Generate CREATE TABLE and associated statements for a table."""
        create_stmt = self._create_table_statement(table)
        script.table_creation_statements.append(create_stmt)

        # Add constraint statements (some may not be inlined)
        for constraint in sorted(table.constraints, key=lambda c: c.name):
            stmt = self._constraint_statement(constraint, table)
            if stmt:
                script.constraint_statements.append(stmt)

        # Add index statements
        for index in sorted(table.indexes, key=lambda i: i.name):
            stmt = self._index_statement(index)
            script.index_statements.append(stmt)

        # Add partition/clustering recommendations as comments
        if table.partition_candidates or table.clustering_candidates:
            stmt = self._partition_clustering_recommendation(table)
            script.partition_clustering_statements.append(stmt)

        # Add comments on table and columns
        if self.include_comments:
            comments = self._comment_statements(table)
            script.comment_statements.extend(comments)

    def _fully_qualified_table_name(self, table_name: str) -> str:
        """Build fully qualified table name with optional catalog and schema.

        Examples:
        - table_name only: `customers`
        - with catalog: `dblearn`.`customers`
        - with catalog and schema: `dblearn`.`bronze`.`customers`
        """
        parts = []
        if self.catalog:
            parts.append(self._quote(self.catalog))
        if self.schema:
            parts.append(self._quote(self.schema))
        parts.append(self._quote(table_name))
        return ".".join(parts)

    def _create_table_statement(self, table: TargetTable) -> DDLStatement:
        """Generate CREATE TABLE IF NOT EXISTS with inline constraints.

        Only PRIMARY KEY and FOREIGN KEY constraints are ever inlined here -
        the only constraint types Unity Catalog Delta tables accept inside
        CREATE TABLE. UNIQUE has no Delta equivalent at all (handled by the
        target adapter, which drops it with a recorded note) and CHECK is
        added afterward via ALTER TABLE ADD CONSTRAINT, which is the only
        form Databricks accepts for CHECK - not inline. `IF NOT EXISTS` makes
        a rerun of the same script safe rather than replacing (and losing)
        an existing table's data.
        """
        table_ref = self._fully_qualified_table_name(table.name)
        lines = [f"CREATE TABLE IF NOT EXISTS {table_ref} ("]

        # Columns in deterministic order
        for col in sorted(table.columns, key=lambda c: c.name):
            col_def = self._column_definition(col)
            lines.append(f"  {col_def},")

        # Primary key constraint (inline; Databricks accepts this in CREATE TABLE)
        if TargetCapability.PRIMARY_KEYS in self._capabilities:
            pk_cols = [c for c in table.constraints if c.constraint_type == "PRIMARY_KEY"]
            if pk_cols:
                pk_constraint = pk_cols[0]
                pk_cols_str = ", ".join(self._quote(c) for c in pk_constraint.columns)
                lines.append(f"  CONSTRAINT {self._quote(pk_constraint.name)} PRIMARY KEY ({pk_cols_str}),")

        # Remove trailing comma from last line
        if len(lines) > 1:
            lines[-1] = lines[-1].rstrip(",")

        lines.append(")")

        # PARTITIONED BY / CLUSTERED BY are executable only when the operator
        # has confirmed the configured Databricks runtime supports them -
        # otherwise they stay a comment recommendation (see
        # _partition_clustering_recommendation, emitted unconditionally).
        if self.enable_clustering and (table.partition_candidates or table.clustering_candidates):
            if table.partition_candidates:
                parts = ", ".join(self._quote(c) for c in table.partition_candidates)
                lines.append(f"PARTITIONED BY ({parts})")
            if table.clustering_candidates:
                clusters = ", ".join(self._quote(c) for c in table.clustering_candidates)
                lines.append(f"CLUSTER BY ({clusters})")

        lines.append(";")

        statement = "\n".join(lines)
        return DDLStatement(
            statement=statement,
            description=f"Create table {table.name}",
            source_table=table.source_table,
            statement_type="CREATE",
        )

    def _column_definition(self, col) -> str:
        """Generate column definition: name TYPE [NOT NULL] [DEFAULT val] [COMMENT '...'].

        Column comments are inlined here rather than as separate ALTER TABLE
        statements, so they live in the source of truth (the CREATE TABLE) and
        are readable in a single script. Comments are only included if
        include_comments is True."""
        databricks_type = self._format_databricks_type(col)
        parts = [self._quote(col.name), databricks_type]

        if not col.nullable:
            parts.append("NOT NULL")

        if col.default_value:
            parts.append(f"DEFAULT {col.default_value}")

        # Inline column comment with source metadata (only if enabled)
        if self.include_comments:
            comment_parts = []
            if col.source_column:
                comment_parts.append(f"Source: {col.source_column}")
            if col.physical_type:
                comment_parts.append(f"Physical type: {col.physical_type}")

            if comment_parts:
                comment = " | ".join(comment_parts)
                escaped = self._escape_string(comment)
                parts.append(f"COMMENT '{escaped}'")

        return " ".join(parts)

    def _constraint_statement(self, constraint, table: TargetTable) -> DDLStatement | None:
        """Generate an ALTER TABLE statement for a constraint not inlined in
        CREATE TABLE: foreign keys (may reference a table that doesn't exist
        yet, so they are always separate) and CHECK constraints (Databricks
        only accepts CHECK via ALTER TABLE ADD CONSTRAINT - not inline in
        CREATE TABLE, unlike PRIMARY KEY/FOREIGN KEY).

        Foreign keys are validated before being emitted:
        - referenced columns must exactly match a target PK or UNIQUE constraint
        - column count/order must match
        If validation fails, the FK is emitted as a comment explaining why."""
        if constraint.constraint_type == "FOREIGN_KEY":
            if TargetCapability.FOREIGN_KEYS not in self._capabilities:
                return None

            # Validate the FK before emitting it as executable SQL
            fk_valid, validation_reason = self._validate_foreign_key(constraint)
            if not fk_valid:
                # Emit as non-executable comment explaining why
                statement = f"-- FOREIGN KEY VALIDATION FAILED: {constraint.name}\n-- Reason: {validation_reason}"
                return DDLStatement(
                    statement=statement,
                    description=f"FK validation failure for {constraint.name}",
                    source_table=table.source_table,
                    statement_type="COMMENT",
                )

            fk_cols = ", ".join(self._quote(c) for c in constraint.columns)
            ref_cols = ", ".join(self._quote(c) for c in constraint.referenced_columns)
            ref_table = self._fully_qualified_table_name(constraint.referenced_table or "unknown")

            table_ref = self._fully_qualified_table_name(table.name)
            statement = (
                f"ALTER TABLE {table_ref} "
                f"ADD CONSTRAINT {self._quote(constraint.name)} "
                f"FOREIGN KEY ({fk_cols}) REFERENCES {ref_table}({ref_cols});"
            )

            return DDLStatement(
                statement=statement,
                description=f"Add foreign key {constraint.name}",
                source_table=table.source_table,
                statement_type="ALTER",
            )

        if constraint.constraint_type == "CHECK":
            if TargetCapability.CHECK_CONSTRAINTS not in self._capabilities:
                return None

            table_ref = self._fully_qualified_table_name(table.name)
            statement = (
                f"ALTER TABLE {table_ref} "
                f"ADD CONSTRAINT {self._quote(constraint.name)} "
                f"CHECK ({constraint.expression});"
            )

            return DDLStatement(
                statement=statement,
                description=f"Add check constraint {constraint.name}",
                source_table=table.source_table,
                statement_type="ALTER",
            )

        return None

    def _index_statement(self, index) -> DDLStatement:
        """Preserve an index recommendation as a non-executable comment.

        Delta Lake has no CREATE INDEX (or CREATE UNIQUE INDEX, or any
        USING-clause secondary index) - a traditional relational index is
        simply not a thing a Delta table has. The recommendation itself
        (which columns, why) is still valuable, so it survives as a comment
        rather than being dropped or - worse - rendered as SQL Databricks
        cannot execute.
        """
        unique = "UNIQUE " if index.is_unique else ""
        cols = ", ".join(index.columns)
        table_ref = self._fully_qualified_table_name(index.table)
        rationale = f" | {index.rationale}" if index.rationale else ""

        statement = (
            f"-- Index recommendation ({index.name}): {unique}INDEX on {table_ref}({cols}) "
            f"- Delta Lake has no CREATE INDEX; consider Z-ORDER BY or a generated "
            f"column instead{rationale}"
        )

        return DDLStatement(
            statement=statement,
            description=f"Index recommendation for {index.name}",
            source_table=table_ref,
            statement_type="COMMENT",
        )

    def _partition_clustering_recommendation(self, table: TargetTable) -> DDLStatement:
        """Generate comment with partition/clustering recommendations."""
        parts = []

        if table.partition_candidates:
            partition_cols = ", ".join(table.partition_candidates)
            parts.append(f"PARTITION BY: {partition_cols}")

        if table.clustering_candidates:
            cluster_cols = ", ".join(table.clustering_candidates)
            parts.append(f"CLUSTER BY: {cluster_cols}")

        if table.storage_rationale:
            parts.append(f"Rationale: {table.storage_rationale}")

        description = " | ".join(parts)

        # In Databricks, we can add this as a comment
        statement = f"-- Partition/Clustering Recommendation: {description}"

        return DDLStatement(
            statement=statement,
            description="Partition/clustering recommendation",
            source_table=table.source_table,
            statement_type="COMMENT",
        )

    def _comment_statements(self, table: TargetTable) -> list[DDLStatement]:
        """Generate COMMENT statements for table and columns.

        Column comments are now inlined in CREATE TABLE (see _column_definition),
        so this method now returns an empty list. Column comment statements are
        no longer generated as separate ALTER TABLE ... CHANGE COLUMN statements."""
        return []

    def _validate_foreign_key(self, fk_constraint) -> tuple[bool, str]:
        """Validate a foreign key before emitting it as executable SQL.

        A valid FK must:
        1. Reference a table that exists in the target model
        2. Have referenced columns that exactly match (count, order, names) a
           PRIMARY KEY or UNIQUE constraint on the referenced table

        Returns: (is_valid: bool, reason: str if invalid, else empty)
        """
        # Find the referenced table
        ref_table_name = fk_constraint.referenced_table
        if not ref_table_name:
            return False, "Referenced table is unknown"

        ref_table = next((t for t in self.model.tables if t.name == ref_table_name), None)
        if not ref_table:
            return False, f"Referenced table '{ref_table_name}' does not exist in target model"

        # Get the FK's referenced columns (as specified in the constraint)
        fk_ref_cols = fk_constraint.referenced_columns
        if not fk_ref_cols:
            return False, "Foreign key has no referenced columns specified"

        # Find a matching PK or UNIQUE constraint on the referenced table
        for constraint in ref_table.constraints:
            if constraint.constraint_type not in ("PRIMARY_KEY", "UNIQUE"):
                continue

            # Check if this constraint's columns exactly match the FK's referenced columns
            if (
                len(constraint.columns) == len(fk_ref_cols)
                and constraint.columns == fk_ref_cols
            ):
                # Valid match found
                return True, ""

        # No matching PK or UNIQUE found
        return False, (
            f"Referenced columns {fk_ref_cols} do not exactly match any PRIMARY KEY "
            f"or UNIQUE constraint on '{ref_table_name}'"
        )

    @staticmethod
    def _format_databricks_type(col) -> str:
        """Format Databricks SQL type from TargetColumn.

        The TargetColumn already has the mapped target_type from the adapter.
        This method builds the complete type string with parameters.

        Key note: Databricks STRING doesn't support length constraints, so we
        only include length for types where it's meaningful (VARCHAR, CHAR, etc).
        """
        target_type = col.target_type

        # Databricks DECIMAL requires precision and scale
        if target_type == "DECIMAL" and col.precision is not None:
            scale = col.scale if col.scale is not None else 0
            return f"DECIMAL({col.precision},{scale})"

        # Databricks STRING doesn't support length; ignore it
        if target_type == "STRING":
            return "STRING"

        # All other types: return as-is (INT, DATE, TIMESTAMP, BOOLEAN, BINARY, etc)
        return target_type

    @staticmethod
    def _quote(identifier: str) -> str:
        """Quote an identifier for Databricks (backticks)."""
        return f"`{identifier}`"

    @staticmethod
    def _escape_string(value: str) -> str:
        """Escape a string value for SQL (single quotes, backslashes)."""
        return value.replace("\\", "\\\\").replace("'", "''")
