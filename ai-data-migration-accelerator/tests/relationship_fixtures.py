"""Shared builders for relationship engine tests.

The relationship engine consumes in-memory models only, so — unlike the
profiler tests — these tests need no database and no fake connector at all.
Everything is constructed directly.

Kept independent of the sample `bronze` database so the tests never depend on
one particular schema's contents.
"""

from __future__ import annotations

from migration.canonical.models import (
    ColumnMetadata,
    DatabaseMetadata,
    ForeignKeyMetadata,
    PrimaryKeyMetadata,
    SchemaMetadata,
    TableMetadata,
)
from migration.profiler.models import (
    ColumnProfile,
    DatabaseProfile,
    SchemaProfile,
    TableProfile,
)

SCHEMA = "app"


def column(
    name: str,
    data_type: str = "integer",
    *,
    nullable: bool = True,
    position: int = 1,
    is_primary_key: bool = False,
) -> ColumnMetadata:
    return ColumnMetadata(
        name=name,
        data_type=data_type,
        nullable=nullable,
        ordinal_position=position,
        is_primary_key=is_primary_key,
    )


def table(
    name: str,
    columns: list[ColumnMetadata],
    *,
    primary_key: list[str] | None = None,
    foreign_keys: list[ForeignKeyMetadata] | None = None,
    table_type: str = "BASE TABLE",
) -> TableMetadata:
    return TableMetadata(
        table_name=name,
        table_type=table_type,
        columns=columns,
        primary_keys=(
            [PrimaryKeyMetadata(constraint_name=f"{name}_pkey", columns=primary_key)]
            if primary_key
            else []
        ),
        foreign_keys=foreign_keys or [],
    )


def foreign_key(
    constraint_name: str,
    local_column: str,
    referenced_table: str,
    referenced_column: str,
    referenced_schema: str = SCHEMA,
) -> ForeignKeyMetadata:
    return ForeignKeyMetadata(
        constraint_name=constraint_name,
        column=local_column,
        referenced_schema=referenced_schema,
        referenced_table=referenced_table,
        referenced_column=referenced_column,
    )


def metadata(tables: list[TableMetadata], schema_name: str = SCHEMA) -> DatabaseMetadata:
    return DatabaseMetadata(
        database_name="testdb",
        source_database_type="postgres",
        schemas=[SchemaMetadata(schema_name=schema_name, tables=tables)],
    )


def column_profile(
    name: str,
    *,
    data_type: str = "integer",
    distinct_count: int = 0,
    null_count: int = 0,
    min_value: str | None = None,
    max_value: str | None = None,
    detected_pattern: str | None = None,
) -> ColumnProfile:
    return ColumnProfile(
        name=name,
        data_type=data_type,
        distinct_count=distinct_count,
        null_count=null_count,
        min_value=min_value,
        max_value=max_value,
        detected_pattern=detected_pattern,
    )


def table_profile(name: str, row_count: int, columns: list[ColumnProfile]) -> TableProfile:
    return TableProfile(table_name=name, row_count=row_count, columns=columns)


def profile(tables: list[TableProfile], schema_name: str = SCHEMA) -> DatabaseProfile:
    return DatabaseProfile(
        database_name="testdb",
        schemas=[SchemaProfile(schema_name=schema_name, tables=tables)],
    )


# ---------------------------------------------------------
# A miniature schema exercising every rule in a handful of tables
# ---------------------------------------------------------


def sample_metadata() -> DatabaseMetadata:
    """country -> state -> city -> customer, plus a self-reference, a
    junction table, a dependent entity and an orphan."""
    country = table(
        "country",
        [column("country_id", nullable=False, is_primary_key=True), column("name", "text")],
        primary_key=["country_id"],
    )
    state = table(
        "state",
        [
            column("state_id", nullable=False, is_primary_key=True),
            column("country_id"),
            column("name", "text"),
        ],
        primary_key=["state_id"],
        foreign_keys=[foreign_key("state_country_fk", "country_id", "country", "country_id")],
    )
    city = table(
        "city",
        [column("city_id", nullable=False, is_primary_key=True), column("state_id")],
        primary_key=["city_id"],
        foreign_keys=[foreign_key("city_state_fk", "state_id", "state", "state_id")],
    )
    customer = table(
        "customer",
        [column("customer_id", nullable=False, is_primary_key=True), column("city_id")],
        primary_key=["customer_id"],
        foreign_keys=[foreign_key("customer_city_fk", "city_id", "city", "city_id")],
    )
    employee = table(
        "employee",
        [column("employee_id", nullable=False, is_primary_key=True), column("manager_id")],
        primary_key=["employee_id"],
        foreign_keys=[
            foreign_key("employee_manager_fk", "manager_id", "employee", "employee_id")
        ],
    )
    product = table(
        "product",
        [column("product_id", nullable=False, is_primary_key=True)],
        primary_key=["product_id"],
    )
    promotion = table(
        "promotion",
        [column("promotion_id", nullable=False, is_primary_key=True)],
        primary_key=["promotion_id"],
    )
    product_promotion = table(
        "product_promotion",
        [
            column("product_id", nullable=False, is_primary_key=True),
            column("promotion_id", nullable=False, position=2, is_primary_key=True),
        ],
        primary_key=["product_id", "promotion_id"],
        foreign_keys=[
            foreign_key("pp_product_fk", "product_id", "product", "product_id"),
            foreign_key("pp_promotion_fk", "promotion_id", "promotion", "promotion_id"),
        ],
    )
    orders = table(
        "orders",
        [column("order_id", nullable=False, is_primary_key=True), column("customer_id")],
        primary_key=["order_id"],
        foreign_keys=[foreign_key("orders_customer_fk", "customer_id", "customer", "customer_id")],
    )
    # Dependent entity, NOT a junction: line_number is not a foreign key.
    order_item = table(
        "order_item",
        [
            column("order_id", nullable=False, is_primary_key=True),
            column("line_number", nullable=False, position=2, is_primary_key=True),
            column("product_id", position=3),
        ],
        primary_key=["order_id", "line_number"],
        foreign_keys=[
            foreign_key("oi_order_fk", "order_id", "orders", "order_id"),
            foreign_key("oi_product_fk", "product_id", "product", "product_id"),
        ],
    )
    audit_log = table(
        "audit_log",
        [column("audit_id", nullable=False, is_primary_key=True), column("note", "text")],
        primary_key=["audit_id"],
    )

    return metadata(
        [
            audit_log,
            city,
            country,
            customer,
            employee,
            order_item,
            orders,
            product,
            product_promotion,
            promotion,
            state,
        ]
    )
