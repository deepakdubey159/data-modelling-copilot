"""
Relationship Discovery Engine

Consumes the canonical metadata model and (optionally) the data profile, and
produces a relationship graph.

This engine contains no SQL, no connector logic and no source-specific
branching — exactly like `metadata/builder.py` and `profiler/engine.py`. It is
a pure function of its inputs::

    (DatabaseMetadata, DatabaseProfile | None) -> RelationshipPackage

Consequences worth stating, because they are load-bearing:

- It never touches a database, so it cannot be slow because of data volume.
  It reads catalog metadata and pre-computed aggregate statistics only, which
  is what lets it scale to 10,000+ tables and billions of rows.
- It is fully testable without a database, and without even a fake connector.
- It works identically whether the metadata came from Oracle, Postgres, a
  COBOL copybook or a Parquet catalog.

`profile` is optional. Without it the engine still produces the complete
declared graph, junction detection, structural cardinality and dependency
order — it simply has less evidence for inference. Degrading rather than
failing matches how the profiler handles an uncomputable duplicate count.

Five phases, in order:

    0. Index      build lookups once
    1. Declared   foreign key constraints  -> relationships (confidence 1.0)
    2. Inferred   naming rules + profile evidence -> scored relationships
    3. Derived    junction tables -> logical many-to-many
    4. Graph      nodes, depths, dependency order, cycles, orphans
"""

from __future__ import annotations

import logging
from collections import defaultdict
from itertools import combinations

from migration.canonical.models import ColumnMetadata, DatabaseMetadata, TableMetadata
from migration.profiler.models import ColumnProfile, DatabaseProfile, TableProfile
from migration.relationship import graph as graph_utils
from migration.relationship import rules
from migration.relationship.models import (
    Cardinality,
    CardinalitySource,
    DiscoveryMethod,
    GraphNode,
    JunctionTable,
    Relationship,
    RelationshipGraph,
    RelationshipPackage,
    RelationshipSummary,
    RelationshipType,
)

logger = logging.getLogger(__name__)

PHYSICAL_METHODS = frozenset(
    {
        DiscoveryMethod.DECLARED,
        DiscoveryMethod.INFERRED_NAMING,
        DiscoveryMethod.INFERRED_PROFILE,
        DiscoveryMethod.INFERRED_VERIFIED,
    }
)
"""Methods that represent a real column-level reference. Only these become
graph edges. DERIVED_JUNCTION relationships are logical annotations for the
conceptual model; treating them as edges would invent ordering constraints
between two parents that have no direct dependency on each other."""

TableKey = tuple[str, str]


