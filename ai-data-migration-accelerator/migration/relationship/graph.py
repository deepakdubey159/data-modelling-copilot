"""
Graph Algorithms

Deliberately free of domain knowledge. These functions operate on opaque node
labels and `(child, parent)` edge tuples and know nothing about foreign keys,
schemas or databases. That keeps them trivially testable and reusable by the
migration planner later, which needs the same ordering logic for a different
kind of dependency.

Every function is deterministic: ties are broken by sorting node labels, so
repeated runs over identical input produce identical output.
"""

from __future__ import annotations

import heapq
from collections import defaultdict

Edge = tuple[str, str]
"""``(child, parent)`` — the child depends on the parent."""


def _adjacency(nodes: list[str], edges: list[Edge]) -> tuple[dict, dict]:
    """Build parent/child maps, ignoring self-loops and unknown endpoints."""
    known = set(nodes)
    parents: dict[str, set[str]] = defaultdict(set)
    children: dict[str, set[str]] = defaultdict(set)

    for child, parent in edges:
        if child == parent:
            # A self-loop constrains row order within one table, not the
            # order of tables relative to each other. Excluding it here is
            # what stops a self-referencing table being reported as a cycle.
            continue
        if child not in known or parent not in known:
            continue
        parents[child].add(parent)
        children[parent].add(child)

    return parents, children


def build_dependency_order(
    nodes: list[str], edges: list[Edge]
) -> tuple[list[str], dict[str, int], list[str]]:
    """Topologically order `nodes` so every parent precedes its children.

    Returns ``(order, depths, unresolved)``:

    - ``order`` — parents first, grouped by depth then name. Safe as a
      load/creation sequence, and everything sharing a depth can be processed
      in parallel.
    - ``depths`` — 0 for a node with no dependencies, otherwise one more than
      its deepest parent.
    - ``unresolved`` — nodes that could not be ordered because they take part
      in (or sit downstream of) a cycle. Sorted; never silently dropped.

    Kahn's algorithm with a heap, so ties resolve by name rather than by
    dictionary iteration order. The final sort by ``(depth, name)`` preserves
    validity: a child's depth is always strictly greater than every parent's,
    so no child can sort ahead of a parent.
    """
    parents, children = _adjacency(nodes, edges)

    remaining = {node: len(parents[node]) for node in nodes}
    depths = {node: 0 for node in nodes}

    ready = [node for node in nodes if remaining[node] == 0]
    heapq.heapify(ready)

    order: list[str] = []
    while ready:
        node = heapq.heappop(ready)
        order.append(node)
        for child in sorted(children[node]):
            depths[child] = max(depths[child], depths[node] + 1)
            remaining[child] -= 1
            if remaining[child] == 0:
                heapq.heappush(ready, child)

    ordered = set(order)
    unresolved = sorted(node for node in nodes if node not in ordered)

    order.sort(key=lambda node: (depths[node], node))
    return order, depths, unresolved


def find_cycles(nodes: list[str], edges: list[Edge]) -> list[list[str]]:
    """Return groups of mutually dependent nodes.

    Tarjan's strongly connected components, iterative so that a deep
    dependency chain cannot exhaust the Python recursion limit — relevant at
    the 10,000-table scale this platform targets.

    Self-loops are excluded (see `_adjacency`), so a single node is never
    reported. Only components of two or more nodes are returned.
    """
    _, children = _adjacency(nodes, edges)

    # Traverse child -> parent so a reported component reads in dependency
    # direction. Rebuild from `children` to keep a single source of truth.
    successors: dict[str, list[str]] = defaultdict(list)
    for parent, child_set in children.items():
        for child in child_set:
            successors[child].append(parent)
    for ordered in successors.values():
        ordered.sort()

    index: dict[str, int] = {}
    lowlink: dict[str, int] = {}
    on_stack: dict[str, bool] = {}
    stack: list[str] = []
    components: list[list[str]] = []
    counter = 0

    for start in sorted(nodes):
        if start in index:
            continue

        work: list[tuple[str, int]] = [(start, 0)]
        while work:
            node, next_child = work[-1]

            if next_child == 0:
                index[node] = counter
                lowlink[node] = counter
                counter += 1
                stack.append(node)
                on_stack[node] = True

            descended = False
            neighbours = successors.get(node, [])
            for position in range(next_child, len(neighbours)):
                neighbour = neighbours[position]
                if neighbour not in index:
                    work[-1] = (node, position + 1)
                    work.append((neighbour, 0))
                    descended = True
                    break
                if on_stack.get(neighbour):
                    lowlink[node] = min(lowlink[node], index[neighbour])

            if descended:
                continue

            if lowlink[node] == index[node]:
                component = []
                while True:
                    member = stack.pop()
                    on_stack[member] = False
                    component.append(member)
                    if member == node:
                        break
                if len(component) > 1:
                    components.append(sorted(component))

            work.pop()
            if work:
                parent_node = work[-1][0]
                lowlink[parent_node] = min(lowlink[parent_node], lowlink[node])

    return sorted(components)


def compute_degrees(
    nodes: list[str], edges: list[Edge]
) -> tuple[dict[str, int], dict[str, int]]:
    """Count edges into and out of each node.

    Unlike the ordering functions, self-loops **are** counted here: a
    self-referencing table genuinely has a relationship and must not be
    reported as an orphan.
    """
    inbound = {node: 0 for node in nodes}
    outbound = {node: 0 for node in nodes}

    for child, parent in edges:
        if child in outbound:
            outbound[child] += 1
        if parent in inbound:
            inbound[parent] += 1

    return inbound, outbound
