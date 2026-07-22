"""
Data Profile Models

These models define the shape of `profile.json`. They mirror the
Database -> Schema -> Table -> Column hierarchy used by the canonical
metadata models (`migration/canonical/models.py`) so the two artifacts can
be joined by name downstream (e.g. by the LLM layer or a documentation
generator), but they are kept as a separate model tree since profiling is
a distinct concern from structural metadata: metadata describes the
*shape* of the data, profiling describes its *content*.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Column Profile
# ---------------------------------------------------------


class ColumnProfile(BaseModel):
    """Data-quality and content statistics for one column."""

    name: str

    data_type: str

    null_count: int = 0

    null_percentage: float = 0.0

    distinct_count: int = 0

    distinct_percentage: float = 0.0

    min_value: Optional[str] = None

    max_value: Optional[str] = None

    min_length: Optional[int] = None

    max_length: Optional[int] = None

    detected_pattern: Optional[str] = None
    """Name of the best-matching format pattern (e.g. 'email', 'uuid'),
    or None if no pattern matched at least 80% of the sampled values."""

    pattern_match_ratio: Optional[float] = None
    """Fraction (0-1) of sampled non-null values matching `detected_pattern`."""


# ---------------------------------------------------------
# Table Profile
# ---------------------------------------------------------


class TableProfile(BaseModel):
    """Data-quality and content statistics for one table."""

    table_name: str

    row_count: int = 0

    duplicate_row_count: Optional[int] = None
    """None means "could not be computed" (e.g. a column type that can't
    participate in a distinct/partition comparison) — treat as unknown,
    not zero."""

    duplicate_percentage: Optional[float] = None

    columns: List[ColumnProfile] = Field(default_factory=list)

    profiling_error: Optional[str] = None
    """Set (and `columns` left empty) if profiling this table failed
    entirely — e.g. a permissions error. The run continues profiling
    other tables rather than aborting."""


# ---------------------------------------------------------
# Schema Profile
# ---------------------------------------------------------


class SchemaProfile(BaseModel):
    schema_name: str

    tables: List[TableProfile] = Field(default_factory=list)


# ---------------------------------------------------------
# Database Profile
# ---------------------------------------------------------


class DatabaseProfile(BaseModel):
    """Root object passed throughout the application for profiling data."""

    database_name: str

    schemas: List[SchemaProfile] = Field(default_factory=list)


# ---------------------------------------------------------
# Profile Package
# ---------------------------------------------------------


class ProfilePackage(BaseModel):
    """This is the object serialized into profile.json."""

    profile: DatabaseProfile
