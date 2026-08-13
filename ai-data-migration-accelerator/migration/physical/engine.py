"""
Physical Data Model Engine

Derives a platform-independent physical model from the logical model.

Deterministic — no LLM. The logical model already carries the design
judgment; sizing it, naming it and recommending indexes is a set of rules.

Transformation rules
--------------------
1.  Every logical entity becomes a table, named in snake_case and capped at
    the most conservative identifier length across platforms.
2.  Every logical attribute becomes a column. Abstract domains map onto
    generic storage classes with inferred length, precision and scale.
3.  Nullability comes from logical optionality; defaults are set only where
    genuinely inferable.
4.  Primary, foreign, alternate and composite keys are preserved verbatim.
5.  Indexes are recommended for primary keys, unique constraints and every
    foreign key.
6.  Check constraints are added only where the domain makes the rule certain
    (a percentage is 0-100; a quantity is not negative).
7.  Tables are classified LOOKUP / MASTER / TRANSACTION from their shape,
    which drives size, growth and storage recommendations.

Nothing here emits vendor SQL. `STRING(255)` is a statement about the data;
turning it into `VARCHAR2(255 CHAR)` or `STRING` is Module 7's job.
"""

from __future__ import annotations

import logging
import re

from migration.logical.models import (
    AttributeRole,
    EntityKind,
    LogicalAttribute,
    LogicalDataType,
    LogicalEntity,
    LogicalModel,
    LogicalModelPackage,
    Optionality,
)
from migration.physical.models import (
    ConstraintType,
    GrowthRate,
    IndexPurpose,
    NamingConvention,
    PhysicalColumn,
    PhysicalConstraint,
    PhysicalDataType,
    PhysicalIndex,
    PhysicalModel,
    PhysicalModelPackage,
    PhysicalTable,
    SizeCategory,
    StorageRecommendation,
    TableClassification,
)

logger = logging.getLogger(__name__)

# The most conservative identifier limit across the platforms this
# accelerator targets. Staying inside it means a generated name never has to
# be shortened again per-target.
MAX_IDENTIFIER_LENGTH = 30

# Abstract logical domain -> generic physical storage class, with sizing.
# (data_type, length, precision, scale)
_TYPE_MAP: dict[LogicalDataType, tuple[PhysicalDataType, int | None, int | None, int | None]] = {
    LogicalDataType.IDENTIFIER: (PhysicalDataType.IDENTIFIER, None, None, None),
    LogicalDataType.CODE: (PhysicalDataType.STRING, 30, None, None),
    LogicalDataType.TEXT: (PhysicalDataType.STRING, 255, None, None),
    LogicalDataType.WHOLE_NUMBER: (PhysicalDataType.INTEGER, None, None, None),
    LogicalDataType.DECIMAL: (PhysicalDataType.DECIMAL, None, 18, 4),
    LogicalDataType.AMOUNT: (PhysicalDataType.DECIMAL, None, 18, 2),
    LogicalDataType.PERCENTAGE: (PhysicalDataType.DECIMAL, None, 5, 2),
    LogicalDataType.DATE: (PhysicalDataType.DATE, None, None, None),
    LogicalDataType.TIMESTAMP: (PhysicalDataType.TIMESTAMP, None, None, None),
    LogicalDataType.BOOLEAN: (PhysicalDataType.BOOLEAN, None, None, None),
    LogicalDataType.EMAIL: (PhysicalDataType.STRING, 255, None, None),
    LogicalDataType.PHONE: (PhysicalDataType.STRING, 30, None, None),
}

# Name fragments that refine STRING sizing beyond the domain default.
_LENGTH_HINTS: tuple[tuple[tuple[str, ...], int], ...] = (
    (("description", "comment", "note", "summary", "reason"), 500),
    (("address", "url", "path"), 255),
    (("name", "title"), 100),
)


