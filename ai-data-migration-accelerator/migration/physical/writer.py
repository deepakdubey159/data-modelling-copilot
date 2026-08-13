"""
Physical Model Writer

Writes `physical_model.json`, `physical_model.md` and `physical_model.html`.

Same shape as the conceptual and logical writers. Rendering is a pure
function of the model, so the same model always produces byte-identical
output.

Business descriptions are not repeated here. They live in the conceptual and
logical models, and every table carries `logical_entity` as the pointer back.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from migration.physical.html_renderer import render_physical_html
from migration.physical.models import (
    ConstraintType,
    PhysicalModel,
    PhysicalModelPackage,
    PhysicalTable,
)

logger = logging.getLogger(__name__)


class PhysicalModelWriter:
    """Serializes and renders the physical model."""

    def write(
        self, package: PhysicalModelPackage, run_directory: Path
    ) -> tuple[Path, Path, Path]:
        """Write all three artifacts. Returns (json, markdown, html)."""
        return (
            self.write_json(package, run_directory),
            self.write_markdown(package, run_directory),
            self.write_html(package, run_directory),
        )

    def write_json(self, package: PhysicalModelPackage, run_directory: Path) -> Path:
        output_file = run_directory / "physical_model.json"
        with open(output_file, "w", encoding="utf-8") as fp:
            json.dump(package.model_dump(mode="json"), fp, indent=4, default=str)
        return output_file

    def write_markdown(self, package: PhysicalModelPackage, run_directory: Path) -> Path:
        output_file = run_directory / "physical_model.md"
        with open(output_file, "w", encoding="utf-8") as fp:
            fp.write(self.render_markdown(package))
        return output_file

    def write_html(self, package: PhysicalModelPackage, run_directory: Path) -> Path:
        output_file = run_directory / "physical_model.html"
        with open(output_file, "w", encoding="utf-8") as fp:
            fp.write(render_physical_html(package))
        return output_file

    # -- Rendering (pure) --------------------------------------------------

    def render_markdown(self, package: PhysicalModelPackage) -> str:
        model = package.physical_model
        lines: list[str] = []

        lines += ["# Executive Summary", "", model.summary, ""]
        lines += self._provenance(package)
        lines += self._architecture_overview(model)
        lines += self._tables(model)
        lines += self._column_definitions(model)
        lines += self._constraints(model)
        lines += self._indexes(model)
        lines += self._storage(model)

        return "\n".join(lines).rstrip() + "\n"

    # -- Sections ----------------------------------------------------------

    @staticmethod
    def _provenance(package: PhysicalModelPackage) -> list[str]:
        source = package.generated_from or "the logical model"
        return [
            f"> Derived deterministically from `{source}`. Business descriptions are "
            "not repeated here — each table names the logical entity it came from. "
            "Types, lengths and precision are generic: no vendor syntax appears until "
            "DDL generation.",
            "",
        ]

    @staticmethod
    def _architecture_overview(model: PhysicalModel) -> list[str]:
        from migration.physical.models import TableClassification

        counts = {c: 0 for c in TableClassification}
        for table in model.tables:
            counts[table.classification] += 1

        lines = [
            "# Physical Architecture Overview",
            "",
            f"- **Database:** {model.database_name}",
            f"- **Tables:** {len(model.tables)} "
            f"({counts[TableClassification.LOOKUP]} lookup, "
            f"{counts[TableClassification.MASTER]} master, "
            f"{counts[TableClassification.TRANSACTION]} transaction)",
            f"- **Columns:** {sum(len(t.columns) for t in model.tables)}",
            f"- **Constraints:** {len(model.all_constraints())}",
            f"- **Recommended indexes:** {len(model.all_indexes())}",
            f"- **Naming:** {model.naming_convention.style}, "
            f"max {model.naming_convention.max_identifier_length} characters",
            "",
        ]

        if model.naming_convention.notes:
            lines += ["**Naming notes**", ""]
            lines += [f"- {note}" for note in model.naming_convention.notes]
            lines.append("")

        if model.design_notes:
            lines += ["**Design notes**", ""]
            lines += [f"- {note}" for note in model.design_notes]
            lines.append("")

        return lines

    @staticmethod
    def _tables(model: PhysicalModel) -> list[str]:
        lines = ["# Physical Tables", ""]
        if not model.tables:
            return lines + ["_No tables._", ""]

        lines += [
            "| Table | Classification | Size | Growth | Columns | Logical entity |",
            "|---|---|---|---|---|---|",
        ]
        for table in model.tables:
            lines.append(
                f"| `{table.name}` "
                f"| {table.classification.value.title()} "
                f"| {table.size_category.value.replace('_', ' ').title()} "
                f"| {table.growth_rate.value.title()} "
                f"| {len(table.columns)} "
                f"| {table.logical_entity} |"
            )
        lines.append("")
        return lines

    def _column_definitions(self, model: PhysicalModel) -> list[str]:
        lines = ["# Column Definitions", ""]
        for table in model.tables:
            lines += [f"## `{table.name}`", ""]
            lines += self._column_table(table)
        return lines

    @staticmethod
    def _column_table(table: PhysicalTable) -> list[str]:
        if not table.columns:
            return ["_No columns._", ""]

        lines = [
            "| Column | Type | Null | Key | Default |",
            "|---|---|---|---|---|",
        ]
        for column in table.columns:
            markers = []
            if column.is_primary_key:
                markers.append("PK")
            if column.is_foreign_key:
                markers.append("FK")
            if column.is_unique:
                markers.append("AK")

            lines.append(
                f"| `{column.name}` "
                f"| {column.type_signature()} "
                f"| {'NULL' if column.nullable else 'NOT NULL'} "
                f"| {' '.join(markers)} "
                f"| {column.default_value or ''} |"
            )
        lines.append("")
        return lines

    @staticmethod
    def _constraints(model: PhysicalModel) -> list[str]:
        lines = ["# Constraints", ""]
        constraints = model.all_constraints()
        if not constraints:
            return lines + ["_No constraints._", ""]

        lines += [
            "| Constraint | Type | Table | Columns | References |",
            "|---|---|---|---|---|",
        ]
        for constraint in constraints:
            reference = ""
            if constraint.constraint_type == ConstraintType.FOREIGN_KEY:
                reference = (
                    f"`{constraint.referenced_table}`"
                    f"({', '.join(constraint.referenced_columns)})"
                )
            elif constraint.expression:
                reference = f"`{constraint.expression}`"

            lines.append(
                f"| `{constraint.name}` "
                f"| {constraint.constraint_type.value.replace('_', ' ').title()} "
                f"| `{constraint.table}` "
                f"| {', '.join(constraint.columns)} "
                f"| {reference} |"
            )
        lines.append("")
        return lines

    @staticmethod
    def _indexes(model: PhysicalModel) -> list[str]:
        lines = ["# Index Recommendations", ""]
        indexes = model.all_indexes()
        if not indexes:
            return lines + ["_No indexes recommended._", ""]

        lines += [
            "| Index | Table | Columns | Unique | Purpose |",
            "|---|---|---|---|---|",
        ]
        for index in indexes:
            lines.append(
                f"| `{index.name}` "
                f"| `{index.table}` "
                f"| {', '.join(index.columns)} "
                f"| {'Yes' if index.is_unique else 'No'} "
                f"| {index.purpose.value.replace('_', ' ').title()} |"
            )
        lines.append("")
        return lines

    @staticmethod
    def _storage(model: PhysicalModel) -> list[str]:
        lines = ["# Storage Recommendations", ""]
        recommendations = [t.storage for t in model.tables if t.storage]
        if not recommendations:
            return lines + ["_No storage recommendations._", ""]

        for table in model.tables:
            storage = table.storage
            if storage is None:
                continue
            partition = ", ".join(storage.partition_candidates) or "None"
            clustering = ", ".join(storage.clustering_candidates) or "None"
            lines += [
                f"### `{table.name}`",
                "",
                f"- **Partition candidates:** {partition}",
                f"- **Clustering candidates:** {clustering}",
                f"- {storage.rationale}",
                "",
            ]
        return lines
