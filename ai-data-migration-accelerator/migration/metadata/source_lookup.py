"""Resolve a modelled attribute back to its authoritative source column.

The conceptual model is free to rename a column into business language (a
DB2 column `CUST_NO` may become the attribute "Customer Number"), so by the
time an attribute reaches the logical or physical model its name is no
longer reliably the source column's name. Source fidelity - preserving the
exact type, length, precision, scale, nullability and default the source
database declared - requires finding that source column again.

This resolver is deliberately conservative: it maps an attribute back to a
column only when exactly one column, across the entity's declared source
tables, normalizes to the same name. An ambiguous or absent match returns
None rather than guessing - a wrong structural fact is worse than a missing
one, and the caller is expected to fall back to a documented, generic
mapping and record why.
"""

from __future__ import annotations

from migration.canonical.models import ColumnMetadata, DatabaseMetadata
from migration.relationship.rules import name_variants, normalize_identifier


def resolve_source_column(
    source_tables: list[str],
    attribute_name: str,
    metadata: DatabaseMetadata,
) -> ColumnMetadata | None:
    """Find the source column an attribute was derived from.

    Args:
        source_tables: Qualified ("schema.table") or bare table names the
            owning entity declares it was derived from.
        attribute_name: The attribute's name as it appears in the logical
            or conceptual model - may equal the source column name verbatim,
            or may be a business-language rename.
        metadata: The full source database metadata to search.

    Returns:
        The matching ColumnMetadata, or None if no table in source_tables
        resolves, or more than one column matches unambiguously.
    """
    candidate_tables = _resolve_tables(source_tables, metadata)
    if not candidate_tables:
        return None

    target_variants = name_variants(normalize_identifier(attribute_name))

    matches: list[ColumnMetadata] = []
    seen_columns: set[int] = set()
    for table in candidate_tables:
        for column in table.columns:
            if id(column) in seen_columns:
                continue
            if normalize_identifier(column.name) in target_variants:
                matches.append(column)
                seen_columns.add(id(column))

    if len(matches) == 1:
        return matches[0]
    return None


def _resolve_tables(source_tables: list[str], metadata: DatabaseMetadata):
    """Resolve declared source table names to actual TableMetadata objects.

    Accepts both "schema.table" and bare "table" forms, matching case-
    insensitively - the conceptual model is not guaranteed to preserve the
    source's exact casing.
    """
    resolved = []
    for schema in metadata.schemas:
        for table in schema.tables:
            qualified = f"{schema.schema_name}.{table.table_name}".lower()
            bare = table.table_name.lower()
            for declared in source_tables:
                declared_lower = declared.strip().lower()
                if declared_lower in (qualified, bare):
                    resolved.append(table)
                    break
    return resolved
