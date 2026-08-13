"""
Logical Data Model

The implementation-independent view of the data: entities, resolved
attributes with abstract domains, keys, and normalized relationships. It
sits between the conceptual model (what the business means) and the physical
model (what one platform requires).

Deliberately free of anything platform-specific. No SQL types, no lengths,
no precision, no storage, no indexes. `LogicalDataType` is a business domain
such as AMOUNT or EMAIL, not `DECIMAL(12,2)` or `VARCHAR(255)` — mapping a
domain onto a vendor type is the physical model's job, and doing it here
would tie the logical model to one target.

Fifth parallel model tree, joinable to the others by name:
canonical metadata (structure), profile (content), relationships (structure
between tables), conceptual (business meaning), logical (implementation-
independent design).
"""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field

from migration.relationship.models import Cardinality


# ---------------------------------------------------------
# Enumerations
# ---------------------------------------------------------


class LogicalDataType(str, Enum):
    """Abstract attribute domains, independent of any database.

    Chosen to be things a business analyst would recognise. The physical
    model maps each onto a concrete vendor type.
    """

    IDENTIFIER = "IDENTIFIER"
    """A key value whose only job is to identify. No business meaning."""

    CODE = "CODE"
    """A short controlled value drawn from a fixed vocabulary."""

    TEXT = "TEXT"
    WHOLE_NUMBER = "WHOLE_NUMBER"
    DECIMAL = "DECIMAL"
    AMOUNT = "AMOUNT"
    """Money. Separated from DECIMAL because it carries currency and
    rounding rules the physical model must respect."""

    PERCENTAGE = "PERCENTAGE"
    DATE = "DATE"
    TIMESTAMP = "TIMESTAMP"
    BOOLEAN = "BOOLEAN"
    EMAIL = "EMAIL"
    PHONE = "PHONE"


class EntityKind(str, Enum):
    FUNDAMENTAL = "FUNDAMENTAL"
    """Exists in its own right. Identified without reference to a parent."""

    DEPENDENT = "DEPENDENT"
    """Cannot exist without its parent, and its key includes the parent's."""

    ASSOCIATIVE = "ASSOCIATIVE"
    """Introduced to resolve a many-to-many relationship."""


class KeyKind(str, Enum):
    PRIMARY = "PRIMARY"
    ALTERNATE = "ALTERNATE"


class AttributeRole(str, Enum):
    PRIMARY_KEY = "PRIMARY_KEY"
    ALTERNATE_KEY = "ALTERNATE_KEY"
    FOREIGN_KEY = "FOREIGN_KEY"
    DESCRIPTIVE = "DESCRIPTIVE"


class Optionality(str, Enum):
    MANDATORY = "MANDATORY"
    OPTIONAL = "OPTIONAL"


class NormalForm(str, Enum):
    FIRST = "1NF"
    SECOND = "2NF"
    THIRD = "3NF"


# ---------------------------------------------------------
# Attributes and keys
# ---------------------------------------------------------


class LogicalAttribute(BaseModel):
    name: str
    data_type: LogicalDataType
    optionality: Optionality = Optionality.OPTIONAL
    role: AttributeRole = AttributeRole.DESCRIPTIVE

    references_entity: Optional[str] = None
    """Set on foreign key attributes: the entity this attribute points at."""

    source_attribute: Optional[str] = None
    """The conceptual attribute this was resolved from. Empty when the
    attribute was introduced by the logical design (a surrogate key, or a
    foreign key propagated from a parent)."""

    description: Optional[str] = None


class LogicalKey(BaseModel):
    name: str
    kind: KeyKind
    attributes: List[str] = Field(default_factory=list)

    is_surrogate: bool = False
    """True when the logical design introduced this key because the business
    identified no natural one. Recorded rather than hidden: a surrogate key
    is a design decision, not a discovery."""


# ---------------------------------------------------------
# Entities and relationships
# ---------------------------------------------------------


class LogicalEntity(BaseModel):
    name: str
    description: str
    kind: EntityKind = EntityKind.FUNDAMENTAL
    subject_area: str = ""

    attributes: List[LogicalAttribute] = Field(default_factory=list)
    primary_key: Optional[LogicalKey] = None
    alternate_keys: List[LogicalKey] = Field(default_factory=list)

    source_entities: List[str] = Field(default_factory=list)
    """Conceptual entities this was derived from. An associative entity
    derives from the two it connects."""

    source_tables: List[str] = Field(default_factory=list)


class LogicalRelationship(BaseModel):
    name: str
    parent_entity: str
    child_entity: str

    cardinality: Cardinality
    """Reuses the relationship engine's enum rather than defining a fourth
    copy of the same concept."""

    optionality: Optionality = Optionality.OPTIONAL
    """Participation of the child in the relationship."""

    is_identifying: bool = False
    """True when the foreign key forms part of the child's primary key, so
    the child cannot be identified without its parent."""

    foreign_key_attributes: List[str] = Field(default_factory=list)
    verb_phrase: str = ""
    derived_from: str = ""


# ---------------------------------------------------------
# Normalization
# ---------------------------------------------------------


class NormalizationAction(BaseModel):
    """One normalization decision, recorded so it can be audited.

    Covers both changes made and checks performed — a check that found
    nothing is still evidence the design was examined.
    """

    normal_form: NormalForm
    entity: str
    action: str
    rationale: str


# ---------------------------------------------------------
# Model
# ---------------------------------------------------------


class SubjectArea(BaseModel):
    name: str
    description: str
    entities: List[str] = Field(default_factory=list)


class LogicalModel(BaseModel):
    database_name: str
    summary: str

    subject_areas: List[SubjectArea] = Field(default_factory=list)
    entities: List[LogicalEntity] = Field(default_factory=list)
    relationships: List[LogicalRelationship] = Field(default_factory=list)
    normalization_actions: List[NormalizationAction] = Field(default_factory=list)
    assumptions: List[str] = Field(default_factory=list)


class LogicalModelPackage(BaseModel):
    """This is the object serialized into logical_model.json."""

    logical_model: LogicalModel

    generated_from: Optional[str] = None
    """The artifact this was derived from, for traceability."""

    generated_by: Optional[str] = None
