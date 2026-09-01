"""
Tests for migration.planner.dependency_analyzer.SchemaDependencyAnalyzer.

Everything here is deterministic graph analysis over canonical metadata -
no LLM, no network, no connector. Metadata is built directly via the same
fixture helpers the relationship engine tests use, so this is source-agnostic
by construction (it never touches PostgreSQL- or DB2-specific shapes).
"""

from __future__ import annotations

from migration.canonical.models import DatabaseMetadata, MetadataPackage, SchemaMetadata
from migration.planner.dependency_analyzer import SchemaDependencyAnalyzer
from tests.relationship_fixtures import column, foreign_key, table


def _package(schemas: list[SchemaMetadata]) -> MetadataPackage:
    return MetadataPackage(
        metadata=DatabaseMetadata(
            database_name="testdb",
            source_database_type="postgres",
            schemas=schemas,
        )
    )


class TestSingleSchemaOrdering:
    """A simple parent -> child chain within one schema."""

    def test_root_table_has_no_dependencies(self):
        customer = table("customer", [column("customer_id", is_primary_key=True)], primary_key=["customer_id"])
        orders = table(
            "orders",
            [column("order_id", is_primary_key=True), column("customer_id")],
            primary_key=["order_id"],
            foreign_keys=[foreign_key("orders_customer_fk", "customer_id", "customer", "customer_id")],
        )
        pkg = _package([SchemaMetadata(schema_name="app", tables=[customer, orders])])

        plan = SchemaDependencyAnalyzer(pkg).analyze()

        assert "app.customer" in plan.root_tables
        assert "app.orders" not in plan.root_tables

    def test_recommended_order_places_parent_before_child(self):
        customer = table("customer", [column("customer_id", is_primary_key=True)], primary_key=["customer_id"])
        orders = table(
            "orders",
            [column("order_id", is_primary_key=True), column("customer_id")],
            primary_key=["order_id"],
            foreign_keys=[foreign_key("orders_customer_fk", "customer_id", "customer", "customer_id")],
        )
        pkg = _package([SchemaMetadata(schema_name="app", tables=[customer, orders])])

        plan = SchemaDependencyAnalyzer(pkg).analyze()

        assert plan.recommended_table_order.index("app.customer") < plan.recommended_table_order.index("app.orders")
        assert plan.has_cycles is False

    def test_most_depended_on_table_is_identified(self):
        """A table referenced by two children should rank first by in-degree."""
        customer = table("customer", [column("customer_id", is_primary_key=True)], primary_key=["customer_id"])
        orders = table(
            "orders",
            [column("order_id", is_primary_key=True), column("customer_id")],
            primary_key=["order_id"],
            foreign_keys=[foreign_key("orders_customer_fk", "customer_id", "customer", "customer_id")],
        )
        invoices = table(
            "invoices",
            [column("invoice_id", is_primary_key=True), column("customer_id")],
            primary_key=["invoice_id"],
            foreign_keys=[foreign_key("invoices_customer_fk", "customer_id", "customer", "customer_id")],
        )
        pkg = _package([SchemaMetadata(schema_name="app", tables=[customer, orders, invoices])])

        plan = SchemaDependencyAnalyzer(pkg).analyze()

        assert plan.most_depended_on_tables[0] == "app.customer"

    def test_self_referencing_fk_is_not_a_dependency_edge(self):
        """An employee.manager_id -> employee.employee_id FK must not make
        the table depend on itself (that would make it un-orderable)."""
        employee = table(
            "employee",
            [column("employee_id", is_primary_key=True), column("manager_id")],
            primary_key=["employee_id"],
            foreign_keys=[foreign_key("employee_manager_fk", "manager_id", "employee", "employee_id")],
        )
        pkg = _package([SchemaMetadata(schema_name="app", tables=[employee])])

        plan = SchemaDependencyAnalyzer(pkg).analyze()

        assert "app.employee" in plan.root_tables
        assert plan.recommended_table_order == ["app.employee"]
        assert plan.has_cycles is False


