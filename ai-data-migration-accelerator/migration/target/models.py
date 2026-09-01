"""Target-specific data models.

Represents the physical model mapped to a concrete database platform.
Carries lineage back to the generic physical model for DDL generation.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class TargetCapability(str, Enum):
    """Capabilities a target platform supports."""

    PRIMARY_KEYS = "PRIMARY_KEYS"
    FOREIGN_KEYS = "FOREIGN_KEYS"
    UNIQUE_CONSTRAINTS = "UNIQUE_CONSTRAINTS"
    CHECK_CONSTRAINTS = "CHECK_CONSTRAINTS"
    INDEXES = "INDEXES"
    PARTITIONING = "PARTITIONING"
    CLUSTERING = "CLUSTERING"
    COMPUTED_COLUMNS = "COMPUTED_COLUMNS"
    DEFAULT_VALUES = "DEFAULT_VALUES"
    IDENTITY_COLUMNS = "IDENTITY_COLUMNS"
    TRANSACTIONS = "TRANSACTIONS"


class TargetIdentifierRule(BaseModel):
    """Rules for identifier naming and length in the target platform."""

    max_length: int
    """Maximum identifier length."""

    allow_unicode: bool = False
    """Whether the platform allows unicode in identifiers."""

    reserved_words: List[str] = Field(default_factory=list)
    """Platform-specific reserved words that require quoting."""

    quote_char: str = '"'
    """Character used to quote identifiers."""

    supports_case_sensitivity: bool = True
    """Whether the platform distinguishes identifier case."""


class TargetDataTypeMapping(BaseModel):
    """Maps a generic data type to target-specific type(s)."""

    generic_type: str
    """The generic type (e.g., 'STRING', 'DECIMAL')."""

    target_type: str
    """The target platform type (e.g., 'VARCHAR' for PostgreSQL, 'STRING' for Databricks)."""

    parameters: str = ""
    """Parameter template: {length}, {precision}, {scale} are substituted."""

    supports_nullable: bool = True
    minimum_value: Optional[str] = None
    maximum_value: Optional[str] = None
    rationale: Optional[str] = None


class TargetColumn(BaseModel):
    """A column mapped to target-specific types and rules."""

    name: str
    target_type: str
    """The native type in the target platform."""

    length: Optional[int] = None
    precision: Optional[int] = None
    scale: Optional[int] = None

    nullable: bool = True
    default_value: Optional[str] = None

    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_unique: bool = False

    source_column: Optional[str] = None
    """Pointer back to the physical model column for lineage."""

    physical_type: Optional[str] = None
    """The generic physical type (STRING, DECIMAL, etc.)."""

    def type_signature(self) -> str:
        """Human-readable type for this target."""
        if self.length is not None:
            return f"{self.target_type}({self.length})"
        if self.precision is not None:
            scale = self.scale if self.scale is not None else 0
            return f"{self.target_type}({self.precision},{scale})"
        return self.target_type


class TargetConstraint(BaseModel):
    """A constraint mapped to the target platform."""

    name: str
    constraint_type: str
    """PRIMARY_KEY, FOREIGN_KEY, UNIQUE, CHECK in target dialect."""

    table: str
    columns: List[str] = Field(default_factory=list)

    referenced_table: Optional[str] = None
    referenced_columns: List[str] = Field(default_factory=list)

    expression: Optional[str] = None
    """For CHECK constraints, in target-specific syntax."""

    rationale: Optional[str] = None
    source_constraint: Optional[str] = None
    """Pointer back to the physical model constraint for lineage."""


class TargetIndex(BaseModel):
    """An index recommendation mapped to target platform syntax."""

    name: str
    table: str
    columns: List[str] = Field(default_factory=list)
    is_unique: bool = False
    is_clustered: bool = False
    purpose: str = "FOREIGN_KEY"

    rationale: Optional[str] = None
    source_index: Optional[str] = None
    """Pointer back to the physical model index for lineage."""


class TargetTable(BaseModel):
    """A table mapped to target-specific types, constraints and recommendations."""

    name: str
    """Target-specific table name."""

    source_table: Optional[str] = None
    """The physical model table this was derived from."""

    logical_entity: str
    """Pointer to the logical entity for business context."""

    columns: List[TargetColumn] = Field(default_factory=list)
    constraints: List[TargetConstraint] = Field(default_factory=list)
    indexes: List[TargetIndex] = Field(default_factory=list)

    partition_candidates: List[str] = Field(default_factory=list)
    """Recommended columns for partitioning, if supported."""

    clustering_candidates: List[str] = Field(default_factory=list)
    """Recommended columns for clustering, if supported."""

    subject_area: str = ""
    """Classification: LOOKUP, MASTER, TRANSACTION."""

    storage_rationale: Optional[str] = None


class TargetModel(BaseModel):
    """The physical model mapped to a target database platform.

    This is the input to DDL generation. It preserves lineage through
    source_table/source_column/source_constraint pointers so that generated
    DDL can be traced back to the original design decisions.
    """

    database_name: str
    summary: str
    """What changed in the mapping from physical to target."""

    target_type: str
    """The platform: 'databricks', 'postgres', 'snowflake', etc."""

    capabilities: List[TargetCapability] = Field(default_factory=list)
    """What this platform supports."""

    identifier_rules: TargetIdentifierRule
    data_type_mappings: List[TargetDataTypeMapping] = Field(default_factory=list)

    tables: List[TargetTable] = Field(default_factory=list)
    mapping_notes: List[str] = Field(default_factory=list)
    """Design decisions and unsupported feature warnings."""

    def all_constraints(self) -> List[TargetConstraint]:
        return [c for table in self.tables for c in table.constraints]

    def all_indexes(self) -> List[TargetIndex]:
        return [i for table in self.tables for i in table.indexes]


class TargetModelPackage(BaseModel):
    """Wrapper for serialization. Carries provenance."""

    target_model: TargetModel
    generated_from: Optional[str] = None
    """The physical_model.json this was derived from."""

    generated_by: Optional[str] = None
    """The adapter that created this mapping."""
