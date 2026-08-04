"""Tests for migration.relationship.graph.

These exercise the graph algorithms in isolation. The module has no domain
knowledge, so the fixtures are plain node labels and edge tuples — no
metadata, no profiles, no database.
"""

from __future__ import annotations

from migration.relationship.graph import (
    build_dependency_order,
    compute_degrees,
    find_cycles,
)


def test_linear_chain_orders_parents_first():
    nodes = ["a", "b", "c"]
    edges = [("c", "b"), ("b", "a")]  # c depends on b, b depends on a

    order, depths, unresolved = build_dependency_order(nodes, edges)

    assert order == ["a", "b", "c"]
    assert depths == {"a": 0, "b": 1, "c": 2}
    assert unresolved == []


def test_independent_nodes_are_sorted_by_name():
    nodes = ["zebra", "apple", "mango"]

    order, depths, unresolved = build_dependency_order(nodes, [])

    assert order == ["apple", "mango", "zebra"]
    assert set(depths.values()) == {0}
    assert unresolved == []


def test_depth_uses_deepest_parent():
    # d depends on both b (depth 1) and c (depth 2), so d must be depth 3.
    nodes = ["a", "b", "c", "d"]
    edges = [("b", "a"), ("c", "b"), ("d", "b"), ("d", "c")]

    order, depths, _ = build_dependency_order(nodes, edges)

    assert depths["d"] == 3
    assert order.index("c") < order.index("d")


def test_self_loop_is_not_a_cycle_and_does_not_block_ordering():
    nodes = ["employee"]
    edges = [("employee", "employee")]

    order, _, unresolved = build_dependency_order(nodes, edges)

    assert order == ["employee"]
    assert unresolved == []
    assert find_cycles(nodes, edges) == []


def test_true_cycle_is_detected():
    nodes = ["department", "employee"]
    edges = [("department", "employee"), ("employee", "department")]

    cycles = find_cycles(nodes, edges)

    assert cycles == [["department", "employee"]]


def test_cycle_members_are_unresolved_but_never_dropped():
    nodes = ["a", "b", "c"]
    edges = [("b", "c"), ("c", "b")]  # b and c are mutually dependent

    order, _, unresolved = build_dependency_order(nodes, edges)

    assert order == ["a"]
    assert unresolved == ["b", "c"]
    # Callers append unresolved so every node is still accounted for.
    assert sorted(order + unresolved) == nodes


def test_longer_cycle_is_detected_as_one_component():
    nodes = ["a", "b", "c"]
    edges = [("a", "b"), ("b", "c"), ("c", "a")]

    assert find_cycles(nodes, edges) == [["a", "b", "c"]]


def test_two_separate_cycles_are_reported_separately():
    nodes = ["a", "b", "x", "y"]
    edges = [("a", "b"), ("b", "a"), ("x", "y"), ("y", "x")]

    assert find_cycles(nodes, edges) == [["a", "b"], ["x", "y"]]


def test_order_is_grouped_by_depth_then_name():
    # `zulu` has no dependencies (depth 0) and must precede `alpha`, which
    # depends on `beta` (depth 1) — depth wins over alphabetical order.
    nodes = ["alpha", "beta", "zulu"]
    edges = [("alpha", "beta")]

    order, depths, _ = build_dependency_order(nodes, edges)

    assert order == ["beta", "zulu", "alpha"]
    assert depths == {"beta": 0, "zulu": 0, "alpha": 1}


def test_depth_grouping_never_places_a_child_before_its_parent():
    nodes = ["a", "b", "c", "d", "e", "f"]
    edges = [("b", "a"), ("c", "b"), ("d", "c"), ("e", "a"), ("f", "e")]

    order, _, _ = build_dependency_order(nodes, edges)

    for child, parent in edges:
        assert order.index(parent) < order.index(child)


def test_degrees_count_inbound_and_outbound():
    nodes = ["child", "parent", "lonely"]
    edges = [("child", "parent")]

    inbound, outbound = compute_degrees(nodes, edges)

    assert outbound["child"] == 1
    assert inbound["child"] == 0
    assert inbound["parent"] == 1
    assert outbound["parent"] == 0
    assert inbound["lonely"] == 0 and outbound["lonely"] == 0


def test_self_loop_counts_toward_degrees():
    # A self-referencing table has a real relationship and must not later be
    # classified as an orphan.
    nodes = ["employee"]
    inbound, outbound = compute_degrees(nodes, [("employee", "employee")])

    assert inbound["employee"] == 1
    assert outbound["employee"] == 1


def test_edges_to_unknown_nodes_are_ignored():
    nodes = ["a"]
    edges = [("a", "somewhere_else")]

    order, depths, unresolved = build_dependency_order(nodes, edges)

    assert order == ["a"]
    assert depths["a"] == 0
    assert unresolved == []


def test_ordering_is_deterministic_across_runs():
    nodes = ["a", "b", "c", "d", "e"]
    edges = [("b", "a"), ("c", "a"), ("d", "b"), ("e", "b")]

    first = build_dependency_order(nodes, edges)
    second = build_dependency_order(list(reversed(nodes)), list(reversed(edges)))

    assert first[0] == second[0]
