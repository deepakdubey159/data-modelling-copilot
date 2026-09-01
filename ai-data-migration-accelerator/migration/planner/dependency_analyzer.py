"""
Schema Dependency Analyzer.

Builds a deterministic table/schema dependency graph from canonical FK
metadata and computes a recommended migration order from it. Every
computation here is a graph algorithm (topological sort via Kahn's
algorithm, cycle detection via DFS) - nothing is inferred by an LLM, so the
same metadata always produces the same plan.

Input: `MetadataPackage` (the same canonical metadata every connector
already produces via `MetadataBuilder`). Source-agnostic by construction -
it reads `foreign_keys` off `TableMetadata`, a field every connector fills
identically, so PostgreSQL and DB2 metadata are analyzed the same way.
"""

from __future__ import annotations

from collections import defaultdict, deque

from migration.canonical.models import MetadataPackage
from migration.planner.models import (
    DependencyCycle,
    MigrationPlan,
    SchemaDependency,
    TableDependency,
)


class SchemaDependencyAnalyzer:
    """Computes a deterministic migration order from FK metadata."""

    def __init__(self, metadata: MetadataPackage):
        self.metadata = metadata.metadata

    def analyze(self) -> MigrationPlan:
        table_deps = self._table_dependencies()
        schema_deps = self._schema_dependencies(table_deps)

        all_tables = self._all_qualified_table_names()

        table_order, table_cycles = self._topological_sort(all_tables, table_deps)
        schema_names = [s.schema_name for s in self.metadata.schemas]
        schema_order, schema_cycles = self._topological_sort(
            schema_names,
            [(d.schema_name, d.depends_on) for d in schema_deps],
        )

        root_tables = sorted(
            t for t in all_tables if not any(a == t for a, _ in table_deps)
        )
        root_schemas = sorted(
            s for s in schema_names if not any(a == s for a, _ in [(d.schema_name, d.depends_on) for d in schema_deps])
        )

        in_degree: dict[str, int] = defaultdict(int)
        for _child, parent in table_deps:
            in_degree[parent] += 1
        most_depended_on = sorted(
            in_degree.keys(), key=lambda t: (-in_degree[t], t)
        )

        cross_schema = [
            TableDependency(
                table=dep.table,
                depends_on=dep.depends_on,
                constraint_name=dep.constraint_name,
                cross_schema=True,
            )
            for dep in self._table_dependency_models(table_deps)
            if dep.cross_schema
        ]

        explanation = self._build_explanation(
            root_schemas=root_schemas,
            most_depended_on=most_depended_on,
            schema_cycles=schema_cycles,
            cross_schema_count=len(cross_schema),
        )

        return MigrationPlan(
            schemas_analyzed=schema_names,
            table_dependencies=self._table_dependency_models(table_deps),
            schema_dependencies=schema_deps,
            root_tables=root_tables,
            root_schemas=root_schemas,
            most_depended_on_tables=most_depended_on[:10],
            cross_schema_foreign_keys=cross_schema,
            table_cycles=[DependencyCycle(tables=c) for c in table_cycles],
            schema_cycles=[DependencyCycle(tables=c) for c in schema_cycles],
            recommended_table_order=table_order,
            recommended_schema_order=schema_order,
            has_cycles=bool(table_cycles or schema_cycles),
            explanation=explanation,
        )

    # -- Graph construction --------------------------------------------

    def _all_qualified_table_names(self) -> list[str]:
        names = []
        for schema in self.metadata.schemas:
            for table in schema.tables:
                names.append(f"{schema.schema_name}.{table.table_name}")
        return names

    def _table_dependencies(self) -> list[tuple[str, str]]:
        """Return (child_qualified_name, parent_qualified_name) edges."""
        edges: list[tuple[str, str]] = []
        for schema in self.metadata.schemas:
            for table in schema.tables:
                child = f"{schema.schema_name}.{table.table_name}"
                for fk in table.foreign_keys:
                    parent = f"{fk.referenced_schema}.{fk.referenced_table}"
                    if parent == child:
                        # Self-referencing FK is not a migration-order
                        # dependency between two different tables.
                        continue
                    edges.append((child, parent))
        return edges

    def _table_dependency_models(
        self, edges: list[tuple[str, str]]
    ) -> list[TableDependency]:
        models = []
        constraint_lookup: dict[tuple[str, str], str] = {}
        for schema in self.metadata.schemas:
            for table in schema.tables:
                child = f"{schema.schema_name}.{table.table_name}"
                for fk in table.foreign_keys:
                    parent = f"{fk.referenced_schema}.{fk.referenced_table}"
                    constraint_lookup[(child, parent)] = fk.constraint_name

        for child, parent in edges:
            models.append(
                TableDependency(
                    table=child,
                    depends_on=parent,
                    constraint_name=constraint_lookup.get((child, parent), "unknown"),
                    cross_schema=child.split(".")[0] != parent.split(".")[0],
                )
            )
        return models

    def _schema_dependencies(
        self, table_edges: list[tuple[str, str]]
    ) -> list[SchemaDependency]:
        """Collapse table-level edges to distinct schema-level edges."""
        seen: set[tuple[str, str]] = set()
        deps: list[SchemaDependency] = []
        for child, parent in table_edges:
            child_schema = child.split(".")[0]
            parent_schema = parent.split(".")[0]
            if child_schema == parent_schema:
                continue
            key = (child_schema, parent_schema)
            if key in seen:
                continue
            seen.add(key)
            deps.append(SchemaDependency(schema_name=child_schema, depends_on=parent_schema))
        return deps

    # -- Algorithms -------------------------------------------------------

    def _topological_sort(
        self, nodes: list[str], edges: list[tuple[str, str]]
    ) -> tuple[list[str], list[list[str]]]:
        """Kahn's algorithm: parents before children.

        `edges` are (child, parent) pairs, i.e. child depends on parent.
        Returns (order, cycles). `order` is empty when a cycle exists -
        a partial order that hides a broken dependency is worse than none.
        Ties are broken alphabetically so the result is fully deterministic.
        """
        node_set = list(dict.fromkeys(nodes))  # de-dup, preserve order
        children_of: dict[str, set[str]] = defaultdict(set)  # parent -> children
        in_degree: dict[str, int] = {n: 0 for n in node_set}

        for child, parent in edges:
            if parent not in in_degree or child not in in_degree:
                continue
            if child in children_of[parent]:
                continue
            children_of[parent].add(child)
            in_degree[child] += 1

        ready = deque(sorted(n for n in node_set if in_degree[n] == 0))
        order: list[str] = []

        while ready:
            node = ready.popleft()
            order.append(node)
            for child in sorted(children_of[node]):
                in_degree[child] -= 1
                if in_degree[child] == 0:
                    ready.append(child)
            ready = deque(sorted(ready))

        if len(order) == len(node_set):
            return order, []

        # Nodes left with in_degree > 0 are part of (or depend on) a cycle.
        remaining = {n for n in node_set if n not in order}
        cycles = self._find_cycles(remaining, edges)
        return [], cycles

    def _find_cycles(
        self, nodes: set[str], edges: list[tuple[str, str]]
    ) -> list[list[str]]:
        """DFS-based cycle detection restricted to the given node subset."""
        adjacency: dict[str, list[str]] = defaultdict(list)
        for child, parent in edges:
            if child in nodes and parent in nodes:
                adjacency[child].append(parent)

        WHITE, GRAY, BLACK = 0, 1, 2
        color = {n: WHITE for n in nodes}
        cycles: list[list[str]] = []
        seen_cycle_sets: set[frozenset] = set()

        def dfs(node: str, stack: list[str]) -> None:
            color[node] = GRAY
            stack.append(node)
            for neighbor in sorted(adjacency[node]):
                if color[neighbor] == WHITE:
                    dfs(neighbor, stack)
                elif color[neighbor] == GRAY:
                    idx = stack.index(neighbor)
                    cycle = stack[idx:] + [neighbor]
                    key = frozenset(cycle)
                    if key not in seen_cycle_sets:
                        seen_cycle_sets.add(key)
                        cycles.append(cycle)
            stack.pop()
            color[node] = BLACK

        for node in sorted(nodes):
            if color[node] == WHITE:
                dfs(node, [])

        return cycles

    def _build_explanation(
        self,
        root_schemas: list[str],
        most_depended_on: list[str],
        schema_cycles: list[list[str]],
        cross_schema_count: int,
    ) -> list[str]:
        lines: list[str] = []
        if root_schemas:
            lines.append(
                f"Schemas with no outgoing cross-schema foreign keys "
                f"({', '.join(root_schemas)}) have no prerequisites and are "
                f"placed first."
            )
        if most_depended_on:
            top = most_depended_on[:3]
            lines.append(
                f"Tables referenced by the most foreign keys ({', '.join(top)}) "
                f"are prioritized early since other tables cannot be created "
                f"before them."
            )
        if cross_schema_count:
            lines.append(
                f"{cross_schema_count} cross-schema foreign key(s) were found; "
                f"the recommended schema order accounts for them."
            )
        if schema_cycles:
            lines.append(
                f"{len(schema_cycles)} circular schema dependency(ies) were "
                f"detected and could not be linearly ordered - see "
                f"schema_cycles for the tables involved."
            )
        return lines
