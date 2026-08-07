"""
Business Context Builder

Condenses the three deterministic artifacts into a compact, structured
business context suitable for an LLM prompt.

This is deliberately NOT a metadata dump. A raw `metadata.json` for 19 tables
is 41 KB; for 10,000 tables it would be hundreds of megabytes and could never
fit in a context window. The context builder selects what matters and states
plainly what it left out.

Source independence
-------------------
The context carries no indication of which system produced the metadata. It
never emits `source_database_type`. A conceptual model is a statement about
the *business*, and the answer must not change because the same schema was
read from Oracle rather than a COBOL copybook.

Reusability
-----------
`BusinessContext` is the shared input for every future AI-assisted engine —
glossary, catalog, logical model, migration assessment. Only the prompt and
the response model change per engine. Nothing here is conceptual-model
specific.
"""

from __future__ import annotations

import json
import logging

from migration.canonical.models import DatabaseMetadata, TableMetadata
from migration.conceptual.models import (
    BusinessContext,
    ColumnContext,
    JunctionContext,
    TableContext,
)
from migration.profiler.models import DatabaseProfile
from migration.relationship.models import RelationshipGraph

logger = logging.getLogger(__name__)

BASE_TABLE_TYPE = "BASE TABLE"

DEFAULT_MAX_TABLES = 300
"""Cap on tables described in full. Beyond this the context lists names only
and records the omission. Chosen so a large context stays well inside a
1M-token window while leaving room for the response."""

DEFAULT_MAX_COLUMNS_PER_TABLE = 15
"""Cap on columns per table. Wide fact tables and COBOL-derived records can
carry 200+ fields, almost all of which are attributes rather than structure."""

CATEGORICAL_MAX_DISTINCT = 25
"""At or below this distinct count, a column is treated as a business
category (status, type, code) rather than free data. These are unusually
informative about business rules, so they are prioritized."""