class TestCrossSchemaDependencies:
    """FKs that cross schema boundaries (e.g. silver -> bronze)."""

    def test_cross_schema_fk_is_reported(self):
        bronze_customer = table("customer", [column("customer_id", is_primary_key=True)], primary_key=["customer_id"])
        silver_orders = table(
            "orders",
            [column("order_id", is_primary_key=True), column("customer_id")],
            primary_key=["order_id"],
            foreign_keys=[
                foreign_key(
                    "orders_customer_fk", "customer_id", "customer", "customer_id",
                    referenced_schema="bronze",
                )
            ],
        )
        pkg = _package(
            [
                SchemaMetadata(schema_name="bronze", tables=[bronze_customer]),
                SchemaMetadata(schema_name="silver", tables=[silver_orders]),
            ]
        )

        plan = SchemaDependencyAnalyzer(pkg).analyze()

        assert len(plan.cross_schema_foreign_keys) == 1
        assert plan.cross_schema_foreign_keys[0].table == "silver.orders"
        assert plan.cross_schema_foreign_keys[0].depends_on == "bronze.customer"

    def test_root_schema_and_recommended_schema_order(self):
        bronze_customer = table("customer", [column("customer_id", is_primary_key=True)], primary_key=["customer_id"])
        silver_orders = table(
            "orders",
            [column("order_id", is_primary_key=True), column("customer_id")],
            primary_key=["order_id"],
            foreign_keys=[
                foreign_key(
                    "orders_customer_fk", "customer_id", "customer", "customer_id",
                    referenced_schema="bronze",
                )
            ],
        )
        pkg = _package(
            [
                SchemaMetadata(schema_name="bronze", tables=[bronze_customer]),
                SchemaMetadata(schema_name="silver", tables=[silver_orders]),
            ]
        )

        plan = SchemaDependencyAnalyzer(pkg).analyze()

        assert plan.root_schemas == ["bronze"]
        assert plan.recommended_schema_order == ["bronze", "silver"]


class TestCircularDependencies:
    """A -> B -> A must be reported, never silently ordered."""

    def test_circular_table_dependency_is_reported_not_ordered(self):
        a = table(
            "a",
            [column("id", is_primary_key=True), column("b_id")],
            primary_key=["id"],
            foreign_keys=[foreign_key("a_b_fk", "b_id", "b", "id")],
        )
        b = table(
            "b",
            [column("id", is_primary_key=True), column("a_id")],
            primary_key=["id"],
            foreign_keys=[foreign_key("b_a_fk", "a_id", "a", "id")],
        )
        pkg = _package([SchemaMetadata(schema_name="app", tables=[a, b])])

        plan = SchemaDependencyAnalyzer(pkg).analyze()

        assert plan.has_cycles is True
        assert plan.recommended_table_order == []
        assert len(plan.table_cycles) == 1
        assert set(plan.table_cycles[0].tables) >= {"app.a", "app.b"}

    def test_circular_schema_dependency_is_reported(self):
        a_table = table(
            "a",
            [column("id", is_primary_key=True), column("b_id")],
            primary_key=["id"],
            foreign_keys=[foreign_key("a_b_fk", "b_id", "b", "id", referenced_schema="schema_b")],
        )
        b_table = table(
            "b",
            [column("id", is_primary_key=True), column("a_id")],
            primary_key=["id"],
            foreign_keys=[foreign_key("b_a_fk", "a_id", "a", "id", referenced_schema="schema_a")],
        )
        pkg = _package(
            [
                SchemaMetadata(schema_name="schema_a", tables=[a_table]),
                SchemaMetadata(schema_name="schema_b", tables=[b_table]),
            ]
        )

        plan = SchemaDependencyAnalyzer(pkg).analyze()

        assert plan.has_cycles is True
        assert plan.recommended_schema_order == []
        assert len(plan.schema_cycles) == 1


class TestDeterminism:
    """The same metadata must always produce the same plan."""

    def test_analysis_is_deterministic_across_runs(self):
        customer = table("customer", [column("customer_id", is_primary_key=True)], primary_key=["customer_id"])
        orders = table(
            "orders",
            [column("order_id", is_primary_key=True), column("customer_id")],
            primary_key=["order_id"],
            foreign_keys=[foreign_key("orders_customer_fk", "customer_id", "customer", "customer_id")],
        )
        pkg = _package([SchemaMetadata(schema_name="app", tables=[customer, orders])])

        plan1 = SchemaDependencyAnalyzer(pkg).analyze()
        plan2 = SchemaDependencyAnalyzer(pkg).analyze()

        assert plan1.recommended_table_order == plan2.recommended_table_order
        assert plan1.root_tables == plan2.root_tables
