"""DDL output models.

Represents generated SQL statements organized by logical grouping.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class DDLStatement(BaseModel):
    """A single DDL statement."""

    statement: str
    """The SQL statement, ending with semicolon."""

    description: Optional[str] = None
    """What this statement does (for documentation)."""

    source_table: Optional[str] = None
    """The logical table this statement was generated from."""

    statement_type: str = "CREATE"
    """CREATE, ALTER, CREATE INDEX, COMMENT, etc."""


class DDLScript(BaseModel):
    """A collection of DDL statements organized by purpose."""

    database_name: str
    target_type: str
    """The platform: 'databricks', etc."""

    table_creation_statements: List[DDLStatement] = Field(default_factory=list)
    """CREATE TABLE and column definitions."""

    constraint_statements: List[DDLStatement] = Field(default_factory=list)
    """ALTER TABLE ADD CONSTRAINT (if not inline with CREATE)."""

    index_statements: List[DDLStatement] = Field(default_factory=list)
    """CREATE INDEX statements."""

    comment_statements: List[DDLStatement] = Field(default_factory=list)
    """COMMENT ON TABLE/COLUMN statements."""

    partition_clustering_statements: List[DDLStatement] = Field(default_factory=list)
    """Partition and clustering recommendations/configurations."""

    def all_statements(self) -> List[DDLStatement]:
        """All statements in logical order: tables, constraints, indexes, comments."""
        return (
            self.table_creation_statements
            + self.constraint_statements
            + self.index_statements
            + self.partition_clustering_statements
            + self.comment_statements
        )

    def to_sql(self, include_comments: bool = True) -> str:
        """Generate complete SQL script."""
        statements = self.all_statements()

        if not include_comments:
            statements = [s for s in statements if s.statement_type != "COMMENT"]

        return "\n\n".join(s.statement for s in statements) + "\n"


class DDLPackage(BaseModel):
    """Wrapper for serialization. Carries provenance."""

    ddl_script: DDLScript
    generated_from: Optional[str] = None
    """The target_model.json or physical_model.json this was generated from."""

    generated_by: Optional[str] = None
    """The generator that created this DDL."""
