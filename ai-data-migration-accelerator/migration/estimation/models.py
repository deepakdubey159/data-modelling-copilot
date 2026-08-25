"""Effort estimation models.

Represents calculated effort components and complexity metrics.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


class ComplexityLevel(str, Enum):
    """Overall complexity classification."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    VERY_HIGH = "VERY_HIGH"


class ComplexityFactors(BaseModel):
    """Individual complexity drivers."""

    table_count: int
    """Number of tables in the schema."""

    total_columns: int
    """Total columns across all tables."""

    primary_key_relationships: int
    """Count of primary keys."""

    foreign_key_relationships: int
    """Count of foreign key constraints."""

    complex_relationships: int
    """Many-to-many, circular, or deeply nested relationships."""

    unique_constraints: int
    """Unique constraints (alternate keys)."""

    check_constraints: int
    """Check constraints."""

    large_tables: int
    """Tables with > 1M rows."""

    views_count: int = 0
    """Number of views (if applicable)."""

    procedures_count: int = 0
    """Number of stored procedures."""

    triggers_count: int = 0
    """Number of triggers."""

    datatype_conversions: int
    """Number of columns requiring datatype conversion."""

    target_specific_complexity: int
    """Target-platform-specific complexity points."""

    # DB2-specific complexity factors
    db2_legacy_datatypes: int = 0
    """Count of legacy DB2 datatypes (GRAPHIC, VARGRAPHIC, DECFLOAT, etc.)."""

    db2_lob_columns: int = 0
    """Count of CLOB/BLOB/XML columns."""

    db2_graphic_columns: int = 0
    """Count of GRAPHIC/VARGRAPHIC columns."""

    db2_decimal_columns: int = 0
    """Count of DECIMAL/DECFLOAT columns requiring precision handling."""

    db2_indexes: int = 0
    """Count of indexes in DB2 schema."""

    db2_xml_columns: int = 0
    """Count of XML columns."""


class EffortComponent(BaseModel):
    """A component of the total effort."""

    name: str
    """Component name (discovery, modeling, etc.)."""

    effort_days: float
    """Estimated person-days of effort."""

    description: str
    """What this component covers."""

    drivers: List[str] = Field(default_factory=list)
    """Factors driving this estimate."""


class EstimationResult(BaseModel):
    """Complete effort estimation for a migration."""

    source_type: str
    """Source database type."""

    target_type: str
    """Target database type."""

    complexity_level: ComplexityLevel
    """Overall complexity classification."""

    complexity_factors: ComplexityFactors
    """Individual complexity metrics."""

    effort_components: List[EffortComponent] = Field(default_factory=list)
    """Breakdown by effort type."""

    total_effort_days: float
    """Sum of all effort components."""

    total_effort_weeks: float
    """Total effort in weeks (5 working days)."""

    total_effort_months: float
    """Total effort in months (22 working days)."""

    discovery_effort_days: float
    """Discovery and assessment phase."""

    modeling_effort_days: float
    """Logical and physical modeling."""

    ddl_effort_days: float
    """DDL generation and validation."""

    conversion_effort_days: float
    """Data type conversion and migration logic."""

    testing_effort_days: float
    """Testing and validation."""

    migration_effort_days: float
    """Live migration execution."""

    assumptions: List[str] = Field(default_factory=list)
    """Assumptions underlying the estimate."""

    risks: List[str] = Field(default_factory=list)
    """Identified risks and mitigation."""

    recommendations: List[str] = Field(default_factory=list)
    """Recommendations for effort reduction."""

    confidence_level: str = "MEDIUM"
    """Confidence in the estimate (LOW, MEDIUM, HIGH)."""


class EstimationPackage(BaseModel):
    """Wrapper for serialization. Carries provenance."""

    estimation_result: EstimationResult
    generated_from: Optional[str] = None
    """The physical_model.json this was derived from."""

    generated_by: Optional[str] = None
    """The estimator that created this."""
