"""
Conceptual Data Model

The business view of a database: what entities the organization actually
works with, how they relate, and what rules govern them. Deliberately free
of anything physical — no tables, no columns, no data types, no keys as the
database defines them.

This is the fourth parallel model tree, alongside canonical metadata
(structure), profile (content) and relationships (structure between
entities). Each is joinable to the others by name, and each evolves
independently.

Unlike the first three, this model is produced with AI assistance. Every
field is still a validated Pydantic model — the AI proposes, the parser
validates, and nothing unvalidated reaches disk.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field

from migration.relationship.models import Cardinality


# =========================================================
# Business context — the input side
# =========================================================
# Produced by the context builder from the deterministic artifacts and fed
# to the prompt builder. Reusable by every future AI-assisted engine; only
# the prompt and the response model change per engine.


class ColumnContext(BaseModel):
    """One column, described by business role rather than data type."""

    name: str

    role: str
    """identifier | reference | category | formatted_value | attribute.
    Deliberately business-flavoured — the AI is asked about meaning, not
    storage, so `data_type` is withheld on purpose."""

    nullable: bool = True
    references: Optional[str] = None
    distinct_count: Optional[int] = None
    null_percentage: Optional[float] = None
    detected_pattern: Optional[str] = None
    sample_range: Optional[str] = None


class TableContext(BaseModel):
    schema_name: str
    table_name: str
    row_count: Optional[int] = None
    column_count: int = 0
    primary_key: List[str] = Field(default_factory=list)
    columns: List[ColumnContext] = Field(default_factory=list)
    omitted_column_count: int = 0


class JunctionContext(BaseModel):
    table_name: str
    connects: List[str] = Field(default_factory=list)
    is_pure_link: bool = True
    extra_attributes: List[str] = Field(default_factory=list)


class BusinessContext(BaseModel):
    """Compact, source-independent business context for an LLM prompt."""

    database_name: str
    schemas: List[str] = Field(default_factory=list)
    total_tables: int = 0
    total_columns: int = 0
    total_relationships: int = 0

    tables: List[TableContext] = Field(default_factory=list)
    omitted_tables: List[str] = Field(default_factory=list)

    relationships: List[str] = Field(default_factory=list)
    junction_tables: List[JunctionContext] = Field(default_factory=list)
    self_referencing: List[str] = Field(default_factory=list)
    dependency_order: List[str] = Field(default_factory=list)
    orphan_tables: List[str] = Field(default_factory=list)

    notes: List[str] = Field(default_factory=list)
    """What was truncated or unavailable. Stated explicitly so the model
    knows the difference between 'this does not exist' and 'this was not
    shown to you' — and so its assumptions can reflect that."""


# =========================================================
# Conceptual model — the output side
# =========================================================


# ---------------------------------------------------------
# Relationship between business entities
# ---------------------------------------------------------


class ConceptualRelationship(BaseModel):
    """A relationship as a business person would describe it."""

    related_entity: str
    """Name of the entity on the other side. Must resolve to an entity in
    the same model — the parser rejects dangling references."""

    verb_phrase: str
    """How the relationship reads in business language, e.g. 'places',
    'is stocked in', 'reports to'. This is what a foreign key cannot tell
    you and what the AI layer exists to supply."""

    cardinality: Cardinality
    """Reuses the relationship engine's enum rather than defining a second
    one — the concept is identical and duplicating it would let the two
    drift apart."""

    is_optional: bool = False
    """True when participation is optional (zero-or-more rather than
    one-or-more)."""

    description: Optional[str] = None


# ---------------------------------------------------------
# Business entity
# ---------------------------------------------------------


class ConceptualEntity(BaseModel):
    """A thing the business cares about, independent of how it is stored."""

    name: str
    """Business name, not the table name. 'Customer', not 'cust_mstr'."""

    description: str

    business_key: List[str] = Field(default_factory=list)
    """How the business identifies one of these in the real world — an order
    number, an email address. Not necessarily the physical primary key, and
    frequently different from it."""

    attributes: List[str] = Field(default_factory=list)
    """High-level business attributes. Names only — no data types, lengths
    or nullability. Those belong to the logical and physical models."""

    relationships: List[ConceptualRelationship] = Field(default_factory=list)

    source_tables: List[str] = Field(default_factory=list)
    """Qualified physical tables this entity was derived from. Pure
    traceability: it lets a reviewer check the AI's work against the
    deterministic artifacts, and lets the logical model generator map
    entities back to structure without re-deriving the mapping."""


# ---------------------------------------------------------
# Business domain
# ---------------------------------------------------------


class ConceptualDomain(BaseModel):
    """A subject area grouping related entities — Sales, Inventory, HR."""

    name: str
    description: str
    entities: List[str] = Field(default_factory=list)
    """Entity names in this domain. Validated against the entity list."""


# ---------------------------------------------------------
# Conceptual model
# ---------------------------------------------------------


class ConceptualModel(BaseModel):
    """The complete business view. This is the shape the AI must return."""

    database_name: str
    summary: str
    """Executive summary: what business this database appears to support."""

    domains: List[ConceptualDomain] = Field(default_factory=list)
    entities: List[ConceptualEntity] = Field(default_factory=list)

    business_rules: List[str] = Field(default_factory=list)
    """Rules the structure and data imply, stated in business language."""

    assumptions: List[str] = Field(default_factory=list)
    """What the AI had to assume. Makes the model auditable — a reviewer can
    check each assumption rather than guessing where interpretation
    happened."""

    recommendations: List[str] = Field(default_factory=list)


# ---------------------------------------------------------
# Package
# ---------------------------------------------------------


class ConceptualModelPackage(BaseModel):
    """This is the object serialized into conceptual_model.json."""

    conceptual_model: ConceptualModel

    generated_by: Optional[str] = None
    """Model identifier that produced this artifact. An AI-generated
    enterprise artifact must record its provenance — without it there is no
    way to tell which model's judgment a downstream decision rests on."""
