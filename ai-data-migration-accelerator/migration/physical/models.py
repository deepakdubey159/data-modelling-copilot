"""
Physical Data Model

The implementation-ready design: tables, columns with concrete sizing,
constraints, index recommendations and storage guidance — expressed in
generic terms that any relational or lakehouse platform can be targeted
from.

Deliberately platform-independent. `PhysicalDataType.STRING` with
`length=255` is a statement about the data, not about `VARCHAR(255)` or
`NVARCHAR2(255)` or `STRING`. Choosing the vendor spelling is Module 7's
job; doing it here would tie a single physical model to one target and
defeat the point of a migration accelerator.

`physical_model.json` is the single source of truth for DDL generation, so
everything a generator needs is on the model: names, types, sizing,
nullability, defaults, keys, constraints and indexes.

Business descriptions are deliberately absent. They already live in the
conceptual and logical models, and each entity carries `logical_entity` as a
pointer back. Repeating prose here would create three copies to keep in sync.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Enumerations
# ---------------------------------------------------------


class PhysicalDataType(str, Enum):
    """Generic storage classes. Module 7 maps these onto vendor types."""

    IDENTIFIER = "IDENTIFIER"
    STRING = "STRING"
    INTEGER = "INTEGER"
    DECIMAL = "DECIMAL"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    BOOLEAN = "BOOLEAN"
    BINARY = "BINARY"
    JSON = "JSON"


class TableClassification(str, Enum):
    """How the table behaves at runtime, which drives sizing and indexing."""

    LOOKUP = "LOOKUP"
    """Small reference data. Read constantly, written rarely."""

    MASTER = "MASTER"
    """Core business records with their own identity and lifecycle."""

    TRANSACTION = "TRANSACTION"
    """Event or activity records. The tables that grow."""


class SizeCategory(str, Enum):
    SMALL = "SMALL"
    MEDIUM = "MEDIUM"
    LARGE = "LARGE"
    VERY_LARGE = "VERY_LARGE"


class GrowthRate(str, Enum):
    STATIC = "STATIC"
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"


class ConstraintType(str, Enum):
    PRIMARY_KEY = "PRIMARY_KEY"
    FOREIGN_KEY = "FOREIGN_KEY"
    UNIQUE = "UNIQUE"
    CHECK = "CHECK"


class IndexPurpose(str, Enum):
    PRIMARY_KEY = "PRIMARY_KEY"
    UNIQUE_CONSTRAINT = "UNIQUE_CONSTRAINT"
    FOREIGN_KEY = "FOREIGN_KEY"


# ---------------------------------------------------------
# Columns
# ---------------------------------------------------------


class PhysicalColumn(BaseModel):
    name: str
    data_type: PhysicalDataType

    length: Optional[int] = None
    """Character length for STRING. None for types where it has no meaning."""

    precision: Optional[int] = None
    scale: Optional[int] = None

    nullable: bool = True

    default_value: Optional[str] = None
    """A generic token such as CURRENT_TIMESTAMP or FALSE, not vendor SQL.
    Only set where the default is genuinely inferable."""

    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_unique: bool = False

    ordinal_position: int = 0
    source_attribute: Optional[str] = None
    """The logical attribute this column was resolved from."""

    source_database_type: Optional[str] = None
    """The original source database type name (e.g. 'VARCHAR', 'DECIMAL'),
    verbatim from the source catalog. Used for accurate type mapping when
    source type information is available."""

    source_length: Optional[int] = None
    source_precision: Optional[int] = None
    source_scale: Optional[int] = None
    """The source's own declared length/precision/scale, structurally -
    never parsed out of a combined type string. Authoritative over the
    generic length/precision/scale above whenever a confident source column
    match exists; kept separately so a target adapter can tell the
    difference between 'the source said so' and 'a generic default'."""

    source_nullable: Optional[bool] = None
    source_default: Optional[str] = None
    """The source's raw default expression, verbatim, for traceability only.
    Not necessarily valid syntax on any target - a target adapter must
    translate or omit it, never emit it unchanged."""

    def type_signature(self) -> str:
        """Human-readable type, e.g. STRING(255) or DECIMAL(18,2)."""
        if self.length is not None:
            return f"{self.data_type.value}({self.length})"
        if self.precision is not None:
            scale = self.scale if self.scale is not None else 0
            return f"{self.data_type.value}({self.precision},{scale})"
        return self.data_type.value


# ---------------------------------------------------------
# Constraints and indexes
# ---------------------------------------------------------


class PhysicalConstraint(BaseModel):
    name: str
    constraint_type: ConstraintType
    table: str
    columns: List[str] = Field(default_factory=list)

    referenced_table: Optional[str] = None
    referenced_columns: List[str] = Field(default_factory=list)

    expression: Optional[str] = None
    """For CHECK constraints. Written generically so any dialect can render
    it, e.g. 'discount_percentage BETWEEN 0 AND 100'."""

    rationale: Optional[str] = None


class PhysicalIndex(BaseModel):
    name: str
    table: str
    columns: List[str] = Field(default_factory=list)
    is_unique: bool = False
    purpose: IndexPurpose = IndexPurpose.FOREIGN_KEY
    rationale: str = ""


class StorageRecommendation(BaseModel):
    table: str
    partition_candidates: List[str] = Field(default_factory=list)
    clustering_candidates: List[str] = Field(default_factory=list)
    rationale: str = ""


# ---------------------------------------------------------
# Tables
# ---------------------------------------------------------


class PhysicalTable(BaseModel):
    name: str

    logical_entity: str
    """Pointer back to the logical model. Business meaning lives there and
    is deliberately not duplicated here."""

    subject_area: str = ""
    classification: TableClassification = TableClassification.MASTER
    size_category: SizeCategory = SizeCategory.MEDIUM
    growth_rate: GrowthRate = GrowthRate.LOW

    columns: List[PhysicalColumn] = Field(default_factory=list)
    constraints: List[PhysicalConstraint] = Field(default_factory=list)
    indexes: List[PhysicalIndex] = Field(default_factory=list)
    storage: Optional[StorageRecommendation] = None

    source_tables: List[str] = Field(default_factory=list)
    """Original source tables, carried through for lineage."""

    def primary_key_columns(self) -> List[str]:
        return [c.name for c in self.columns if c.is_primary_key]


# ---------------------------------------------------------
# Model
# ---------------------------------------------------------


class NamingConvention(BaseModel):
    """Recorded so a reviewer can see the rules the names were built with,
    and so Module 7 does not have to reverse-engineer them."""

    style: str = "snake_case"
    max_identifier_length: int = 30
    notes: List[str] = Field(default_factory=list)


class PhysicalModel(BaseModel):
    database_name: str
    summary: str

    naming_convention: NamingConvention = Field(default_factory=NamingConvention)
    tables: List[PhysicalTable] = Field(default_factory=list)
    design_notes: List[str] = Field(default_factory=list)

    def all_constraints(self) -> List[PhysicalConstraint]:
        return [c for table in self.tables for c in table.constraints]

    def all_indexes(self) -> List[PhysicalIndex]:
        return [i for table in self.tables for i in table.indexes]


class PhysicalModelPackage(BaseModel):
    """This is the object serialized into physical_model.json."""

    physical_model: PhysicalModel
    generated_from: Optional[str] = None
    generated_by: Optional[str] = None