class ContextBuilder:
    """Builds a compact business context from the deterministic artifacts."""

    def __init__(
        self,
        max_tables: int = DEFAULT_MAX_TABLES,
        max_columns_per_table: int = DEFAULT_MAX_COLUMNS_PER_TABLE,
    ):
        self.max_tables = max_tables
        self.max_columns_per_table = max_columns_per_table

    # -- Public API --------------------------------------------------------

    def build(
        self,
        metadata: DatabaseMetadata,
        profile: DatabaseProfile | None = None,
        relationships: RelationshipGraph | None = None,
    ) -> BusinessContext:
        """Condense the artifacts into a business context.

        `profile` and `relationships` are optional. Without them the context
        is thinner but still valid — the same degrade-don't-fail stance the
        profiler and relationship engine take.
        """
        self._index(profile, relationships)

        all_tables = [
            (schema.schema_name, table)
            for schema in metadata.schemas
            for table in schema.tables
        ]
        base_tables = [(s, t) for s, t in all_tables if t.table_type == BASE_TABLE_TYPE]

        ranked = sorted(base_tables, key=lambda pair: self._importance(pair), reverse=True)
        selected = ranked[: self.max_tables]
        omitted = ranked[self.max_tables :]

        # Restore a stable order for output; ranking was only for selection.
        selected.sort(key=lambda pair: (pair[0], pair[1].table_name))

        notes: list[str] = []
        if profile is None:
            notes.append("No data profile available - value statistics are absent.")
        if relationships is None:
            notes.append(
                "No relationship graph available - only declared foreign keys visible."
            )
        if omitted:
            notes.append(
                f"{len(omitted)} of {len(base_tables)} tables omitted from detail for size; "
                f"names listed under omitted_tables. Selection favoured tables with the most "
                f"relationships."
            )

        return BusinessContext(
            database_name=metadata.database_name,
            schemas=sorted({schema.schema_name for schema in metadata.schemas}),
            total_tables=len(all_tables),
            total_columns=sum(len(t.columns) for _, t in all_tables),
            total_relationships=len(relationships.relationships) if relationships else 0,
            tables=[self._table_context(s, t) for s, t in selected],
            omitted_tables=sorted(f"{s}.{t.table_name}" for s, t in omitted),
            relationships=self._relationship_lines(relationships),
            junction_tables=self._junction_contexts(relationships),
            self_referencing=self._self_referencing(relationships),
            dependency_order=relationships.dependency_order if relationships else [],
            orphan_tables=relationships.orphan_tables if relationships else [],
            notes=notes,
        )

    @staticmethod
    def to_prompt_json(context: BusinessContext) -> str:
        """Serialize the context for embedding in a prompt.

        Sorted keys and no null fields: deterministic bytes keep the prompt
        prefix cacheable across runs, and dropping nulls removes noise the
        model would otherwise have to read past.
        """
        return json.dumps(
            context.model_dump(mode="json", exclude_none=True),
            indent=2,
            sort_keys=True,
            default=str,
        )

    # -- Indexing ----------------------------------------------------------

    def _index(
        self, profile: DatabaseProfile | None, relationships: RelationshipGraph | None
    ) -> None:
        self._column_profiles: dict[tuple[str, str, str], object] = {}
        self._table_profiles: dict[tuple[str, str], object] = {}
        self._degrees: dict[str, int] = {}
        self._foreign_keys: dict[tuple[str, str], dict[str, str]] = {}

        if profile is not None:
            for schema_profile in profile.schemas:
                for table_profile in schema_profile.tables:
                    key = (schema_profile.schema_name, table_profile.table_name)
                    self._table_profiles[key] = table_profile
                    for column_profile in table_profile.columns:
                        self._column_profiles[(*key, column_profile.name)] = column_profile

        if relationships is not None:
            for node in relationships.nodes:
                qualified = f"{node.schema_name}.{node.table_name}"
                self._degrees[qualified] = (
                    node.inbound_relationship_count + node.outbound_relationship_count
                )
            for relationship in relationships.relationships:
                key = (relationship.source_schema, relationship.source_table)
                target = f"{relationship.target_schema}.{relationship.target_table}"
                for column in relationship.source_columns:
                    self._foreign_keys.setdefault(key, {})[column] = target

    def _importance(self, pair: tuple[str, TableMetadata]) -> tuple:
        """Rank tables so that, when the schema is too large to describe in
        full, the ones carrying the most business structure survive."""
        schema_name, table = pair
        qualified = f"{schema_name}.{table.table_name}"
        return (self._degrees.get(qualified, 0), len(table.columns))

    # -- Per-table context -------------------------------------------------

    def _table_context(self, schema_name: str, table: TableMetadata) -> TableContext:
        key = (schema_name, table.table_name)
        table_profile = self._table_profiles.get(key)
        foreign_keys = self._foreign_keys.get(key, {})

        primary_key = [c for pk in table.primary_keys for c in pk.columns]
        selected = self._select_columns(table, primary_key, foreign_keys)

        return TableContext(
            schema_name=schema_name,
            table_name=table.table_name,
            row_count=getattr(table_profile, "row_count", None),
            column_count=len(table.columns),
            primary_key=primary_key,
            columns=[
                self._column_context(schema_name, table, column, primary_key, foreign_keys)
                for column in selected
            ],
            omitted_column_count=len(table.columns) - len(selected),
        )

    def _select_columns(
        self, table: TableMetadata, primary_key: list[str], foreign_keys: dict[str, str]
    ) -> list:
        """Choose the most business-informative columns, in original order.

        Priority: keys first (they define identity and relationships), then
        low-cardinality categoricals and columns with a detected format
        (these reveal business rules), then remaining columns by position.
        """
        if len(table.columns) <= self.max_columns_per_table:
            return list(table.columns)

        keys = [c for c in table.columns if c.name in primary_key or c.name in foreign_keys]
        rest = [c for c in table.columns if c not in keys]

        interesting = []
        plain = []
        for column in rest:
            profile = self._find_column_profile(table, column.name)
            distinct = getattr(profile, "distinct_count", None) if profile else None
            pattern = getattr(profile, "detected_pattern", None) if profile else None
            if pattern or (distinct is not None and 0 < distinct <= CATEGORICAL_MAX_DISTINCT):
                interesting.append(column)
            else:
                plain.append(column)

        chosen = keys + interesting + plain
        chosen = chosen[: self.max_columns_per_table]
        # Restore declaration order so the model reads the table naturally.
        return [c for c in table.columns if c in chosen]

    def _find_column_profile(self, table: TableMetadata, column_name: str):
        for (schema_name, table_name, name), profile in self._column_profiles.items():
            if table_name == table.table_name and name == column_name:
                return profile
        return None

    def _column_context(
        self,
        schema_name: str,
        table: TableMetadata,
        column,
        primary_key: list[str],
        foreign_keys: dict[str, str],
    ) -> ColumnContext:
        profile = self._column_profiles.get((schema_name, table.table_name, column.name))

        if column.name in primary_key:
            role = "identifier"
        elif column.name in foreign_keys:
            role = "reference"
        elif profile is not None and getattr(profile, "detected_pattern", None):
            role = "formatted_value"
        elif (
            profile is not None
            and 0 < getattr(profile, "distinct_count", 0) <= CATEGORICAL_MAX_DISTINCT
        ):
            role = "category"
        else:
            role = "attribute"

        return ColumnContext(
            name=column.name,
            role=role,
            nullable=column.nullable,
            references=foreign_keys.get(column.name),
            distinct_count=getattr(profile, "distinct_count", None) if profile else None,
            null_percentage=getattr(profile, "null_percentage", None) if profile else None,
            detected_pattern=getattr(profile, "detected_pattern", None) if profile else None,
            sample_range=self._sample_range(profile),
        )

    @staticmethod
    def _sample_range(profile) -> str | None:
        if profile is None:
            return None
        minimum = getattr(profile, "min_value", None)
        maximum = getattr(profile, "max_value", None)
        if minimum is None or maximum is None:
            return None
        if minimum == maximum:
            return str(minimum)[:60]
        return f"{str(minimum)[:30]} .. {str(maximum)[:30]}"

    # -- Relationship context ----------------------------------------------

    @staticmethod
    def _relationship_lines(relationships: RelationshipGraph | None) -> list[str]:
        """One compact line per relationship. Prose is far cheaper in tokens
        than nested JSON and reads more naturally to a language model."""
        if relationships is None:
            return []

        lines = []
        for relationship in relationships.relationships:
            source = f"{relationship.source_schema}.{relationship.source_table}"
            target = f"{relationship.target_schema}.{relationship.target_table}"
            optional = " (optional)" if relationship.is_optional else ""
            confidence = (
                ""
                if relationship.confidence >= 1.0
                else f" [inferred, confidence {relationship.confidence}]"
            )
            lines.append(
                f"{source}.{'+'.join(relationship.source_columns)} -> "
                f"{target}.{'+'.join(relationship.target_columns)} "
                f"[{relationship.cardinality.value}]{optional}{confidence}"
            )
        return lines

    @staticmethod
    def _junction_contexts(relationships: RelationshipGraph | None) -> list[JunctionContext]:
        if relationships is None:
            return []
        return [
            JunctionContext(
                table_name=f"{junction.schema_name}.{junction.table_name}",
                connects=junction.connected_tables,
                is_pure_link=junction.is_pure,
                extra_attributes=junction.payload_columns,
            )
            for junction in relationships.junction_tables
        ]

    @staticmethod
    def _self_referencing(relationships: RelationshipGraph | None) -> list[str]:
        if relationships is None:
            return []
        return sorted(
            f"{r.source_schema}.{r.source_table}.{'+'.join(r.source_columns)}"
            for r in relationships.relationships
            if r.is_self_referencing
        )
