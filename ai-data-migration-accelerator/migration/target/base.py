"""Base target adapter abstraction.

Defines the contract every target implementation must fulfill.
Concrete implementations map the generic physical model to their platform.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Optional

from migration.physical.models import (
    ConstraintType,
    PhysicalColumn,
    PhysicalConstraint,
    PhysicalDataType,
    PhysicalIndex,
    PhysicalModel,
    PhysicalModelPackage,
    PhysicalTable,
)
from migration.target.models import (
    TargetCapability,
    TargetColumn,
    TargetConstraint,
    TargetDataTypeMapping,
    TargetIdentifierRule,
    TargetIndex,
    TargetModel,
    TargetModelPackage,
    TargetTable,
)

logger = logging.getLogger(__name__)


class TargetAdapterError(Exception):
    """Raised when a physical model feature cannot be mapped to the target."""

    pass


class BaseTargetAdapter(ABC):
    """Abstract base for all target platform adapters.

    Maps the generic physical model to target-specific types, naming rules,
    supported constraints, and storage options. Every adapter must:

    1. Define what data types it supports and how they map
    2. Implement identifier naming rules
    3. List what constraints and features are supported
    4. Preserve lineage back to the physical model
    5. Explicitly reject unsupported features with clear error messages
    """

    def __init__(self, package: PhysicalModelPackage, source_artifact: str = "physical_model.json"):
        self.package = package
        self.model: PhysicalModel = package.physical_model
        self.source_artifact = source_artifact

        self._notes: list[str] = []
        self._type_mappings: dict[PhysicalDataType, TargetDataTypeMapping] = {}

    # -- Public API --------------------------------------------------------

    def map(self) -> TargetModelPackage:
        """Map the physical model to the target platform.

        Returns a fully-mapped model ready for DDL generation, or raises
        TargetAdapterError if an unsupported feature is encountered.
        """
        self._build_type_mappings()

        tables = [self._map_table(table) for table in self.model.tables]

        target = TargetModel(
            database_name=self.model.database_name,
            summary=self._summary(tables),
            target_type=self.target_type(),
            capabilities=self.supported_capabilities(),
            identifier_rules=self.identifier_rules(),
            data_type_mappings=list(self._type_mappings.values()),
            tables=tables,
            mapping_notes=sorted(set(self._notes)),
        )

        logger.info(
            "Target model mapped: %s tables, %s columns, %s constraints, %s indexes",
            len(target.tables),
            sum(len(t.columns) for t in target.tables),
            len(target.all_constraints()),
            len(target.all_indexes()),
        )

        return TargetModelPackage(
            target_model=target,
            generated_from=self.source_artifact,
            generated_by=self.adapter_name(),
        )

    # -- Contract: platform identification --------------------------------

    @abstractmethod
    def target_type(self) -> str:
        """The target platform name: 'databricks', 'postgres', 'snowflake', etc."""
        pass

    @abstractmethod
    def adapter_name(self) -> str:
        """Human-readable adapter name, e.g. 'DatabricksTargetAdapter'."""
        pass

    # -- Contract: capabilities and rules ---------------------------------

    @abstractmethod
    def supported_capabilities(self) -> list[TargetCapability]:
        """List what this platform supports.

        If a physical model feature (constraint, index, etc.) is not in this
        list, map() will raise TargetAdapterError rather than attempting to
        generate it.
        """
        pass

    @abstractmethod
    def identifier_rules(self) -> TargetIdentifierRule:
        """Naming and quoting rules for this platform."""
        pass

    @abstractmethod
    def data_type_mappings(self) -> dict[PhysicalDataType, TargetDataTypeMapping]:
        """Map each generic physical type to the native target type(s).

        Keys are PhysicalDataType enum values. Values describe the mapping,
        including any parameter substitution. For example:

            PhysicalDataType.STRING: TargetDataTypeMapping(
                generic_type="STRING",
                target_type="STRING",
                parameters="{length}",
            )
        """
        pass

    # -- Implementation: type mapping
    # (private; uses the abstract methods above) --

    def _build_type_mappings(self) -> None:
        """Populate the type mapping dictionary."""
        self._type_mappings = self.data_type_mappings()
        if not all(isinstance(k, PhysicalDataType) for k in self._type_mappings.keys()):
            raise TargetAdapterError(
                f"{self.adapter_name()} data_type_mappings() keys must be PhysicalDataType enums"
            )

    def _map_data_type(self, column: PhysicalColumn) -> tuple[str, Optional[int], Optional[int], Optional[int]]:
        """Map a physical column to the target type, returning (type, length, precision, scale).

        Raises TargetAdapterError if the column's type is not mapped.
        """
        if column.data_type not in self._type_mappings:
            raise TargetAdapterError(
                f"{self.target_type()} does not support {column.data_type.value}. "
                f"Mapped types: {', '.join(t.value for t in self._type_mappings.keys())}"
            )

        mapping = self._type_mappings[column.data_type]
        target_type = mapping.target_type

        length = None
        precision = None
        scale = None

        if "{length}" in mapping.parameters and column.length is not None:
            length = column.length
        elif "{precision}" in mapping.parameters and column.precision is not None:
            precision = column.precision
            scale = column.scale

        return target_type, length, precision, scale

    # -- Implementation: table/column mapping (private) ----------

    def _map_table(self, table: PhysicalTable) -> TargetTable:
        """Map a physical table to the target."""
        mapped_table = TargetTable(
            name=table.name,
            source_table=table.name,
            logical_entity=table.logical_entity,
            subject_area=table.subject_area,
        )

        mapped_table.columns = [
            self._map_column(col) for col in table.columns
        ]

        for constraint in table.constraints:
            mapped_constraint = self._map_constraint(constraint, table)
            if mapped_constraint is not None:
                mapped_table.constraints.append(mapped_constraint)

        for index in table.indexes:
            mapped_index = self._map_index(index)
            if mapped_index is not None:
                mapped_table.indexes.append(mapped_index)

        if table.storage:
            mapped_table.partition_candidates = list(table.storage.partition_candidates)
            mapped_table.clustering_candidates = list(table.storage.clustering_candidates)
            mapped_table.storage_rationale = table.storage.rationale

        return mapped_table

    def _map_column(self, column: PhysicalColumn) -> TargetColumn:
        """Map a physical column to the target."""
        target_type, length, precision, scale = self._map_data_type(column)

        mapped = TargetColumn(
            name=column.name,
            target_type=target_type,
            length=length,
            precision=precision,
            scale=scale,
            nullable=column.nullable,
            default_value=self._map_default(column),
            is_primary_key=column.is_primary_key,
            is_foreign_key=column.is_foreign_key,
            is_unique=column.is_unique,
            source_column=column.name,
            physical_type=column.data_type.value,
        )

        return mapped

    def _map_default(self, column: PhysicalColumn) -> Optional[str]:
        """Map a physical default value to target syntax.

        Generic tokens like 'CURRENT_TIMESTAMP' are passed through unchanged;
        concrete implementations can override to produce target-specific syntax.
        """
        return column.default_value

    def _map_constraint(
        self, constraint: PhysicalConstraint, table: PhysicalTable
    ) -> Optional[TargetConstraint]:
        """Map a physical constraint to the target.

        Returns None if the constraint type is not supported; raises
        TargetAdapterError if it is unsupported but required.
        """
        if constraint.constraint_type == ConstraintType.PRIMARY_KEY:
            if TargetCapability.PRIMARY_KEYS not in self.supported_capabilities():
                raise TargetAdapterError(
                    f"{self.target_type()} does not support primary keys, "
                    f"but {table.name} requires one."
                )
            return TargetConstraint(
                name=constraint.name,
                constraint_type="PRIMARY_KEY",
                table=constraint.table,
                columns=list(constraint.columns),
                rationale=constraint.rationale,
                source_constraint=constraint.name,
            )

        if constraint.constraint_type == ConstraintType.FOREIGN_KEY:
            if TargetCapability.FOREIGN_KEYS not in self.supported_capabilities():
                self._notes.append(
                    f"Foreign key {constraint.name} omitted: {self.target_type()} does not support them."
                )
                return None

            return TargetConstraint(
                name=constraint.name,
                constraint_type="FOREIGN_KEY",
                table=constraint.table,
                columns=list(constraint.columns),
                referenced_table=constraint.referenced_table,
                referenced_columns=list(constraint.referenced_columns),
                rationale=constraint.rationale,
                source_constraint=constraint.name,
            )

        if constraint.constraint_type == ConstraintType.UNIQUE:
            if TargetCapability.UNIQUE_CONSTRAINTS not in self.supported_capabilities():
                self._notes.append(
                    f"Unique constraint {constraint.name} omitted: {self.target_type()} does not support them."
                )
                return None

            return TargetConstraint(
                name=constraint.name,
                constraint_type="UNIQUE",
                table=constraint.table,
                columns=list(constraint.columns),
                rationale=constraint.rationale,
                source_constraint=constraint.name,
            )

        if constraint.constraint_type == ConstraintType.CHECK:
            if TargetCapability.CHECK_CONSTRAINTS not in self.supported_capabilities():
                self._notes.append(
                    f"Check constraint {constraint.name} omitted: {self.target_type()} does not support them."
                )
                return None

            return TargetConstraint(
                name=constraint.name,
                constraint_type="CHECK",
                table=constraint.table,
                columns=list(constraint.columns),
                expression=constraint.expression,
                rationale=constraint.rationale,
                source_constraint=constraint.name,
            )

        raise TargetAdapterError(f"Unknown constraint type: {constraint.constraint_type}")

    def _map_index(self, index: PhysicalIndex) -> Optional[TargetIndex]:
        """Map a physical index recommendation to the target.

        Returns None if indexing is not supported; raises TargetAdapterError
        if the index type is unknown.
        """
        if TargetCapability.INDEXES not in self.supported_capabilities():
            return None

        return TargetIndex(
            name=index.name,
            table=index.table,
            columns=list(index.columns),
            is_unique=index.is_unique,
            purpose=index.purpose.value,
            rationale=index.rationale,
            source_index=index.name,
        )

    # -- Summary (private) -------------------------------------------------

    @staticmethod
    def _summary(tables: list[TargetTable]) -> str:
        columns = sum(len(t.columns) for t in tables)
        constraints = sum(len(t.constraints) for t in tables)
        indexes = sum(len(t.indexes) for t in tables)

        return (
            f"Target model for {len(tables)} tables and {columns} columns, carrying "
            f"{constraints} constraints and {indexes} indexes. All types are native to "
            f"the target platform; names follow the target platform's rules."
        )
