"""
Metadata Builder

Converts raw connector metadata into the Canonical Metadata Model.

This module should NEVER contain SQL.

It only transforms dictionaries returned by the connector
into strongly typed Pydantic models.
"""

from __future__ import annotations

from collections import defaultdict

from migration.canonical.models import (
    ColumnMetadata,
    ConstraintMetadata,
    DatabaseMetadata,
    ForeignKeyMetadata,
    IndexMetadata,
    MetadataPackage,
    PrimaryKeyMetadata,
    SchemaMetadata,
    TableMetadata,
    TableStatistics,
)


class MetadataBuilder:
    """
    Builds canonical metadata from a connector.
    """

    def __init__(self, connector, database_name: str, database_type: str):
        self.connector = connector
        self.database_name = database_name
        self.database_type = database_type

    def build(self, schemas: list[str]) -> MetadataPackage:
        """
        Build complete metadata package.
        """

        tables = self.connector.extract_tables(schemas)
        columns = self.connector.extract_columns(schemas)
        primary_keys = self.connector.extract_primary_keys(schemas)
        foreign_keys = self.connector.extract_foreign_keys(schemas)
        constraints = self.connector.extract_constraints(schemas)
        indexes = self.connector.extract_indexes(schemas)
        statistics = self.connector.extract_statistics(schemas)

        schema_lookup = {}

        table_lookup = {}

        # ---------------------------------------------------
        # Create Schema + Table objects
        # ---------------------------------------------------

        for row in tables:

            schema_name = row["table_schema"]

            table_name = row["table_name"]

            if schema_name not in schema_lookup:
                schema_lookup[schema_name] = SchemaMetadata(
                    schema_name=schema_name
                )

            table = TableMetadata(
                table_name=table_name,
                table_type=row["table_type"],
            )

            schema_lookup[schema_name].tables.append(table)

            table_lookup[(schema_name, table_name)] = table

        # ---------------------------------------------------
        # Columns
        # ---------------------------------------------------

        for row in columns:

            key = (row["table_schema"], row["table_name"])

            if key not in table_lookup:
                continue

            table = table_lookup[key]

            table.columns.append(
                ColumnMetadata(
                    name=row["column_name"],
                    data_type=row["data_type"],
                    nullable=row["is_nullable"] == "YES",
                    default_value=row["column_default"],
                    ordinal_position=row["ordinal_position"],
                    character_length=row["character_maximum_length"],
                    numeric_precision=row["numeric_precision"],
                    numeric_scale=row["numeric_scale"],
                )
            )

        # ---------------------------------------------------
        # Primary Keys
        # ---------------------------------------------------

        pk_map = defaultdict(list)

        for row in primary_keys:

            key = (
                row["table_schema"],
                row["table_name"],
                row["constraint_name"],
            )

            pk_map[key].append(row["column_name"])

        for key, cols in pk_map.items():

            schema_name, table_name, constraint = key

            table = table_lookup[(schema_name, table_name)]

            table.primary_keys.append(
                PrimaryKeyMetadata(
                    constraint_name=constraint,
                    columns=cols,
                )
            )

            for col in table.columns:
                if col.name in cols:
                    col.is_primary_key = True

        # ---------------------------------------------------
        # Foreign Keys
        # ---------------------------------------------------

        for row in foreign_keys:

            table = table_lookup[
                (
                    row["table_schema"],
                    row["table_name"],
                )
            ]

            table.foreign_keys.append(
                ForeignKeyMetadata(
                    constraint_name=row["constraint_name"],
                    column=row["column_name"],
                    referenced_schema=row["foreign_table_schema"],
                    referenced_table=row["foreign_table_name"],
                    referenced_column=row["foreign_column_name"],
                )
            )

            for col in table.columns:
                if col.name == row["column_name"]:
                    col.is_foreign_key = True

        # ---------------------------------------------------
        # Constraints
        # ---------------------------------------------------

        for row in constraints:

            table = table_lookup[
                (
                    row["table_schema"],
                    row["table_name"],
                )
            ]

            table.constraints.append(
                ConstraintMetadata(
                    constraint_name=row["constraint_name"],
                    constraint_type=row["constraint_type"],
                )
            )

        # ---------------------------------------------------
        # Indexes
        # ---------------------------------------------------

        for row in indexes:

            table = table_lookup[
                (
                    row["table_schema"],
                    row["table_name"],
                )
            ]

            table.indexes.append(
                IndexMetadata(
                    index_name=row["index_name"],
                    definition=row["index_definition"],
                )
            )

        # ---------------------------------------------------
        # Statistics
        # ---------------------------------------------------

        for row in statistics:

            key = (
                row["table_schema"],
                row["table_name"],
            )

            if key not in table_lookup:
                continue

            table = table_lookup[key]

            table.statistics = TableStatistics(
                row_estimate=row["row_estimate"],
                dead_row_estimate=row["dead_row_estimate"],
                last_analyze=str(row["last_analyze"])
                if row["last_analyze"]
                else None,
                last_autoanalyze=str(row["last_autoanalyze"])
                if row["last_autoanalyze"]
                else None,
            )

        database = DatabaseMetadata(
            database_name=self.database_name,
            source_database_type=self.database_type,
            schemas=list(schema_lookup.values()),
        )

        return MetadataPackage(
            metadata=database
        )