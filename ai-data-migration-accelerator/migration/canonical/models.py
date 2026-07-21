"""
Canonical Metadata Models

Every supported source system (PostgreSQL, Oracle, SQL Server,
SAP HANA, Snowflake, etc.) must be converted into these models.

The remainder of the application never works directly with
vendor-specific metadata.

Source DB
    ↓
Connector
    ↓
Canonical Metadata
    ↓
Profiler
    ↓
Relationship Engine
    ↓
LLM
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Column
# ---------------------------------------------------------


class ColumnMetadata(BaseModel):
    """
    Represents one database column.
    """

    name: str

    data_type: str

    nullable: bool

    default_value: Optional[str] = None

    ordinal_position: int

    character_length: Optional[int] = None

    numeric_precision: Optional[int] = None

    numeric_scale: Optional[int] = None

    is_primary_key: bool = False

    is_foreign_key: bool = False

    comment: Optional[str] = None


# ---------------------------------------------------------
# Primary Key
# ---------------------------------------------------------


class PrimaryKeyMetadata(BaseModel):
    constraint_name: str

    columns: List[str] = Field(default_factory=list)


# ---------------------------------------------------------
# Foreign Key
# ---------------------------------------------------------


class ForeignKeyMetadata(BaseModel):
    constraint_name: str

    column: str

    referenced_schema: str

    referenced_table: str

    referenced_column: str


# ---------------------------------------------------------
# Index
# ---------------------------------------------------------


class IndexMetadata(BaseModel):
    index_name: str

    definition: str


# ---------------------------------------------------------
# Constraint
# ---------------------------------------------------------


class ConstraintMetadata(BaseModel):
    constraint_name: str

    constraint_type: str


# ---------------------------------------------------------
# Table Statistics
# ---------------------------------------------------------


class TableStatistics(BaseModel):
    row_estimate: Optional[int] = None

    dead_row_estimate: Optional[int] = None

    last_analyze: Optional[str] = None

    last_autoanalyze: Optional[str] = None


# ---------------------------------------------------------
# Table
# ---------------------------------------------------------


class TableMetadata(BaseModel):
    """
    Canonical table model.
    """

    table_name: str

    table_type: str

    columns: List[ColumnMetadata] = Field(default_factory=list)

    primary_keys: List[PrimaryKeyMetadata] = Field(default_factory=list)

    foreign_keys: List[ForeignKeyMetadata] = Field(default_factory=list)

    indexes: List[IndexMetadata] = Field(default_factory=list)

    constraints: List[ConstraintMetadata] = Field(default_factory=list)

    statistics: Optional[TableStatistics] = None


# ---------------------------------------------------------
# View
# ---------------------------------------------------------


class ViewMetadata(BaseModel):
    view_name: str

    definition: Optional[str] = None


# ---------------------------------------------------------
# Function
# ---------------------------------------------------------


class FunctionMetadata(BaseModel):
    function_name: str

    return_type: Optional[str] = None

    definition: Optional[str] = None


# ---------------------------------------------------------
# Procedure
# ---------------------------------------------------------


class ProcedureMetadata(BaseModel):
    procedure_name: str

    definition: Optional[str] = None


# ---------------------------------------------------------
# Trigger
# ---------------------------------------------------------


class TriggerMetadata(BaseModel):
    trigger_name: str

    table_name: str

    timing: Optional[str] = None

    event: Optional[str] = None

    action: Optional[str] = None


# ---------------------------------------------------------
# Schema
# ---------------------------------------------------------


class SchemaMetadata(BaseModel):
    schema_name: str

    tables: List[TableMetadata] = Field(default_factory=list)

    views: List[ViewMetadata] = Field(default_factory=list)

    functions: List[FunctionMetadata] = Field(default_factory=list)

    procedures: List[ProcedureMetadata] = Field(default_factory=list)

    triggers: List[TriggerMetadata] = Field(default_factory=list)


# ---------------------------------------------------------
# Database
# ---------------------------------------------------------


class DatabaseMetadata(BaseModel):
    """
    Root object passed throughout the application.
    """

    database_name: str

    source_database_type: str

    schemas: List[SchemaMetadata] = Field(default_factory=list)


# ---------------------------------------------------------
# Metadata Profile
# ---------------------------------------------------------


class MetadataProfile(BaseModel):
    total_schemas: int = 0

    total_tables: int = 0

    total_columns: int = 0

    total_views: int = 0

    total_functions: int = 0

    total_procedures: int = 0

    total_triggers: int = 0

    total_primary_keys: int = 0

    total_foreign_keys: int = 0

    total_indexes: int = 0

    total_constraints: int = 0


# ---------------------------------------------------------
# Metadata Package
# ---------------------------------------------------------


class MetadataPackage(BaseModel):
    """
    This is the object that will eventually
    be serialized into metadata.json.

    Future engines (Profiler, AI, DDL Generator,
    Documentation Generator) will consume this object.
    """

    metadata: DatabaseMetadata

    profile: Optional[MetadataProfile] = None