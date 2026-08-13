"""
Logical Model Writer

Writes `logical_model.json`, `logical_model.md` and `logical_model.html`.

Same shape as `ConceptualModelWriter`: JSON is the machine artifact,
Markdown is the reviewable text, HTML is the presentation report. Rendering
is a pure function of the model, so the same model always produces
byte-identical output.

No Mermaid. The diagram lives in the HTML report as hand-rendered SVG.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from migration.logical.html_renderer import render_logical_html
from migration.logical.models import (
    AttributeRole,
    LogicalEntity,
    LogicalModel,
    LogicalModelPackage,
)

logger = logging.getLogger(__name__)

_ROLE_LABEL = {
    AttributeRole.PRIMARY_KEY: "PK",
    AttributeRole.ALTERNATE_KEY: "AK",
    AttributeRole.FOREIGN_KEY: "FK",
    AttributeRole.DESCRIPTIVE: "",
}


class LogicalModelWriter:
    """Serializes and renders the logical model."""

    def write(
        self, package: LogicalModelPackage, run_directory: Path
    ) -> tuple[Path, Path, Path]:
        """Write all three artifacts. Returns (json, markdown, html)."""
        return (
            self.write_json(package, run_directory),
            self.write_markdown(package, run_directory),
            self.write_html(package, run_directory),
        )

    def write_json(self, package: LogicalModelPackage, run_directory: Path) -> Path:
        output_file = run_directory / "logical_model.json"
        with open(output_file, "w", encoding="utf-8") as fp:
            json.dump(package.model_dump(mode="json"), fp, indent=4, default=str)
        return output_file

    def write_markdown(self, package: LogicalModelPackage, run_directory: Path) -> Path:
        output_file = run_directory / "logical_model.md"
        with open(output_file, "w", encoding="utf-8") as fp:
            fp.write(self.render_markdown(package))
        return output_file

    def write_html(self, package: LogicalModelPackage, run_directory: Path) -> Path:
        output_file = run_directory / "logical_model.html"
        with open(output_file, "w", encoding="utf-8") as fp:
            fp.write(render_logical_html(package))
        return output_file

    # -- Rendering (pure) --------------------------------------------------

    def render_markdown(self, package: LogicalModelPackage) -> str:
        model = package.logical_model
        lines: list[str] = []

        lines += ["# Executive Summary", "", model.summary, ""]
        lines += self._provenance(package)
        lines += self._overview(model)
        lines += self._subject_areas(model)
        lines += self._entities(model)
        lines += self._relationships(model)
        lines += self._normalization(model)
        lines += self._list_section("Assumptions", model.assumptions)

        return "\n".join(lines).rstrip() + "\n"

    # -- Sections ----------------------------------------------------------

    @staticmethod
    def _provenance(package: LogicalModelPackage) -> list[str]:
        source = package.generated_from or "the conceptual model"
        return [
            f"> Derived deterministically from `{source}`. No AI was involved in this "
            "step: the conceptual model already carries the business judgement, and "
            "turning it into a normalized logical design is a set of transformation "
            "rules. Every design decision appears under Normalization or Assumptions.",
            "",
        ]

    @staticmethod
    def _overview(model: LogicalModel) -> list[str]:
        from migration.logical.models import EntityKind

        kinds = {kind: 0 for kind in EntityKind}
        for entity in model.entities:
            kinds[entity.kind] += 1

        attribute_count = sum(len(entity.attributes) for entity in model.entities)
        identifying = sum(1 for r in model.relationships if r.is_identifying)

        return [
            "# Logical Model Overview",
            "",
            f"- **Database:** {model.database_name}",
            f"- **Subject areas:** {len(model.subject_areas)}",
            f"- **Entities:** {len(model.entities)} "
            f"({kinds[EntityKind.FUNDAMENTAL]} fundamental, "
            f"{kinds[EntityKind.DEPENDENT]} dependent, "
            f"{kinds[EntityKind.ASSOCIATIVE]} associative)",
            f"- **Attributes:** {attribute_count}",
            f"- **Relationships:** {len(model.relationships)} ({identifying} identifying)",
            f"- **Normalization actions:** {len(model.normalization_actions)}",
            "",
        ]

    @staticmethod
    def _subject_areas(model: LogicalModel) -> list[str]:
        lines = ["# Subject Areas", ""]
        if not model.subject_areas:
            return lines + ["_None identified._", ""]

        for area in model.subject_areas:
            lines += [f"## {area.name}", "", area.description, ""]
            if area.entities:
                lines += [f"**Entities:** {', '.join(area.entities)}", ""]
        return lines

    def _entities(self, model: LogicalModel) -> list[str]:
        lines = ["# Logical Entities", ""]

        for entity in model.entities:
            lines += [f"## {entity.name}", "", entity.description, ""]
            lines += [
                f"- **Kind:** {entity.kind.value.title()}",
                f"- **Subject area:** {entity.subject_area or 'Unassigned'}",
            ]
            if entity.primary_key:
                surrogate = " _(surrogate)_" if entity.primary_key.is_surrogate else ""
                lines.append(
                    f"- **Primary key:** {', '.join(entity.primary_key.attributes)}{surrogate}"
                )
            if entity.alternate_keys:
                rendered = "; ".join(
                    ", ".join(key.attributes) for key in entity.alternate_keys
                )
                lines.append(f"- **Alternate keys:** {rendered}")
            if entity.source_tables:
                lines.append(f"- **Derived from:** `{'`, `'.join(entity.source_tables)}`")
            lines.append("")

            lines += self._attribute_table(entity)

        return lines

    @staticmethod
    def _attribute_table(entity: LogicalEntity) -> list[str]:
        if not entity.attributes:
            return ["_No attributes resolved._", ""]

        lines = [
            "| Attribute | Domain | Key | Optionality | References |",
            "|---|---|---|---|---|",
        ]
        for attribute in entity.attributes:
            lines.append(
                f"| {attribute.name} "
                f"| {attribute.data_type.value.replace('_', ' ').title()} "
                f"| {_ROLE_LABEL[attribute.role]} "
                f"| {attribute.optionality.value.title()} "
                f"| {attribute.references_entity or ''} |"
            )
        lines.append("")
        return lines

    @staticmethod
    def _relationships(model: LogicalModel) -> list[str]:
        lines = ["# Entity Relationships", ""]
        if not model.relationships:
            return lines + ["_No relationships identified._", ""]

        lines += [
            "| Parent | Child | Cardinality | Optionality | Identifying | Foreign key |",
            "|---|---|---|---|---|---|",
        ]
        for relationship in model.relationships:
            lines.append(
                f"| {relationship.parent_entity} "
                f"| {relationship.child_entity} "
                f"| {relationship.cardinality.value.replace('_', '-').lower()} "
                f"| {relationship.optionality.value.title()} "
                f"| {'Yes' if relationship.is_identifying else 'No'} "
                f"| {', '.join(relationship.foreign_key_attributes)} |"
            )
        lines.append("")
        return lines

    @staticmethod
    def _normalization(model: LogicalModel) -> list[str]:
        lines = ["# Normalization", ""]
        if not model.normalization_actions:
            return lines + ["_No normalization actions were required._", ""]

        lines.append(
            "Actions taken and checks performed while deriving the logical design. "
            "Checks that found nothing are listed too, so a compliant design is "
            "distinguishable from one that was never examined."
        )
        lines.append("")

        for action in model.normalization_actions:
            lines += [
                f"### {action.normal_form.value} — {action.entity}",
                "",
                f"**{action.action}.** {action.rationale}",
                "",
            ]
        return lines

    @staticmethod
    def _list_section(title: str, items: list[str]) -> list[str]:
        lines = [f"# {title}", ""]
        if not items:
            return lines + ["_None identified._", ""]
        lines += [f"{index}. {item}" for index, item in enumerate(items, start=1)]
        lines.append("")
        return lines
