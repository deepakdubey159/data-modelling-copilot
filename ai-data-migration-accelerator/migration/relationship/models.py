"""
Relationship Models

These models define the shape of `relationships.json`. They form a third
parallel model tree alongside `migration/canonical/models.py` (structural
metadata) and `migration/profiler/models.py` (data content), for the same
reason those two are separate: metadata describes the *shape* of the data,
profiling describes its *content*, and relationships describe the *structure
between entities*. All three are joined downstream by schema/table/column
name.

Direction convention (normative)
--------------------------------
An edge always points **from the table holding the foreign key** to the table
holding the referenced key. `source` is the child, `target` is the parent.
The natural cardinality of a foreign key is therefore MANY_TO_ONE, not
ONE_TO_MANY. `dependency_order` follows the opposite arrow — parents first —
so it is directly usable as a safe load order.
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ---------------------------------------------------------
# Enumerations
# ---------------------------------------------------------


class DiscoveryMethod(str, Enum):
    """How a relationship was found."""

    DECLARED = "DECLARED"
    """Read from a foreign key constraint declared in the source system."""

    INFERRED_NAMING = "INFERRED_NAMING"
    """Inferred from naming conventions alone (no profile evidence applied)."""

    INFERRED_PROFILE = "INFERRED_PROFILE"
    """Inferred from naming and corroborated by profile statistics."""

    DERIVED_JUNCTION = "DERIVED_JUNCTION"
    """Logical many-to-many derived from a bridge/junction table."""

    INFERRED_VERIFIED = "INFERRED_VERIFIED"
    """Reserved. Inference confirmed by actual value-overlap checking. Not
    produced today — the engine never queries data. Declared up front so that
    adding verification later is a new enum *value*, not a model change."""


class RelationshipType(str, Enum):
    IDENTIFYING = "IDENTIFYING"
    """The foreign key columns are part of the child's own primary key."""

    NON_IDENTIFYING = "NON_IDENTIFYING"

    SELF_REFERENCING = "SELF_REFERENCING"
    """Child and parent are the same table — a hierarchy."""

    MANY_TO_MANY_LOGICAL = "MANY_TO_MANY_LOGICAL"
    """Not a physical constraint. Derived from a junction table."""


class Cardinality(str, Enum):
    ONE_TO_ONE = "ONE_TO_ONE"
    ONE_TO_MANY = "ONE_TO_MANY"
    MANY_TO_ONE = "MANY_TO_ONE"
    MANY_TO_MANY = "MANY_TO_MANY"
    UNKNOWN = "UNKNOWN"


class CardinalitySource(str, Enum):
    """Whether cardinality was guaranteed by structure or merely observed."""

    STRUCTURAL = "STRUCTURAL"
    """Derived from keys/constraints — a guarantee."""

    OBSERVED = "OBSERVED"
    """Derived from profile statistics — true of today's data only."""

    UNKNOWN = "UNKNOWN"


class ConfidenceBand(str, Enum):
    """Coarse bucketing of `confidence`, so consumers need not hardcode
    thresholds of their own."""

    CERTAIN = "CERTAIN"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


# ---------------------------------------------------------
# Relationship
# ---------------------------------------------------------


class Relationship(BaseModel):
    """One directed edge: child (source) references parent (target)."""

    id: str
    """Deterministic and stable across runs. Lets downstream consumers —
    including an AI layer — reference a relationship without restating it."""

    constraint_name: Optional[str] = None
    """Populated for DECLARED relationships only."""

    source_schema: str
    source_table: str
    source_columns: List[str] = Field(default_factory=list)
    """A list so composite foreign keys are representable. Positionally
    aligned with `target_columns`."""

    target_schema: str
    target_table: str
    target_columns: List[str] = Field(default_factory=list)

    relationship_type: RelationshipType
    cardinality: Cardinality
    cardinality_source: CardinalitySource
    discovery_method: DiscoveryMethod

    confidence: float = 1.0
    """0.0-1.0. Always 1.0 for DECLARED — a constraint the database enforces
    cannot be made less certain by statistics."""

    confidence_band: ConfidenceBand = ConfidenceBand.CERTAIN

    is_self_referencing: bool = False

    is_optional: bool = False
    """True when any source column is nullable — optional participation."""

    is_identifying: bool = False

    evidence: List[str] = Field(default_factory=list)
    """Ordered, human-readable rationale. Every signal that was considered,
    including the ones that argued against. Intended to be read by a human
    reviewer or passed verbatim to an AI layer."""


# ---------------------------------------------------------
# Junction (bridge) table
# ---------------------------------------------------------


class JunctionTable(BaseModel):
    """A table whose primary key is composed entirely of foreign keys
    referencing two or more distinct tables."""

    schema_name: str
    table_name: str
    connected_tables: List[str] = Field(default_factory=list)
    key_columns: List[str] = Field(default_factory=list)
    payload_columns: List[str] = Field(default_factory=list)

    is_pure: bool = True
    """True when the table has no columns outside its primary key. A pure
    junction is usually not a business entity; one carrying payload columns
    is an associative entity in its own right. The conceptual model
    generator needs this distinction."""


# ---------------------------------------------------------
# Graph node
# ---------------------------------------------------------


class GraphNode(BaseModel):
    schema_name: str
    table_name: str
    table_type: str

    is_orphan: bool = False
    inbound_relationship_count: int = 0
    outbound_relationship_count: int = 0

    depth: int = 0
    """Topological level. 0 means the table depends on nothing."""


# ---------------------------------------------------------
# Summary
# ---------------------------------------------------------


class RelationshipSummary(BaseModel):
    total_relationships: int = 0
    declared_count: int = 0
    inferred_count: int = 0
    derived_count: int = 0
    junction_table_count: int = 0
    self_referencing_count: int = 0
    orphan_table_count: int = 0
    cycle_count: int = 0
    max_dependency_depth: int = 0
    tables_analyzed: int = 0
    columns_analyzed: int = 0


# ---------------------------------------------------------
# Graph
# ---------------------------------------------------------


class RelationshipGraph(BaseModel):
    database_name: str

    nodes: List[GraphNode] = Field(default_factory=list)
    relationships: List[Relationship] = Field(default_factory=list)
    junction_tables: List[JunctionTable] = Field(default_factory=list)

    dependency_order: List[str] = Field(default_factory=list)
    """Qualified `schema.table` names, parents first. Contains every table,
    including those involved in cycles (appended last)."""

    cycles: List[List[str]] = Field(default_factory=list)
    """Groups of tables that mutually depend on each other, making a total
    order impossible. Self-references are NOT reported here — they constrain
    row order within one table, not table order."""

    orphan_tables: List[str] = Field(default_factory=list)
    summary: RelationshipSummary = Field(default_factory=RelationshipSummary)


# ---------------------------------------------------------
# Package
# ---------------------------------------------------------


class RelationshipPackage(BaseModel):
    """This is the object serialized into relationships.json."""

    relationships: RelationshipGraph