class RelationshipEngine:
    """Discovers relationships from canonical metadata and profile statistics."""

    def __init__(self, metadata: DatabaseMetadata, profile: DatabaseProfile | None = None):
        self.metadata = metadata
        self.profile = profile

        self._tables: dict[TableKey, TableMetadata] = {}
        self._pk_columns: dict[TableKey, list[str]] = {}
        self._columns: dict[tuple[str, str, str], ColumnMetadata] = {}
        self._table_profiles: dict[TableKey, TableProfile] = {}
        self._column_profiles: dict[tuple[str, str, str], ColumnProfile] = {}
        self._pk_name_index: dict[str, list[TableKey]] = defaultdict(list)
        self._table_name_index: dict[tuple[str, str], TableKey] = {}

    # -- Public API --------------------------------------------------------

    def discover(self) -> RelationshipPackage:
        """Run all phases and return the complete relationship package."""
        self._build_indexes()

        declared = self._extract_declared()
        inferred = self._infer_relationships(declared)
        physical = declared + inferred

        junctions = self._detect_junctions(physical)
        derived = self._derive_many_to_many(junctions, physical)

        relationships = sorted(physical + derived, key=_sort_key)
        graph = self._build_graph(relationships, junctions)

        logger.info(
            "Relationship discovery complete: %s relationships across %s tables "
            "(%s declared, %s inferred, %s derived)",
            graph.summary.total_relationships,
            graph.summary.tables_analyzed,
            graph.summary.declared_count,
            graph.summary.inferred_count,
            graph.summary.derived_count,
        )
        return RelationshipPackage(relationships=graph)

    # -- Phase 0: indexes --------------------------------------------------

    def _build_indexes(self) -> None:
        for schema in self.metadata.schemas:
            for table in schema.tables:
                key = (schema.schema_name, table.table_name)
                self._tables[key] = table

                primary_key: list[str] = []
                for pk in table.primary_keys:
                    primary_key.extend(pk.columns)
                self._pk_columns[key] = primary_key

                for column in table.columns:
                    self._columns[(key[0], key[1], column.name)] = column

                if table.table_type != rules.BASE_TABLE_TYPE:
                    continue

                self._table_name_index[
                    (schema.schema_name, rules.normalize_identifier(table.table_name))
                ] = key

                # Only single-column primary keys are inference targets. A
                # naming rule cannot responsibly guess which part of a
                # composite key a lone column refers to.
                if len(primary_key) == 1:
                    self._pk_name_index[rules.normalize_identifier(primary_key[0])].append(key)

        if self.profile is None:
            return

        for schema_profile in self.profile.schemas:
            for table_profile in schema_profile.tables:
                key = (schema_profile.schema_name, table_profile.table_name)
                self._table_profiles[key] = table_profile
                for column_profile in table_profile.columns:
                    self._column_profiles[(key[0], key[1], column_profile.name)] = column_profile

    # -- Phase 1: declared foreign keys ------------------------------------

    def _extract_declared(self) -> list[Relationship]:
        """Read foreign key constraints straight from the canonical metadata.

        `ForeignKeyMetadata` is per *column*, not per constraint, so a
        composite foreign key arrives as several rows sharing one constraint
        name. Grouping by constraint name reassembles them into one
        relationship.

        Column pairs are de-duplicated. Some catalog queries can emit the same
        pair more than once for a composite key; de-duplicating here keeps a
        connector-side quirk from becoming phantom relationships in the
        artifact.
        """
        relationships: list[Relationship] = []

        for schema in self.metadata.schemas:
            for table in schema.tables:
                grouped: dict[str, list] = defaultdict(list)
                for foreign_key in table.foreign_keys:
                    grouped[foreign_key.constraint_name].append(foreign_key)

                for constraint_name in sorted(grouped):
                    members = grouped[constraint_name]

                    seen: set[tuple[str, str]] = set()
                    source_columns: list[str] = []
                    target_columns: list[str] = []
                    for member in members:
                        pair = (member.column, member.referenced_column)
                        if pair in seen:
                            continue
                        seen.add(pair)
                        source_columns.append(member.column)
                        target_columns.append(member.referenced_column)

                    if not source_columns:
                        continue

                    first = members[0]
                    evidence = [f"declared foreign key constraint '{constraint_name}'"]
                    if len(source_columns) > 1:
                        evidence.append(
                            f"composite key of {len(source_columns)} columns, "
                            f"reassembled from per-column catalog rows"
                        )

                    relationships.append(
                        self._make_relationship(
                            source_schema=schema.schema_name,
                            source_table=table.table_name,
                            source_columns=source_columns,
                            target_schema=first.referenced_schema,
                            target_table=first.referenced_table,
                            target_columns=target_columns,
                            discovery_method=DiscoveryMethod.DECLARED,
                            confidence=1.0,
                            evidence=evidence,
                            constraint_name=constraint_name,
                        )
                    )

        return relationships

    # -- Phase 2: inference ------------------------------------------------

    def _infer_relationships(self, declared: list[Relationship]) -> list[Relationship]:
        """Propose relationships from naming conventions, then score them
        against profile statistics."""
        covered: dict[TableKey, set[str]] = defaultdict(set)
        for relationship in declared:
            covered[(relationship.source_schema, relationship.source_table)].update(
                relationship.source_columns
            )

        inferred: list[Relationship] = []

        for schema in self.metadata.schemas:
            for table in schema.tables:
                if table.table_type != rules.BASE_TABLE_TYPE:
                    continue

                source_key = (schema.schema_name, table.table_name)
                for column in table.columns:
                    if column.name in covered[source_key]:
                        # A declared constraint always wins over a guess.
                        continue

                    for target_key, rule_id, base_score in self._naming_candidates(
                        source_key, column
                    ):
                        relationship = self._score_candidate(
                            source_key, column, target_key, rule_id, base_score
                        )
                        if relationship is not None:
                            inferred.append(relationship)

        return inferred

    def _naming_candidates(
        self, source_key: TableKey, column: ColumnMetadata
    ) -> list[tuple[TableKey, str, float]]:
        """Propose target tables for one column, best rule per target.

        Inference stays within a schema. A `customer_id` in one schema
        matching a `customer` table in another is far more likely to be
        coincidence than a relationship; declared cross-schema foreign keys
        are of course still honoured, because they are facts.
        """
        schema_name = source_key[0]
        best: dict[TableKey, tuple[str, float]] = {}

        def offer(target_key: TableKey, rule_id: str, score: float) -> None:
            existing = best.get(target_key)
            if existing is None or score > existing[1]:
                best[target_key] = (rule_id, score)

        normalized_column = rules.normalize_identifier(column.name)

        # N1 - the column name is another table's primary key name.
        for target_key in self._pk_name_index.get(normalized_column, []):
            if target_key == source_key or target_key[0] != schema_name:
                continue
            offer(target_key, "N1", rules.BASE_SCORE_EXACT_PK_NAME)

        # N2 / N3 - strip an id suffix and resolve the entity to a table.
        for entity, rule_id, base_score in rules.entity_candidates(column.name):
            for variant in sorted(rules.name_variants(entity)):
                target_key = self._table_name_index.get((schema_name, variant))
                if target_key is None or target_key == source_key:
                    continue
                offer(target_key, rule_id, base_score)

        return sorted(
            (target_key, rule_id, score) for target_key, (rule_id, score) in best.items()
        )

    def _score_candidate(
        self,
        source_key: TableKey,
        column: ColumnMetadata,
        target_key: TableKey,
        rule_id: str,
        base_score: float,
    ) -> Relationship | None:
        """Apply gates and profile evidence. Returns None if rejected."""
        target_primary_key = self._pk_columns.get(target_key, [])
        if len(target_primary_key) != 1:
            return None

        target_column_name = target_primary_key[0]
        target_column = self._columns.get((target_key[0], target_key[1], target_column_name))
        if target_column is None:
            return None

        if not rules.types_compatible(column.data_type, target_column.data_type):
            return None

        score = base_score
        evidence = [
            f"naming rule {rule_id}: '{column.name}' resolves to "
            f"'{rules.qualified_name(*target_key)}' (+{base_score:.2f})"
        ]

        score += rules.BONUS_TARGET_IS_SINGLE_COLUMN_PK
        evidence.append(
            f"target column '{target_column_name}' is a single-column primary key "
            f"(+{rules.BONUS_TARGET_IS_SINGLE_COLUMN_PK:.2f})"
        )

        if column.data_type.strip().lower() == target_column.data_type.strip().lower():
            score += rules.BONUS_EXACT_TYPE_MATCH
            evidence.append(
                f"exact data type match: {column.data_type} "
                f"(+{rules.BONUS_EXACT_TYPE_MATCH:.2f})"
            )

        adjustment, profile_evidence, rejected = self._profile_evidence(
            source_key, column, target_key, target_column
        )
        evidence.extend(profile_evidence)
        if rejected:
            return None
        score += adjustment

        used_profile = bool(profile_evidence) and self.profile is not None
        score = max(0.0, min(1.0, score))

        if score < rules.MIN_INFERENCE_CONFIDENCE:
            return None

        evidence.append("no declared foreign key constraint exists for this column")

        return self._make_relationship(
            source_schema=source_key[0],
            source_table=source_key[1],
            source_columns=[column.name],
            target_schema=target_key[0],
            target_table=target_key[1],
            target_columns=[target_column_name],
            discovery_method=(
                DiscoveryMethod.INFERRED_PROFILE if used_profile else DiscoveryMethod.INFERRED_NAMING
            ),
            confidence=round(score, 2),
            evidence=evidence,
        )

    def _profile_evidence(
        self,
        source_key: TableKey,
        column: ColumnMetadata,
        target_key: TableKey,
        target_column: ColumnMetadata,
    ) -> tuple[float, list[str], bool]:
        """Score a candidate against profile statistics.

        Returns ``(adjustment, evidence, rejected)``. `rejected` is True only
        for a logical impossibility, never for weak evidence.
        """
        if self.profile is None:
            return 0.0, ["no profile available - scored on naming and types alone"], False

        source_profile = self._column_profiles.get((source_key[0], source_key[1], column.name))
        target_profile = self._column_profiles.get(
            (target_key[0], target_key[1], target_column.name)
        )
        if source_profile is None or target_profile is None:
            return 0.0, ["no profile statistics for this column pair"], False

        adjustment = 0.0
        evidence: list[str] = []

        source_table_profile = self._table_profiles.get(source_key)
        target_table_profile = self._table_profiles.get(target_key)
        source_rows = source_table_profile.row_count if source_table_profile else 0
        target_rows = target_table_profile.row_count if target_table_profile else 0

        if source_rows == 0 or target_rows == 0:
            return (
                rules.PENALTY_NO_DATA,
                [f"no data to corroborate: source rows={source_rows}, target rows={target_rows} "
                 f"({rules.PENALTY_NO_DATA:+.2f})"],
                False,
            )

        # Distinct-value inclusion. A child cannot reference more distinct
        # parents than exist. Violating this is a logical impossibility, which
        # makes it the one place aggregate statistics give a sound negative.
        if source_profile.distinct_count > 0 and target_profile.distinct_count > 0:
            if source_profile.distinct_count > target_profile.distinct_count:
                return (
                    0.0,
                    [
                        f"rejected: distinct value inclusion violated - source has "
                        f"{source_profile.distinct_count} distinct values but target key has "
                        f"only {target_profile.distinct_count}"
                    ],
                    True,
                )
            adjustment += rules.BONUS_DISTINCT_INCLUSION
            evidence.append(
                f"distinct value inclusion holds: {source_profile.distinct_count} <= "
                f"{target_profile.distinct_count} (+{rules.BONUS_DISTINCT_INCLUSION:.2f})"
            )

        range_adjustment, range_evidence = self._range_evidence(
            column, target_column, source_profile, target_profile
        )
        adjustment += range_adjustment
        evidence.extend(range_evidence)

        if (
            source_profile.detected_pattern
            and source_profile.detected_pattern == target_profile.detected_pattern
        ):
            adjustment += rules.BONUS_PATTERN_AGREEMENT
            evidence.append(
                f"format pattern agreement: both look like "
                f"'{source_profile.detected_pattern}' (+{rules.BONUS_PATTERN_AGREEMENT:.2f})"
            )

        return adjustment, evidence, False

    @staticmethod
    def _range_evidence(
        column: ColumnMetadata,
        target_column: ColumnMetadata,
        source_profile: ColumnProfile,
        target_profile: ColumnProfile,
    ) -> tuple[float, list[str]]:
        """Compare min/max ranges, numerically where possible.

        `min_value` / `max_value` are captured as text by the profiler, so a
        direct string comparison is *lexicographic*: "9" sorts after "10".
        Comparing numeric columns that way produces false containment
        violations on any table crossing a digit boundary. Numeric columns are
        therefore parsed back to numbers, and the signal is skipped entirely
        when parsing fails rather than falling back to a comparison known to
        be wrong.
        """
        if not rules.is_numeric_type(column.data_type) or not rules.is_numeric_type(
            target_column.data_type
        ):
            return 0.0, []

        values = _parse_floats(
            source_profile.min_value,
            source_profile.max_value,
            target_profile.min_value,
            target_profile.max_value,
        )
        if values is None:
            return 0.0, ["range containment skipped: extremes are not numerically comparable"]

        source_min, source_max, target_min, target_max = values
        if source_min >= target_min and source_max <= target_max:
            return (
                rules.BONUS_RANGE_CONTAINMENT,
                [
                    f"numeric range containment holds: [{_pretty(source_min)}, "
                    f"{_pretty(source_max)}] within [{_pretty(target_min)}, "
                    f"{_pretty(target_max)}] (+{rules.BONUS_RANGE_CONTAINMENT:.2f})"
                ],
            )

        return (
            rules.PENALTY_RANGE_VIOLATION,
            [
                f"numeric range containment violated: [{_pretty(source_min)}, "
                f"{_pretty(source_max)}] escapes [{_pretty(target_min)}, "
                f"{_pretty(target_max)}] ({rules.PENALTY_RANGE_VIOLATION:+.2f})"
            ],
        )

    # -- Phase 3: junction tables ------------------------------------------

    def _detect_junctions(self, relationships: list[Relationship]) -> list[JunctionTable]:
        """A junction (bridge) table's primary key is made up entirely of
        foreign key columns pointing at two or more distinct tables.

        The "two or more distinct tables" clause is what distinguishes a real
        bridge table from a weak entity: a table keyed on (order_id,
        line_number) has a composite primary key too, but `line_number` is not
        a foreign key, so it is a dependent entity rather than a junction.
        """
        by_source: dict[TableKey, list[Relationship]] = defaultdict(list)
        for relationship in relationships:
            if relationship.discovery_method in PHYSICAL_METHODS:
                by_source[(relationship.source_schema, relationship.source_table)].append(
                    relationship
                )

        junctions: list[JunctionTable] = []

        for key in sorted(self._tables):
            table = self._tables[key]
            if table.table_type != rules.BASE_TABLE_TYPE:
                continue

            primary_key = self._pk_columns.get(key, [])
            if len(primary_key) < 2:
                continue

            column_to_target: dict[str, str] = {}
            for relationship in by_source.get(key, []):
                for column_name in relationship.source_columns:
                    column_to_target[column_name] = rules.qualified_name(
                        relationship.target_schema, relationship.target_table
                    )

            if not all(column in column_to_target for column in primary_key):
                continue

            connected = sorted({column_to_target[column] for column in primary_key})
            if len(connected) < 2:
                continue

            payload = [
                column.name for column in table.columns if column.name not in set(primary_key)
            ]
            junctions.append(
                JunctionTable(
                    schema_name=key[0],
                    table_name=key[1],
                    connected_tables=connected,
                    key_columns=list(primary_key),
                    payload_columns=payload,
                    is_pure=not payload,
                )
            )

        return junctions

    def _derive_many_to_many(
        self, junctions: list[JunctionTable], relationships: list[Relationship]
    ) -> list[Relationship]:
        """Turn each junction into logical many-to-many relationships between
        the tables it connects."""
        by_source: dict[TableKey, list[Relationship]] = defaultdict(list)
        for relationship in relationships:
            if relationship.discovery_method in PHYSICAL_METHODS:
                by_source[(relationship.source_schema, relationship.source_table)].append(
                    relationship
                )

        derived: list[Relationship] = []

        for junction in junctions:
            key = (junction.schema_name, junction.table_name)
            key_columns = set(junction.key_columns)

            # Qualified parent name -> (schema, table, referenced columns).
            parents: dict[str, tuple[str, str, list[str]]] = {}
            for relationship in by_source.get(key, []):
                if not key_columns.intersection(relationship.source_columns):
                    continue
                qualified = rules.qualified_name(
                    relationship.target_schema, relationship.target_table
                )
                parents.setdefault(
                    qualified,
                    (
                        relationship.target_schema,
                        relationship.target_table,
                        list(relationship.target_columns),
                    ),
                )

            for left, right in combinations(sorted(parents), 2):
                left_schema, left_table, left_columns = parents[left]
                right_schema, right_table, right_columns = parents[right]

                evidence = [
                    f"derived from junction table "
                    f"'{rules.qualified_name(junction.schema_name, junction.table_name)}'",
                    f"junction primary key ({', '.join(junction.key_columns)}) is composed "
                    f"entirely of foreign keys",
                ]
                if not junction.is_pure:
                    evidence.append(
                        f"junction carries {len(junction.payload_columns)} payload column(s) - "
                        f"an associative entity, not a pure link table"
                    )

                derived.append(
                    self._make_relationship(
                        source_schema=left_schema,
                        source_table=left_table,
                        source_columns=left_columns,
                        target_schema=right_schema,
                        target_table=right_table,
                        target_columns=right_columns,
                        discovery_method=DiscoveryMethod.DERIVED_JUNCTION,
                        confidence=1.0,
                        evidence=evidence,
                        cardinality=Cardinality.MANY_TO_MANY,
                        relationship_type=RelationshipType.MANY_TO_MANY_LOGICAL,
                        separator="<->",
                    )
                )

        return derived

    # -- Phase 4: graph assembly -------------------------------------------

    def _build_graph(
        self, relationships: list[Relationship], junctions: list[JunctionTable]
    ) -> RelationshipGraph:
        node_names = sorted(rules.qualified_name(*key) for key in self._tables)
        edges = [
            (
                rules.qualified_name(relationship.source_schema, relationship.source_table),
                rules.qualified_name(relationship.target_schema, relationship.target_table),
            )
            for relationship in relationships
            if relationship.discovery_method in PHYSICAL_METHODS
        ]

        order, depths, unresolved = graph_utils.build_dependency_order(node_names, edges)
        cycles = graph_utils.find_cycles(node_names, edges)
        inbound, outbound = graph_utils.compute_degrees(node_names, edges)

        # Tables caught in a cycle cannot be ordered, but they must still
        # appear: a load order missing tables is worse than one flagged as
        # needing manual intervention.
        dependency_order = order + unresolved

        nodes: list[GraphNode] = []
        orphan_tables: list[str] = []
        for key in sorted(self._tables):
            qualified = rules.qualified_name(*key)
            is_orphan = inbound[qualified] == 0 and outbound[qualified] == 0
            if is_orphan:
                orphan_tables.append(qualified)
            nodes.append(
                GraphNode(
                    schema_name=key[0],
                    table_name=key[1],
                    table_type=self._tables[key].table_type,
                    is_orphan=is_orphan,
                    inbound_relationship_count=inbound[qualified],
                    outbound_relationship_count=outbound[qualified],
                    depth=depths.get(qualified, 0),
                )
            )

        summary = RelationshipSummary(
            total_relationships=len(relationships),
            declared_count=_count(relationships, DiscoveryMethod.DECLARED),
            inferred_count=_count(
                relationships,
                DiscoveryMethod.INFERRED_NAMING,
                DiscoveryMethod.INFERRED_PROFILE,
                DiscoveryMethod.INFERRED_VERIFIED,
            ),
            derived_count=_count(relationships, DiscoveryMethod.DERIVED_JUNCTION),
            junction_table_count=len(junctions),
            self_referencing_count=sum(1 for r in relationships if r.is_self_referencing),
            orphan_table_count=len(orphan_tables),
            cycle_count=len(cycles),
            max_dependency_depth=max(depths.values()) if depths else 0,
            tables_analyzed=len(self._tables),
            columns_analyzed=sum(len(table.columns) for table in self._tables.values()),
        )

        return RelationshipGraph(
            database_name=self.metadata.database_name,
            nodes=nodes,
            relationships=relationships,
            junction_tables=junctions,
            dependency_order=dependency_order,
            cycles=cycles,
            orphan_tables=orphan_tables,
            summary=summary,
        )

    # -- Shared construction -----------------------------------------------

    def _make_relationship(
        self,
        *,
        source_schema: str,
        source_table: str,
        source_columns: list[str],
        target_schema: str,
        target_table: str,
        target_columns: list[str],
        discovery_method: DiscoveryMethod,
        confidence: float,
        evidence: list[str],
        constraint_name: str | None = None,
        cardinality: Cardinality | None = None,
        relationship_type: RelationshipType | None = None,
        separator: str = "->",
    ) -> Relationship:
        source_key = (source_schema, source_table)
        is_self_referencing = source_key == (target_schema, target_table)

        primary_key = self._pk_columns.get(source_key, [])
        is_identifying = bool(primary_key) and set(source_columns).issubset(set(primary_key))

        is_optional = any(
            column.nullable
            for column in (
                self._columns.get((source_schema, source_table, name)) for name in source_columns
            )
            if column is not None
        )

        if relationship_type is None:
            if is_self_referencing:
                relationship_type = RelationshipType.SELF_REFERENCING
            elif is_identifying:
                relationship_type = RelationshipType.IDENTIFYING
            else:
                relationship_type = RelationshipType.NON_IDENTIFYING

        if cardinality is not None:
            cardinality_source = CardinalitySource.STRUCTURAL
        else:
            cardinality, cardinality_source, cardinality_evidence = self._classify_cardinality(
                source_key, source_columns, primary_key
            )
            evidence = evidence + cardinality_evidence

        return Relationship(
            id=rules.relationship_id(
                source_schema,
                source_table,
                source_columns,
                target_schema,
                target_table,
                target_columns,
                separator=separator,
            ),
            constraint_name=constraint_name,
            source_schema=source_schema,
            source_table=source_table,
            source_columns=source_columns,
            target_schema=target_schema,
            target_table=target_table,
            target_columns=target_columns,
            relationship_type=relationship_type,
            cardinality=cardinality,
            cardinality_source=cardinality_source,
            discovery_method=discovery_method,
            confidence=confidence,
            confidence_band=rules.confidence_band(confidence),
            is_self_referencing=is_self_referencing,
            is_optional=is_optional,
            is_identifying=is_identifying,
            evidence=evidence,
        )

    def _classify_cardinality(
        self, source_key: TableKey, source_columns: list[str], primary_key: list[str]
    ) -> tuple[Cardinality, CardinalitySource, list[str]]:
        """Structural evidence first; observed statistics only as a fallback.

        Structure is a guarantee the database enforces. Observation describes
        today's data and can change tomorrow, so it never overrides structure
        and is always recorded as OBSERVED so consumers can tell the two apart.
        """
        if primary_key and set(source_columns) == set(primary_key):
            return (
                Cardinality.ONE_TO_ONE,
                CardinalitySource.STRUCTURAL,
                [
                    f"source columns are the complete primary key "
                    f"({', '.join(primary_key)}) - at most one row per parent"
                ],
            )

        if primary_key and set(source_columns).issubset(set(primary_key)):
            return (
                Cardinality.MANY_TO_ONE,
                CardinalitySource.STRUCTURAL,
                [
                    f"source columns are a proper subset of the primary key "
                    f"({', '.join(primary_key)})"
                ],
            )

        observed = self._observed_one_to_one(source_key, source_columns)
        if observed is not None:
            return Cardinality.ONE_TO_ONE, CardinalitySource.OBSERVED, [observed]

        return Cardinality.MANY_TO_ONE, CardinalitySource.STRUCTURAL, []

    def _observed_one_to_one(self, source_key: TableKey, source_columns: list[str]) -> str | None:
        """Return evidence text if the data currently looks one-to-one.

        Requires a meaningful number of rows. Ten rows with ten distinct
        values is not evidence of uniqueness, and treating it as such would
        manufacture false one-to-one claims from small development datasets.
        """
        if self.profile is None or len(source_columns) != 1:
            return None

        table_profile = self._table_profiles.get(source_key)
        column_profile = self._column_profiles.get(
            (source_key[0], source_key[1], source_columns[0])
        )
        if table_profile is None or column_profile is None:
            return None

        row_count = table_profile.row_count
        if row_count < rules.MIN_ROWS_FOR_OBSERVED_CARDINALITY:
            return None

        if column_profile.distinct_count == row_count and column_profile.null_count == 0:
            return (
                f"observed one-to-one: {column_profile.distinct_count} distinct values across "
                f"{row_count} rows with no nulls (current data only, not enforced)"
            )
        return None


# ---------------------------------------------------------
# Helpers
# ---------------------------------------------------------


def _sort_key(relationship: Relationship) -> tuple:
    """Total ordering, so two runs over identical input produce identical
    output and the artifact can be diffed across runs."""
    return (
        relationship.source_schema,
        relationship.source_table,
        tuple(relationship.source_columns),
        relationship.target_schema,
        relationship.target_table,
        tuple(relationship.target_columns),
        relationship.discovery_method.value,
    )


def _count(relationships: list[Relationship], *methods: DiscoveryMethod) -> int:
    wanted = set(methods)
    return sum(1 for relationship in relationships if relationship.discovery_method in wanted)


def _parse_floats(*values) -> tuple[float, ...] | None:
    """Parse every value to float, or return None if any cannot be parsed."""
    parsed: list[float] = []
    for value in values:
        if value is None:
            return None
        try:
            parsed.append(float(str(value).strip()))
        except (TypeError, ValueError):
            return None
    return tuple(parsed)


def _pretty(value: float) -> str:
    return str(int(value)) if value == int(value) else str(value)
