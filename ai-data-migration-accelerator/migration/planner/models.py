"""
Migration plan models.

Represents a deterministic, FK-derived table/schema dependency graph and the
recommended migration order computed from it. Nothing here is AI-generated -
every field is derived by graph algorithms over canonical metadata that the
connectors and MetadataBuilder already produce.
"""

from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class TableRef(BaseModel):
    """A fully-qualified table identity: schema.table."""

    schema_name: str
    table_name: str

    @property
    def qualified_name(self) -> str:
        return f"{self.schema_name}.{self.table_name}"

    def __hash__(self) -> int:
        return hash((self.schema_name, self.table_name))


class TableDependency(BaseModel):
    """One FK-derived edge: `table` depends on `depends_on` (its parent)."""

    table: str
    """Qualified name of the dependent (child/FK-holding) table."""

    depends_on: str
    """Qualified name of the referenced (parent) table."""

    constraint_name: str
    cross_schema: bool = False


class DependencyCycle(BaseModel):
    """A set of tables whose FK references form a cycle.

    Reported rather than silently broken - the caller decides how to
    resolve it (e.g. deferred constraints, manual staging).
    """

    tables: List[str] = Field(default_factory=list)
    """Qualified table names participating in the cycle, in cycle order."""


class SchemaDependency(BaseModel):
    """One FK-derived edge at schema granularity: `schema` depends on `depends_on`."""

    schema_name: str
    depends_on: str


class MigrationPlan(BaseModel):
    """The full deterministic migration-order recommendation."""

    schemas_analyzed: List[str] = Field(default_factory=list)

    table_dependencies: List[TableDependency] = Field(default_factory=list)
    schema_dependencies: List[SchemaDependency] = Field(default_factory=list)

    root_tables: List[str] = Field(default_factory=list)
    """Tables with no outgoing FK dependency - safe to migrate first."""

    root_schemas: List[str] = Field(default_factory=list)
    """Schemas with no outgoing cross-schema FK dependency."""

    most_depended_on_tables: List[str] = Field(default_factory=list)
    """Tables referenced by the largest number of other tables, ordered
    descending by in-degree. High migration priority: many tables need
    these to exist first."""

    cross_schema_foreign_keys: List[TableDependency] = Field(default_factory=list)

    table_cycles: List[DependencyCycle] = Field(default_factory=list)
    schema_cycles: List[DependencyCycle] = Field(default_factory=list)

    recommended_table_order: List[str] = Field(default_factory=list)
    """Topological order (parents before children). Empty when a cycle
    makes a single valid order impossible - see `table_cycles`."""

    recommended_schema_order: List[str] = Field(default_factory=list)
    """Topological order for schemas. Empty when `schema_cycles` is
    non-empty."""

    has_cycles: bool = False

    explanation: List[str] = Field(default_factory=list)
    """Human-readable reasons behind the recommended order, e.g. why a
    schema was placed first (no dependencies) or last (most depended upon)."""


class MigrationPlanPackage(BaseModel):
    plan: MigrationPlan
    generated_by: str = "SchemaDependencyAnalyzer"