class PhysicalModelEngine:
    """Derives a `PhysicalModelPackage` from a logical model."""

    def __init__(
        self,
        package: LogicalModelPackage,
        source_artifact: str = "logical_model.json",
    ):
        self.package = package
        self.model: LogicalModel = package.logical_model
        self.source_artifact = source_artifact

        self._table_names: dict[str, str] = {}
        self._notes: list[str] = []

    # -- Public API --------------------------------------------------------

    def generate(self) -> PhysicalModelPackage:
        self._table_names = self._assign_table_names()

        inbound, outbound = self._reference_counts()
        tables = [
            self._build_table(entity, inbound, outbound) for entity in self.model.entities
        ]
        self._align_foreign_key_types(tables)

        physical = PhysicalModel(
            database_name=self.model.database_name,
            summary=self._summary(tables),
            naming_convention=NamingConvention(
                style="snake_case",
                max_identifier_length=MAX_IDENTIFIER_LENGTH,
                notes=sorted(set(self._notes)),
            ),
            tables=sorted(tables, key=lambda t: t.name),
            design_notes=self._design_notes(tables),
        )

        logger.info(
            "Physical model derived: %s tables, %s columns, %s constraints, %s indexes",
            len(physical.tables),
            sum(len(t.columns) for t in physical.tables),
            len(physical.all_constraints()),
            len(physical.all_indexes()),
        )

        return PhysicalModelPackage(
            physical_model=physical,
            generated_from=self.source_artifact,
            generated_by=self.package.generated_by,
        )

    # -- Naming ------------------------------------------------------------

    def _assign_table_names(self) -> dict[str, str]:
        """Map every logical entity onto a unique physical table name."""
        names: dict[str, str] = {}
        used: set[str] = set()

        for entity in self.model.entities:
            candidate = _identifier(entity.name)
            if len(candidate) > MAX_IDENTIFIER_LENGTH:
                candidate = _truncate_identifier(candidate)
                self._notes.append(
                    f"'{entity.name}' was shortened to '{candidate}' to stay within the "
                    f"{MAX_IDENTIFIER_LENGTH}-character identifier limit."
                )

            name, suffix = candidate, 2
            while name in used:
                name = _truncate_identifier(f"{candidate}_{suffix}")
                suffix += 1

            used.add(name)
            names[entity.name] = name

        return names

    # -- Tables ------------------------------------------------------------

    def _reference_counts(self) -> tuple[dict[str, int], dict[str, int]]:
        inbound = {entity.name: 0 for entity in self.model.entities}
        outbound = {entity.name: 0 for entity in self.model.entities}

        for relationship in self.model.relationships:
            if relationship.parent_entity in inbound:
                inbound[relationship.parent_entity] += 1
            if relationship.child_entity in outbound:
                outbound[relationship.child_entity] += 1

        return inbound, outbound

    def _build_table(
        self, entity: LogicalEntity, inbound: dict[str, int], outbound: dict[str, int]
    ) -> PhysicalTable:
        table_name = self._table_names[entity.name]
        columns = [
            self._build_column(attribute, position)
            for position, attribute in enumerate(entity.attributes, start=1)
        ]

        classification = self._classify(entity, columns, inbound, outbound)
        size, growth = _size_and_growth(classification, entity.kind)

        table = PhysicalTable(
            name=table_name,
            logical_entity=entity.name,
            subject_area=entity.subject_area,
            classification=classification,
            size_category=size,
            growth_rate=growth,
            columns=columns,
            source_tables=list(entity.source_tables),
        )

        table.constraints = self._build_constraints(entity, table)
        table.indexes = self._build_indexes(table)
        table.storage = self._build_storage(table)
        return table

    def _build_column(self, attribute: LogicalAttribute, position: int) -> PhysicalColumn:
        data_type, length, precision, scale = _TYPE_MAP.get(
            attribute.data_type, (PhysicalDataType.STRING, 255, None, None)
        )

        if data_type == PhysicalDataType.STRING:
            length = _refine_length(attribute.name, length)

        nullable = attribute.optionality != Optionality.MANDATORY

        return PhysicalColumn(
            name=_identifier(attribute.name),
            data_type=data_type,
            length=length,
            precision=precision,
            scale=scale,
            nullable=nullable,
            default_value=_default_for(attribute, data_type, nullable),
            is_primary_key=attribute.role == AttributeRole.PRIMARY_KEY,
            is_foreign_key=attribute.role == AttributeRole.FOREIGN_KEY
            or (
                attribute.references_entity is not None
                and attribute.role == AttributeRole.PRIMARY_KEY
            ),
            is_unique=attribute.role == AttributeRole.ALTERNATE_KEY,
            ordinal_position=position,
            source_attribute=attribute.name,
        )

    # -- Referential type alignment ----------------------------------------

    def _align_foreign_key_types(self, tables: list[PhysicalTable]) -> None:
        """Give every foreign key the same storage class as the key it points at.

        The logical model types foreign keys abstractly as IDENTIFIER, which
        is right at that level but wrong here: a foreign key must be
        physically comparable to the column it references or the constraint
        cannot be created. `city.state_name` referencing `state.state_name`
        has to be STRING(100), not IDENTIFIER.

        This is the one place the model has to be looked at as a whole, so it
        runs after every table exists.
        """
        by_name = {table.name: table for table in tables}
        aligned = 0

        for table in tables:
            columns = {column.name: column for column in table.columns}
            for constraint in table.constraints:
                if constraint.constraint_type != ConstraintType.FOREIGN_KEY:
                    continue

                parent = by_name.get(constraint.referenced_table or "")
                if parent is None or not constraint.columns:
                    continue

                target_name = (
                    constraint.referenced_columns[0]
                    if constraint.referenced_columns
                    else None
                )
                target = next(
                    (c for c in parent.columns if c.name == target_name),
                    next((c for c in parent.columns if c.is_primary_key), None),
                )
                column = columns.get(constraint.columns[0])
                if target is None or column is None:
                    continue

                if (
                    column.data_type != target.data_type
                    or column.length != target.length
                    or column.precision != target.precision
                    or column.scale != target.scale
                ):
                    column.data_type = target.data_type
                    column.length = target.length
                    column.precision = target.precision
                    column.scale = target.scale
                    aligned += 1

        if aligned:
            self._notes.append(
                f"{aligned} foreign key columns were retyped to match the key they "
                f"reference. A foreign key must be physically comparable to its parent "
                f"column or the constraint cannot be created."
            )

    # -- Classification ----------------------------------------------------

    def _classify(
        self,
        entity: LogicalEntity,
        columns: list[PhysicalColumn],
        inbound: dict[str, int],
        outbound: dict[str, int],
    ) -> TableClassification:
        """Classify by shape. First match wins.

        The signal is structural: what references it, what it references, and
        whether it records a point in time. This is a heuristic, not a
        derivation — the report says so, and the classification is worth a
        reviewer's eye before it drives sizing decisions.
        """
        if entity.kind in (EntityKind.ASSOCIATIVE, EntityKind.DEPENDENT):
            # Link rows and detail lines multiply against their parent.
            return TableClassification.TRANSACTION

        references_out = outbound.get(entity.name, 0)
        referenced_by = inbound.get(entity.name, 0)
        temporal = any(
            column.data_type in (PhysicalDataType.DATE, PhysicalDataType.TIMESTAMP)
            for column in columns
        )

        # A self-reference is a hierarchy within one table, not a dependency
        # on other data, so it must not make a table look transactional.
        outward = references_out - sum(
            1
            for relationship in self.model.relationships
            if relationship.child_entity == entity.name
            and relationship.parent_entity == entity.name
        )

        if references_out == 0:
            # References nothing: either static reference data, or a
            # standalone log if it records a point in time.
            return (
                TableClassification.TRANSACTION
                if temporal and referenced_by == 0
                else TableClassification.LOOKUP
            )
        if referenced_by == 0:
            # A leaf that points at other data is an event record.
            return TableClassification.TRANSACTION
        if temporal and outward >= 2:
            # Records a moment and ties together two or more other things.
            return TableClassification.TRANSACTION
        return TableClassification.MASTER

    # -- Constraints -------------------------------------------------------

    def _build_constraints(
        self, entity: LogicalEntity, table: PhysicalTable
    ) -> list[PhysicalConstraint]:
        constraints: list[PhysicalConstraint] = []

        key_columns = table.primary_key_columns()
        if key_columns:
            constraints.append(
                PhysicalConstraint(
                    name=_constraint_name("pk", table.name),
                    constraint_type=ConstraintType.PRIMARY_KEY,
                    table=table.name,
                    columns=key_columns,
                    rationale=(
                        "Composite key preserved from the logical model."
                        if len(key_columns) > 1
                        else "Primary key preserved from the logical model."
                    ),
                )
            )

        for key in entity.alternate_keys:
            columns = [_identifier(name) for name in key.attributes]
            constraints.append(
                PhysicalConstraint(
                    name=_constraint_name("uq", table.name, *columns),
                    constraint_type=ConstraintType.UNIQUE,
                    table=table.name,
                    columns=columns,
                    rationale="Alternate key: identifies a row as reliably as the primary key.",
                )
            )

        for attribute in entity.attributes:
            if attribute.references_entity is None:
                continue
            parent = self._table_names.get(attribute.references_entity)
            if parent is None:
                continue

            parent_entity = next(
                (e for e in self.model.entities if e.name == attribute.references_entity), None
            )
            referenced = (
                [_identifier(a) for a in parent_entity.primary_key.attributes]
                if parent_entity and parent_entity.primary_key
                else []
            )
            column = _identifier(attribute.name)
            constraints.append(
                PhysicalConstraint(
                    name=_constraint_name("fk", table.name, column),
                    constraint_type=ConstraintType.FOREIGN_KEY,
                    table=table.name,
                    columns=[column],
                    referenced_table=parent,
                    referenced_columns=referenced[:1] or [column],
                    rationale=f"Preserves the relationship to {attribute.references_entity}.",
                )
            )

        constraints.extend(self._check_constraints(table))
        return constraints

    @staticmethod
    def _check_constraints(table: PhysicalTable) -> list[PhysicalConstraint]:
        """Only rules the domain makes certain.

        A percentage is bounded and a quantity is not negative. An amount is
        deliberately left alone: refunds, adjustments and credits are all
        legitimately negative, so a `>= 0` check would reject valid data.
        """
        constraints: list[PhysicalConstraint] = []

        for column in table.columns:
            lowered = column.name.lower()

            if column.precision == 5 and column.scale == 2 and "percent" in lowered:
                constraints.append(
                    PhysicalConstraint(
                        name=_constraint_name("ck", table.name, column.name),
                        constraint_type=ConstraintType.CHECK,
                        table=table.name,
                        columns=[column.name],
                        expression=f"{column.name} BETWEEN 0 AND 100",
                        rationale="A percentage cannot fall outside 0-100.",
                    )
                )
            elif column.data_type == PhysicalDataType.INTEGER and re.search(
                r"\b(quantity|count|level)\b", lowered
            ):
                constraints.append(
                    PhysicalConstraint(
                        name=_constraint_name("ck", table.name, column.name),
                        constraint_type=ConstraintType.CHECK,
                        table=table.name,
                        columns=[column.name],
                        expression=f"{column.name} >= 0",
                        rationale="A counted quantity cannot be negative.",
                    )
                )

        return constraints

    # -- Indexes and storage ------------------------------------------------

    @staticmethod
    def _build_indexes(table: PhysicalTable) -> list[PhysicalIndex]:
        indexes: list[PhysicalIndex] = []

        key_columns = table.primary_key_columns()
        if key_columns:
            indexes.append(
                PhysicalIndex(
                    name=_constraint_name("idx", table.name, "pk"),
                    table=table.name,
                    columns=key_columns,
                    is_unique=True,
                    purpose=IndexPurpose.PRIMARY_KEY,
                    rationale="Enforces and serves lookups on the primary key.",
                )
            )

        for constraint in table.constraints:
            if constraint.constraint_type == ConstraintType.UNIQUE:
                indexes.append(
                    PhysicalIndex(
                        name=_constraint_name("idx", table.name, *constraint.columns),
                        table=table.name,
                        columns=list(constraint.columns),
                        is_unique=True,
                        purpose=IndexPurpose.UNIQUE_CONSTRAINT,
                        rationale="Enforces the alternate key.",
                    )
                )

        # Foreign keys that are not already covered by the primary key index.
        covered = {tuple(index.columns) for index in indexes}
        for constraint in table.constraints:
            if constraint.constraint_type != ConstraintType.FOREIGN_KEY:
                continue
            columns = tuple(constraint.columns)
            if columns in covered or (key_columns and columns[0] == key_columns[0]):
                continue
            covered.add(columns)
            indexes.append(
                PhysicalIndex(
                    name=_constraint_name("idx", table.name, *constraint.columns),
                    table=table.name,
                    columns=list(constraint.columns),
                    is_unique=False,
                    purpose=IndexPurpose.FOREIGN_KEY,
                    rationale=(
                        "Foreign keys are joined on constantly and are scanned when the "
                        "parent is deleted; an unindexed foreign key is a common cause of "
                        "slow joins and lock escalation."
                    ),
                )
            )

        return indexes

    @staticmethod
    def _build_storage(table: PhysicalTable) -> StorageRecommendation:
        """Recommend partition and clustering candidates.

        Partitioning only helps where there is volume to prune, so it is
        recommended for growing tables and withheld from lookups.
        """
        partitions: list[str] = []
        clustering: list[str] = []
        reasons: list[str] = []

        if table.classification == TableClassification.TRANSACTION:
            temporal = [
                c.name
                for c in table.columns
                if c.data_type in (PhysicalDataType.DATE, PhysicalDataType.TIMESTAMP)
            ]
            if temporal:
                partitions.append(temporal[0])
                reasons.append(
                    f"Transaction volume accumulates over time, so partitioning on "
                    f"{temporal[0]} lets queries prune to a date range."
                )

            foreign = [c.name for c in table.columns if c.is_foreign_key]
            if foreign:
                clustering.extend(foreign[:2])
                reasons.append(
                    f"Clustering on {', '.join(foreign[:2])} co-locates rows that are "
                    f"joined and filtered together."
                )

        elif table.classification == TableClassification.MASTER:
            key_columns = table.primary_key_columns()
            if key_columns:
                clustering.extend(key_columns)
                reasons.append(
                    "Master data is looked up by key; clustering on it keeps those "
                    "reads to a minimum of blocks."
                )
        else:
            reasons.append(
                "Lookup data is small enough to be scanned or cached in full; "
                "partitioning would add maintenance without reducing work."
            )

        return StorageRecommendation(
            table=table.name,
            partition_candidates=partitions,
            clustering_candidates=clustering,
            rationale=" ".join(reasons),
        )

    # -- Assembly ----------------------------------------------------------

    @staticmethod
    def _summary(tables: list[PhysicalTable]) -> str:
        counts = {classification: 0 for classification in TableClassification}
        for table in tables:
            counts[table.classification] += 1

        columns = sum(len(t.columns) for t in tables)
        constraints = sum(len(t.constraints) for t in tables)
        indexes = sum(len(t.indexes) for t in tables)
        partitioned = sum(
            1 for t in tables if t.storage and t.storage.partition_candidates
        )

        return (
            f"{len(tables)} tables and {columns} columns, carrying {constraints} "
            f"constraints and {indexes} recommended indexes. "
            f"{counts[TableClassification.TRANSACTION]} tables are transactional, "
            f"{counts[TableClassification.MASTER]} hold master data and "
            f"{counts[TableClassification.LOOKUP]} are lookups; {partitioned} are "
            f"candidates for partitioning. Types, lengths and precision are generic — "
            f"no vendor syntax appears until DDL generation."
        )

    @staticmethod
    def _design_notes(tables: list[PhysicalTable]) -> list[str]:
        notes = [
            "Data types are generic storage classes. STRING(255) states the shape of "
            "the data, not a vendor type; mapping onto VARCHAR2, NVARCHAR or STRING "
            "happens during DDL generation.",
            "Every foreign key carries an index recommendation. Unindexed foreign keys "
            "are a routine cause of slow joins and of lock escalation on parent deletes.",
            "Check constraints are only added where the domain makes the rule certain. "
            "Amounts are deliberately left unconstrained because refunds, credits and "
            "adjustments are legitimately negative.",
        ]

        surrogate_tables = [
            t.name
            for t in tables
            if any(c.is_primary_key and c.name.endswith("_identifier") for c in t.columns)
        ]
        if surrogate_tables:
            notes.append(
                f"{len(surrogate_tables)} tables are keyed on a surrogate identifier "
                f"carried through from the logical model "
                f"({', '.join(sorted(surrogate_tables))})."
            )

        return notes


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def _identifier(name: str) -> str:
    """Convert a business name into a portable snake_case identifier."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", name).strip("_").lower()
    cleaned = re.sub(r"_+", "_", cleaned)
    if cleaned and cleaned[0].isdigit():
        cleaned = f"t_{cleaned}"
    return _truncate_identifier(cleaned) if len(cleaned) > MAX_IDENTIFIER_LENGTH else cleaned


def _truncate_identifier(name: str) -> str:
    """Shorten on a word boundary so the result stays readable."""
    if len(name) <= MAX_IDENTIFIER_LENGTH:
        return name
    parts = name.split("_")
    while len(parts) > 1 and len("_".join(parts)) > MAX_IDENTIFIER_LENGTH:
        parts.pop()
    shortened = "_".join(parts)
    return shortened[:MAX_IDENTIFIER_LENGTH].rstrip("_") or name[:MAX_IDENTIFIER_LENGTH]


def _constraint_name(prefix: str, table: str, *parts: str) -> str:
    name = "_".join([prefix, table, *parts])
    return _truncate_identifier(name)


def _refine_length(name: str, default: int | None) -> int | None:
    lowered = name.lower()
    for fragments, length in _LENGTH_HINTS:
        if any(fragment in lowered for fragment in fragments):
            return length
    return default


def _default_for(
    attribute: LogicalAttribute, data_type: PhysicalDataType, nullable: bool
) -> str | None:
    """Only where the default is genuinely inferable.

    Guessing defaults is worse than leaving them out: a wrong default is
    silently written into every row that omits the column.
    """
    if nullable:
        return None

    lowered = attribute.name.lower()
    if data_type == PhysicalDataType.BOOLEAN:
        return "FALSE"
    if data_type == PhysicalDataType.TIMESTAMP and re.search(
        r"\b(created|recorded|performed|logged)\b", lowered
    ):
        return "CURRENT_TIMESTAMP"
    return None


def _size_and_growth(
    classification: TableClassification, kind: EntityKind
) -> tuple[SizeCategory, GrowthRate]:
    if classification == TableClassification.LOOKUP:
        return SizeCategory.SMALL, GrowthRate.STATIC
    if classification == TableClassification.MASTER:
        return SizeCategory.MEDIUM, GrowthRate.LOW
    if kind in (EntityKind.DEPENDENT, EntityKind.ASSOCIATIVE):
        # Detail lines and link rows multiply against their parent.
        return SizeCategory.VERY_LARGE, GrowthRate.HIGH
    return SizeCategory.LARGE, GrowthRate.MODERATE
